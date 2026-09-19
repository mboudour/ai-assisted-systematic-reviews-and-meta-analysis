from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_all_twenty_cases_received_independent_structural_review() -> None:
    payload = json.loads(
        (ROOT / "results/tables/meta_analysis_case_assessments.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(payload["assessments"]) == 20
    assert payload["failures"] == []
    assert [item["case_id"] for item in payload["assessments"]] == list(range(1, 21))


def test_no_case_currently_passes_frozen_meta_analysis_gate() -> None:
    rows = read_rows("results/tables/meta_analysis_eligibility.csv")
    assert len(rows) == 20
    assert all(row["currently_eligible_for_meta_analysis"] == "false" for row in rows)
    statuses = Counter(row["final_gate_status"] for row in rows)
    assert statuses == {"structurally_ineligible": 16, "pending_human_verification": 4}
    pending_cases = {
        int(row["case_id"])
        for row in rows
        if row["final_gate_status"] == "pending_human_verification"
    }
    assert pending_cases == {2, 3, 6, 15}


def test_provisional_meta_analysis_rows_are_never_marked_verified() -> None:
    rows = read_rows("results/tables/meta_analysis_candidates_unverified.csv")
    assert len(rows) == 921
    assert all(row["human_verified"] == "false" for row in rows)
    assert all(row["independent_study_verified"] == "false" for row in rows)
    assert all(row["common_estimand_verified"] == "false" for row in rows)
    assert all(row["analysis_eligibility"] == "provisional_unverified" for row in rows)
