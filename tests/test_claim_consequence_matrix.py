from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_five_lessons_have_observed_consequences_and_limits() -> None:
    rows = read_rows("results/tables/claim_consequence_matrix.csv")
    assert len(rows) == 5
    assert all(row["observed_consequence"] for row in rows)
    assert all(row["quantified_effect"] for row in rows)
    assert all(row["not_identifiable"] for row in rows)
    by_lesson = {row["lesson"]: row for row in rows}
    assert "94,522" in by_lesson["Typed operational failure states"]["observed_consequence"]
    assert "75,246" in by_lesson["Typed operational failure states"]["observed_consequence"]
    assert "94,522" in by_lesson["Versioned relational provenance"]["quantified_effect"]
    assert "36 (7.20%)" in by_lesson[
        "Representation- and null-aware repeatability"
    ]["observed_consequence"]
    assert "927 complete numeric rows" in by_lesson[
        "Downstream-requirements-first schema design"
    ]["observed_consequence"]


def test_schema_requirement_coverage_is_explicit() -> None:
    rows = read_rows("results/tables/schema_requirement_coverage.csv")
    by_requirement = {row["requirement"]: row for row in rows}
    assert int(by_requirement["study-level linkage identifier"]["cases_with_required_field"]) == 0
    assert int(by_requirement["effect-measure label"]["cases_with_required_field"]) == 0
    assert int(by_requirement["effect-specific estimate column"]["cases_with_required_field"]) == 1
    assert int(by_requirement["variance or standard error"]["cases_with_required_field"]) == 0
    assert int(by_requirement["dependence or clustering identifier"]["cases_with_required_field"]) == 0
    assert int(by_requirement["analysis time point"]["cases_with_required_field"]) == 2
    assert int(by_requirement["confidence interval"]["cases_with_required_field"]) == 10


def test_coverage_ablation_uses_both_denominators() -> None:
    rows = read_rows("results/tables/sensitivity_ablations.csv")
    by_metric = {row["metric"]: row for row in rows}
    all_cases = by_metric["share_of_all_included_records_not_extracted_due_to_cap"]
    capped = by_metric["share_of_capped_case_included_records_not_extracted"]
    assert math.isclose(float(all_cases["value"]), 7_776 / 19_276)
    assert math.isclose(float(capped["value"]), 7_776 / 8_776)
