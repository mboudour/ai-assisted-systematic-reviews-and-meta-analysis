#!/usr/bin/env python3
"""Build the frozen Step 3 study configuration from preserved historical sources."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0.0"
FREEZE_DATE = "2026-09-19"
SOURCE_COMMIT = "0a74f80eb30113aad2ebad024541920d2f8558a4"
MASTER_SEED = 20260919

DOMAIN_BY_CASE = {
    **{case_id: "Health and Clinical" for case_id in range(1, 5)},
    **{case_id: "Social and Behavioral" for case_id in range(5, 9)},
    **{case_id: "Education and Learning" for case_id in range(9, 13)},
    **{case_id: "Environmental" for case_id in range(13, 17)},
    **{case_id: "Computer Science and AI" for case_id in range(17, 21)},
}

SYNTHESIS_CRITICAL_NAMES = {
    "sample_size",
    "effect_size",
    "hazard_ratio",
    "ci_lower",
    "ci_upper",
    "sensitivity",
    "specificity",
    "auc",
    "recidivism_rate_treatment",
    "recidivism_rate_control",
    "gap_percent",
    "class_size_treatment",
    "class_size_control",
    "carbon_stock_tC_ha",
    "concentration_items_L",
    "accuracy_percent",
    "f1_score",
}

FAILURE_STATES = [
    "ok",
    "api_error",
    "timeout",
    "rate_limited",
    "invalid_response",
    "parse_error",
    "cancelled",
]

SOURCE_STATES = [
    "reported_explicitly",
    "derivable_from_source",
    "not_reported",
    "ambiguous_source",
    "source_unavailable",
    "not_applicable",
]

HUMAN_RESOLUTION_STATES = [
    "resolved",
    "human_unresolved",
]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DictCallToLiteral(ast.NodeTransformer):
    """Convert declarative dict(key=value) calls into literal AST dictionaries."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.func, ast.Name) or node.func.id != "dict" or node.args:
            raise ValueError("Only keyword-only dict(...) calls are allowed in frozen assignments")
        if any(keyword.arg is None for keyword in node.keywords):
            raise ValueError("Dictionary unpacking is not allowed in frozen assignments")
        return ast.copy_location(
            ast.Dict(
                keys=[ast.Constant(keyword.arg) for keyword in node.keywords],
                values=[keyword.value for keyword in node.keywords],
            ),
            node,
        )


def safe_literal(value_node: ast.AST) -> Any:
    transformed = DictCallToLiteral().visit(value_node)
    ast.fix_missing_locations(transformed)
    return ast.literal_eval(transformed)


def literal_assignments(path: Path, names: set[str]) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            value_node = node.value
        else:
            targets = [node.target.id] if isinstance(node.target, ast.Name) else []
            value_node = node.value
        for target in targets:
            if target in names and value_node is not None:
                values[target] = safe_literal(value_node)
    missing = sorted(names - values.keys())
    if missing:
        raise ValueError(f"Missing assignments in {path}: {missing}")
    return values


def read_case_manifest(path: Path) -> dict[int, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {int(row["case_id"]): row for row in csv.DictReader(handle)}


def field_role(name: str, declared_type: str) -> str:
    if name in SYNTHESIS_CRITICAL_NAMES:
        return "potentially_synthesis_critical"
    if declared_type == "num":
        return "other_numeric"
    return "categorical"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_cases(
    retrieval_values: dict[str, Any],
    screening_values: dict[str, Any],
    extraction_values: dict[str, Any],
    case_manifest: dict[int, dict[str, str]],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    inclusion = {int(key): value for key, value in screening_values["INCLUSION_CRITERIA"].items()}
    schemas = {int(key): value for key, value in extraction_values["SCHEMAS"].items()}
    cases: list[dict[str, Any]] = []
    for historical_case in retrieval_values["CASES"]:
        case_id = int(historical_case["id"])
        manifest = case_manifest[case_id]
        source = historical_case["db"]
        query_semantics = (
            "free_text_keywords" if source == "semanticscholar" else "source_specific_query"
        )
        fields = [
            {
                "name": name,
                "declared_type": "numeric" if declared_type == "num" else "categorical",
                "audit_class": field_role(name, declared_type),
            }
            for name, declared_type in schemas[case_id].items()
        ]
        cases.append(
            {
                "case_id": case_id,
                "slug": historical_case["slug"],
                "domain_assignment": DOMAIN_BY_CASE[case_id],
                "selection_design": "purposive_test_case",
                "historical_retrieval": {
                    "source": source,
                    "query": historical_case["query"],
                    "query_semantics": query_semantics,
                    "configured_max_records": historical_case["max_records"],
                    "pre_dedup_row_count": None,
                    "post_dedup_row_count": int(manifest["raw_rows"]),
                    "source_reported_total_hits": None,
                    "truncation_status": "not_yet_audited",
                },
                "historical_screening": {
                    "inclusion_criteria": inclusion[case_id],
                    "screened_rows": int(manifest["screened_rows"]),
                    "include_rows": int(manifest["included_rows"]),
                    "actual_model_snapshot": None,
                    "actual_prompt_version": None,
                    "failure_log_available": False,
                },
                "historical_extraction": {
                    "fields": fields,
                    "extracted_rows": int(manifest["extracted_rows"]),
                    "coverage_status": manifest["lineage_status"],
                    "actual_model_snapshot": None,
                    "actual_prompt_version": None,
                    "failure_log_available": False,
                },
                "meta_analysis_eligibility": {
                    "status": "not_assessed",
                    "common_estimand": None,
                    "independent_study_count": None,
                    "decision_reason": None,
                },
            }
        )
    return {
        "registry_version": PROTOCOL_VERSION,
        "freeze_date": FREEZE_DATE,
        "historical_source_commit": SOURCE_COMMIT,
        "historical_source_hashes": source_hashes,
        "interpretation": (
            "Queries, criteria, schemas, and model aliases below are declarations in the tracked "
            "historical scripts. They are not proof that every archived row was generated with "
            "those exact script versions or model snapshots."
        ),
        "cases": cases,
    }


def build_prompts(
    screening_values: dict[str, Any],
    extraction_values: dict[str, Any],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    return {
        "register_version": PROTOCOL_VERSION,
        "freeze_date": FREEZE_DATE,
        "historical_source_commit": SOURCE_COMMIT,
        "historical_source_hashes": source_hashes,
        "provenance_status": "conflicting_screening_documentation_and_no_per_call_verification",
        "screening": {
            "historical_execution_model_alias": None,
            "model_identity_status": "unresolved",
            "script_declared_model_alias": screening_values["SCREENING_MODEL"],
            "repository_readme_reported_model_alias": "gpt-4o-mini",
            "manuscript_reported_model_alias": "gpt-4o",
            "conflict_evidence": {
                "script": "previous/empirical_evaluation/scripts/02_screening.py line 76",
                "script_sha256": source_hashes[
                    "previous/empirical_evaluation/scripts/02_screening.py"
                ],
                "repository_readme": "previous/empirical_evaluation/README.md line 10",
                "repository_readme_sha256": "8f26d22bb10433fc5c582675af8f824f449c91e92d0767c27d61d695381a3643",
                "manuscript": "uploaded main.pdf Section 4.5.1",
                "manuscript_sha256": "1d40f48c92885d68b4813d34494d187d8a778b8f4df1a0215731f72d14b0ca80",
            },
            "actual_model_snapshot": None,
            "temperature": 0,
            "system_prompt": screening_values["SYSTEM_PROMPT"],
            "response_contract": "free text parsed as INCLUDE when substring INCLUDE is present; otherwise EXCLUDE",
            "known_failure_behavior": "final API failure converted to EXCLUDE without a failure flag",
        },
        "extraction": {
            "declared_model_alias": extraction_values["MODEL"],
            "actual_model_snapshot": None,
            "temperature": 0,
            "system_prompt": extraction_values["EXTRACTOR_SYSTEM"],
            "response_contract": "JSON object; requested keys; values numeric/string/null",
            "known_failure_behavior": "final API failure converted to all-null extraction",
        },
        "evaluator": {
            "declared_model_alias": extraction_values["MODEL"],
            "actual_model_snapshot": None,
            "temperature": 0,
            "system_prompt": extraction_values["JUDGE_SYSTEM"],
            "response_contract": "JSON object with CORRECT, INCORRECT, or UNVERIFIABLE per field",
            "known_failure_behavior": "final API failure converted to UNVERIFIABLE for every field",
        },
    }


def build_protocol(snapshot_hash: str, model_catalog_hash: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "frozen_before_new_primary_computations",
        "freeze_date": FREEZE_DATE,
        "target_venue": "ACM Journal of Data and Information Quality (JDIQ)",
        "working_title": "Data Quality and Error Propagation in LLM-Assisted Evidence Synthesis",
        "design": {
            "type": "retrospective_validation_plus_prospective_audit_and_simulation",
            "case_selection": "20 purposively selected test cases across five assigned domains",
            "generalization_limit": (
                "Cases do not constitute a probability sample of disciplines, systematic reviews, "
                "or bibliographic corpora. Domain comparisons are descriptive."
            ),
            "historical_snapshot_sha256": snapshot_hash,
            "historical_reference_status": "model_generated_outputs_not_ground_truth",
            "primary_reference_standard": "human_adjudication",
        },
        "research_questions": [
            {
                "id": "RQ1",
                "question": (
                    "What completeness, validity, uniqueness, provenance, and technical-reliability "
                    "problems occur across retrieval and corpus construction?"
                ),
            },
            {
                "id": "RQ2",
                "question": (
                    "How valid are archived LLM screening decisions and structured extractions "
                    "against a human-adjudicated reference?"
                ),
            },
            {
                "id": "RQ3",
                "question": (
                    "How well does an LLM evaluator identify correct, incorrect, and source-"
                    "unassessable extracted fields, including controlled injected errors?"
                ),
            },
            {
                "id": "RQ4",
                "question": (
                    "How do observed and calibrated screening, extraction, and technical failures "
                    "change eligible meta-analyses and their conclusions?"
                ),
            },
        ],
        "units_of_analysis": {
            "case": "one purposively selected topic and retrieval configuration",
            "record": "one retained bibliographic report record",
            "field": "one requested structured value for one record",
            "study": "one underlying independent study after report linkage",
            "estimate": "one harmonized effect estimate for a defined estimand",
            "call": "one attempted model API operation, including failed attempts",
        },
        "data_quality_dimensions": [
            {
                "name": "completeness",
                "operationalization": "presence of required metadata, source text, and synthesis fields",
            },
            {
                "name": "accuracy",
                "operationalization": "agreement with adjudicated human reference data",
            },
            {
                "name": "validity_and_conformance",
                "operationalization": "type, range, unit, logical ordering, and schema checks",
            },
            {
                "name": "consistency",
                "operationalization": "agreement among linked values such as estimate and interval",
            },
            {
                "name": "uniqueness",
                "operationalization": "report deduplication and underlying-study linkage accuracy",
            },
            {
                "name": "provenance",
                "operationalization": "traceability to source record, text, prompt, model, call, and code version",
            },
            {
                "name": "technical_reliability",
                "operationalization": "successful completion without API, parsing, or schema failure",
            },
            {
                "name": "source_adequacy",
                "operationalization": "whether the supplied title/abstract supports field verification",
            },
        ],
        "primary_estimands": [
            {
                "id": "P1_screening_sensitivity",
                "unit": "record",
                "target": "design-weighted probability that an adjudicated relevant record was labeled INCLUDE",
                "numerator": "weighted true-positive records",
                "denominator": "weighted adjudicated relevant records",
                "reference": "adjudicated human screening label",
            },
            {
                "id": "P2_extraction_error_rate",
                "unit": "field",
                "target": "design-weighted probability that a source-assessable extracted field is incorrect",
                "numerator": "weighted human-labeled incorrect fields",
                "denominator": "weighted source-assessable extracted fields",
                "reference": "adjudicated same-source human field label",
            },
            {
                "id": "P3_evaluator_sensitivity",
                "unit": "field",
                "target": "probability that the evaluator identifies a human-confirmed incorrect field",
                "numerator": "human-confirmed incorrect fields labeled INCORRECT by evaluator",
                "denominator": "human-confirmed incorrect fields with completed evaluator calls",
                "reference": "adjudicated same-source human field label",
            },
            {
                "id": "P4_evaluator_specificity",
                "unit": "field",
                "target": "probability that the evaluator accepts a human-confirmed correct field",
                "numerator": "human-confirmed correct fields labeled CORRECT by evaluator",
                "denominator": "human-confirmed correct fields with completed evaluator calls",
                "reference": "adjudicated same-source human field label",
            },
            {
                "id": "P5_observed_propagation_shift",
                "unit": "eligible_meta_analysis",
                "target": "difference between pooled effects from matched LLM and human-adjudicated datasets",
                "numerator": "pooled effect on analysis scale from LLM data minus human-reference pooled effect",
                "denominator": "not_applicable",
                "reference": "human-adjudicated synthesis dataset",
            },
            {
                "id": "P6_simulated_conclusion_change",
                "unit": "monte_carlo_draw",
                "target": "probability that calibrated pipeline errors change a prespecified conclusion",
                "numerator": "draws with a changed statistical or substantive conclusion",
                "denominator": "all valid simulation draws",
                "reference": "human-adjudicated synthesis result",
            },
        ],
        "required_companion_rates": [
            {
                "id": "technical_failure_rate",
                "denominator": "all attempted calls",
                "rule": "Report each failure state separately and combined; never impute an analytical value.",
            },
            {
                "id": "unverifiability_rate",
                "denominator": "all completed evaluator field judgments",
                "rule": "Do not exclude UNVERIFIABLE from its own denominator or merge it with failures.",
            },
            {
                "id": "source_inadequacy_rate",
                "denominator": "all human-reviewed fields",
                "rule": "Report not reported, ambiguous, unavailable, and not applicable separately.",
            },
        ],
        "secondary_estimands": [
            "screening specificity, precision, negative predictive value, balanced accuracy, and F1",
            "field accuracy by case, field name, field class, null status, and source adequacy",
            "raw human agreement, Cohen kappa, and Gwet AC1 before adjudication",
            "evaluator predictive values and abstention rate",
            "repeat-run stability and transition probabilities",
            "retrieval completeness, metadata conformance, and deduplication error rates",
            "confidence-interval width, prediction interval, tau-squared, I-squared, and weight shifts",
        ],
        "human_reference_sampling": {
            "screening": {
                "sampling_frame": "all 94,522 archived screened records",
                "strata": ["case_id", "historical_llm_decision"],
                "initial_draw_per_nonempty_stratum": 30,
                "sample_all_if_stratum_smaller_than": 30,
                "expected_initial_records": 1192,
                "sampling": "without replacement using stable record identities",
                "analysis": "retain inverse inclusion probabilities for design-weighted estimates",
            },
            "extraction": {
                "sampling_frame": "all archived record-field pairs",
                "population_fields": 90554,
                "strata": [
                    "case_id",
                    "field_audit_class",
                    "extracted_null_status",
                    "historical_evaluator_verdict",
                ],
                "initial_draw_per_nonempty_stratum": 10,
                "sample_all_if_stratum_smaller_than": 10,
                "expected_initial_fields": 1504,
                "sampling": "without replacement using stable record-field identities",
                "analysis": "retain inverse inclusion probabilities and cluster by record",
            },
            "annotators": {
                "count": 2,
                "independent_before_adjudication": True,
                "blind_to_model_outputs_where_task_allows": True,
                "adjudication": "consensus or third reviewer; unresolved remains a reported state",
            },
            "adaptive_precision_rule": {
                "pooled_primary_half_width_target": 0.05,
                "reported_case_level_half_width_target": 0.10,
                "interval_level": 0.95,
                "restriction": "increase sample size by frozen strata only; do not stop based on favorable results",
            },
        },
        "uncertainty_methods": {
            "unweighted_proportions": "Wilson 95% confidence interval",
            "weighted_validation_estimands": (
                "10,000-replicate stratified cluster bootstrap respecting sampling strata and record clustering"
            ),
            "case_aggregation": [
                "macro average across cases",
                "record- or field-weighted micro estimate",
            ],
            "domain_aggregation": "descriptive only; no population-level domain claim",
            "exploratory_multiple_testing": "Benjamini-Hochberg correction within each declared family",
        },
        "status_vocabularies": {
            "call_status": FAILURE_STATES,
            "source_status": SOURCE_STATES,
            "human_resolution_status": HUMAN_RESOLUTION_STATES,
            "screening_label": ["include", "exclude", "uncertain"],
            "human_field_label": ["correct", "incorrect", "not_assessable"],
            "evaluator_verdict": ["CORRECT", "INCORRECT", "UNVERIFIABLE"],
        },
        "prospective_model_roles": {
            "catalog_checked_on": FREEZE_DATE,
            "catalog_snapshot_file": "config/model_catalog_snapshot.json",
            "catalog_snapshot_sha256": model_catalog_hash,
            "available_models_observed": [
                "gpt-5",
                "gpt-5-mini",
                "gpt-5-nano",
                "gpt-5.5",
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
            ],
            "primary_generator_and_dependent_evaluator": {
                "model_id": "gpt-5-mini",
                "reasoning": "disabled_for_classification_and_structured_extraction",
                "response_format": "strict_json_schema",
                "temperature": 0,
            },
            "independent_evaluator_robustness_check": {
                "model_id": "gemini-3.1-pro-preview",
                "reasoning": "provider_default",
                "response_format": "strict_json_schema",
                "temperature": 0,
            },
            "human_reference_priority": (
                "Model comparisons are secondary; no model output replaces human adjudication."
            ),
            "runtime_logging": [
                "requested_model_id",
                "returned_model_id",
                "system_fingerprint_if_available",
                "request_id",
                "prompt_hash",
                "schema_hash",
                "attempt_number",
                "timestamps",
                "latency",
                "usage",
                "raw_response",
                "call_status",
            ],
        },
        "evaluator_error_injection": {
            "eligible_inputs": "human-verified source-field pairs",
            "allocation": "blocked random assignment to unchanged control or one injected error",
            "blinding": "evaluator is not told assignment or error type",
            "initial_per_error_type": 30,
            "control_ratio": 1.0,
            "error_types": [
                "small_numeric_error",
                "large_numeric_error",
                "decimal_or_scale_error",
                "unit_error",
                "sign_or_direction_reversal",
                "swapped_confidence_bounds",
                "estimate_interval_inconsistency",
                "wrong_effect_measure_label",
                "wrong_outcome_comparator_subgroup_or_timepoint",
                "false_null_or_false_nonnull",
                "wrong_categorical_value",
            ],
            "primary_outcome": "detection as INCORRECT",
            "companion_outcome": "false-alarm rate on unchanged controls",
            "precision_rule": "increase within frozen blocks until reported 95% half-width is at most 0.10",
        },
        "repeatability": {
            "screening_records_initial": 200,
            "extraction_fields_initial": 500,
            "independent_repeats": 3,
            "seed_note": "Model-side nondeterminism is measured; local sampling remains seeded.",
        },
        "meta_analysis_eligibility": {
            "required": [
                "a prespecified common estimand or a defensible conversion to one",
                "at least five independent studies for any synthesis",
                "at least ten independent studies for a primary propagation analysis",
                "human verification of synthesis-critical values",
                "documented handling of multiple reports, outcomes, subgroups, and time points",
            ],
            "primary_estimate_selection": "one prespecified estimate per independent study",
            "dependent_estimates": "use multilevel or cluster-robust analysis as a secondary model",
            "exclusion_rule": "do not pool incompatible effect measures merely because they share a column",
        },
        "meta_analysis_models": {
            "primary": "REML random effects with Hartung-Knapp inference",
            "comparators": [
                "fixed-effect inverse variance",
                "DerSimonian-Laird random effects",
            ],
            "prediction_interval": "report for random-effects models when mathematically estimable",
            "heterogeneity": ["tau_squared", "I_squared", "Q"],
            "conclusion_rules": [
                "whether the confidence interval crosses the null",
                "whether a case-specific substantive threshold is crossed",
            ],
            "threshold_timing": "freeze each substantive threshold before comparing LLM and human results",
        },
        "propagation_analyses": {
            "observed_order": [
                "human-adjudicated synthesis dataset",
                "matched original LLM-extracted dataset",
                "extraction-corrected dataset",
                "screening-restored dataset where validation supports it",
                "combined corrected dataset",
                "failure-aware lower and upper bounds",
            ],
            "monte_carlo_mechanisms": [
                "screening omission",
                "numeric extraction corruption",
                "wrong unit or scale",
                "confidence-bound corruption",
                "wrong outcome or comparator selection",
                "technical failure",
                "joint pipeline error",
            ],
            "rate_uncertainty": "bootstrap or hierarchical draws from observed validation data",
            "minimum_draws_per_primary_scenario": 10000,
            "monte_carlo_standard_error_target": 0.0025,
        },
        "randomness": {
            "master_seed": MASTER_SEED,
            "generator": "NumPy PCG64DXSM",
            "stream_derivation": "SHA-256 of protocol version, task namespace, case, and replicate",
            "rule": "record every derived seed and never use one mutable global stream across analyses",
        },
        "analysis_invariants": [
            "Archived historical files are immutable.",
            "No technical failure is converted to an analytical label or null value.",
            "No same-model verdict is described as accuracy without human reference.",
            "UNVERIFIABLE is reported with its own denominator.",
            "No placeholder or random analytical result is generated when inputs are absent.",
            "No meta-analysis proceeds before common estimand and study independence checks.",
            "Case and domain summaries disclose weighting and remain descriptive for purposive cases.",
        ],
        "amendment_policy": {
            "allowed": True,
            "requirements": [
                "append-only amendment record",
                "timestamp and author",
                "reason and affected protocol fields",
                "classification as before or after viewing relevant outcome",
                "new semantic protocol version",
            ],
            "prohibited": "silent editing of frozen decisions",
        },
    }


def markdown_report(protocol: dict[str, Any], cases_registry: dict[str, Any]) -> str:
    dimensions = protocol["data_quality_dimensions"]
    estimands = protocol["primary_estimands"]
    case_rows = cases_registry["cases"]
    partial_cases = [
        str(case["case_id"])
        for case in case_rows
        if case["historical_extraction"]["coverage_status"] == "partial_extraction_coverage"
    ]
    lines = [
        "# Step 3 Frozen Study Protocol",
        "",
        f"**Protocol version:** {protocol['protocol_version']}",
        "",
        f"**Freeze date:** {protocol['freeze_date']}",
        "",
        f"**Status:** `{protocol['status']}`",
        "",
        "## Study design",
        "",
        "The study is a retrospective validation of archived pipeline outputs combined with a "
        "prospective audit, controlled error-injection experiment, and calibrated propagation "
        "simulation. The 20 cases are purposive test cases. They do not support population-level "
        "claims about disciplines. The target venue is ACM JDIQ, and manuscript preparation will "
        "follow its current author guidance.[1]",
        "",
        "Archived model outputs are observations, not ground truth. Human adjudication is the "
        "primary reference standard. New model calls will be labeled as prospective 2026 audit "
        "runs and will not be attributed retroactively to the historical execution.",
        "",
        "## Data-quality dimensions",
        "",
        "| Dimension | Operational meaning |",
        "|---|---|",
    ]
    lines.extend(
        f"| {item['name'].replace('_', ' ').title()} | {item['operationalization']} |"
        for item in dimensions
    )
    lines.extend(
        [
            "",
            "No arbitrary composite data-quality score will be calculated. Dimensions will be "
            "reported separately so that a high value in one dimension cannot mask a defect in another.",
            "",
            "## Primary estimands",
            "",
            "| ID | Unit | Target | Reference |",
            "|---|---|---|---|",
        ]
    )
    lines.extend(
        f"| {item['id']} | {item['unit']} | {item['target']} | {item['reference']} |"
        for item in estimands
    )
    lines.extend(
        [
            "",
            "Technical failure, evaluator unverifiability, and source inadequacy are required "
            "companion rates. None may be removed from reporting by conditional-denominator choices.",
            "",
            "## Human reference sample",
            "",
            "For screening, the initial stratified sample contains up to 30 historical INCLUDE "
            "and 30 historical EXCLUDE records per case. Case 1 contributes all 22 INCLUDE records, "
            "giving an expected initial total of 1,192 records. Sampling probabilities will be "
            "retained for design-weighted estimation.",
            "",
            "For extraction, sampling occurs within case, field audit class, extracted-null status, "
            "and historical evaluator verdict. Up to 10 fields are drawn from every nonempty stratum. "
            "This gives an initial sample of 1,504 fields from 90,554 archived record-field pairs. "
            "Two reviewers independently label all sampled items before adjudication. Sample sizes "
            "may increase only under the frozen confidence-interval precision rule.",
            "",
            "## Model roles for prospective audits",
            "",
            "The primary prospective generator and same-lineage evaluator use `gpt-5-mini` with "
            "strict JSON schemas. An independent-evaluator robustness check uses "
            "`gemini-3.1-pro-preview`. Human adjudication remains primary. Every call must retain "
            "the requested and returned model IDs, prompt and schema hashes, request identifiers, "
            "attempts, timestamps, latency, usage, raw response, and explicit call status.",
            "",
            "## Meta-analysis gate",
            "",
            "A case requires a common estimand, at least five independent studies, human-verified "
            "synthesis-critical values, and documented handling of dependent estimates. A primary "
            "propagation analysis additionally requires at least ten independent studies. The primary "
            "model is REML with Hartung–Knapp inference; fixed-effect and DerSimonian–Laird analyses "
            "are comparators.",
            "",
            "The number of eligible cases is an output of this gate. It is not fixed in advance, and "
            "no additional case will be forced into a meta-analysis merely to increase that number.",
            "",
            "## Historical limitations frozen into the protocol",
            "",
            "The archived files do not establish actual model snapshots, per-record prompt versions, "
            "call dates, retry events, API failures, pre-deduplication rows, or duplicate-pair decisions. "
            "These values remain explicitly unknown.",
            "",
            f"Cases {', '.join(partial_cases)} have partial extraction coverage because their "
            "retained extraction files contain 200 records despite larger INCLUDE sets.",
            "",
            "The query, criterion, schema, and historical prompt registers preserve declarations "
            "from the tracked scripts at the historical source commit. They do not prove that every "
            "archived output was generated by those exact script versions.",
            "",
            "## Amendment policy",
            "",
            "Any change requires an append-only amendment that identifies the reason, affected fields, "
            "timing relative to outcome inspection, and a new semantic protocol version. Silent edits "
            "to frozen decisions are prohibited.",
            "",
            "## Machine-readable files",
            "",
            "- `config/study_protocol.json` contains the complete estimands and decision rules.",
            "- `config/cases.json` contains the 20 case definitions, queries, criteria, and schemas.",
            "- `config/historical_prompts.json` contains prompt declarations from the preserved scripts and records the unresolved screening-model conflict among the script, README, and manuscript.",
            "- `config/amendments.jsonl` is reserved for append-only protocol amendments.",
            "",
            "## References",
            "",
            "[1]: https://dl.acm.org/journal/jdiq/author-guidelines \"ACM Journal of Data and Information Quality Author Guidelines\"",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    previous_scripts = root / "previous" / "empirical_evaluation" / "scripts"
    retrieval_path = previous_scripts / "01_retrieval.py"
    screening_path = previous_scripts / "02_screening.py"
    extraction_path = previous_scripts / "03_extraction.py"
    source_hashes = {
        retrieval_path.relative_to(root).as_posix(): sha256_file(retrieval_path),
        screening_path.relative_to(root).as_posix(): sha256_file(screening_path),
        extraction_path.relative_to(root).as_posix(): sha256_file(extraction_path),
    }
    retrieval_values = literal_assignments(retrieval_path, {"CASES"})
    screening_values = literal_assignments(
        screening_path, {"INCLUSION_CRITERIA", "SCREENING_MODEL", "SYSTEM_PROMPT"}
    )
    extraction_values = literal_assignments(
        extraction_path, {"SCHEMAS", "MODEL", "EXTRACTOR_SYSTEM", "JUDGE_SYSTEM"}
    )
    case_manifest = read_case_manifest(root / "data" / "manifests" / "cases.csv")
    snapshot = json.loads(
        (root / "data" / "manifests" / "snapshot.json").read_text(encoding="utf-8")
    )
    model_catalog_hash = sha256_file(root / "config" / "model_catalog_snapshot.json")

    cases_registry = build_cases(
        retrieval_values,
        screening_values,
        extraction_values,
        case_manifest,
        source_hashes,
    )
    prompt_register = build_prompts(screening_values, extraction_values, source_hashes)
    protocol = build_protocol(snapshot["source_archive_sha256"], model_catalog_hash)

    write_json(root / "config" / "cases.json", cases_registry)
    write_json(root / "config" / "historical_prompts.json", prompt_register)
    write_json(root / "config" / "study_protocol.json", protocol)
    amendments = root / "config" / "amendments.jsonl"
    if not amendments.exists():
        amendments.write_text("", encoding="utf-8")
    report = markdown_report(protocol, cases_registry)
    (root / "docs" / "step03_frozen_protocol.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
