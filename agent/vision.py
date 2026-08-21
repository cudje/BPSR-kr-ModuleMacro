"""화면 캡처 + 영역 내 템플릿 이미지 매칭."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import ImageGrab

from agent.regions import Region

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.85


@dataclass(frozen=True)
class MatchResult:
    found: bool
    confidence: float
    # 화면 절대 좌표 기준 매칭 박스
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.right) // 2, (self.top + self.bottom) // 2


def grab_region_bgr(region: Region) -> np.ndarray:
    """영역 스크린샷을 OpenCV BGR ndarray로."""
    bbox = (region.left, region.top, region.right, region.bottom)
    img = ImageGrab.grab(bbox=bbox)
    rgb = np.array(img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def find_image_in_region(
    region: Region,
    template_path: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    quiet_miss: bool = False,
) -> MatchResult:
    """region 안에서 template 이미지를 찾는다."""
    path = Path(template_path)
    if not path.is_file():
        log.warning("템플릿 없음: %s", path)
        return MatchResult(found=False, confidence=0.0)

    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        log.warning("템플릿 로드 실패: %s", path)
        return MatchResult(found=False, confidence=0.0)

    haystack = grab_region_bgr(region)
    th, tw = template.shape[:2]
    hh, hw = haystack.shape[:2]
    if th > hh or tw > hw:
        log.warning(
            "템플릿이 영역보다 큼: template=%sx%s region=%sx%s",
            tw,
            th,
            hw,
            hh,
        )
        return MatchResult(found=False, confidence=0.0)

    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    conf = float(max_val)
    if conf < threshold:
        return MatchResult(found=False, confidence=conf)

    mx, my = max_loc
    left = region.left + mx
    top = region.top + my
    right = left + tw
    bottom = top + th
    return MatchResult(
        found=True,
        confidence=conf,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
    )


def find_image_in_region_for(
    region: Region,
    template_path: Path,
    *,
    timeout_sec: float = 2.0,
    interval_sec: float = 0.15,
    threshold: float = DEFAULT_THRESHOLD,
    should_continue: Callable[[], bool] | None = None,
) -> MatchResult:
    """timeout_sec 동안 반복 탐색. 찾으면 즉시 반환, 아니면 마지막 미검출 결과."""
    deadline = time.monotonic() + timeout_sec
    last = MatchResult(found=False, confidence=0.0)

    while True:
        if should_continue is not None and not should_continue():
            return last

        last = find_image_in_region(
            region,
            template_path,
            threshold=threshold,
            quiet_miss=True,
        )
        if last.found:
            return last

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval_sec, remaining))

    return last


def _match_template_in_haystack(
    region: Region,
    haystack: np.ndarray,
    template: np.ndarray,
    *,
    threshold: float,
) -> MatchResult:
    th, tw = template.shape[:2]
    hh, hw = haystack.shape[:2]
    if th > hh or tw > hw:
        return MatchResult(found=False, confidence=0.0)

    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    conf = float(max_val)
    mx, my = max_loc
    left = region.left + mx
    top = region.top + my
    return MatchResult(
        found=conf >= threshold,
        confidence=conf,
        left=left,
        top=top,
        right=left + tw,
        bottom=top + th,
    )


def find_first_image_in_region_for(
    region: Region,
    candidates: list[tuple[str, Path]],
    *,
    timeout_sec: float = 5.0,
    interval_sec: float = 0.15,
    threshold: float = DEFAULT_THRESHOLD,
    min_margin: float = 0.05,
    should_continue: Callable[[], bool] | None = None,
) -> tuple[str | None, MatchResult, dict[str, float]]:
    """한 영역을 반복 캡처하며 candidates 전부 점수화한 뒤 최고점 채택.

    - threshold 미만은 후보에서 제외
    - 1등 점수가 2등보다 min_margin 이상 높을 때만 확정 (애매하면 대기 계속)
    - 타임아웃까지 확정 없으면 (None, 미검출, 마지막 점수)
    """
    loaded: list[tuple[str, Path, np.ndarray]] = []
    for key, path in candidates:
        p = Path(path)
        if not p.is_file():
            log.warning("템플릿 없음: %s (%s)", key, p)
            continue
        tmpl = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if tmpl is None:
            log.warning("템플릿 로드 실패: %s (%s)", key, p)
            continue
        loaded.append((key, p, tmpl))

    empty_scores = {key: 0.0 for key, _ in candidates}
    if not loaded:
        return None, MatchResult(found=False, confidence=0.0), empty_scores

    deadline = time.monotonic() + timeout_sec
    last_scores = dict(empty_scores)
    while True:
        if should_continue is not None and not should_continue():
            return None, MatchResult(found=False, confidence=0.0), last_scores

        haystack = grab_region_bgr(region)
        scored: list[tuple[str, MatchResult]] = []
        for key, _path, tmpl in loaded:
            match = _match_template_in_haystack(
                region, haystack, tmpl, threshold=0.0
            )
            scored.append((key, match))
            last_scores[key] = match.confidence

        scored_sorted = sorted(scored, key=lambda x: x[1].confidence, reverse=True)

        best_key, best = scored_sorted[0]
        second_conf = scored_sorted[1][1].confidence if len(scored_sorted) > 1 else 0.0

        if best.confidence >= threshold and (best.confidence - second_conf) >= min_margin:
            return best_key, MatchResult(
                found=True,
                confidence=best.confidence,
                left=best.left,
                top=best.top,
                right=best.right,
                bottom=best.bottom,
            ), last_scores

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval_sec, remaining))

    return None, MatchResult(found=False, confidence=0.0), last_scores
