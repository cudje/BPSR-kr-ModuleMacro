"""매크로 시퀀스 정의/실행.

매크로 내부 좌표·키 입력은 9번 영역 표시 대상이 아님.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from agent.context import AgentContext
from agent.keyboard_util import key_down, key_tap, key_up
from agent.mouse_util import left_click, left_down, left_up, move_to, right_click
from agent.user_info import DEFAULT_STEP_GAP, load_user_info

log = logging.getLogger(__name__)

# 저사양(7)일 때 지연만 이 배율로 늘림
LOW_SPEC_DELAY_SCALE = 1.5


@dataclass(frozen=True)
class Delay:
    seconds: float


@dataclass(frozen=True)
class Click:
    x: int
    y: int
    button: Literal["left", "right"] = "left"


@dataclass(frozen=True)
class Move:
    x: int
    y: int


@dataclass(frozen=True)
class MouseDown:
    """왼버튼 누름. 좌표가 있으면 이동 후 누름."""

    x: int | None = None
    y: int | None = None
    button: Literal["left"] = "left"


@dataclass(frozen=True)
class MouseUp:
    button: Literal["left"] = "left"


@dataclass(frozen=True)
class KeyTap:
    key: str


@dataclass(frozen=True)
class KeyDown:
    key: str


@dataclass(frozen=True)
class KeyUp:
    key: str


MacroStep = Delay | Click | Move | MouseDown | MouseUp | KeyTap | KeyDown | KeyUp


MACRO_1: tuple[MacroStep, ...] = (
    Delay(0.700),  # 매크로 시작 전 대기
    Delay(0.600),
    Click(1766, 995, "left"),
    Delay(0.700),
    Click(1813, 991, "left"),
    Delay(0.700),
    Click(1754, 949, "left"),
    Delay(0.100),
    Click(1185, 794, "left"),
)

MACRO_2: tuple[MacroStep, ...] = (
    KeyTap("esc"),
    Delay(0.700),
    KeyTap("esc"),
    Delay(0.800),
    KeyDown("w"),
    Delay(0.400),
    KeyUp("w"),
    KeyTap("f"),
    Delay(0.400),
    KeyTap("esc"),
    Delay(0.400),
    KeyTap("esc"),
    Delay(0.500),
    KeyDown("d"),
    Delay(0.850),
    KeyUp("d"),
    KeyTap("f"),
    KeyDown("d"),
    Delay(1.700),
    KeyUp("d"),
    KeyDown("w"),
    Delay(0.400),
    KeyUp("w"),
    KeyTap("f"),
    Delay(0.700),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("esc"),
    Delay(0.200),
    KeyTap("q"),
    Delay(0.200),
    Click(1152, 958, "left"),
    Delay(3.000),
    KeyTap("esc"),
    Delay(0.100),
    Delay(1.300),
    Delay(0.100),
    Click(1313, 711, "left"),
    Delay(0.500),
    Click(645, 907, "left"),
    Delay(2.100),
    Click(1134, 904, "left"),
    Delay(0.300),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("j"),
    Delay(0.800),
    Click(222, 792, "left"),
    Delay(0.700),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("esc"),
    Delay(0.300),
    Click(1404, 241, "left"),
    Delay(1.500),
    Click(67, 799, "left"),
    Delay(0.600),
    Click(537, 145, "left"),
    Delay(0.200),
    Click(531, 334, "left"),
    Delay(0.200),
    Click(1552, 723, "left"),
    Delay(0.200),
    Click(1204, 928, "left"),
    Delay(0.200),
    Click(1191, 801, "left"),
    Delay(0.900),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("esc"),
    Delay(0.600),
    KeyTap("esc"),
    Delay(0.300),
    KeyTap("b"),
    Delay(1.000),
    Click(1778, 1002, "left"),
    Delay(0.400),
    Click(701, 657, "left"),
    Delay(0.040),
    Click(904, 562, "left"),
    Delay(0.040),
    Click(904, 562, "left"),
    Delay(0.040),
    Click(1218, 921, "left"),
    Delay(0.900),
    Click(1778, 1002, "left"),
    Delay(0.400),
    Click(701, 657, "left"),
    Delay(0.040),
    Click(904, 562, "left"),
    Delay(0.040),
    Click(904, 562, "left"),
    Delay(0.040),
    Click(1218, 921, "left"),
    Delay(0.900),
    KeyTap("esc"),
    Delay(0.200),
    Click(1350, 640, "left"),
    Delay(1.000),
    Click(178, 988, "left"),
    Delay(0.300),
    Click(1646, 800, "left"),
    Delay(0.200),
    # 드래그 1
    Move(1174, 609),
    MouseDown(),
    Move(1174, 609),
    Move(1177, 589),
    Move(1177, 569),
    Move(1176, 548),
    Move(1173, 522),
    Move(1174, 500),
    Move(1176, 477),
    Move(1177, 454),
    Move(1179, 433),
    Move(1180, 413),
    Move(1180, 392),
    Move(1180, 372),
    MouseUp(),
    Delay(0.200),
    Click(954, 659, "left"),
    Click(918, 790, "left"),
    Click(1183, 914, "left"),
    Delay(0.200),
    # 드래그 2
    Move(1643, 544),
    MouseDown(),
    Delay(0.100),
    Move(1643, 544),
    Move(1653, 545),
    Move(1663, 546),
    Move(1673, 546),
    Move(1683, 547),
    Move(1690, 547),
    Move(1697, 547),
    Delay(0.100),
    MouseUp(),
    Delay(0.100),
    Click(1779, 993, "left"),
)


def _sleep_while(ctx: AgentContext, seconds: float, *, step: float = 0.05) -> bool:
    deadline = time.monotonic() + seconds
    while ctx.running:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(step, remaining))
    return False


def run_macro(
    ctx: AgentContext,
    steps: Sequence[MacroStep],
    *,
    name: str,
) -> bool:
    """시퀀스 실행. 중단되면 False.

    모든 스텝(Delay 포함) 직후 user_info.step_gap 만큼 텀을 둔다.
    """
    try:
        gap = load_user_info().step_gap
    except (OSError, ValueError):
        gap = DEFAULT_STEP_GAP
    scale = LOW_SPEC_DELAY_SCALE if ctx.low_spec else 1.0
    gap *= scale

    for i, step in enumerate(steps, start=1):
        if not ctx.running:
            return False

        if isinstance(step, Delay):
            wait = step.seconds * scale
            if not _sleep_while(ctx, wait):
                return False
        elif isinstance(step, Click):
            if step.button == "right":
                right_click(step.x, step.y)
            else:
                left_click(step.x, step.y)
        elif isinstance(step, Move):
            move_to(step.x, step.y)
        elif isinstance(step, MouseDown):
            left_down(step.x, step.y)
        elif isinstance(step, MouseUp):
            left_up()
        elif isinstance(step, KeyTap):
            key_tap(step.key)
        elif isinstance(step, KeyDown):
            key_down(step.key)
        elif isinstance(step, KeyUp):
            key_up(step.key)
        else:
            log.warning("[%s] #%s unknown step: %s", name, i, step)

        # 모든 동작(Delay 포함) 직후 공통 텀
        if gap > 0:
            if not _sleep_while(ctx, gap):
                return False

    return True
