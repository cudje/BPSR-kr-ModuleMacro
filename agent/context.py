"""런타임 컨텍스트 — 상태 간 공유 데이터."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentContext:
    """상태 핸들러가 읽고 쓰는 공유 상태."""

    running: bool = False

    # 계정 index (user_info) / 캐릭터 슬롯 Num (V2=2, V3=3, 신규=1)
    account_id: str | None = None
    character_slot: int | None = None

    # 조건 분기용 플래그 (핸들러가 설정)
    last_error: str | None = None
    notes: list[str] = field(default_factory=list)

    # 매크로2 채널 전환 중 읽은 캐릭터 컨테이너. 없으면 조합을 계산하지 않는다.
    module_vdata: object | None = None

    def reset_cycle_flags(self) -> None:
        """한 사이클 안에서만 쓰는 플래그 초기화."""
        self.last_error = None
        self.module_vdata = None
