from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_deduplication_summary_covers_all_cases_and_records() -> None:
    rows = read_rows("results/tables/deduplication_retained_audit.csv")
    assert [int(row["case_id"]) for row in rows] == list(range(1, 21))
    assert sum(int(row["retained_rows"]) for row in rows) == 94_522
    assert sum(int(row["extra_rows_in_duplicate_doi_groups"]) for row in rows) == 0
    assert sum(int(row["extra_rows_in_duplicate_title_groups"]) for row in rows) == 407
    assert sum(int(row["retained_candidate_pairs"]) for row in rows) == 713


def test_retained_pair_sample_is_fixed_and_unlabeled() -> None:
    rows = read_rows("annotations/forms/dedup_retained_pair_sample.csv")
    assert len(rows) == 200
    assert len({row["pair_id"] for row in rows}) == 200
    assert all(not row["human_same_report"] for row in rows)
    assert all(not row["human_same_study"] for row in rows)
    assert all(not row["reviewer_id"] for row in rows)


def test_removed_pair_form_is_schema_only_until_log_is_recovered() -> None:
    rows = read_rows("annotations/forms/dedup_removed_pair_sample.csv")
    assert rows == []
