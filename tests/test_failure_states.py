from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_historical_failure_rates_are_not_fabricated() -> None:
    rows = read_rows("results/tables/failure_missingness_audit.csv")
    assert len(rows) == 20
    assert all(row["screening_failure_flag_present"] == "false" for row in rows)
    assert all(row["screening_technical_failure_rate"] == "" for row in rows)
    assert all(
        row["screening_failure_identifiability"]
        == "not_identifiable_from_archived_output"
        for row in rows
    )
    assert sum(int(row["screened_records"]) for row in rows) == 94_522
    assert sum(int(row["exclude_labels"]) for row in rows) == 75_246
    assert sum(int(row["extracted_records"]) for row in rows) == 11_500
    assert sum(int(row["all_null_records"]) for row in rows) == 23
    assert sum(int(row["all_unverifiable_records"]) for row in rows) == 22


def test_archived_field_denominators_include_unverifiable() -> None:
    rows = read_rows("results/tables/failure_missingness_audit.csv")
    requested = sum(int(row["requested_field_cells"]) for row in rows)
    nulls = sum(int(row["extraction_null_cells"]) for row in rows)
    correct = sum(int(row["judge_correct_cells"]) for row in rows)
    incorrect = sum(int(row["judge_incorrect_cells"]) for row in rows)
    unverifiable = sum(int(row["judge_unverifiable_cells"]) for row in rows)
    assert requested == 90_554
    assert nulls == 36_641
    assert correct == 52_877
    assert incorrect == 796
    assert unverifiable == 36_881
    assert correct + incorrect + unverifiable == requested


def test_null_verdict_breakdown_is_complete() -> None:
    rows = read_rows("results/tables/failure_missingness_audit.csv")
    nulls = sum(int(row["extraction_null_cells"]) for row in rows)
    null_breakdown = sum(
        int(row[column])
        for row in rows
        for column in (
            "null_judged_correct",
            "null_judged_incorrect",
            "null_judged_unverifiable",
        )
    )
    assert null_breakdown == nulls


def test_event_schema_requires_explicit_call_status() -> None:
    schema = json.loads(
        (ROOT / "config/pipeline_event.schema.json").read_text(encoding="utf-8")
    )
    assert "call_status" in schema["required"]
    statuses = set(schema["properties"]["call_status"]["enum"])
    assert statuses == {
        "ok",
        "api_error",
        "timeout",
        "rate_limited",
        "invalid_response",
        "parse_error",
        "cancelled",
    }


def test_event_table_template_contains_no_fabricated_events() -> None:
    rows = read_rows("config/pipeline_events_template.csv")
    assert rows == []
