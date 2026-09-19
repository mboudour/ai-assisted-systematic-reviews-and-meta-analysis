#!/usr/bin/env python3
"""Run prespecified meta-analyses only for cases that pass every frozen gate."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evidence_quality.meta import run_all_models

SUMMARY_FIELDS = [
    "case_id",
    "slug",
    "analysis_scale",
    "model",
    "k",
    "estimate",
    "ci_lower",
    "ci_upper",
    "back_transformed_estimate",
    "back_transformed_ci_lower",
    "back_transformed_ci_upper",
    "prediction_lower",
    "prediction_upper",
    "tau2",
    "i2",
    "q",
    "null_crossed",
    "status",
]

WEIGHT_FIELDS = [
    "case_id",
    "model",
    "independent_study_id",
    "candidate_id",
    "yi",
    "vi",
    "normalized_weight",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def is_true(value: str) -> bool:
    return (value or "").strip().lower() == "true"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eligibility", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    eligibility = {
        int(row["case_id"]): row for row in read_rows(args.eligibility)
    }
    data = read_rows(args.data)
    eligible_cases = {
        case_id
        for case_id, row in eligibility.items()
        if is_true(row["currently_eligible_for_meta_analysis"])
    }
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in data:
        case_id = int(row["case_id"])
        if case_id not in eligible_cases:
            continue
        required_flags = (
            "human_verified",
            "independent_study_verified",
            "common_estimand_verified",
            "variance_derivation_valid",
        )
        if not all(is_true(row.get(flag, "")) for flag in required_flags):
            continue
        if not row.get("independent_study_id"):
            raise ValueError(f"Eligible row lacks independent_study_id: {row.get('candidate_id')}")
        groups[case_id].append(row)

    summary_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    for case_id, rows in sorted(groups.items()):
        unique_studies = {row["independent_study_id"] for row in rows}
        if len(unique_studies) != len(rows):
            raise ValueError(
                f"Case {case_id} contains dependent rows; select one estimate per study or use the declared secondary model"
            )
        if len(rows) < 5:
            raise ValueError(f"Case {case_id} has fewer than five verified independent studies")
        yi = [float(row["yi"]) for row in rows]
        vi = [float(row["vi"]) for row in rows]
        analysis_scale = rows[0]["analysis_scale"]
        if any(row["analysis_scale"] != analysis_scale for row in rows):
            raise ValueError(f"Case {case_id} mixes analysis scales")
        for model in run_all_models(yi, vi):
            ratio_scale = analysis_scale.startswith("log_")
            back = math.exp(model["estimate"]) if ratio_scale else model["estimate"]
            back_lower = math.exp(model["ci_lower"]) if ratio_scale else model["ci_lower"]
            back_upper = math.exp(model["ci_upper"]) if ratio_scale else model["ci_upper"]
            null_value = 0.0
            summary_rows.append(
                {
                    "case_id": case_id,
                    "slug": rows[0]["slug"],
                    "analysis_scale": analysis_scale,
                    "model": model["model"],
                    "k": model["k"],
                    "estimate": model["estimate"],
                    "ci_lower": model["ci_lower"],
                    "ci_upper": model["ci_upper"],
                    "back_transformed_estimate": back,
                    "back_transformed_ci_lower": back_lower,
                    "back_transformed_ci_upper": back_upper,
                    "prediction_lower": model["prediction_lower"],
                    "prediction_upper": model["prediction_upper"],
                    "tau2": model["tau2"],
                    "i2": model["i2"],
                    "q": model["q"],
                    "null_crossed": str(
                        model["ci_lower"] <= null_value <= model["ci_upper"]
                    ).lower(),
                    "status": "verified_and_eligible",
                }
            )
            for row, weight in zip(rows, model["normalized_weights"], strict=True):
                weight_rows.append(
                    {
                        "case_id": case_id,
                        "model": model["model"],
                        "independent_study_id": row["independent_study_id"],
                        "candidate_id": row["candidate_id"],
                        "yi": row["yi"],
                        "vi": row["vi"],
                        "normalized_weight": weight,
                    }
                )
    write_csv(args.summary, summary_rows, SUMMARY_FIELDS)
    write_csv(args.weights, weight_rows, WEIGHT_FIELDS)

    if not summary_rows:
        report = [
            "# Step 13 Prespecified Meta-Analysis Models",
            "",
            "## No pooled estimates were produced",
            "",
            "Step 12 found zero cases that currently pass the frozen synthesis gate. The final "
            "meta-analysis summary and weight tables are therefore schema-correct and empty. The 921 "
            "provisional effect-and-interval rows were not pooled because none is human verified, "
            "linked to an independent study, or confirmed to share a common estimand.",
            "",
            "The implemented engine supports fixed-effect inverse variance, DerSimonian–Laird random "
            "effects, and REML random effects with Hartung–Knapp inference. It reports normalized "
            "weights, confidence intervals, prediction intervals, Q, I-squared, and tau-squared. The "
            "runner enforces at least five verified independent studies and rejects mixed analysis scales.",
            "",
            "This empty result is a substantive quality-control outcome. Reproducing the prior pooled "
            "values on unverified, heterogeneous report rows would violate the frozen protocol.[1]",
            "",
            "## References",
            "",
            "[1]: https://training.cochrane.org/handbook/current/chapter-10 \"Cochrane Handbook Chapter 10: Analysing Data and Undertaking Meta-Analyses\"",
            "[2]: https://doi.org/10.18637/jss.v036.i03 \"Conducting Meta-Analyses in R with the metafor Package\"",
        ]
    else:
        report = [
            "# Step 13 Prespecified Meta-Analysis Models",
            "",
            "Verified eligible cases were analyzed. See the summary and study-weight tables.",
            "",
            "## References",
            "",
            "[1]: https://doi.org/10.18637/jss.v036.i03 \"Conducting Meta-Analyses in R with the metafor Package\"",
        ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
