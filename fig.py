"""results / good_results 를 집계하고 한 장의 그림으로 저장한다.

누락은 results 맨 위 캐릭터부터 마지막 캐릭터까지,
1333_2, 1333_3, 1334_1 순서로 파일이 없는 칸의 개수다.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

from agent.regions import GOOD_RESULT_DIR, PROJECT_ROOT, RESULT_DIR

FILE_RE = re.compile(r"^(\d+)_(\d+)\.txt$")
SCORE_RE = re.compile(r"^점수:\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.M)
INVALID_TEXT = "유효한 조합이 없습니다."
SCORE_ORIGIN = 1600
BIN_WIDTH = 75
SCORE_MARKS = (
    (1350, "극666", "#c0392b"),
    (1600, "극6665", "#1f4e79"),
    (1675, "극6666(극6극66)", "#6c3483"),
    (1750, "극6극665", "#b9770e"),
    (1850, "극6극666", "#0e6655"),
)


def _use_korean_font() -> None:
    font = Path(r"C:\Windows\Fonts\malgun.ttf")
    if font.is_file():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False


def _top_score(path: Path) -> float | None:
    text = path.read_text(encoding="utf-8")
    if INVALID_TEXT in text:
        return None
    match = SCORE_RE.search(text)
    if match is None:
        return None
    return float(match.group(1))


def _indexed_files(folder: Path) -> list[tuple[int, int, Path]]:
    rows = []
    if not folder.is_dir():
        return rows
    for path in folder.glob("*.txt"):
        match = FILE_RE.match(path.name)
        if match is None:
            continue
        rows.append((int(match.group(1)), int(match.group(2)), path))
    rows.sort()
    return rows


def _next_character(index: int, slot: int) -> tuple[int, int]:
    """한 계정의 슬롯은 1, 2, 3 이고 그 다음은 다음 계정의 1번이다."""
    if slot >= 3:
        return index + 1, 1
    return index, slot + 1


def _character_span(start: tuple[int, int], end: tuple[int, int]):
    index, slot = start
    while (index, slot) <= end:
        yield index, slot
        index, slot = _next_character(index, slot)


def collect() -> dict:
    results = _indexed_files(RESULT_DIR)
    goods = _indexed_files(GOOD_RESULT_DIR)
    if not results:
        raise SystemExit(f"results 에 결과 파일이 없습니다: {RESULT_DIR}")

    start = (results[0][0], results[0][1])
    start_path = results[0][2]
    present = {(index, slot) for index, slot, _path in results + goods}
    end = max(key for key in present if key >= start)
    expected = list(_character_span(start, end))
    missing = [f"{index}_{slot}" for index, slot in expected if (index, slot) not in present]

    invalid_count = 0
    below_scores: list[float] = []
    good_scores: list[float] = []
    for _index, _slot, path in results:
        score = _top_score(path)
        if score is None:
            invalid_count += 1
        else:
            below_scores.append(score)
    for _index, _slot, path in goods:
        score = _top_score(path)
        if score is None:
            invalid_count += 1
        else:
            good_scores.append(score)

    return {
        "start_name": start_path.name,
        "start_label": f"{start[0]}_{start[1]}",
        "end_label": f"{end[0]}_{end[1]}",
        "expected_count": len(expected),
        "missing": missing,
        "invalid_count": invalid_count,
        "below_scores": below_scores,
        "good_scores": good_scores,
    }


def _score_bins(scores: list[float]) -> list[tuple[int, int, int]]:
    """1600을 경계로 75점씩 나눈 구간. 점수는 왼쪽 경계 이상, 오른쪽 경계 미만."""
    if not scores:
        return []
    indexes = [math.floor((score - SCORE_ORIGIN) / BIN_WIDTH) for score in scores]
    low = min(indexes)
    high = max(indexes)
    counts = {index: 0 for index in range(low, high + 1)}
    for index in indexes:
        counts[index] += 1
    rows = []
    for index in range(low, high + 1):
        start = SCORE_ORIGIN + BIN_WIDTH * index
        rows.append((start, start + BIN_WIDTH, counts[index]))
    return rows


def _ratio_text(count: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{count / total * 100:.1f}%"


def save_figure(summary: dict, out_path: Path) -> None:
    _use_korean_font()
    missing_n = len(summary["missing"])
    invalid_n = summary["invalid_count"]
    below_n = len(summary["below_scores"])
    good_n = len(summary["good_scores"])
    labels = ["누락", "유효하지 않음", "미달", "좋음"]
    counts = [missing_n, invalid_n, below_n, good_n]
    total = sum(counts)

    fig = plt.figure(figsize=(11, 7.2), dpi=140)
    grid = fig.add_gridspec(2, 1, height_ratios=[0.85, 1.55], hspace=0.08)
    table_ax = fig.add_subplot(grid[0])
    hist_ax = fig.add_subplot(grid[1])

    table_ax.axis("off")
    cell_text = [
        [label, str(count), _ratio_text(count, total)]
        for label, count in zip(labels, counts)
    ]
    cell_text.append(["합계", str(total), "100.0%" if total else "0.0%"])
    table = table_ax.table(
        cellText=cell_text,
        colLabels=["구분", "개수", "비율"],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.6)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#e6e6e6")
            cell.set_text_props(weight="bold")
        elif row == len(cell_text):
            cell.set_facecolor("#f4f4f4")

    scores = summary["below_scores"] + summary["good_scores"]
    bins = _score_bins(scores)
    if not bins:
        hist_ax.text(0.5, 0.5, "점수 없음", ha="center", va="center", transform=hist_ax.transAxes)
        hist_ax.set_xticks([])
        hist_ax.set_yticks([])
    else:
        tick_labels = [f"{start}-{end}" for start, end, _count in bins]
        heights = [count for _start, _end, count in bins]
        xs = list(range(len(bins)))
        bars = hist_ax.bar(
            xs,
            heights,
            width=1.0,
            align="edge",
            color="#3d7ea6",
            edgecolor="#3d7ea6",
            linewidth=0,
        )
        hist_ax.set_ylabel("개수")
        origin = bins[0][0]

        def _score_x(score: float) -> float:
            return (score - origin) / BIN_WIDTH

        hist_ax.set_xticks([x + 0.5 for x in xs])
        hist_ax.set_xticklabels(tick_labels, rotation=35, ha="right")
        ymax = max(heights) if heights else 1
        hist_ax.set_ylim(0, ymax * 1.18 + 1)
        hist_ax.set_xlim(0, max(len(bins), _score_x(1850) + 0.2))
        for bar, height in zip(bars, heights):
            if height <= 0:
                continue
            hist_ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                str(height),
                ha="center",
                va="bottom",
                fontsize=9,
            )
        handles = []
        for score, label, color in SCORE_MARKS:
            hist_ax.axvline(_score_x(score), color=color, linewidth=1.3, zorder=3)
            handles.append(Line2D([0], [0], color=color, linewidth=2.0, label=f"{score}  {label}"))
        hist_ax.legend(
            handles=handles,
            loc="upper left",
            framealpha=0.95,
            fontsize=10,
            borderpad=0.6,
            labelspacing=0.45,
        )

    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="결과 폴더를 집계해 그림 한 장으로 저장합니다.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=PROJECT_ROOT / "fig.png",
        help="저장할 이미지 경로 (기본: fig.png)",
    )
    args = parser.parse_args()
    summary = collect()
    out_path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_figure(summary, out_path)
    print(f"기준 파일: {summary['start_name']}")
    print(f"범위: {summary['start_label']}-{summary['end_label']} ({summary['expected_count']}개 캐릭터)")
    print(f"누락: {len(summary['missing'])}")
    if summary["missing"]:
        preview = ", ".join(summary["missing"][:30])
        suffix = " ..." if len(summary["missing"]) > 30 else ""
        print(f"  없는 캐릭터: {preview}{suffix}")
    print(f"유효하지 않음: {summary['invalid_count']}")
    print(f"미달: {len(summary['below_scores'])}")
    print(f"좋음: {len(summary['good_scores'])}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
