from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_current_source_count_audit_has_one_row_per_case() -> None:
    rows = read_rows("results/tables/current_source_count_audit.csv")
    assert [int(row["case_id"]) for row in rows] == list(range(1, 21))
    statuses = Counter(row["status"] for row in rows)
    assert statuses == {
        "ok": 16,
        "not_queried_missing_api_key": 2,
        "request_failed": 2,
    }


def test_historical_totals_and_configured_limit_flags_are_preserved() -> None:
    rows = read_rows("results/tables/retrieval_corpus_quality.csv")
    assert sum(int(row["historical_pre_dedup_rows_reported"]) for row in rows) == 95_292
    assert sum(int(row["historical_post_dedup_rows"]) for row in rows) == 94_522
    assert sum(int(row["duplicates_removed_reported"]) for row in rows) == 770
    limited_cases = [
        int(row["case_id"]) for row in rows if row["configured_limit_reached"] == "true"
    ]
    assert limited_cases == [3, 5, 8, 11, 15, 20]


def test_uncollected_metadata_is_not_reported_as_zero_completeness() -> None:
    rows = read_rows("results/tables/retrieval_corpus_quality.csv")
    assert all(row["language_status"] == "not_collected" for row in rows)
    assert all(row["source_record_id_status"] == "not_collected" for row in rows)


def test_current_counts_remain_separate_from_historical_counts() -> None:
    rows = read_rows("results/tables/retrieval_corpus_quality.csv")
    case_three = next(row for row in rows if row["case_id"] == "3")
    assert case_three["historical_post_dedup_rows"] == "5945"
    assert int(case_three["current_source_reported_hits"]) > 5945
    assert case_three["historical_completeness_status"] == "configured_limit_reached"
