#!/usr/bin/env python3
"""Build provisional meta-analysis rows from archived values without asserting validity."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

Z_975 = 1.959963984540054


def clean(value: str) -> str:
    return " ".join((value or "").split())


def number(value: str) -> float | None:
    try:
        return float((value or "").strip())
    except ValueError:
        return None


def record_id(case_id: int, row_number: int, title: str, doi: str, year: str) -> str:
    key = clean(doi).lower() or f"{clean(title).lower()}|{clean(year)}"
    return hashlib.sha256(f"{case_id}|{row_number}|{key}".encode("utf-8")).hexdigest()[:24]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-packet", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    with args.audit.open("r", encoding="utf-8", newline="") as handle:
        audit = {int(row["case_id"]): row for row in csv.DictReader(handle)}
    cases_payload = json.loads((root / "config/cases.json").read_text(encoding="utf-8"))
    cases = {int(case["case_id"]): case for case in cases_payload["cases"]}
    extracted_dir = root / "data/raw_snapshot/legacy/extracted"
    output_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    for case_id, audit_row in sorted(audit.items()):
        if audit_row["archived_structural_status"] != "candidate_pending_estimand_independence_and_human_checks":
            continue
        estimate_field = audit_row["estimate_field"]
        path = next(extracted_dir.glob(f"case_{case_id:02d}_*_extracted.csv"))
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                estimate = number(row.get(estimate_field, ""))
                lower = number(row.get("ci_lower", ""))
                upper = number(row.get("ci_upper", ""))
                if None in (estimate, lower, upper):
                    continue
                source_scale = "ratio" if estimate_field == "hazard_ratio" else "reported_effect_scale"
                if estimate_field == "hazard_ratio":
                    valid_transform = estimate > 0 and lower > 0 and upper > 0 and lower < upper
                    yi = math.log(estimate) if valid_transform else None
                    sei = (math.log(upper) - math.log(lower)) / (2 * Z_975) if valid_transform else None
                    analysis_scale = "log_hazard_ratio"
                else:
                    valid_transform = lower < upper
                    yi = estimate if valid_transform else None
                    sei = (upper - lower) / (2 * Z_975) if valid_transform else None
                    analysis_scale = "unverified_reported_effect_scale"
                valid_variance = bool(valid_transform and sei is not None and sei > 0)
                rec_id = record_id(
                    case_id,
                    row_number,
                    row.get("_title", ""),
                    row.get("_doi", ""),
                    row.get("_year", ""),
                )
                candidate_id = f"MA-{case_id:02d}-{rec_id}"
                output_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "case_id": case_id,
                        "slug": cases[case_id]["slug"],
                        "record_id": rec_id,
                        "source_row_number": row_number,
                        "estimate_field": estimate_field,
                        "reported_estimate": estimate,
                        "reported_ci_lower": lower,
                        "reported_ci_upper": upper,
                        "source_scale": source_scale,
                        "analysis_scale": analysis_scale,
                        "yi": "" if yi is None else yi,
                        "sei": "" if sei is None else sei,
                        "vi": "" if sei is None else sei * sei,
                        "interval_order_valid": str(lower < upper).lower(),
                        "estimate_within_interval": str(lower <= estimate <= upper).lower(),
                        "variance_derivation_valid": str(valid_variance).lower(),
                        "human_verified": "false",
                        "independent_study_verified": "false",
                        "common_estimand_verified": "false",
                        "analysis_eligibility": "provisional_unverified",
                    }
                )
                review_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "case_id": case_id,
                        "record_id": rec_id,
                        "title": clean(row.get("_title", "")),
                        "doi": clean(row.get("_doi", "")),
                        "year": clean(row.get("_year", "")),
                        "outcome": clean(row.get("outcome", "") or row.get("outcome_measure", "")),
                        "study_design": clean(row.get("study_design", "")),
                        "estimate_field": estimate_field,
                        "reported_estimate": estimate,
                        "reported_ci_lower": lower,
                        "reported_ci_upper": upper,
                        "human_verified": "",
                        "independent_study_id": "",
                        "common_estimand_id": "",
                        "preferred_estimate": "",
                        "verification_notes": "",
                    }
                )
    output_fields = list(output_rows[0].keys())
    review_fields = list(review_rows[0].keys())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    args.review_packet.parent.mkdir(parents=True, exist_ok=True)
    with args.review_packet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(review_rows)


if __name__ == "__main__":
    main()
