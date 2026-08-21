"""상태별 동작.

각 핸들러는 현재 작업을 수행한 뒤 다음 State를 반환한다.
로그는 상태별 핵심 이벤트만 남긴다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from agent.context import AgentContext
from agent.states import State

log = logging.getLogger(__name__)

Handler = Callable[[AgentContext], State]


def _sleep_while_running(ctx: AgentContext, seconds: float, *, step: float = 0.2) -> bool:
    """ctx.running 인 동안만 대기. 중단되면 False."""
    deadline = time.monotonic() + seconds
    while ctx.running:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(step, remaining))
    return False


def _click_match_center(match) -> None:
    from agent.mouse_util import left_click

    cx, cy = match.center
    left_click(cx, cy)


def handle_idle(ctx: AgentContext) -> State:
    """대기 — 머신 루프에서는 보통 진입하지 않음."""
    return State.IDLE


def handle_prepare_login(ctx: AgentContext) -> State:
    """① 로그인 UI 상태 정리.

    1) Logout 최대 5초 → 있으면 클릭 (없어도 다음)
    2) LoginToEmail 최대 10초
       - 찾음 → 클릭 → EMAIL_LOGIN
       - 못 찾음 → Exit(있으면 Check) → Start
         · Exit 없으면 Check 스킵
         · Start 30초 실패 시 메인 메뉴(IDLE)
         · Start 성공 시 20초 대기 후 PREPARE_LOGIN 처음으로
    """
    from agent.regions import (
        CHECK,
        CHECK_IMAGE,
        EXIT,
        EXIT_IMAGE,
        LOGIN_TO_EMAIL,
        LOGIN_TO_EMAIL_IMAGE,
        LOGOUT,
        LOGOUT_IMAGE,
        START_IMAGE,
        full_screen_region,
    )
    from agent.vision import find_image_in_region_for

    def _still_running() -> bool:
        return ctx.running

    log.info("로그아웃 시도")
    logout = find_image_in_region_for(
        LOGOUT,
        LOGOUT_IMAGE,
        timeout_sec=5.0,
        should_continue=_still_running,
    )
    if logout.found:
        _click_match_center(logout)
    else:
        log.info("로그아웃 시도 실패")

    if not ctx.running:
        return State.IDLE

    log.info("LoginToEmail 시도")
    email_btn = find_image_in_region_for(
        LOGIN_TO_EMAIL,
        LOGIN_TO_EMAIL_IMAGE,
        timeout_sec=10.0,
        should_continue=_still_running,
    )
    if email_btn.found:
        _click_match_center(email_btn)
        return State.EMAIL_LOGIN

    if not ctx.running:
        return State.IDLE

    log.info("LoginToEmail 시도 실패")
    log.info("재시작 시도")

    exit_btn = find_image_in_region_for(
        EXIT,
        EXIT_IMAGE,
        timeout_sec=3.0,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE

    if exit_btn.found:
        _click_match_center(exit_btn)
        if not ctx.running:
            return State.IDLE

        check_btn = find_image_in_region_for(
            CHECK,
            CHECK_IMAGE,
            timeout_sec=5.0,
            should_continue=_still_running,
        )
        if not ctx.running:
            return State.IDLE
        if check_btn.found:
            _click_match_center(check_btn)

    if not ctx.running:
        return State.IDLE

    log.info("게임시작 시도")
    screen = full_screen_region()
    start_btn = find_image_in_region_for(
        screen,
        START_IMAGE,
        timeout_sec=30.0,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE

    if not start_btn.found:
        log.warning("게임시작 시도 실패 — 메인 메뉴로")
        ctx.running = False
        return State.IDLE

    _click_match_center(start_btn)

    if not _sleep_while_running(ctx, 20.0):
        return State.IDLE

    return State.PREPARE_LOGIN


def handle_email_login(ctx: AgentContext) -> State:
    """② 이메일 입력 → 인증요청 클릭 → Gmail 코드 → Login → SERVER_SELECT."""
    from agent.gmail_client import get_gmail_service, snapshot_latest_auth_id, wait_for_auth_code
    from agent.keyboard_util import select_all_and_type
    from agent.mouse_util import left_click
    from agent.regions import (
        AUTH_CODE_CLICK,
        EMAIL_AFTER_CLICK,
        EMAIL_FIELD_CLICK,
        LOGIN,
        LOGIN_IMAGE,
        POST_CLICK,
        XD,
        XD_IMAGE,
    )
    from agent.user_info import load_user_info
    from agent.vision import find_image_in_region_for

    def _still_running() -> bool:
        return ctx.running

    log.info("이메일 로그인 시도")

    try:
        info = load_user_info()
    except (OSError, ValueError) as exc:
        log.error("user_info 로드 실패: %s", exc)
        ctx.last_error = str(exc)
        return State.STOPPED

    ctx.account_id = str(info.index)
    login_email = info.login_email

    xd = find_image_in_region_for(
        XD,
        XD_IMAGE,
        timeout_sec=5.0,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE

    if not xd.found:
        log.warning("이메일 로그인 실패 — XD 미검출")
        ctx.last_error = "XD not found"
        return State.STOPPED

    ex, ey = EMAIL_FIELD_CLICK
    left_click(ex, ey)
    if not _sleep_while_running(ctx, 0.2):
        return State.IDLE

    select_all_and_type(login_email)
    if not _sleep_while_running(ctx, 0.1):
        return State.IDLE

    ax0, ay0 = EMAIL_AFTER_CLICK
    left_click(ax0, ay0)

    try:
        service = get_gmail_service()
        prev_id, prev_ms = snapshot_latest_auth_id(service)
    except Exception as exc:
        log.error("Gmail 준비 실패: %s", exc)
        ctx.last_error = f"gmail setup: {exc}"
        return State.STOPPED

    import time as _time

    click_ms = int(_time.time() * 1000)
    not_before_ms = max(prev_ms, click_ms - 5_000)

    if not _sleep_while_running(ctx, 0.1):
        return State.IDLE
    px, py = POST_CLICK
    left_click(px, py)

    auth = wait_for_auth_code(
        timeout_sec=90.0,
        not_before_ms=not_before_ms,
        exclude_message_id=prev_id,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE
    if auth is None:
        log.warning("인증번호 수신 실패")
        ctx.last_error = "auth code timeout"
        return State.STOPPED

    log.info("인증번호 %s", auth.code)

    ax, ay = AUTH_CODE_CLICK
    left_click(ax, ay)
    if not _sleep_while_running(ctx, 0.2):
        return State.IDLE

    select_all_and_type(auth.code)
    if not _sleep_while_running(ctx, 0.3):
        return State.IDLE

    login_btn = find_image_in_region_for(
        LOGIN,
        LOGIN_IMAGE,
        timeout_sec=5.0,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE
    if not login_btn.found:
        log.warning("Login 미검출")
        ctx.last_error = "Login not found"
        return State.STOPPED

    lx, ly = login_btn.center
    left_click(lx, ly)
    if not _sleep_while_running(ctx, 0.3):
        return State.IDLE

    return State.SERVER_SELECT


def handle_server_select(ctx: AgentContext) -> State:
    """③ 서버 선택 — 있으면 선택 후 확인, 없으면 확인만 → CREATE_CHARACTER."""
    from agent.mouse_util import left_click
    from agent.regions import (
        SERVER,
        SERVER_CONFIRM_CLICK,
        SERVER_EXTRA_CLICK,
        SERVER_IMAGE,
    )
    from agent.vision import find_image_in_region_for

    def _still_running() -> bool:
        return ctx.running

    log.info("서버 선택 시도")

    server = find_image_in_region_for(
        SERVER,
        SERVER_IMAGE,
        timeout_sec=4.0,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE

    if server.found:
        sx, sy = server.center
        left_click(sx, sy)
        if not _sleep_while_running(ctx, 0.2):
            return State.IDLE

        ex2, ey2 = SERVER_EXTRA_CLICK
        left_click(ex2, ey2)
        if not _sleep_while_running(ctx, 0.2):
            return State.IDLE

    cx2, cy2 = SERVER_CONFIRM_CLICK
    left_click(cx2, cy2)

    return State.CREATE_CHARACTER


def handle_create_character(ctx: AgentContext) -> State:
    """③ 캐릭터 슬롯/생성.

    FullSlot / V2 / V3 를 같은 영역에서 동시에 탐색 (우선순위: FullSlot > V2 > V3).
    - FullSlot → index+1, (1861,51) → PREPARE_LOGIN
    - V2 → Num=2, (1809,335) → RUN_MACRO_1
    - V3 → Num=3, (1809,335) → RUN_MACRO_1
    - 셋 다 미검출 → Num=1 → RUN_MACRO_1
    """
    from agent.mouse_util import left_click
    from agent.regions import (
        CREATE_SLOT_CLICK,
        FULL_SLOT,
        FULL_SLOT_IMAGE,
        SLOTS_FULL_EXIT_CLICK,
        V2_IMAGE,
        V3_IMAGE,
    )
    from agent.user_info import increment_index
    from agent.vision import find_first_image_in_region_for

    def _still_running() -> bool:
        return ctx.running

    hit, _match, scores = find_first_image_in_region_for(
        FULL_SLOT,
        [
            ("FullSlot", FULL_SLOT_IMAGE),
            ("V2", V2_IMAGE),
            ("V3", V3_IMAGE),
        ],
        timeout_sec=4.0,
        threshold=0.90,
        min_margin=0.05,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE

    log.info(
        "슬롯 확인 신뢰도 %.3f | %.3f | %.3f",
        scores.get("FullSlot", 0.0),
        scores.get("V2", 0.0),
        scores.get("V3", 0.0),
    )

    if hit == "FullSlot":
        updated = increment_index()
        ctx.account_id = str(updated.index)
        ctx.reset_cycle_flags()
        ex, ey = SLOTS_FULL_EXIT_CLICK
        left_click(ex, ey)
        return State.PREPARE_LOGIN

    if hit == "V2":
        ctx.character_slot = 2
        cx, cy = CREATE_SLOT_CLICK
        left_click(cx, cy)
        return State.RUN_MACRO_1

    if hit == "V3":
        ctx.character_slot = 3
        cx, cy = CREATE_SLOT_CLICK
        left_click(cx, cy)
        return State.RUN_MACRO_1

    ctx.character_slot = 1
    return State.RUN_MACRO_1


def handle_run_macro_1(ctx: AgentContext) -> State:
    """④ 매크로 1 — 좌클릭 시퀀스."""
    from agent.macros import MACRO_1, run_macro

    log.info("매크로1 실행")
    ok = run_macro(ctx, MACRO_1, name="MACRO_1")
    if not ok:
        return State.IDLE
    return State.RUN_MACRO_2


def handle_run_macro_2(ctx: AgentContext) -> State:
    """⑤ Loading 이미지 검출 → 성공 시 MACRO_2 시퀀스."""
    from agent.macros import MACRO_2, run_macro
    from agent.regions import LOADING, LOADING_IMAGE
    from agent.vision import find_image_in_region_for

    def _still_running() -> bool:
        return ctx.running

    log.info("매크로2 실행")

    match = find_image_in_region_for(
        LOADING,
        LOADING_IMAGE,
        timeout_sec=60.0,
        should_continue=_still_running,
    )
    if not ctx.running:
        return State.IDLE
    if not match.found:
        log.warning("Loading 미검출")
        ctx.last_error = "Loading not found"
        return State.STOPPED

    ok = run_macro(ctx, MACRO_2, name="MACRO_2")
    if not ok:
        return State.IDLE
    return State.SAVE_SCREENSHOT


def handle_save_screenshot(ctx: AgentContext) -> State:
    """⑦ 스크린샷 저장 + 로그아웃 → SERVER_SELECT."""
    import cv2

    from agent.keyboard_util import key_tap
    from agent.mouse_util import left_click
    from agent.regions import (
        LOGOUT_CONFIRM_CLICK,
        LOGOUT_MENU_CLICK,
        RESULT_DIR,
        SCREENSHOT,
    )
    from agent.vision import grab_region_bgr

    index = ctx.account_id if ctx.account_id is not None else "unknown"
    num = ctx.character_slot if ctx.character_slot is not None else 0
    filename = f"{index}_{num}.png"

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULT_DIR / filename

    if not _sleep_while_running(ctx, 0.3):
        return State.IDLE

    image = grab_region_bgr(SCREENSHOT)
    if not cv2.imwrite(str(out_path), image):
        log.error("스크린샷 저장 실패: %s", out_path)
        ctx.last_error = f"screenshot save failed: {out_path}"
        return State.STOPPED

    log.info("스크린샷 저장 경로 %s", out_path)

    if not _sleep_while_running(ctx, 0.3):
        return State.IDLE

    key_tap("esc")
    if not _sleep_while_running(ctx, 0.3):
        return State.IDLE

    mx, my = LOGOUT_MENU_CLICK
    left_click(mx, my)
    if not _sleep_while_running(ctx, 0.3):
        return State.IDLE

    cx, cy = LOGOUT_CONFIRM_CLICK
    left_click(cx, cy)
    if not _sleep_while_running(ctx, 0.3):
        return State.IDLE

    if not _sleep_while_running(ctx, 4.0):
        return State.IDLE

    return State.SERVER_SELECT


def handle_stopped(ctx: AgentContext) -> State:
    """중단 — 루프 종료 신호."""
    if ctx.last_error:
        log.info("중단 (error=%s)", ctx.last_error)
    ctx.running = False
    return State.STOPPED


HANDLERS: dict[State, Handler] = {
    State.IDLE: handle_idle,
    State.PREPARE_LOGIN: handle_prepare_login,
    State.EMAIL_LOGIN: handle_email_login,
    State.SERVER_SELECT: handle_server_select,
    State.CREATE_CHARACTER: handle_create_character,
    State.RUN_MACRO_1: handle_run_macro_1,
    State.RUN_MACRO_2: handle_run_macro_2,
    State.SAVE_SCREENSHOT: handle_save_screenshot,
    State.STOPPED: handle_stopped,
}
