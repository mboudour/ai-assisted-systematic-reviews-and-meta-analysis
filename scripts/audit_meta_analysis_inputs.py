#!/usr/bin/env python3
"""Audit structural availability of meta-analysis inputs in archived extractions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def numeric(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    cases = json.loads((root / "config/cases.json").read_text(encoding="utf-8"))["cases"]
    rows = []
    extracted_dir = root / "data/raw_snapshot/legacy/extracted"
    for case in cases:
        case_id = int(case["case_id"])
        field_names = {field["name"] for field in case["historical_extraction"]["fields"]}
        estimate_field = (
            "hazard_ratio"
            if "hazard_ratio" in field_names
            else "effect_size"
            if "effect_size" in field_names
            else ""
        )
        has_interval_schema = bool(
            estimate_field and {"ci_lower", "ci_upper"}.issubset(field_names)
        )
        path = next(extracted_dir.glob(f"case_{case_id:02d}_*_extracted.csv"))
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            extracted = list(csv.DictReader(handle))
        complete = 0
        numeric_complete = 0
        ordered = 0
        contains = 0
        for row in extracted:
            if not has_interval_schema:
                continue
            raw = [row.get(estimate_field, ""), row.get("ci_lower", ""), row.get("ci_upper", "")]
            if all((value or "").strip() for value in raw):
                complete += 1
            values = [numeric(value) for value in raw]
            if all(value is not None for value in values):
                numeric_complete += 1
                estimate, lower, upper = values
                if lower <= upper:
                    ordered += 1
                if lower <= estimate <= upper:
                    contains += 1
        archived_status = (
            "candidate_pending_estimand_independence_and_human_checks"
            if has_interval_schema and numeric_complete >= 5
            else "insufficient_archived_effect_and_uncertainty_fields"
        )
        primary_candidate = has_interval_schema and numeric_complete >= 10
        rows.append(
            {
                "case_id": case_id,
                "slug": case["slug"],
                "estimate_field": estimate_field,
                "has_estimate_and_ci_schema": str(has_interval_schema).lower(),
                "extracted_records": len(extracted),
                "complete_estimate_ci_rows": complete,
                "numeric_estimate_ci_rows": numeric_complete,
                "ordered_ci_rows": ordered,
                "estimate_within_ci_rows": contains,
                "minimum_five_rows_met": str(numeric_complete >= 5).lower(),
                "minimum_ten_rows_met": str(numeric_complete >= 10).lower(),
                "primary_candidate_by_row_count": str(primary_candidate).lower(),
                "independent_study_count": "",
                "common_estimand_verified": "false",
                "synthesis_critical_values_human_verified": "false",
                "archived_structural_status": archived_status,
                "final_eligibility_status": "pending_case_review_and_human_verification"
                if archived_status.startswith("candidate")
                else "ineligible_from_archived_schema",
            }
        )
    write_csv(args.output, rows)


if __name__ == "__main__":
    main()
