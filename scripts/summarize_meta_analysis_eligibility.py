#!/usr/bin/env python3
"""Consolidate case-level structural and judgment-based synthesis eligibility audits."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> dict[int, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {int(row["case_id"]): row for row in csv.DictReader(handle)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assessments", type=Path, required=True)
    parser.add_argument("--input-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.assessments.read_text(encoding="utf-8"))
    input_audit = read_csv(args.input_audit)
    rows: list[dict[str, Any]] = []
    for assessment in sorted(payload["assessments"], key=lambda item: item["case_id"]):
        case_id = int(assessment["case_id"])
        audit = input_audit[case_id]
        rows.append(
            {
                "case_id": case_id,
                "slug": assessment["slug"],
                "has_estimate_and_ci_schema": audit["has_estimate_and_ci_schema"],
                "numeric_estimate_ci_rows": audit["numeric_estimate_ci_rows"],
                "conservative_complete_rows_from_case_review": assessment["complete_effect_rows"],
                "structural_eligibility": assessment["structural_eligibility"],
                "common_estimand_candidate": assessment["common_estimand_candidate"] or "",
                "independent_study_count_status": assessment["independent_study_count_status"],
                "recommended_role": assessment["recommended_role"],
                "final_gate_status": assessment["final_gate_status"],
                "currently_eligible_for_meta_analysis": "false",
                "blocking_issue_count": len(assessment["blocking_issues"]),
                "reasoning": assessment["reasoning"],
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    pending = [row for row in rows if row["final_gate_status"] == "pending_human_verification"]
    ineligible = [row for row in rows if row["final_gate_status"] == "structurally_ineligible"]
    sensitivity = [
        row for row in rows if row["recommended_role"] == "sensitivity_candidate_after_verification"
    ]
    descriptive = [row for row in rows if row["recommended_role"] == "descriptive_only"]
    lines = [
        "# Step 12 Meta-Analysis Eligibility Audit",
        "",
        "## No case currently passes the frozen gate",
        "",
        "All 20 cases were reviewed independently against the frozen requirements for a common "
        "estimand, independent-study identification, human verification of synthesis-critical values, "
        "and dependence handling. **Zero cases currently qualify for meta-analysis.**",
        "",
        f"Sixteen cases are structurally ineligible from the archived schema and records. Four cases "
        f"remain pending human verification: {', '.join(str(row['case_id']) for row in pending)}. "
        "Pending means that a narrower estimand might be recoverable after source-level work; it does "
        "not mean that the case is eligible now.",
        "",
        "## Candidate roles after verification",
        "",
        f"Cases {', '.join(str(row['case_id']) for row in sensitivity)} were judged possible "
        "sensitivity-analysis candidates after full human verification and study linkage. Cases "
        f"{', '.join(str(row['case_id']) for row in descriptive)} remain descriptive candidates. "
        "No case was accepted as a primary synthesis candidate.",
        "",
        "Case 3 may support a narrowly defined log hazard-ratio synthesis for three-component major "
        "adverse cardiovascular events. Case 15 may support a narrowly defined adjusted odds-ratio "
        "synthesis for childhood acute lower respiratory infection under a specified fuel contrast. "
        "Both require full-text verification, effect-measure confirmation, report-to-study linkage, "
        "one prespecified estimate per independent study, and explicit handling of dependent estimates.",
        "",
        "Cases 2 and 6 have possible topic-restricted estimands, but their current archives mix effect "
        "measures, outcomes, designs, and secondary reports. They remain descriptive until a new "
        "source-level synthesis dataset is constructed.",
        "",
        "## Consequence for later steps",
        "",
        "The 921 provisional rows with an estimate and interval are retained as an audit inventory. "
        "They are marked unverified and must not be pooled. Step 13 therefore supplies tested "
        "meta-analysis code and empty final result tables. Step 14 supplies a propagation engine but "
        "cannot produce calibrated inferential results until at least one case passes this gate and "
        "human error-rate estimates exist.",
        "",
        "## References",
        "",
        "[1]: https://training.cochrane.org/handbook/current/chapter-10 \"Cochrane Handbook Chapter 10: Analysing Data and Undertaking Meta-Analyses\"",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
