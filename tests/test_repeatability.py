from __future__ import annotations

import importlib.util
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load("repeatability_runner", "scripts/run_repeatability_audit.py")
ANALYSIS = load("repeatability_analysis", "scripts/analyze_repeatability.py")


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row(task: str, sample_id: str, repeat: int, output: str, status: str = "ok"):
    return {
        "task": task,
        "sample_id": sample_id,
        "case_id": "1",
        "field_name": "effect_size" if task == "extraction" else "",
        "repeat_index": str(repeat),
        "call_status": status,
        "output_value": output,
    }


def test_sampling_rank_is_deterministic_and_namespaced() -> None:
    assert RUNNER.stable_rank("screening", "abc") == RUNNER.stable_rank(
        "screening", "abc"
    )
    assert RUNNER.stable_rank("screening", "abc") != RUNNER.stable_rank(
        "extraction", "abc"
    )


def test_repeatability_requires_three_successful_equal_outputs() -> None:
    rows = [
        row("screening", "s1", 1, '"INCLUDE"'),
        row("screening", "s1", 2, '"INCLUDE"'),
        row("screening", "s1", 3, '"INCLUDE"'),
        row("screening", "s2", 1, '"INCLUDE"'),
        row("screening", "s2", 2, '"EXCLUDE"'),
        row("screening", "s2", 3, '"INCLUDE"'),
        row("extraction", "e1", 1, "null"),
        row("extraction", "e1", 2, "null"),
        row("extraction", "e1", 3, "null"),
    ]
    summary, items, transitions = ANALYSIS.analyze(rows)
    by_task = {item["task"]: item for item in summary}
    assert by_task["screening"]["complete_items"] == 2
    assert by_task["screening"]["stable_items"] == 1
    assert by_task["screening"]["exact_three_repeat_stability"] == 0.5
    assert by_task["extraction"]["exact_three_repeat_stability"] == 1.0
    extraction = next(item for item in items if item["sample_id"] == "e1")
    assert extraction["null_state_stable"] == "true"
    assert sum(item["count"] for item in transitions) == 4


def test_call_failure_prevents_complete_item_classification() -> None:
    rows = [
        row("screening", "s1", 1, '"INCLUDE"'),
        row("screening", "s1", 2, "", status="api_error"),
        row("screening", "s1", 3, '"INCLUDE"'),
    ]
    summary, items, _ = ANALYSIS.analyze(rows)
    assert summary[0]["complete_items"] == 0
    assert summary[0]["stable_items"] == 0
    assert items[0]["successful_calls"] == 2


def test_saved_raw_response_can_be_recovered_without_new_call(tmp_path: Path) -> None:
    source_row = {
        "sample_id": "sample-1",
        "case_id": "3",
        "field_name": "hazard_ratio",
        "declared_type": "numeric",
        "title": "Trial title",
        "abstract": "The hazard ratio was 0.80.",
    }
    raw = {
        "id": "response-1",
        "created": 1_700_000_000,
        "model": "gpt-5-mini-2026-01-01",
        "system_fingerprint": "fp-test",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "value_text": "0.8",
                            "is_null": False,
                            "reason": "Reported in the abstract.",
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    raw_path = tmp_path / "response.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    recovered = RUNNER.recover_raw("extraction", source_row, 2, raw_path)
    assert recovered["call_status"] == "ok"
    assert recovered["output_value"] == "0.8"
    assert recovered["returned_model_id"] == "gpt-5-mini-2026-01-01"
    assert recovered["system_fingerprint"] == "fp-test"
    assert recovered["attempts"] == 1


def test_numeric_field_text_with_multiple_quantities_remains_successful(tmp_path: Path) -> None:
    source_row = {
        "sample_id": "sample-2",
        "case_id": "1",
        "field_name": "sample_size",
        "declared_type": "numeric",
        "title": "Study",
        "abstract": "There were 459,113 patients and 111,342 nurses.",
    }
    raw = {
        "id": "response-2",
        "model": "gpt-5-mini",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "value_text": "459,113 patients and 111,342 nurses",
                            "is_null": False,
                            "reason": "Both values are reported.",
                        }
                    )
                }
            }
        ],
        "usage": {},
    }
    raw_path = tmp_path / "response.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    recovered = RUNNER.recover_raw("extraction", source_row, 1, raw_path)
    assert recovered["call_status"] == "ok"
    assert "459,113 patients" in recovered["output_value"]


def test_completed_repeatability_audit_has_all_planned_successful_calls() -> None:
    calls = read_rows("results/tables/repeatability_calls.csv")
    assert len(calls) == 2_100
    assert {row["call_status"] for row in calls} == {"ok"}
    summary = {
        row["task"]: row for row in read_rows("results/tables/repeatability_summary.csv")
    }
    assert float(summary["screening"]["exact_three_repeat_stability"]) == 0.95
    assert float(summary["extraction"]["exact_three_repeat_stability"]) == 0.614


def test_preflight_schema_failure_is_preserved_separately() -> None:
    rows = read_rows("results/tables/repeatability_preflight_attempts.csv")
    assert len(rows) == 2_100
    statuses = {}
    for row in rows:
        statuses[row["call_status"]] = statuses.get(row["call_status"], 0) + 1
    assert statuses == {"ok": 600, "response_parse_error": 1_500}


def test_extraction_repeatability_is_stratified_by_declared_type() -> None:
    strata = read_rows("results/tables/repeatability_extraction_strata.csv")
    by_type = {
        row["value"]: row for row in strata if row["dimension"] == "declared_type"
    }
    assert int(by_type["categorical"]["items"]) == 219
    assert int(by_type["numeric"]["items"]) == 281
    assert float(by_type["categorical"]["exact_three_repeat_stability"]) < 0.36
    assert float(by_type["numeric"]["exact_three_repeat_stability"]) > 0.81
