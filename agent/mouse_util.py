"""화면/마우스 유틸 (좌표 측정, 클릭 등)."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_cursor_pos() -> tuple[int, int]:
    """현재 마우스 커서의 화면 좌표 (x, y)."""
    point = _POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise OSError("GetCursorPos failed")
    return int(point.x), int(point.y)


def move_to(x: int, y: int) -> None:
    if not user32.SetCursorPos(int(x), int(y)):
        raise OSError(f"SetCursorPos failed: ({x}, {y})")


def left_click(x: int, y: int, *, settle_ms: float = 0.05) -> None:
    """절대 좌표로 이동 후 좌클릭."""
    move_to(x, y)
    time.sleep(settle_ms)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def right_click(x: int, y: int, *, settle_ms: float = 0.05) -> None:
    """절대 좌표로 이동 후 우클릭."""
    move_to(x, y)
    time.sleep(settle_ms)
    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


def left_down(x: int | None = None, y: int | None = None) -> None:
    """왼버튼 누름. 좌표가 있으면 먼저 이동."""
    if x is not None and y is not None:
        move_to(x, y)
        time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)


def left_up() -> None:
    """왼버튼 뗌."""
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
