"""콘솔과 게임 창 포커스 전환."""

from __future__ import annotations

import ctypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

_SW_RESTORE = 9
_VK_MENU = 0x12
_KEYEVENTF_KEYUP = 0x0002


def get_foreground_hwnd() -> int:
    return int(user32.GetForegroundWindow() or 0)


def get_console_hwnd() -> int:
    return int(kernel32.GetConsoleWindow() or 0)


def force_foreground(hwnd: int) -> bool:
    """hwnd를 선택된 창으로 올린다. 실패하면 False."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.GetForegroundWindow() == hwnd:
        return True

    foreground = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(foreground, None)
    this_thread = kernel32.GetCurrentThreadId()
    attached = False
    if fg_thread and fg_thread != this_thread:
        attached = bool(user32.AttachThreadInput(this_thread, fg_thread, True))

    user32.ShowWindow(hwnd, _SW_RESTORE)
    # Alt를 한 번 눌러야 백그라운드 프로세스가 포커스를 가져올 수 있다.
    user32.keybd_event(_VK_MENU, 0, 0, 0)
    ok = bool(user32.SetForegroundWindow(hwnd))
    user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
    user32.BringWindowToTop(hwnd)

    if attached:
        user32.AttachThreadInput(this_thread, fg_thread, False)
    return ok or user32.GetForegroundWindow() == hwnd
