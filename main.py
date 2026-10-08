"""
ModuleMacro 진입점.

핫키:
  7 — 저사양 시작 (잠금: 매크로1/2 지연만 늘리는 모드, 추후 개방)
  8 — 시작
  9 — 영역 보기
  0 — 실행 중 중단 (모든 동작 중지 후 초기 메뉴로)
  ; — 패킷 검사만 (20초 대기 후 조합 저장)
  ' — 현재 마우스 좌표 로그
  Ctrl+C — 프로그램 강제 종료
"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from agent.context import AgentContext
from agent.machine import StateMachine
from agent.mouse_util import get_cursor_pos
from agent.states import State

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

# 저사양(7): 매크로1/2 지연만 조금 더 김. 지금은 잠금.
LOW_SPEC_ENABLED = False

MENU_TEXT = """
========================================
 ModuleMacro
  7 : 저사양 시작 (잠금)
  8 : 시작
  9 : 영역 보기
  0 : 실행 중 중단 (초기 메뉴로)
  ; : 패킷 검사만 (조합 텍스트 저장)
  ' : 마우스 좌표 로그
  Ctrl+C : 프로그램 강제 종료
========================================
""".strip()


def print_menu() -> None:
    print(MENU_TEXT)
    log.info("대기 중 — 8/9/0/;/' / Ctrl+C(종료)  [7 잠금]")


def show_regions() -> None:
    """9 — 하드코딩된 클릭/탐색/캡처 영역을 색별 빈 박스로 토글."""
    from agent.overlay import toggle_region_overlay

    toggle_region_overlay()


def log_mouse_pos() -> None:
    """' — 하드코딩용 현재 마우스 좌표 출력."""
    try:
        x, y = get_cursor_pos()
    except OSError as exc:
        log.error("마우스 좌표 읽기 실패: %s", exc)
        return
    msg = f"mouse pos: ({x}, {y})"
    log.info(msg)
    print(msg)


def main() -> int:
    try:
        import keyboard
    except ImportError:
        log.error("keyboard 패키지가 필요합니다. pip install -r requirements.txt")
        return 1

    ctx = AgentContext()
    machine = StateMachine(ctx)
    worker_lock = threading.Lock()
    exit_event = threading.Event()

    def shutdown() -> None:
        """Ctrl+C — 동작 중단 후 프로세스 종료 (메시지 없음)."""
        if exit_event.is_set():
            return
        machine.abort_to_idle(silent=True)
        exit_event.set()

    def run_machine(*, low_spec: bool) -> None:
        if not worker_lock.acquire(blocking=False):
            log.warning("이미 실행 중 — 무시")
            return
        try:
            machine.start(low_spec=low_spec)
            machine.run_until_stop()
        finally:
            if exit_event.is_set():
                worker_lock.release()
                return
            if machine.state != State.IDLE:
                machine.abort_to_idle()
            print_menu()
            worker_lock.release()

    def on_low_spec_start() -> None:
        if not LOW_SPEC_ENABLED:
            log.info("7 — 저사양 시작은 현재 잠금 상태입니다")
            return
        log.info("7 — 저사양 시작")
        threading.Thread(target=run_machine, kwargs={"low_spec": True}, daemon=True).start()

    def on_start() -> None:
        log.info("8 — 시작")
        threading.Thread(target=run_machine, kwargs={"low_spec": False}, daemon=True).start()

    def on_show_regions() -> None:
        log.info("9 — 영역 보기")
        show_regions()

    def on_abort() -> None:
        log.info("0 — 실행 중 중단 → 초기 메뉴")
        was_running = machine.ctx.running
        machine.abort_to_idle()
        if not was_running:
            print_menu()

    def run_packet_probe() -> None:
        """; — 채널 입력 없이 패킷만 기다리고, 오면 조합 텍스트만 저장."""
        if not worker_lock.acquire(blocking=False):
            log.warning("이미 실행 중 — 무시")
            return
        from agent.module_solver import PACKET_WAIT_SEC, ModulePacketSession, save_module_result
        from agent.regions import RESULT_DIR

        ctx.running = True
        session = ModulePacketSession()
        try:
            log.info("; — 패킷 검사 시작 (최대 %.0f초). 게임에서 채널을 전환하세요.", PACKET_WAIT_SEC)
            session.start()
            got_packet = session.wait(PACKET_WAIT_SEC, lambda: ctx.running)
            if not ctx.running:
                log.info("패킷 검사 중단")
                return
            if not got_packet or session.v_data is None:
                log.info("모듈 패킷 미수신")
                return
            out_path = save_module_result(session.v_data, RESULT_DIR / "packet_test.txt")
            log.info("패킷 검사 완료: %s", out_path)
        except Exception as exc:
            log.error("패킷 검사 실패: %s", exc)
        finally:
            session.stop()
            ctx.running = False
            if not exit_event.is_set():
                print_menu()
            worker_lock.release()

    def on_packet_probe() -> None:
        log.info("; — 패킷 검사")
        threading.Thread(target=run_packet_probe, daemon=True).start()

    def on_mouse_pos() -> None:
        log_mouse_pos()

    def _on_sigint(_signum, _frame) -> None:
        shutdown()

    signal.signal(signal.SIGINT, _on_sigint)
    # Windows 콘솔 Ctrl+Break
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _on_sigint)

    keyboard.add_hotkey("7", on_low_spec_start)
    keyboard.add_hotkey("8", on_start)
    keyboard.add_hotkey("9", on_show_regions)
    keyboard.add_hotkey("0", on_abort)
    keyboard.add_hotkey(";", on_packet_probe)
    keyboard.add_hotkey("'", on_mouse_pos)

    print_menu()

    try:
        # 짧은 wait 루프 — Windows에서도 Ctrl+C(SIGINT)가 잘 들어옴
        while not exit_event.wait(0.25):
            pass
    except KeyboardInterrupt:
        shutdown()
    finally:
        machine.abort_to_idle(silent=True)
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
