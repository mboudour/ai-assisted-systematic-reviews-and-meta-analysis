#!/usr/bin/env python3
"""Analyze extraction and evaluator validity against adjudicated human labels."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VALID_HUMAN_LABELS = {"correct", "incorrect", "not_assessable"}
VALID_SOURCE_STATES = {
    "reported_explicitly",
    "derivable_from_source",
    "not_reported",
    "ambiguous_source",
    "source_unavailable",
    "not_applicable",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ratio(numerator: float, denominator: float) -> float:
    return math.nan if denominator == 0 else numerator / denominator


def validation_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals = Counter()
    for row in rows:
        weight = float(row.get("weight", 1.0))
        human = row["human_field_label"]
        evaluator = row["historical_evaluator_verdict"]
        totals["all"] += weight
        if human == "not_assessable":
            totals["not_assessable"] += weight
            continue
        totals["assessable"] += weight
        totals[human] += weight
        if evaluator == "UNVERIFIABLE":
            totals["evaluator_abstain"] += weight
        if human == "incorrect" and evaluator == "INCORRECT":
            totals["evaluator_true_positive"] += weight
        if human == "correct" and evaluator == "CORRECT":
            totals["evaluator_true_negative"] += weight
    return {
        "weighted_total": totals["all"],
        "weighted_assessable": totals["assessable"],
        "weighted_not_assessable": totals["not_assessable"],
        "weighted_correct": totals["correct"],
        "weighted_incorrect": totals["incorrect"],
        "extraction_error_rate": ratio(totals["incorrect"], totals["assessable"]),
        "evaluator_sensitivity": ratio(
            totals["evaluator_true_positive"], totals["incorrect"]
        ),
        "evaluator_specificity": ratio(
            totals["evaluator_true_negative"], totals["correct"]
        ),
        "evaluator_abstention_rate": ratio(
            totals["evaluator_abstain"], totals["assessable"]
        ),
    }


def historical_profile(root: Path) -> list[dict[str, Any]]:
    cases_payload = json.loads((root / "config/cases.json").read_text(encoding="utf-8"))
    cases = {int(case["case_id"]): case for case in cases_payload["cases"]}
    rows: list[dict[str, Any]] = []
    extracted_dir = root / "data/raw_snapshot/legacy/extracted"
    for case_id, case in sorted(cases.items()):
        path = next(extracted_dir.glob(f"case_{case_id:02d}_*_extracted.csv"))
        fields = case["historical_extraction"]["fields"]
        counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for record in csv.DictReader(handle):
                for field in fields:
                    field_name = field["name"]
                    value = (record.get(field_name) or "").strip()
                    verdict = (record.get(f"judge_{field_name}") or "").strip().upper()
                    key = (field_name, field["audit_class"])
                    counts[key]["cells"] += 1
                    counts[key]["null"] += not bool(value)
                    counts[key][verdict] += 1
        for (field_name, field_class), counter in sorted(counts.items()):
            determinate = counter["CORRECT"] + counter["INCORRECT"]
            rows.append(
                {
                    "case_id": case_id,
                    "slug": case["slug"],
                    "field_name": field_name,
                    "field_class": field_class,
                    "field_cells": counter["cells"],
                    "null_cells": counter["null"],
                    "null_rate": counter["null"] / counter["cells"],
                    "evaluator_correct": counter["CORRECT"],
                    "evaluator_incorrect": counter["INCORRECT"],
                    "evaluator_unverifiable": counter["UNVERIFIABLE"],
                    "evaluator_unverifiable_rate_all": counter["UNVERIFIABLE"]
                    / counter["cells"],
                    "conditional_agreement_excluding_unverifiable": (
                        "" if determinate == 0 else counter["CORRECT"] / determinate
                    ),
                    "human_accuracy_status": "pending_human_adjudication",
                }
            )
    return rows


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
        label = (annotation.get("human_field_label") or "").strip().lower()
        source_status = (annotation.get("source_status") or "").strip().lower()
        if label not in VALID_HUMAN_LABELS:
            raise ValueError(f"Invalid human_field_label for {sample_id}: {label}")
        if source_status not in VALID_SOURCE_STATES:
            raise ValueError(f"Invalid source_status for {sample_id}: {source_status}")
        row = dict(manifest_by_id[sample_id])
        row["human_field_label"] = label
        row["source_status"] = source_status
        row["weight"] = 1 / float(row["selection_probability"])
        merged.append(row)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--adjudicated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = read_rows(root / "data/manifests/extraction_sample_manifest.csv")
    annotations = read_rows(args.adjudicated)
    profile = historical_profile(root)
    write_csv(args.profile_output, profile, list(profile[0].keys()))

    metric_fields = [
        "scope_type",
        "scope_value",
        "n_annotated",
        "weighted_total",
        "weighted_assessable",
        "weighted_not_assessable",
        "weighted_correct",
        "weighted_incorrect",
        "extraction_error_rate",
        "evaluator_sensitivity",
        "evaluator_specificity",
        "evaluator_abstention_rate",
        "status",
    ]
    if not annotations:
        write_csv(args.output, [], metric_fields)
        class_counts: dict[str, Counter] = defaultdict(Counter)
        for row in profile:
            group = class_counts[row["field_class"]]
            for key in (
                "field_cells",
                "evaluator_correct",
                "evaluator_incorrect",
                "evaluator_unverifiable",
            ):
                group[key] += int(row[key])
        class_lines = []
        for field_class, counts in sorted(class_counts.items()):
            cells = counts["field_cells"]
            class_lines.append(
                f"| {field_class} | {cells:,} | {counts['evaluator_correct'] / cells:.2%} | "
                f"{counts['evaluator_incorrect'] / cells:.2%} | "
                f"{counts['evaluator_unverifiable'] / cells:.2%} |"
            )
        lines = [
            "# Step 9 Extraction and Evaluator Validation",
            "",
            "## Current status",
            "",
            "No adjudicated human extraction labels have been imported. Human-referenced extraction "
            "error, evaluator sensitivity, evaluator specificity, and evaluator abstention among "
            "source-assessable fields are therefore **not estimable**.",
            "",
            "The historical same-model evaluator profile is retained as a descriptive output. It is "
            "not described as accuracy because the evaluator shares the generator's model lineage "
            "and source text, and the archived verdicts have not been independently validated.",
            "",
            "## Historical evaluator verdict profile",
            "",
            "| Field class | Fields | CORRECT | INCORRECT | UNVERIFIABLE |",
            "|---|---:|---:|---:|---:|",
            *class_lines,
            "",
            "`results/tables/extraction_evaluator_profile.csv` contains case-by-field counts and full "
            "denominators. `results/tables/extraction_validation_metrics.csv` remains schema-correct "
            "and empty until human adjudication is complete.",
            "",
            "## Frozen analysis",
            "",
            "The primary extraction estimand is the design-weighted error rate among source-assessable "
            "fields. The primary evaluator estimands are sensitivity to human-confirmed errors and "
            "specificity for human-confirmed correct fields. Source inadequacy and evaluator abstention "
            "are separate reported rates. Estimates will be stratified by case, field name, field "
            "class, and extracted-null status, with record-clustered uncertainty.",
            "",
            "## References",
            "",
            "[1]: https://doi.org/10.1177/001316446002000104 \"A Coefficient of Agreement for Nominal Scales\"",
        ]
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    merged = merge_adjudicated(manifest, annotations)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    groups[("pooled", "all")] = merged
    for row in merged:
        for key in (
            ("case_id", row["case_id"]),
            ("field_name", row["field_name"]),
            ("field_class", row["field_class"]),
            ("null_status", row["extracted_null_status"]),
        ):
            groups[key].append(row)
    metric_rows = []
    for (scope_type, scope_value), group in sorted(groups.items()):
        metrics = validation_metrics(group)
        metric_rows.append(
            {
                "scope_type": scope_type,
                "scope_value": scope_value,
                "n_annotated": len(group),
                **metrics,
                "status": "estimated_from_adjudicated_sample",
            }
        )
    write_csv(args.output, metric_rows, metric_fields)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        "# Step 9 Extraction and Evaluator Validation\n\nAdjudicated labels were analyzed. See the tracked metrics table.\n\n"
        "## References\n\n"
        "[1]: https://doi.org/10.1177/001316446002000104 \"A Coefficient of Agreement for Nominal Scales\"\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
