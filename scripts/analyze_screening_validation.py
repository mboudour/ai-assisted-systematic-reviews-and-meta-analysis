#!/usr/bin/env python3
"""Analyze screening validity against adjudicated human labels when available."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VALID_HUMAN_LABELS = {"include", "exclude", "uncertain"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def wilson_interval(successes: float, total: float, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def confusion_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals = Counter()
    for row in rows:
        weight = float(row.get("weight", 1.0))
        human = row["human_screening_label"]
        model = row["historical_llm_decision"]
        if human == "include" and model == "INCLUDE":
            totals["tp"] += weight
        elif human == "include" and model == "EXCLUDE":
            totals["fn"] += weight
        elif human == "exclude" and model == "INCLUDE":
            totals["fp"] += weight
        elif human == "exclude" and model == "EXCLUDE":
            totals["tn"] += weight
    tp, fn, fp, tn = (totals[key] for key in ("tp", "fn", "fp", "tn"))

    def ratio(num: float, den: float) -> float:
        return math.nan if den == 0 else num / den

    sensitivity = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    precision = ratio(tp, tp + fp)
    npv = ratio(tn, tn + fn)
    f1 = ratio(2 * precision * sensitivity, precision + sensitivity)
    balanced = (sensitivity + specificity) / 2
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "negative_predictive_value": npv,
        "f1": f1,
        "balanced_accuracy": balanced,
    }


def merge_adjudicated(
    manifest: list[dict[str, str]], annotations: list[dict[str, str]]
) -> list[dict[str, Any]]:
    manifest_by_id = {row["sample_id"]: row for row in manifest}
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for annotation in annotations:
        sample_id = annotation.get("sample_id", "")
        if sample_id not in manifest_by_id:
            raise ValueError(f"Unknown sample_id: {sample_id}")
        if sample_id in seen:
            raise ValueError(f"Duplicate adjudicated sample_id: {sample_id}")
        seen.add(sample_id)
        label = (annotation.get("human_screening_label") or "").strip().lower()
        if label not in VALID_HUMAN_LABELS:
            raise ValueError(f"Invalid human_screening_label for {sample_id}: {label}")
        row = dict(manifest_by_id[sample_id])
        row["human_screening_label"] = label
        row["weight"] = 1 / float(row["selection_probability"])
        merged.append(row)
    return merged


def decision_profile(root: Path) -> list[dict[str, Any]]:
    manifest_path = root / "data" / "manifests" / "cases.csv"
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        cases = list(csv.DictReader(handle))
    rows = []
    for row in cases:
        screened = int(row["screened_rows"])
        included = int(row["included_rows"])
        rows.append(
            {
                "case_id": row["case_id"],
                "slug": row["slug"],
                "screened_records": screened,
                "historical_include_records": included,
                "historical_exclude_records": screened - included,
                "historical_include_rate": included / screened,
                "accuracy_status": "pending_human_adjudication",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--adjudicated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = read_rows(root / "data/manifests/screening_sample_manifest.csv")
    annotations = read_rows(args.adjudicated)
    profile = decision_profile(root)
    write_csv(args.profile_output, profile, list(profile[0].keys()))

    metric_fields = [
        "scope",
        "case_id",
        "n_adjudicated",
        "n_uncertain",
        "tp_weighted",
        "fn_weighted",
        "fp_weighted",
        "tn_weighted",
        "sensitivity",
        "specificity",
        "precision",
        "negative_predictive_value",
        "f1",
        "balanced_accuracy",
        "status",
    ]
    if not annotations:
        write_csv(args.output, [], metric_fields)
        lines = [
            "# Step 8 Screening Validation",
            "",
            "## Current status",
            "",
            "The historical decision profile is complete, but no adjudicated human screening labels "
            "have been imported. Screening sensitivity, specificity, precision, negative predictive "
            "value, balanced accuracy, and F1 are therefore **not estimable**.",
            "",
            "`results/tables/screening_decision_profile.csv` reports the historical INCLUDE and "
            "EXCLUDE counts without calling them accuracy. `results/tables/screening_validation_metrics.csv` "
            "is schema-correct and empty until adjudicated labels are supplied.",
            "",
            "## Frozen analysis",
            "",
            "After import, primary estimates use inverse inclusion-probability weights. Pooled, "
            "case-level, domain-level, and prevalence-sensitive metrics will be reported. Uncertain "
            "human labels remain a separate count and are excluded only from the binary confusion "
            "matrix, not from sample accounting. Confidence intervals will follow the stratified "
            "cluster bootstrap specified in the frozen protocol; Wilson intervals are retained for "
            "unweighted descriptive proportions.[1]",
            "",
            "## References",
            "",
            "[1]: https://doi.org/10.1080/01621459.1927.10502953 \"Probable Inference, the Law of Succession, and Statistical Inference\"",
        ]
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    merged = merge_adjudicated(manifest, annotations)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped["pooled"] = [row for row in merged if row["human_screening_label"] != "uncertain"]
    for row in merged:
        if row["human_screening_label"] != "uncertain":
            grouped[f"case:{row['case_id']}"] .append(row)
    metrics_rows: list[dict[str, Any]] = []
    for scope, group in sorted(grouped.items()):
        metrics = confusion_metrics(group)
        case_id = "" if scope == "pooled" else scope.split(":", 1)[1]
        all_scope = merged if scope == "pooled" else [row for row in merged if row["case_id"] == case_id]
        metrics_rows.append(
            {
                "scope": scope,
                "case_id": case_id,
                "n_adjudicated": len(all_scope),
                "n_uncertain": sum(row["human_screening_label"] == "uncertain" for row in all_scope),
                "tp_weighted": metrics["tp"],
                "fn_weighted": metrics["fn"],
                "fp_weighted": metrics["fp"],
                "tn_weighted": metrics["tn"],
                "sensitivity": metrics["sensitivity"],
                "specificity": metrics["specificity"],
                "precision": metrics["precision"],
                "negative_predictive_value": metrics["negative_predictive_value"],
                "f1": metrics["f1"],
                "balanced_accuracy": metrics["balanced_accuracy"],
                "status": "estimated_from_adjudicated_sample",
            }
        )
    write_csv(args.output, metrics_rows, metric_fields)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        "# Step 8 Screening Validation\n\nAdjudicated labels were analyzed. See the tracked metrics table.\n\n"
        "## References\n\n"
        "[1]: https://doi.org/10.1080/01621459.1927.10502953 \"Probable Inference, the Law of Succession, and Statistical Inference\"\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
