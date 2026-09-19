#!/usr/bin/env python3
"""Build non-stochastic sensitivity and ablation results from completed audits."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    failure = read_rows(root / "results/tables/failure_missingness_audit.csv")
    meta_input = read_rows(root / "results/tables/meta_analysis_input_audit.csv")
    eligibility = read_rows(root / "results/tables/meta_analysis_eligibility.csv")
    cases = read_rows(root / "data/manifests/cases.csv")

    correct = sum(int(row["judge_correct_cells"]) for row in failure)
    incorrect = sum(int(row["judge_incorrect_cells"]) for row in failure)
    unverifiable = sum(int(row["judge_unverifiable_cells"]) for row in failure)
    all_fields = correct + incorrect + unverifiable
    determinate = correct + incorrect
    included_not_extracted = sum(int(row["included_not_extracted"]) for row in cases)
    partial_cases = sum(row["lineage_status"] == "partial_extraction_coverage" for row in cases)
    numeric_five = sum(int(row["numeric_estimate_ci_rows"]) >= 5 for row in meta_input)
    numeric_ten = sum(int(row["numeric_estimate_ci_rows"]) >= 10 for row in meta_input)
    expert_pending = sum(
        row["final_gate_status"] == "pending_human_verification" for row in eligibility
    )
    final_eligible = sum(
        row["currently_eligible_for_meta_analysis"] == "true" for row in eligibility
    )

    rows: list[dict[str, Any]] = [
        {
            "analysis_family": "evaluator_denominator",
            "scenario": "all_requested_fields",
            "metric": "correct_share",
            "value": correct / all_fields,
            "numerator": correct,
            "denominator": all_fields,
            "interpretation": "descriptive archived verdict share",
            "status": "computed",
        },
        {
            "analysis_family": "evaluator_denominator",
            "scenario": "exclude_unverifiable",
            "metric": "conditional_agreement",
            "value": correct / determinate,
            "numerator": correct,
            "denominator": determinate,
            "interpretation": "inflated by removing UNVERIFIABLE from denominator",
            "status": "computed",
        },
        {
            "analysis_family": "evaluator_denominator",
            "scenario": "exclusion_effect",
            "metric": "percentage_point_increase",
            "value": 100 * (correct / determinate - correct / all_fields),
            "numerator": "",
            "denominator": "",
            "interpretation": "change caused solely by denominator restriction",
            "status": "computed",
        },
        {
            "analysis_family": "meta_eligibility_gate",
            "scenario": "numeric_estimate_ci_rows_at_least_5",
            "metric": "cases_passing",
            "value": numeric_five,
            "numerator": numeric_five,
            "denominator": 20,
            "interpretation": "naive field-completeness gate",
            "status": "computed",
        },
        {
            "analysis_family": "meta_eligibility_gate",
            "scenario": "numeric_estimate_ci_rows_at_least_10",
            "metric": "cases_passing",
            "value": numeric_ten,
            "numerator": numeric_ten,
            "denominator": 20,
            "interpretation": "naive row-count gate",
            "status": "computed",
        },
        {
            "analysis_family": "meta_eligibility_gate",
            "scenario": "expert_structural_review",
            "metric": "cases_pending_verification",
            "value": expert_pending,
            "numerator": expert_pending,
            "denominator": 20,
            "interpretation": "not currently eligible",
            "status": "computed",
        },
        {
            "analysis_family": "meta_eligibility_gate",
            "scenario": "full_frozen_gate",
            "metric": "currently_eligible_cases",
            "value": final_eligible,
            "numerator": final_eligible,
            "denominator": 20,
            "interpretation": "requires estimand, independence, human verification, and dependence handling",
            "status": "computed",
        },
        {
            "analysis_family": "extraction_coverage",
            "scenario": "historical_200_record_cap",
            "metric": "affected_cases",
            "value": partial_cases,
            "numerator": partial_cases,
            "denominator": 20,
            "interpretation": "Cases 16 through 20 have partial extraction coverage",
            "status": "computed",
        },
        {
            "analysis_family": "extraction_coverage",
            "scenario": "historical_200_record_cap",
            "metric": "included_records_not_extracted",
            "value": included_not_extracted,
            "numerator": included_not_extracted,
            "denominator": sum(int(row["included_rows"]) for row in cases),
            "interpretation": "unmodeled attrition before field extraction",
            "status": "computed",
        },
        {
            "analysis_family": "pooled_model_robustness",
            "scenario": "fixed_vs_dl_vs_reml_hk",
            "metric": "eligible_cases_available",
            "value": final_eligible,
            "numerator": final_eligible,
            "denominator": 20,
            "interpretation": "model comparison blocked by synthesis gate",
            "status": "not_estimable",
        },
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    all_share = correct / all_fields
    conditional = correct / determinate
    lines = [
        "# Step 15 Sensitivity and Ablation Analyses",
        "",
        "## Self-audit of the earlier conditional denominator",
        "",
        f"Across all 90,554 requested fields, the archived evaluator assigned `CORRECT` to "
        f"{all_share:.2%}. Excluding all 36,881 `UNVERIFIABLE` fields raises the reported value to "
        f"{conditional:.2%}, an increase of {100 * (conditional - all_share):.2f} percentage points "
        "caused solely by denominator restriction. Neither value is human-referenced accuracy. The "
        "contrast is retained to correct the earlier reporting choice and to demonstrate why the full "
        "denominator and excluded-state count must accompany a conditional percentage.",
        "",
        "## Numeric completeness does not establish synthesis readiness",
        "",
        f"A numeric estimate-and-interval threshold of at least five rows admits {numeric_five} cases. "
        f"A ten-row threshold admits {numeric_ten}. Independent case review leaves {expert_pending} "
        "cases that might support source reconstruction, and the full frozen gate admits zero cases. "
        "The historical schemas did not collect enough analytical context to satisfy that gate. This "
        "ablation shows that row completeness cannot substitute for estimand compatibility, study "
        "independence, or value verification; it does not show that every extracted value is invalid.",
        "",
        "## Extraction coverage is not uniform",
        "",
        f"Five cases stop at 200 extracted records, leaving {included_not_extracted:,} historical "
        "INCLUDE decisions without archived extraction rows. Any all-case extraction summary must "
        "report this attrition rather than treating the retained extracted rows as a complete sample.",
        "",
        "## Unavailable pooled-model sensitivity",
        "",
        "Fixed-effect, DerSimonian–Laird, and REML Hartung–Knapp comparisons are not estimable from the "
        "current archive because the historical schemas do not establish an analysis-ready common "
        "estimand. Reporting model-based robustness on provisional rows would obscure, rather than "
        "resolve, the missing analytical context.[1]",
        "",
        "## References",
        "",
        "[1]: https://training.cochrane.org/handbook/current/chapter-10 \"Cochrane Handbook Chapter 10: Analysing Data and Undertaking Meta-Analyses\"",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
