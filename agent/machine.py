"""상태 머신 — 현재 상태에 맞는 핸들러 실행 후 전이."""

from __future__ import annotations

import logging
import time

from agent.context import AgentContext
from agent.handlers import HANDLERS
from agent.states import State

log = logging.getLogger(__name__)

# 상태 핸들러끼리의 짧은 간격 (핸들러 내부 대기는 별도)
_DEFAULT_STEP_GAP = 0.05


class StateMachine:
    def __init__(self, ctx: AgentContext | None = None) -> None:
        self.ctx = ctx or AgentContext()
        self.state = State.IDLE

    def start(self) -> None:
        """8 — PREPARE_LOGIN부터 시작."""
        self.ctx.running = True
        self.ctx.reset_cycle_flags()
        self.state = State.PREPARE_LOGIN
        log.info("시작 → %s", self.state.name)

    def stop(self) -> None:
        """실행만 멈춤 (상태는 STOPPED)."""
        self.ctx.running = False
        self.state = State.STOPPED
        log.info("정지 → %s", self.state.name)

    def abort_to_idle(self, *, silent: bool = False) -> None:
        """0 — 모든 동작 중단 후 초기 메뉴(IDLE)로."""
        self.ctx.running = False
        self.ctx.reset_cycle_flags()
        self.state = State.IDLE
        if not silent:
            log.info("중단 → IDLE (초기 메뉴)")

    def step(self) -> State:
        """한 상태만 처리하고 다음 상태로 전이 (재귀 없이 1회)."""
        handler = HANDLERS.get(self.state)
        if handler is None:
            log.error("핸들러 없음: %s", self.state)
            self.state = State.STOPPED
            self.ctx.running = False
            return self.state

        prev = self.state
        nxt = handler(self.ctx)
        if nxt != prev:
            log.debug("전이 %s → %s", prev.name, nxt.name)
        self.state = nxt
        return self.state

    def run_until_stop(self, *, step_delay: float | None = None) -> None:
        """사용자가 중단하거나 STOPPED/IDLE 이 될 때까지 상태 전이 반복.

        재귀가 아니라 while + step() 이라 호출 스택이 깊어지지 않는다.
        스텝 상한 없음 — 0 키 / Ctrl+C 등으로 running=False 될 때까지 순환.
        """
        delay = _DEFAULT_STEP_GAP if step_delay is None else step_delay

        while self.ctx.running:
            if self.state in (State.STOPPED, State.IDLE):
                break

            self.step()

            if not self.ctx.running:
                break
            if self.state in (State.STOPPED, State.IDLE):
                break

            # 상태 간 최소 간격 (핸들러가 즉시 반환해도 busy-loop 방지)
            if delay > 0:
                time.sleep(delay)

        if self.state == State.STOPPED and self.ctx.running:
            self.ctx.running = False
