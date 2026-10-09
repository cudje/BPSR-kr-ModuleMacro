"""user_info.txt — 이메일 + 인덱스 + 매크로 스텝 텀 + 최소 점수 + 서버 + 추가 지연."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from agent.regions import PROJECT_ROOT

log = logging.getLogger(__name__)

USER_INFO_PATH = PROJECT_ROOT / "user_info.txt"

# Gmail API OAuth 파일 (user_info 와 별도, 프로젝트 루트)
GMAIL_CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
GMAIL_TOKEN_PATH = PROJECT_ROOT / "token.json"

DEFAULT_STEP_GAP = 0.04
DEFAULT_SERVER = "jp"
DEFAULT_DELAY_MS = 0.0


@dataclass
class UserInfo:
    email: str
    index: int
    step_gap: float = DEFAULT_STEP_GAP
    # None 이면 점수와 상관없이 results 에 저장한다.
    min_score: float | None = None
    # kr: 확인만. jp: 서버 이미지를 찾은 뒤 확인.
    server: str = DEFAULT_SERVER
    # MACRO_1/MACRO_2 의 Delay 에 더하는 시간(ms). 이동 키를 누른 동안은 제외.
    delay_ms: float = DEFAULT_DELAY_MS
    path: Path = USER_INFO_PATH

    @property
    def login_email(self) -> str:
        """게임에 입력할 주소: local+{index}@domain."""
        return apply_plus_index(self.email, self.index)

    @property
    def gmail_mailbox(self) -> str:
        """인증번호 수신함 — plus 없이 기본 Gmail 주소."""
        return self.email.strip()


def apply_plus_index(base_email: str, index: int) -> str:
    """qwe@gmail.com + 10 → qwe+10@gmail.com"""
    email = base_email.strip()
    if "@" not in email:
        raise ValueError(f"이메일 형식 오류: {base_email}")
    local, domain = email.split("@", 1)
    # 이미 +숫자가 붙어 있으면 local 부분만 사용
    local = re.sub(r"\+\d+$", "", local)
    return f"{local}+{index}@{domain}"


def load_user_info(path: Path | None = None) -> UserInfo:
    target = path or USER_INFO_PATH
    if not target.is_file():
        raise FileNotFoundError(f"유저 정보 파일이 없습니다: {target}")

    email: str | None = None
    index: int | None = None
    step_gap = DEFAULT_STEP_GAP
    min_score: float | None = None
    server = DEFAULT_SERVER
    delay_ms = DEFAULT_DELAY_MS

    with target.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                log.warning("무시된 줄: %s", line)
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key == "email":
                email = value
            elif key == "index":
                index = int(value)
            elif key == "step_gap":
                step_gap = float(value)
                if step_gap < 0:
                    log.warning("step_gap 이 음수라 기본값 %.3f 사용", DEFAULT_STEP_GAP)
                    step_gap = DEFAULT_STEP_GAP
            elif key == "min_score":
                min_score = float(value)
            elif key == "server":
                server = _parse_server(value)
            elif key == "delay_ms":
                delay_ms = _parse_delay_ms(value)
            else:
                log.warning("알 수 없는 키(무시): %s", key)

    if not email or index is None:
        raise ValueError(f"user_info.txt 에 email 과 index 가 필요합니다: {target}")

    return UserInfo(
        email=email,
        index=index,
        step_gap=step_gap,
        min_score=min_score,
        server=server,
        delay_ms=delay_ms,
        path=target,
    )


def _parse_server(value: str) -> str:
    name = value.strip().lower()
    if name in ("kr", "jp"):
        return name
    log.warning("server 는 kr 또는 jp 만 가능해서 기본값 %s 사용: %s", DEFAULT_SERVER, value)
    return DEFAULT_SERVER


def _parse_delay_ms(value: str) -> float:
    ms = float(value)
    if ms < 0:
        log.warning("delay_ms 가 음수라 기본값 %.0f 사용", DEFAULT_DELAY_MS)
        return DEFAULT_DELAY_MS
    return ms


def save_user_info(info: UserInfo, path: Path | None = None) -> None:
    """email/index/step_gap/min_score 를 단순 포맷으로 저장 (주석은 기본 헤더만 유지)."""
    target = path or info.path
    min_score_line = "" if info.min_score is None else f"min_score={info.min_score}\n"
    text = (
        "# ModuleMacro 유저 정보\n"
        "# email : Gmail 기본 주소 (인증메일 수신)\n"
        "# index : 현재 계정 번호 → 로그인 입력 local+{index}@domain\n"
        "# step_gap : 매크로 각 스텝 직후 텀(초)\n"
        "# min_score : 1위 점수가 이 값 이상이면 good_results 에 저장\n"
        "# server : kr 이면 확인만, jp 이면 서버 이미지를 찾은 뒤 확인\n"
        "# delay_ms : MACRO_1/MACRO_2 Delay 에 더하는 시간(ms). 이동 중 대기는 제외\n"
        "\n"
        f"email={info.email.strip()}\n"
        f"index={info.index}\n"
        f"step_gap={info.step_gap}\n"
        f"server={info.server}\n"
        f"delay_ms={info.delay_ms:g}\n"
        f"{min_score_line}"
    )
    target.write_text(text, encoding="utf-8")


def save_index(index: int, path: Path | None = None) -> UserInfo:
    """index 만 갱신 (슬롯 부족 시 +1 등)."""
    info = load_user_info(path)
    info.index = index
    _update_index_line(info.index, path or info.path)
    return info


def increment_index(path: Path | None = None) -> UserInfo:
    """슬롯 여유 없음 → index+1 후 저장."""
    info = load_user_info(path)
    info.index += 1
    _update_index_line(info.index, path or info.path)
    return info


def _update_index_line(index: int, path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("index=") and not stripped.startswith("#"):
            nl = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
            out.append(f"index={index}{nl}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"\nindex={index}\n")
    path.write_text("".join(out), encoding="utf-8")
