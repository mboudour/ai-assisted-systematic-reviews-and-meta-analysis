#!/usr/bin/env python3
"""Analyze controlled evaluator error-injection results when available."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

METRIC_FIELDS = [
    "model_id",
    "error_type",
    "arm",
    "attempted_calls",
    "successful_calls",
    "failed_calls",
    "incorrect_verdicts",
    "correct_verdicts",
    "unverifiable_verdicts",
    "target_rate",
    "wilson_lower",
    "wilson_upper",
    "status",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return math.nan, math.nan
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def summarize(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["requested_model_id"], row["error_type"], row["arm"])].append(row)
    output = []
    for (model_id, error_type, arm), group in sorted(groups.items()):
        successful = [row for row in group if row["call_status"] == "ok"]
        incorrect = sum(row["verdict"] == "INCORRECT" for row in successful)
        correct = sum(row["verdict"] == "CORRECT" for row in successful)
        unverifiable = sum(row["verdict"] == "UNVERIFIABLE" for row in successful)
        lower, upper = wilson(incorrect, len(successful))
        output.append(
            {
                "model_id": model_id,
                "error_type": error_type,
                "arm": arm,
                "attempted_calls": len(group),
                "successful_calls": len(successful),
                "failed_calls": len(group) - len(successful),
                "incorrect_verdicts": incorrect,
                "correct_verdicts": correct,
                "unverifiable_verdicts": unverifiable,
                "target_rate": "" if not successful else incorrect / len(successful),
                "wilson_lower": "" if not successful else lower,
                "wilson_upper": "" if not successful else upper,
                "status": "estimated" if successful else "no_successful_calls",
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    rows = read_rows(args.input)
    if not rows:
        write_csv(args.output, [])
        report = [
            "# Step 10 Controlled Evaluator Error-Injection Experiment",
            "",
            "## Current status",
            "",
            "The design, input schema, two-model evaluator runner, failure logging, and analysis code "
            "are complete. The experiment has not been executed because it requires human-verified "
            "source-field pairs and controlled candidate values. Detection rates and false-alarm "
            "rates are therefore **not estimable**.",
            "",
            "The frozen design contains 11 error types, 30 injected items and 30 matched controls per "
            "type, and two evaluators. A full initial run therefore comprises 1,320 calls. Technical "
            "failures remain separate from `UNVERIFIABLE` verdicts and from incorrect-value detection.",
            "",
            "## Primary analysis",
            "",
            "For injected items, the target rate is the proportion of successful calls returning "
            "`INCORRECT`. For unchanged controls, the same calculation is the false-alarm rate. "
            "`UNVERIFIABLE` and failed calls retain separate denominators. Wilson intervals are reported "
            "for each model, error type, and arm.[1]",
            "",
            "## References",
            "",
            "[1]: https://doi.org/10.1080/01621459.1927.10502953 \"Probable Inference, the Law of Succession, and Statistical Inference\"",
        ]
    else:
        metrics = summarize(rows)
        write_csv(args.output, metrics)
        report = [
            "# Step 10 Controlled Evaluator Error-Injection Experiment",
            "",
            "The experiment was analyzed. Detection and false-alarm estimates are in "
            "`results/tables/error_injection_metrics.csv`.",
            "",
            "## References",
            "",
            "[1]: https://doi.org/10.1080/01621459.1927.10502953 \"Probable Inference, the Law of Succession, and Statistical Inference\"",
        ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
