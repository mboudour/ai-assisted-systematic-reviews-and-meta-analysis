#!/usr/bin/env python3
"""Run the deterministic offline research pipeline in dependency order."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def command(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    stages = [
        ("02 inventory", command("scripts/inventory_legacy_data.py", "--snapshot-root", "data/raw_snapshot", "--manifest-dir", "data/manifests", "--previous-outputs", "previous/empirical_evaluation/outputs", "--report", "docs/step02_data_inventory.md")),
        ("03 protocol", command("scripts/build_study_protocol.py", "--root", ".")),
        ("03 burden", command("scripts/estimate_annotation_burden.py", "--root", ".", "--screening-per-stratum", "30", "--extraction-per-stratum", "10", "--output", "data/manifests/annotation_sampling_plan.csv")),
        ("04 corpus", command("scripts/audit_corpus_quality.py", "--root", ".", "--current-counts", "results/tables/current_source_count_audit.csv", "--output", "results/tables/retrieval_corpus_quality.csv", "--report", "docs/step04_retrieval_corpus_quality.md")),
        ("05 dedup", command("scripts/audit_deduplication.py", "--root", ".", "--sample-size", "200", "--output", "results/tables/deduplication_retained_audit.csv", "--sample", "annotations/forms/dedup_retained_pair_sample.csv", "--removed-template", "annotations/forms/dedup_removed_pair_sample.csv", "--report", "docs/step05_deduplication_validation.md")),
        ("06 failures", command("scripts/audit_failure_states.py", "--root", ".", "--output", "results/tables/failure_missingness_audit.csv", "--event-template", "config/pipeline_events_template.csv", "--report", "docs/step06_failure_missingness.md")),
        ("06 verdict cube", command("scripts/build_evaluator_verdict_cube.py", "--root", ".", "--output", "results/tables/evaluator_verdict_cube.csv")),
        ("07 samples", command("scripts/build_human_reference_samples.py", "--root", ".", "--screening-per-stratum", "30", "--extraction-per-stratum", "10")),
        ("08 screening", command("scripts/analyze_screening_validation.py", "--root", ".", "--adjudicated", "annotations/forms/screening_annotation_template.csv", "--output", "results/tables/screening_validation_metrics.csv", "--profile-output", "results/tables/screening_decision_profile.csv", "--report", "docs/step08_screening_validation.md")),
        ("09 extraction", command("scripts/analyze_extraction_evaluator_validation.py", "--root", ".", "--adjudicated", "annotations/forms/extraction_annotation_template.csv", "--output", "results/tables/extraction_validation_metrics.csv", "--profile-output", "results/tables/extraction_evaluator_profile.csv", "--report", "docs/step09_extraction_evaluator_validation.md")),
        ("10 injection analysis", command("scripts/analyze_error_injection.py", "--input", "results/tables/error_injection_calls.csv", "--output", "results/tables/error_injection_metrics.csv", "--report", "docs/step10_error_injection.md")),
        ("11 repeatability analysis", command("scripts/analyze_repeatability.py", "--input", "results/tables/repeatability_calls.csv", "--summary", "results/tables/repeatability_summary.csv", "--items", "results/tables/repeatability_items.csv", "--transitions", "results/tables/screening_repeatability_transitions.csv", "--report", "docs/step11_repeatability.md", "--manifest", "data/manifests/extraction_sample_manifest.csv")),
        ("11 screening repeatability", command("scripts/analyze_screening_repeatability.py", "--root", ".")),
        ("11 repeatability sensitivity", command("scripts/analyze_repeatability_normalized.py")),
        ("12 input audit", command("scripts/audit_meta_analysis_inputs.py", "--root", ".", "--output", "results/tables/meta_analysis_input_audit.csv")),
        ("12 candidates", command("scripts/build_meta_analysis_candidates.py", "--root", ".", "--audit", "results/tables/meta_analysis_input_audit.csv", "--output", "results/tables/meta_analysis_candidates_unverified.csv", "--review-packet", "data/interim/meta_analysis_candidate_review.csv")),
        ("12 eligibility", command("scripts/summarize_meta_analysis_eligibility.py", "--assessments", "results/tables/meta_analysis_case_assessments.json", "--input-audit", "results/tables/meta_analysis_input_audit.csv", "--output", "results/tables/meta_analysis_eligibility.csv", "--report", "docs/step12_meta_analysis_eligibility.md")),
        ("13 meta-analysis", command("scripts/run_meta_analyses.py", "--eligibility", "results/tables/meta_analysis_eligibility.csv", "--data", "results/tables/meta_analysis_candidates_unverified.csv", "--summary", "results/tables/meta_analysis_results.csv", "--weights", "results/tables/meta_analysis_weights.csv", "--report", "docs/step13_meta_analysis_models.md")),
        ("14 propagation", command("scripts/run_error_propagation.py", "--error-model", "config/error_model.pending.json", "--verified-data", "results/tables/meta_analysis_candidates_unverified.csv", "--output", "results/tables/error_propagation_results.csv", "--report", "docs/step14_error_propagation.md", "--draws", "10000", "--master-seed", "20260919")),
        ("15 ablations", command("scripts/build_sensitivity_ablations.py", "--root", ".", "--output", "results/tables/sensitivity_ablations.csv", "--report", "docs/step15_sensitivity_ablations.md")),
        ("15 denominator figure", command("scripts/build_denominator_figure.py", "--root", ".", "--png", "results/figures/denominator_ledger.png", "--pdf", "results/figures/denominator_ledger.pdf")),
        ("15 claim consequences", command("scripts/build_claim_consequence_matrix.py", "--root", ".", "--matrix-output", "results/tables/claim_consequence_matrix.csv", "--schema-output", "results/tables/schema_requirement_coverage.csv", "--report", "docs/claim_consequence_matrix.md")),
    ]
    for label, cmd in stages:
        print(f"[{label}] {' '.join(cmd)}", flush=True)
        if not args.dry_run:
            subprocess.run(cmd, cwd=root, check=True)
    environment_cmd = command(
        "scripts/build_environment_manifest.py",
        "--root",
        ".",
        "--output",
        "results/environment.json",
    )
    print(f"[16 environment] {' '.join(environment_cmd)}", flush=True)
    if not args.dry_run:
        subprocess.run(environment_cmd, cwd=root, check=True)
    manifest_cmd = command("scripts/build_artifact_manifest.py", "--root", ".", "--output", "results/artifact_manifest.json")
    print(f"[16 manifest] {' '.join(manifest_cmd)}", flush=True)
    if not args.dry_run:
        subprocess.run(manifest_cmd, cwd=root, check=True)
    if not args.skip_tests:
        test_cmd = [sys.executable, "-m", "pytest", "-q"]
        print(f"[tests] {' '.join(test_cmd)}", flush=True)
        if not args.dry_run:
            subprocess.run(test_cmd, cwd=root, check=True)


if __name__ == "__main__":
    main()
