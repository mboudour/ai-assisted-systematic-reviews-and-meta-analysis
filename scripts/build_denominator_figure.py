#!/usr/bin/env python3
"""Build the one core-paper figure: stage denominators and denominator restriction."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--png",
        type=Path,
        default=Path("results/figures/denominator_ledger.png"),
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("results/figures/denominator_ledger.pdf"),
    )
    args = parser.parse_args()
    root = args.root.resolve()

    retrieval = read_csv(root / "results/tables/retrieval_corpus_quality.csv")
    verdict_cube = read_csv(root / "results/tables/evaluator_verdict_cube.csv")
    cases = read_csv(root / "data/manifests/cases.csv")

    retrieved = sum(int(row["historical_pre_dedup_rows_reported"]) for row in retrieval)
    retained = sum(int(row["historical_post_dedup_rows"]) for row in retrieval)
    included = sum(int(row["included_rows"]) for row in cases)
    extracted = sum(int(row["extracted_rows"]) for row in cases)
    fields = sum(int(row["count"]) for row in verdict_cube)
    correct = sum(int(row["count"]) for row in verdict_cube if row["verdict"] == "CORRECT")
    incorrect = sum(int(row["count"]) for row in verdict_cube if row["verdict"] == "INCORRECT")
    unverifiable = sum(
        int(row["count"]) for row in verdict_cube if row["verdict"] == "UNVERIFIABLE"
    )
    determinate = correct + incorrect

    # The retrieval audit is read deliberately so figure generation fails if the
    # stage audit is absent; the manifest remains the canonical count source.
    assert len(retrieval) == 20
    assert (retrieved, retained, included, extracted, fields) == (
        95_292,
        94_522,
        19_276,
        11_500,
        90_554,
    )

    colors = {
        "navy": "#17324D",
        "blue": "#2F6690",
        "teal": "#3A8D8B",
        "gold": "#D5A021",
        "light": "#F3F5F7",
        "correct": "#2A7F62",
        "incorrect": "#B94A48",
        "unverifiable": "#9AA3AD",
        "text": "#1D2733",
    }

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
        }
    )
    fig = plt.figure(figsize=(10.5, 5.8), facecolor="white")
    grid = fig.add_gridspec(1, 2, width_ratios=[1.08, 1.0], wspace=0.18)

    ax0 = fig.add_subplot(grid[0, 0])
    ax0.set_xlim(0, 1)
    ax0.set_ylim(0, 1)
    ax0.axis("off")
    ax0.set_title("A. Stage-specific denominators", loc="left", fontweight="bold", pad=12)

    stages = [
        ("Retrieved", retrieved, "records", colors["navy"]),
        ("Retained after deduplication", retained, "records", colors["blue"]),
        ("Screened INCLUDE", included, "records", colors["teal"]),
        ("Structured extraction", extracted, "records", colors["gold"]),
        ("Requested extraction fields", fields, "field cells", colors["navy"]),
    ]
    x, width, height = 0.08, 0.84, 0.12
    ys = [0.79, 0.62, 0.45, 0.28, 0.08]
    for index, ((label, value, unit, color), y) in enumerate(zip(stages, ys, strict=True)):
        box = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            linewidth=0,
            facecolor=color,
        )
        ax0.add_patch(box)
        ax0.text(x + 0.03, y + 0.072, label, color="white", fontweight="bold", va="center")
        ax0.text(
            x + width - 0.03,
            y + 0.072,
            f"{value:,} {unit}",
            color="white",
            fontweight="bold",
            va="center",
            ha="right",
        )
        if label == "Structured extraction":
            ax0.text(
                x + 0.03,
                y + 0.026,
                "Coverage: 11,500 of 19,276 INCLUDE labels; 7,776 omitted",
                color="white",
                va="center",
                fontsize=7.2,
            )
        if index < len(stages) - 1:
            next_y = ys[index + 1]
            ax0.annotate(
                "",
                xy=(0.50, next_y + height + 0.007),
                xytext=(0.50, y - 0.007),
                arrowprops=dict(arrowstyle="-|>", color="#627181", lw=1.2),
            )
    ax0.text(
        0.08,
        0.005,
        "Units change at the final stage: records → requested field cells.",
        color="#5B6570",
        fontsize=8,
    )

    ax1 = fig.add_subplot(grid[0, 1])
    ax1.set_title("B. Same numerator, different denominator", loc="left", fontweight="bold", pad=12)

    full = [100 * correct / fields, 100 * incorrect / fields, 100 * unverifiable / fields]
    restricted = [100 * correct / determinate, 100 * incorrect / determinate, 0]
    bar_data = [full, restricted]
    y_positions = [1, 0]
    bar_colors = [colors["correct"], colors["incorrect"], colors["unverifiable"]]
    segment_labels = ["CORRECT", "INCORRECT", "UNVERIFIABLE"]

    for y, values in zip(y_positions, bar_data, strict=True):
        left = 0.0
        for value, color in zip(values, bar_colors, strict=True):
            if value > 0:
                ax1.barh(y, value, left=left, height=0.48, color=color, edgecolor="white", linewidth=1)
            left += value

    ax1.set_yticks([])
    ax1.set_ylim(-0.52, 1.52)
    ax1.text(0, 1.29, "All requested fields (n = 90,554)", ha="left", va="bottom", color=colors["text"])
    ax1.text(0, 0.29, "After excluding UNVERIFIABLE (n = 53,673)", ha="left", va="bottom", color=colors["text"])
    ax1.set_xlim(0, 100)
    ax1.set_xlabel("Share of declared denominator (%)")
    ax1.set_xticks([0, 20, 40, 60, 80, 100])
    ax1.grid(axis="x", color="#DCE1E6", linewidth=0.8)
    ax1.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax1.spines[spine].set_visible(False)
    ax1.spines["bottom"].set_color("#A8B0B8")

    ax1.text(full[0] / 2, 1, f"{full[0]:.2f}%", ha="center", va="center", color="white", fontweight="bold")
    ax1.text(
        full[0] + full[1] + full[2] / 2,
        1,
        f"{full[2]:.2f}%",
        ha="center",
        va="center",
        color="white",
        fontweight="bold",
    )
    ax1.text(
        restricted[0] / 2,
        0,
        f"{restricted[0]:.2f}% CORRECT",
        ha="center",
        va="center",
        color="white",
        fontweight="bold",
    )
    ax1.annotate(
        "+40.12 percentage points",
        xy=(restricted[0], 0.20),
        xytext=(58, 0.53),
        ha="center",
        color=colors["text"],
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#627181", lw=1.2),
    )
    handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in bar_colors]
    ax1.legend(
        handles,
        segment_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.32),
        ncol=3,
        frameon=False,
        fontsize=8,
    )
    ax1.text(
        0,
        -0.18,
        "Neither percentage is an accuracy estimate;\nthe contrast isolates denominator restriction.",
        transform=ax1.transAxes,
        fontsize=8,
        color="#5B6570",
        va="top",
        wrap=True,
    )

    fig.suptitle(
        "Denominator ledger for the archived evidence-synthesis workflow",
        x=0.04,
        ha="left",
        y=0.99,
        fontsize=13,
        fontweight="bold",
        color=colors["text"],
    )
    fig.subplots_adjust(top=0.86, bottom=0.25, left=0.08, right=0.98)

    png_path = root / args.png
    pdf_path = root / args.pdf
    png_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(
        pdf_path,
        bbox_inches="tight",
        facecolor="white",
        metadata={"CreationDate": None, "ModDate": None, "Creator": "Matplotlib"},
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
