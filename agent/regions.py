"""하드코딩 탐색/클릭 영역 레지스트리.

새 영역은 get_all_regions()에 추가하면 9(영역 보기)에 자동 반영된다.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

# 프로젝트 루트 (agent/ 의 상위)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = PROJECT_ROOT / "assets" / "images"


@dataclass(frozen=True)
class Region:
    """좌상단·우하단으로 정의하는 화면 영역."""

    key: str
    name: str
    left: int
    top: int
    right: int
    bottom: int
    color: str  # 오버레이 테두리 색 (#RRGGBB)

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.right) // 2, (self.top + self.bottom) // 2

    def as_xywh(self) -> tuple[int, int, int, int]:
        """(left, top, width, height)"""
        return self.left, self.top, self.width, self.height


# --- PREPARE_LOGIN ---
LOGOUT = Region(
    key="logout",
    name="Logout",
    left=1790,
    top=98,
    right=1901,
    bottom=198,
    color="#FF4444",
)

LOGIN_TO_EMAIL = Region(
    key="login_to_email",
    name="LoginToEmail",
    left=779,
    top=459,
    right=1158,
    bottom=512,
    color="#44AAFF",
)

EXIT = Region(
    key="exit",
    name="Exit",
    left=1807,
    top=21,
    right=1887,
    bottom=97,
    color="#FFAA00",
)

CHECK = Region(
    key="check",
    name="Check",
    left=1057,
    top=781,
    right=1333,
    bottom=835,
    color="#44FF88",
)

# --- EMAIL_LOGIN ---
XD = Region(
    key="xd",
    name="XD",
    left=880,
    top=450,
    right=1069,
    bottom=527,
    color="#FF66CC",
)

# 이메일 입력칸 클릭 좌표 (영역 보기용으로 작은 박스도 등록)
EMAIL_FIELD_CLICK = (948, 550)
EMAIL_FIELD = Region(
    key="email_field",
    name="EmailField",
    left=EMAIL_FIELD_CLICK[0] - 4,
    top=EMAIL_FIELD_CLICK[1] - 4,
    right=EMAIL_FIELD_CLICK[0] + 4,
    bottom=EMAIL_FIELD_CLICK[1] + 4,
    color="#FFFF66",
)

# 이메일 입력 후 → 인증요청 버튼 클릭
EMAIL_AFTER_CLICK = (1186, 551)
POST_CLICK = (1068, 598)

POST = Region(
    key="post",
    name="Post",
    left=987,
    top=581,
    right=1148,
    bottom=618,
    color="#66FFFF",
)

AUTH_CODE_CLICK = (875, 585)
AUTH_CODE_FIELD = Region(
    key="auth_code_field",
    name="AuthCode",
    left=AUTH_CODE_CLICK[0] - 4,
    top=AUTH_CODE_CLICK[1] - 4,
    right=AUTH_CODE_CLICK[0] + 4,
    bottom=AUTH_CODE_CLICK[1] + 4,
    color="#FF9944",
)

LOGIN = Region(
    key="login",
    name="Login",
    left=788,
    top=646,
    right=1147,
    bottom=690,
    color="#88FF44",
)

SERVER = Region(
    key="server",
    name="Server",
    left=720,
    top=745,
    right=1198,
    bottom=796,
    color="#AA88FF",
)

SERVER_EXTRA_CLICK = (838, 627)
SERVER_CONFIRM_CLICK = (959, 901)
SERVER_EXTRA = Region(
    key="server_extra",
    name="ServerExtra",
    left=SERVER_EXTRA_CLICK[0] - 4,
    top=SERVER_EXTRA_CLICK[1] - 4,
    right=SERVER_EXTRA_CLICK[0] + 4,
    bottom=SERVER_EXTRA_CLICK[1] + 4,
    color="#FF88AA",
)
SERVER_CONFIRM = Region(
    key="server_confirm",
    name="ServerConfirm",
    left=SERVER_CONFIRM_CLICK[0] - 4,
    top=SERVER_CONFIRM_CLICK[1] - 4,
    right=SERVER_CONFIRM_CLICK[0] + 4,
    bottom=SERVER_CONFIRM_CLICK[1] + 4,
    color="#88AAFF",
)

# --- CREATE_CHARACTER ---
FULL_SLOT = Region(
    key="full_slot",
    name="FullSlot",
    left=1583,
    top=212,
    right=1885,
    bottom=414,
    color="#FF2222",
)

SLOTS_FULL_EXIT_CLICK = (1861, 51)
SLOTS_FULL_EXIT = Region(
    key="slots_full_exit",
    name="SlotsFullExit",
    left=SLOTS_FULL_EXIT_CLICK[0] - 4,
    top=SLOTS_FULL_EXIT_CLICK[1] - 4,
    right=SLOTS_FULL_EXIT_CLICK[0] + 4,
    bottom=SLOTS_FULL_EXIT_CLICK[1] + 4,
    color="#FFCC00",
)

# FullSlot 과 동일 영역 — V2/V3 슬롯 판별용 (로그/오버레이 구분)
V2_SLOT = Region(
    key="v2_slot",
    name="V2",
    left=FULL_SLOT.left,
    top=FULL_SLOT.top,
    right=FULL_SLOT.right,
    bottom=FULL_SLOT.bottom,
    color="#22AADD",
)
V3_SLOT = Region(
    key="v3_slot",
    name="V3",
    left=FULL_SLOT.left,
    top=FULL_SLOT.top,
    right=FULL_SLOT.right,
    bottom=FULL_SLOT.bottom,
    color="#DD22AA",
)

CREATE_SLOT_CLICK = (1809, 335)
CREATE_SLOT = Region(
    key="create_slot",
    name="CreateSlot",
    left=CREATE_SLOT_CLICK[0] - 4,
    top=CREATE_SLOT_CLICK[1] - 4,
    right=CREATE_SLOT_CLICK[0] + 4,
    bottom=CREATE_SLOT_CLICK[1] + 4,
    color="#AADD22",
)

# --- RUN_MACRO_2 트리거 ---
LOADING = Region(
    key="loading",
    name="Loading",
    left=787,
    top=85,
    right=1165,
    bottom=233,
    color="#FFAA66",
)

# --- SAVE_SCREENSHOT ---
MODULE = Region(
    key="module",
    name="Module",
    left=32,
    top=7,
    right=108,
    bottom=71,
    color="#66AAFF",
)
SCREENSHOT = Region(
    key="screenshot",
    name="Screenshot",
    left=46,
    top=106,
    right=387,
    bottom=904,
    color="#66FFCC",
)

INGAME_LOGOUT = Region(
    key="ingame_logout",
    name="IngameLogout",
    left=1810,
    top=960,
    right=1912,
    bottom=1042,
    color="#FF6688",
)
MAP = Region(
    key="map",
    name="Map",
    left=5,
    top=195,
    right=160,
    bottom=271,
    color="#AADDFF",
)
LOGOUT_MENU_CLICK = (1862, 1005)
LOGOUT_CONFIRM_CLICK = (1189, 796)
LOGOUT_CONFIRM = Region(
    key="logout_confirm",
    name="LogoutConfirm",
    left=LOGOUT_CONFIRM_CLICK[0] - 4,
    top=LOGOUT_CONFIRM_CLICK[1] - 4,
    right=LOGOUT_CONFIRM_CLICK[0] + 4,
    bottom=LOGOUT_CONFIRM_CLICK[1] + 4,
    color="#88FF66",
)

RESULT_DIR = PROJECT_ROOT / "results"
GOOD_RESULT_DIR = PROJECT_ROOT / "good_results"

# 템플릿 이미지 파일명 (assets/images/)
LOGOUT_IMAGE = IMAGES_DIR / "Logout.png"
LOGIN_TO_EMAIL_IMAGE = IMAGES_DIR / "LoginToEmail.png"
EXIT_IMAGE = IMAGES_DIR / "Exit.png"
CHECK_IMAGE = IMAGES_DIR / "Check.png"
START_IMAGE = IMAGES_DIR / "Start.png"
XD_IMAGE = IMAGES_DIR / "XD.png"
POST_IMAGE = IMAGES_DIR / "Post.png"
LOGIN_IMAGE = IMAGES_DIR / "Login.png"
SERVER_IMAGE = IMAGES_DIR / "Server.png"
FULL_SLOT_IMAGE = IMAGES_DIR / "FullSlot.png"
V2_IMAGE = IMAGES_DIR / "V2.png"
V3_IMAGE = IMAGES_DIR / "V3.png"
LOADING_IMAGE = IMAGES_DIR / "Loading.png"
INGAME_LOGOUT_IMAGE = IMAGES_DIR / "IngameLogout.png"
MODULE_IMAGE = IMAGES_DIR / "Module.png"
MAP_IMAGE = IMAGES_DIR / "map.png"


def full_screen_region() -> Region:
    """현재 주 모니터 전체 해상도 (Start 탐색용)."""
    user32 = ctypes.windll.user32
    width = int(user32.GetSystemMetrics(0))
    height = int(user32.GetSystemMetrics(1))
    return Region(
        key="start_fullscreen",
        name="Start(fullscreen)",
        left=0,
        top=0,
        right=width,
        bottom=height,
        color="#CC66FF",
    )


def get_all_regions() -> tuple[Region, ...]:
    """9번 영역 보기에 그릴 전체 목록."""
    return (
        LOGOUT,
        LOGIN_TO_EMAIL,
        EXIT,
        CHECK,
        XD,
        EMAIL_FIELD,
        POST,
        AUTH_CODE_FIELD,
        LOGIN,
        SERVER,
        SERVER_EXTRA,
        SERVER_CONFIRM,
        FULL_SLOT,
        SLOTS_FULL_EXIT,
        V2_SLOT,
        V3_SLOT,
        CREATE_SLOT,
        LOADING,
        MODULE,
        SCREENSHOT,
        INGAME_LOGOUT,
        MAP,
        LOGOUT_CONFIRM,
        full_screen_region(),
    )


# 하위 호환: 고정 영역만 (fullscreen 제외)
ALL_REGIONS: tuple[Region, ...] = (
    LOGOUT,
    LOGIN_TO_EMAIL,
    EXIT,
    CHECK,
    XD,
    EMAIL_FIELD,
    POST,
    AUTH_CODE_FIELD,
    LOGIN,
    SERVER,
    SERVER_EXTRA,
    SERVER_CONFIRM,
    FULL_SLOT,
    SLOTS_FULL_EXIT,
    V2_SLOT,
    V3_SLOT,
    CREATE_SLOT,
    LOADING,
    MODULE,
    SCREENSHOT,
    INGAME_LOGOUT,
    MAP,
    LOGOUT_CONFIRM,
)
