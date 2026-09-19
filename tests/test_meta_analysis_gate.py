from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_final_meta_analysis_tables_are_empty_when_no_case_is_eligible() -> None:
    assert read_rows("results/tables/meta_analysis_results.csv") == []
    assert read_rows("results/tables/meta_analysis_weights.csv") == []


def test_provisional_candidates_are_not_silently_promoted() -> None:
    candidates = read_rows("results/tables/meta_analysis_candidates_unverified.csv")
    eligibility = read_rows("results/tables/meta_analysis_eligibility.csv")
    assert candidates
    assert all(row["analysis_eligibility"] == "provisional_unverified" for row in candidates)
    assert all(row["currently_eligible_for_meta_analysis"] == "false" for row in eligibility)
