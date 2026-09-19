from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_protocol_has_six_unique_primary_estimands() -> None:
    protocol = load_json("config/study_protocol.json")
    estimand_ids = [item["id"] for item in protocol["primary_estimands"]]
    assert estimand_ids == [
        "P1_screening_sensitivity",
        "P2_extraction_error_rate",
        "P3_evaluator_sensitivity",
        "P4_evaluator_specificity",
        "P5_observed_propagation_shift",
        "P6_simulated_conclusion_change",
    ]
    assert len(estimand_ids) == len(set(estimand_ids))


def test_protocol_separates_failures_source_status_and_human_resolution() -> None:
    protocol = load_json("config/study_protocol.json")
    vocabularies = protocol["status_vocabularies"]
    assert "api_error" in vocabularies["call_status"]
    assert "not_reported" in vocabularies["source_status"]
    assert "human_unresolved" in vocabularies["human_resolution_status"]
    assert set(vocabularies["evaluator_verdict"]) == {
        "CORRECT",
        "INCORRECT",
        "UNVERIFIABLE",
    }


def test_human_sampling_burden_is_frozen() -> None:
    protocol = load_json("config/study_protocol.json")
    sampling = protocol["human_reference_sampling"]
    assert sampling["screening"]["expected_initial_records"] == 1_192
    assert sampling["extraction"]["population_fields"] == 90_554
    assert sampling["extraction"]["expected_initial_fields"] == 1_504


def test_case_registry_contains_all_cases_and_preserves_unknown_provenance() -> None:
    registry = load_json("config/cases.json")
    cases = registry["cases"]
    assert [case["case_id"] for case in cases] == list(range(1, 21))
    assert all(case["historical_screening"]["actual_model_snapshot"] is None for case in cases)
    assert all(case["historical_extraction"]["actual_prompt_version"] is None for case in cases)
    assert all(case["meta_analysis_eligibility"]["status"] == "not_assessed" for case in cases)


def test_historical_source_hashes_match_preserved_scripts() -> None:
    registry = load_json("config/cases.json")
    for relative_path, expected_hash in registry["historical_source_hashes"].items():
        assert sha256_file(ROOT / relative_path) == expected_hash


def test_historical_prompt_register_does_not_invent_model_snapshots() -> None:
    prompts = load_json("config/historical_prompts.json")
    assert prompts["provenance_status"] == (
        "conflicting_screening_documentation_and_no_per_call_verification"
    )
    assert prompts["screening"]["historical_execution_model_alias"] is None
    assert prompts["screening"]["model_identity_status"] == "unresolved"
    assert prompts["screening"]["script_declared_model_alias"] == "gpt-4.1-mini"
    assert prompts["screening"]["repository_readme_reported_model_alias"] == "gpt-4o-mini"
    assert prompts["screening"]["manuscript_reported_model_alias"] == "gpt-4o"
    evidence = prompts["screening"]["conflict_evidence"]
    assert sha256_file(ROOT / "previous/empirical_evaluation/scripts/02_screening.py") == evidence[
        "script_sha256"
    ]
    assert sha256_file(ROOT / "previous/empirical_evaluation/README.md") == evidence[
        "repository_readme_sha256"
    ]
    assert prompts["screening"]["actual_model_snapshot"] is None
    assert prompts["extraction"]["actual_model_snapshot"] is None
    assert prompts["evaluator"]["actual_model_snapshot"] is None


def test_prospective_model_choices_are_in_the_frozen_catalog() -> None:
    protocol = load_json("config/study_protocol.json")
    catalog = load_json("config/model_catalog_snapshot.json")
    roles = protocol["prospective_model_roles"]
    catalog_path = ROOT / roles["catalog_snapshot_file"]
    assert sha256_file(catalog_path) == roles["catalog_snapshot_sha256"]
    model_ids = {model["id"] for model in catalog["models"]}
    assert roles["primary_generator_and_dependent_evaluator"]["model_id"] in model_ids
    assert roles["independent_evaluator_robustness_check"]["model_id"] in model_ids


def test_scope_and_model_identity_amendments_are_explicit() -> None:
    lines = [
        line
        for line in (ROOT / "config/amendments.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(lines) == 2
    amendments = [json.loads(line) for line in lines]
    assert [item["amendment_id"] for item in amendments] == [
        "A-2026-09-19-01",
        "A-2026-09-19-02",
    ]
    assert amendments[0]["timing"].startswith("after inspection")
    correction = amendments[1]
    assert correction["corrects"].startswith("A-2026-09-19-01")
    assert "screening model alias is unresolved" in correction["corrected_model_boundary"]
    assert correction["evidence_report"] == "docs/historical_model_identity_audit.md"
