#!/usr/bin/env python3
"""Build the quantified claim-consequence matrix for the ground-truth-free paper."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def requirement_row(
    name: str,
    description: str,
    aliases: set[str],
    fields_by_case: dict[int, set[str]],
    consequence: str,
) -> dict[str, Any]:
    matching = {
        case_id: sorted(fields & aliases)
        for case_id, fields in fields_by_case.items()
        if fields & aliases
    }
    return {
        "requirement": name,
        "operational_definition": description,
        "cases_with_required_field": len(matching),
        "cases_total": len(fields_by_case),
        "case_ids": ";".join(str(case_id) for case_id in sorted(matching)),
        "matching_fields": ";".join(
            f"{case_id}:{'|'.join(values)}" for case_id, values in sorted(matching.items())
        ),
        "observed_consequence": consequence,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--matrix-output",
        type=Path,
        default=Path("results/tables/claim_consequence_matrix.csv"),
    )
    parser.add_argument(
        "--schema-output",
        type=Path,
        default=Path("results/tables/schema_requirement_coverage.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/claim_consequence_matrix.md"),
    )
    args = parser.parse_args()
    root = args.root.resolve()

    cases_payload = read_json(root / "config/cases.json")
    fields_by_case = {
        int(case["case_id"]): {
            field["name"] for field in case["historical_extraction"]["fields"]
        }
        for case in cases_payload["cases"]
    }
    verdict_cube = read_csv(root / "results/tables/evaluator_verdict_cube.csv")
    meta = read_csv(root / "results/tables/meta_analysis_input_audit.csv")
    case_manifest = read_csv(root / "data/manifests/cases.csv")
    repeatability = read_json(
        root / "results/tables/repeatability_normalized_summary.json"
    )
    screened = sum(int(row["screened_rows"]) for row in case_manifest)
    cells = sum(int(row["count"]) for row in verdict_cube)
    correct = sum(
        int(row["count"]) for row in verdict_cube if row["verdict"] == "CORRECT"
    )
    incorrect = sum(
        int(row["count"]) for row in verdict_cube if row["verdict"] == "INCORRECT"
    )
    unverifiable = sum(
        int(row["count"])
        for row in verdict_cube
        if row["verdict"] == "UNVERIFIABLE"
    )
    determinate = correct + incorrect

    complete_estimate_ci_rows = sum(int(row["complete_estimate_ci_rows"]) for row in meta)
    estimate_ci_cases = sum(row["has_estimate_and_ci_schema"] == "true" for row in meta)
    numeric_five_cases = sum(int(row["numeric_estimate_ci_rows"]) >= 5 for row in meta)
    normalized_cat = repeatability["all_nonnull_by_declared_type"]["categorical"]
    normalized_num = repeatability["all_nonnull_by_declared_type"]["numeric"]
    mixed = repeatability["null_state_counts"]
    mixed_weighted = repeatability["null_state_design_weighted"]["mixed_null"]

    schema_rows = [
        requirement_row(
            "study-level linkage identifier",
            "An explicit study_id, trial_id, cohort_id, or study_cluster_id field that can group multiple reports",
            {
                "study_id",
                "trial_id",
                "cohort_id",
                "study_cluster_id",
            },
            fields_by_case,
            "The retained DOI can identify a report when present, but multiple reports from one underlying study cannot be grouped.",
        ),
        requirement_row(
            "explicit outcome construct",
            "A generic outcome or outcome_measure field",
            {"outcome", "outcome_measure"},
            fields_by_case,
            "Most case schemas cannot distinguish estimates for different outcome constructs through a dedicated field.",
        ),
        requirement_row(
            "analysis time point",
            "An explicit follow_up_years, follow_up_months, time_point, or follow_up field",
            {"follow_up_years", "follow_up_months", "time_point", "follow_up"},
            fields_by_case,
            "Estimates measured at different follow-up times cannot generally be separated.",
        ),
        requirement_row(
            "effect-measure label",
            "An explicit effect_measure, effect_measure_type, or measure_type field",
            {"effect_measure", "effect_measure_type", "measure_type"},
            fields_by_case,
            "No schema has a dedicated effect-measure metadata field; generic effect_size values therefore lack a recorded scale.",
        ),
        requirement_row(
            "effect-specific estimate column",
            "An estimate field whose name itself specifies hazard ratio, odds ratio, risk ratio, rate ratio, or mean difference",
            {
                "hazard_ratio",
                "odds_ratio",
                "risk_ratio",
                "rate_ratio",
                "mean_difference",
                "standardized_mean_difference",
            },
            fields_by_case,
            "One schema names hazard_ratio explicitly; the other nine estimate-and-interval schemas use the generic field effect_size.",
        ),
        requirement_row(
            "confidence interval",
            "Both ci_lower and ci_upper fields",
            {"ci_lower", "ci_upper"},
            fields_by_case,
            "Ten schemas collect interval bounds; populated bounds alone do not establish a common estimand or independence.",
        ),
        requirement_row(
            "variance or standard error",
            "An explicit variance, within_study_variance, standard_error, or se field",
            {"variance", "within_study_variance", "standard_error", "se"},
            fields_by_case,
            "No schema directly records the within-study variance used for inverse-variance weighting.",
        ),
        requirement_row(
            "dependence or clustering identifier",
            "An explicit cluster_id, study_cluster_id, arm_id, comparison_id, or effect_id field",
            {"cluster_id", "study_cluster_id", "arm_id", "comparison_id", "effect_id"},
            fields_by_case,
            "Multiple outcomes, time points, contrasts, and reports cannot be grouped for dependence handling.",
        ),
    ]
    # Confidence intervals require both fields, not either field.
    ci_row = next(row for row in schema_rows if row["requirement"] == "confidence interval")
    ci_cases = [
        case_id
        for case_id, fields in fields_by_case.items()
        if {"ci_lower", "ci_upper"}.issubset(fields)
    ]
    ci_row["cases_with_required_field"] = len(ci_cases)
    ci_row["case_ids"] = ";".join(map(str, ci_cases))
    ci_row["matching_fields"] = ";".join(
        f"{case_id}:ci_lower|ci_upper" for case_id in ci_cases
    )
    write_csv(root / args.schema_output, schema_rows)

    matrix_rows = [
        {
            "lesson": "Denominator-explicit reporting",
            "established_principle": "Conditional agreement and abstention-aware coverage answer different questions.",
            "observed_consequence": (
                f"CORRECT is {correct:,}/{cells:,} ({correct / cells:.2%}) of requested fields but "
                f"{correct:,}/{determinate:,} ({correct / determinate:.2%}) after excluding "
                f"{unverifiable:,} UNVERIFIABLE fields."
            ),
            "quantified_effect": f"{100 * (correct / determinate - correct / cells):.2f} percentage-point increase",
            "identifiable_claim": "The displayed percentage is highly sensitive to the declared denominator.",
            "not_identifiable": "Extraction accuracy or evaluator validity",
            "literature_anchor": "Wen et al. 2025 abstention survey; Zheng et al. 2023 LLM-as-judge",
        },
        {
            "lesson": "Typed operational failure states",
            "established_principle": "Logical requests, retries, terminal errors, and content outcomes require separate event fields.",
            "observed_consequence": (
                "The archive retains no call-status, attempt, retry, request, or error fields, while the "
                "historical code maps terminal failures onto ordinary analytical states. A later rerun with "
                "logging would measure a different model, prompt, schema, API, and execution period rather "
                "than recover the historical run."
            ),
            "quantified_effect": "Historical screening, extraction, and evaluator failure rates are not identifiable",
            "identifiable_claim": "The archive cannot distinguish operational failure from specified analytical states.",
            "not_identifiable": "Failure incidence, retry success, or mis-exclusion rate",
            "literature_anchor": "OpenTelemetry GenAI conventions; Google SRE monitoring and retry guidance",
        },
        {
            "lesson": "Versioned relational provenance",
            "established_principle": "Inputs, activities, agents, models, prompts, code, and outputs require linked execution provenance.",
            "observed_consequence": (
                f"The generating model for all {screened:,} historical screening labels is unresolved: "
                "the script, README, and manuscript disagree, "
                "and the rows retain no model or request metadata."
            ),
            "quantified_effect": f"{screened:,} labels cannot receive a model-specific attribution",
            "identifiable_claim": "The historical screening execution identity is not reconstructable from retained artifacts.",
            "not_identifiable": "Which model alias or snapshot generated any historical screening row",
            "literature_anchor": "W3C PROV; scientific-workflow provenance; ML Metadata",
        },
        {
            "lesson": "Representation- and null-aware repeatability",
            "established_principle": "Exact, normalized, semantic, and abstention-aware agreement are distinct constructs.",
            "observed_consequence": (
                f"The design-weighted probability of changing null status was "
                f"{mixed_weighted['weighted_estimate']:.2%} "
                f"({mixed_weighted['cluster_bootstrap_95_lower']:.2%}–"
                f"{mixed_weighted['cluster_bootstrap_95_upper']:.2%}); the realized stratified sample contained "
                f"{mixed['mixed_null']} of 500 such items ({mixed['mixed_null_unweighted_rate']:.2%}). "
                f"For {normalized_cat['raw_exact']['items']} all-non-null categorical items, raw exact "
                f"agreement is {normalized_cat['raw_exact']['weighted_estimate']:.2%} and normalized exact "
                f"agreement is {normalized_cat['normalized_exact']['weighted_estimate']:.2%}."
            ),
            "quantified_effect": (
                f"{100 * (normalized_cat['normalized_exact']['weighted_estimate'] - normalized_cat['raw_exact']['weighted_estimate']):.2f} "
                "percentage-point normalization effect for categorical items"
            ),
            "identifiable_claim": "Null states were largely but not perfectly stable, while categorical agreement depended materially on representation.",
            "not_identifiable": "Semantic equivalence or factual correctness",
            "literature_anchor": "Kamalloo et al. 2023; Wen et al. 2025",
        },
        {
            "lesson": "Downstream-requirements-first schema design",
            "established_principle": "Schema conformance is necessary but fitness for a specific analysis requires task-specific fields and rules.",
            "observed_consequence": (
                f"{estimate_ci_cases} of 20 schemas contain estimate and interval fields, yielding "
                f"{complete_estimate_ci_rows:,} complete numeric rows, and {numeric_five_cases} cases pass "
                "a five-row numeric threshold. Yet 0 of 20 schemas contain a study-level linkage identifier, "
                "a dedicated effect-measure label, a variance/standard-error field, or a dependence identifier. "
                "Only 1 of 20 has an effect-specific estimate column, and only 2 of 20 contain an analysis time-point field."
            ),
            "quantified_effect": "Zero cases establish an analysis-ready common estimand and independent-study set",
            "identifiable_claim": "Numeric completeness does not establish downstream synthesis readiness.",
            "not_identifiable": "A valid pooled effect or calibrated propagation result",
            "literature_anchor": "Wang and Strong 1996; SHACL; PRESERVE 2024",
        },
    ]
    priority = {
        "Denominator-explicit reporting": 1,
        "Representation- and null-aware repeatability": 2,
        "Downstream-requirements-first schema design": 3,
        "Versioned relational provenance": 4,
        "Typed operational failure states": 5,
    }
    matrix_rows.sort(key=lambda row: priority[row["lesson"]])
    write_csv(root / args.matrix_output, matrix_rows)

    report_lines = [
        "# Quantified Claim–Consequence Matrix",
        "",
        "## Positioning rule",
        "",
        "The five control principles are established in provenance, MLOps, observability, data-contract, "
        "and LLM-evaluation literature. The manuscript's contribution is not to invent those controls. "
        "It is to quantify what became unobservable, unreconstructable, or measurement-sensitive when "
        "the historical workflow did not retain them. W3C PROV and ML Metadata already formalize "
        "linked entities, activities, agents, artifacts, and executions.[1] [2] OpenTelemetry and "
        "site-reliability guidance already make errors and retries part of the execution trace.[3] [4] "
        "Fitness-for-use and declarative schema constraints are established data-quality concepts.[5] [6] [7] "
        "LLM evaluation work already distinguishes exact matching, semantic assessment, and abstention-aware "
        "coverage.[8] [9]",
        "",
        "| Lesson | Concrete consequence in these data | Defensible claim | Not identifiable |",
        "|---|---|---|---|",
    ]
    for row in matrix_rows:
        report_lines.append(
            f"| {row['lesson']} | {row['observed_consequence']} {row['quantified_effect']}. | "
            f"{row['identifiable_claim']} | {row['not_identifiable']} |"
        )
    report_lines.extend(
        [
            "",
            "## Historical schema coverage",
            "",
            "| Requirement | Cases with field | Consequence |",
            "|---|---:|---|",
        ]
    )
    for row in schema_rows:
        report_lines.append(
            f"| {row['requirement']} | {row['cases_with_required_field']}/20 | "
            f"{row['observed_consequence']} |"
        )
    report_lines.extend(
        [
            "",
            "## Novelty boundary",
            "",
            "The paper should claim a bounded empirical audit of consequences, not a new general-purpose "
            "provenance framework, observability standard, data contract, or agreement metric. The 20 "
            "cases are purposive and the prospective repeatability results are specific to `gpt-5-mini`, "
            "the frozen inputs, prompts, schemas, and execution period.",
            "",
            "## References",
            "",
            "[1]: https://www.w3.org/TR/prov-dm/ \"PROV-DM: The PROV Data Model\"",
            "",
            "[2]: https://www.tensorflow.org/tfx/guide/mlmd \"ML Metadata\"",
            "",
            "[3]: https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-spans.md \"OpenTelemetry GenAI Semantic Conventions: Generative AI Client Spans\"",
            "",
            "[4]: https://sre.google/sre-book/monitoring-distributed-systems/ \"Monitoring Distributed Systems\"",
            "",
            "[5]: https://doi.org/10.1080/07421222.1996.11518099 \"Beyond Accuracy: What Data Quality Means to Data Consumers\"",
            "",
            "[6]: https://www.w3.org/TR/shacl/ \"Shapes Constraint Language\"",
            "",
            "[7]: https://doi.org/10.1371/journal.pdig.0000527 \"Systematic Data Quality Assessment of Electronic Health Record Data to Evaluate Study-Specific Fitness\"",
            "",
            "[8]: https://aclanthology.org/2023.acl-long.307/ \"Evaluating Open-Domain Question Answering in the Era of Large Language Models\"",
            "",
            "[9]: https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00754/131566/Know-Your-Limits-A-Survey-of-Abstention-in-Large \"Know Your Limits: A Survey of Abstention in Large Language Models\"",
        ]
    )
    report_path = root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
