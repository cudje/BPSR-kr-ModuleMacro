"""채널 전환 중 읽은 캐릭터 패킷으로 모듈 조합을 계산한다."""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

# 채널 전환 입력이 끝난 뒤 모듈 패킷을 기다리는 시간.
PACKET_WAIT_SEC = 15.0
# 조건마다 남기는 상위 조합 수.
RANK_PER_CONSTRAINT = 3

# 매크로와 분리해 둔 패킷 해석·조합 계산 코드.
_OPTIMIZER_ROOT = Path(__file__).resolve().parents[1] / "vendor" / "bpsr"


def _ensure_optimizer_path() -> None:
    root = str(_OPTIMIZER_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _quiet_vendor_logs() -> None:
    """가져온 계산 코드의 안내 로그는 출력하지 않는다."""
    for name in (
        "packet_capture",
        "logging_config",
        "network_interface_util",
        "module_optimizer",
        "module_parser",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def _flush_c_stdio() -> None:
    try:
        ctypes.CDLL("ucrtbase").fflush(None)
    except OSError:
        pass


class _hide_native_status:
    """C++이 찍는 가속 안내를 버리고, 오류 줄만 경고로 남긴다."""

    def __enter__(self):
        self._stdout = sys.stdout
        self._stdout.flush()
        self._fd = self._stdout.fileno()
        self._saved = os.dup(self._fd)
        self._read_fd, write_fd = os.pipe()
        os.dup2(write_fd, self._fd)
        os.close(write_fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        _flush_c_stdio()
        self._stdout.flush()
        os.dup2(self._saved, self._fd)
        os.close(self._saved)
        chunks = []
        while True:
            chunk = os.read(self._read_fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        os.close(self._read_fd)
        text = b"".join(chunks).decode("utf-8", errors="replace")
        for line in text.splitlines():
            message = line.strip()
            if not message:
                continue
            if any(token in message for token in ("ERROR", "Error", "Failed", "失败", "错误")):
                log.warning("%s", message)
        return False


class ModulePacketSession:
    """SyncContainerData가 올 때까지 게임 TCP를 읽는다."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self.v_data = None
        self._capture = None

    def start(self) -> None:
        _ensure_optimizer_path()
        _quiet_vendor_logs()
        try:
            from network_interface_util import (
                find_default_network_interface,
                get_network_interfaces,
            )
            from packet_capture import PacketCapture
        except ImportError as exc:
            raise ImportError(
                "패킷 해석 모듈을 불러오지 못했습니다. "
                "cpp_extension에서 C++ 확장(module_optimizer_cpp)을 먼저 빌드해야 합니다. "
                f"원인: {exc}"
            ) from exc

        interfaces = get_network_interfaces()
        index = find_default_network_interface(interfaces)
        interface_name = None
        if index is not None and 0 <= index < len(interfaces):
            interface_name = interfaces[index]["name"]

        self._capture = PacketCapture(interface_name)
        self._capture.start_capture(self._on_packet)

    def _on_packet(self, data) -> None:
        if not isinstance(data, dict) or self._event.is_set():
            return
        v_data = data.get("v_data")
        if v_data is None:
            return
        self.v_data = v_data
        self._event.set()
        log.info("모듈 패킷 수신")

    def wait(self, timeout: float, should_continue) -> bool:
        """이미 받았거나 timeout 안에 받으면 True. 중단되면 False."""
        deadline = time.monotonic() + timeout
        while should_continue():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._event.is_set()
            if self._event.wait(min(0.2, remaining)):
                return True
        return False

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.stop_capture()
            self._capture = None


def modules_from_vdata(v_data) -> list:
    """CharSerialize(VData)에서 모듈 목록을 만든다."""
    _ensure_optimizer_path()
    from module_types import MODULE_ATTR_NAMES, MODULE_NAMES, ModuleInfo, ModulePart

    modules = []
    mod_infos = v_data.Mod.ModInfos
    for _package_type, package in v_data.ItemPackage.Packages.items():
        for key, item in package.Items.items():
            if not (item.HasField("ModNewAttr") and item.ModNewAttr.ModParts):
                break
            config_id = item.ConfigId
            module_info = ModuleInfo(
                name=MODULE_NAMES.get(config_id, f"未知模组({config_id})"),
                config_id=config_id,
                uuid=item.Uuid,
                quality=item.Quality,
                parts=[],
            )
            mod_info = mod_infos.get(key) if mod_infos else None
            if mod_info:
                mod_parts = list(item.ModNewAttr.ModParts)
                for i, part_id in enumerate(mod_parts):
                    if i >= len(mod_info.InitLinkNums):
                        break
                    module_info.parts.append(
                        ModulePart(
                            id=part_id,
                            name=MODULE_ATTR_NAMES.get(part_id, f"未知属性({part_id})"),
                            value=mod_info.InitLinkNums[i],
                        )
                    )
            modules.append(module_info)
    return modules


def _format_result(ranked) -> str:
    from module_types import to_english_attr, to_english_module

    if not ranked:
        return "유효한 조합이 없습니다.\n"

    lines = []
    for rank, (solution, labels) in enumerate(ranked, start=1):
        total_value = sum(solution.attr_breakdown.values())
        lines.append("")
        lines.append(f"=== {rank}위 ===")
        lines.append(f"해당 조건: {', '.join(labels)}")
        lines.append(f"속성 합계: {total_value}")
        lines.append(f"점수: {solution.score:.2f}")
        lines.append("")
        lines.append("모듈:")
        for i, module in enumerate(solution.modules, start=1):
            parts = ", ".join(
                f"{to_english_attr(part.name)}+{part.value}" for part in module.parts
            )
            name = to_english_module(module.config_id, module.name)
            lines.append(f"  {i}. {name} (품질 {module.quality}) - {parts}")
        lines.append("")
        lines.append("속성 분포:")
        for attr_name, value in sorted(
            solution.attr_breakdown.items(),
            key=lambda item: to_english_attr(item[0]),
        ):
            lines.append(f"  {to_english_attr(attr_name)}: +{value}")

    return "\n".join(lines).strip() + "\n"


def _top_for_attribute(optimizer, modules, attr_name: str, label: str):
    """한 속성이 20 이상인 5개 조합을 전부 검사하고 상위만 반환한다."""
    optimizer.min_attr_sum_requirements = {attr_name: 20}
    with _hide_native_status():
        found = optimizer._strategy_enumeration(modules)
    found = optimizer._complete_deduplicate(found)
    found = optimizer._filter_by_min_attr(found)
    found.sort(key=lambda item: item.score, reverse=True)
    log.info("%s: %s개", label, len(found))
    return [(solution, label) for solution in found[:RANK_PER_CONSTRAINT]]


def _merge_by_score(groups):
    """같은 5개 조합은 한 번만 두고, 점수 내림차순으로 정렬한다."""
    merged: dict[frozenset, tuple] = {}
    for solution, label in groups:
        key = frozenset(module.uuid for module in solution.modules)
        current = merged.get(key)
        if current is None:
            merged[key] = (solution, [label])
            continue
        if label not in current[1]:
            current[1].append(label)
    ranked = list(merged.values())
    ranked.sort(key=lambda item: item[0].score, reverse=True)
    return ranked


def save_module_result(v_data, out_path: Path) -> Path:
    """DMG Stack, Life Wave 각각의 상위 3조합을 모아 점수 순으로 저장한다."""
    _ensure_optimizer_path()
    from module_optimizer import ModuleOptimizer
    from module_types import MODULE_ATTR_NAMES, ModuleAttrType

    _quiet_vendor_logs()
    modules = modules_from_vdata(v_data)
    log.info("모듈 %s개", len(modules))
    damage_stack = MODULE_ATTR_NAMES[ModuleAttrType.EXTREME_DAMAGE_STACK.value]
    life_wave = MODULE_ATTR_NAMES[ModuleAttrType.EXTREME_LIFE_FLUCTUATION.value]
    optimizer = ModuleOptimizer(lang="en", combination_size=5)
    # 상위 3개만 쓰지만, 중복 제거 여유를 위해 열거 결과는 조금 더 남긴다.
    optimizer.max_solutions = 30

    dmg_label = "DMG Stack >= 20"
    life_label = "Life Wave >= 20"
    grouped = _top_for_attribute(optimizer, modules, damage_stack, dmg_label)
    grouped.extend(_top_for_attribute(optimizer, modules, life_wave, life_label))
    ranked = _merge_by_score(grouped)
    top_score = ranked[0][0].score if ranked else None
    out_path = _result_path(out_path, top_score)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_format_result(ranked), encoding="utf-8")
    if top_score is None:
        log.info("저장: %s", out_path)
    else:
        log.info("저장: %s (1위 %.2f)", out_path, top_score)
    return out_path


def _result_path(out_path: Path, top_score: float | None) -> Path:
    """1위 점수가 min_score 이상이면 good_results, 아니면 results 쪽 경로를 반환한다."""
    from agent.regions import GOOD_RESULT_DIR
    from agent.user_info import load_user_info

    if top_score is None:
        return out_path
    try:
        min_score = load_user_info().min_score
    except (OSError, ValueError) as exc:
        log.warning("min_score 를 읽지 못했습니다: %s", exc)
        return out_path
    if min_score is None or top_score < min_score:
        return out_path
    return GOOD_RESULT_DIR / out_path.name
