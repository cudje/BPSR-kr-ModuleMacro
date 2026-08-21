"""키보드 입력 유틸."""

from __future__ import annotations

import time


def hotkey(*keys: str) -> None:
    """예: hotkey('ctrl', 'a')"""
    import keyboard

    combo = "+".join(keys)
    keyboard.send(combo)
    time.sleep(0.05)


def type_text(text: str, *, delay: float = 0.025) -> None:
    """ASCII 문자열 입력 (이메일 등)."""
    import keyboard

    keyboard.write(text, delay=delay)
    time.sleep(0.05)


def select_all_and_type(text: str, *, delay: float = 0.025) -> None:
    """Ctrl+A 후 텍스트 입력 (선택 영역 덮어쓰기)."""
    hotkey("ctrl", "a")
    time.sleep(0.08)
    type_text(text, delay=delay)


def key_tap(key: str) -> None:
    """키 한 번 누르고 뗌."""
    import keyboard

    keyboard.send(key)
    time.sleep(0.02)


def key_down(key: str) -> None:
    """키 누른 상태 유지."""
    import keyboard

    keyboard.press(key)


def key_up(key: str) -> None:
    """키 뗌."""
    import keyboard

    keyboard.release(key)
