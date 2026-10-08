"""상위 상태 정의.

각 상태는 이후 단계에서 세부 동작(클릭, 이미지 탐색 등)을 채운다.
전환 규칙은 `agent.handlers` 참고.
"""

from enum import Enum, auto


class State(Enum):
    """자동화 상위 상태."""

    IDLE = auto()
    """대기. 8(시작) / 9(영역) 메뉴. 7(저사양)은 잠금 — 매크로 지연만 다른 모드."""

    PREPARE_LOGIN = auto()
    """① Logout → LoginToEmail. 실패 시 Exit/Check/Start 후 재시도."""

    EMAIL_LOGIN = auto()
    """② 이메일 로그인 + Gmail 인증 + Login 버튼."""

    SERVER_SELECT = auto()
    """③ 서버 선택 (있으면 선택 후 확인)."""

    CREATE_CHARACTER = auto()
    """④ 슬롯 확인(FullSlot) 및 캐릭터 생성."""

    RUN_MACRO_1 = auto()
    """⑤ 매크로 1 실행."""

    RUN_MACRO_2 = auto()
    """⑥ 조건 이미지 검출 후 매크로 2 실행."""

    SAVE_SCREENSHOT = auto()
    """⑦ 모듈 조합 결과 저장 + 로그아웃 → SERVER_SELECT."""

    STOPPED = auto()
    """중단(수동 정지 또는 치명 오류)."""
