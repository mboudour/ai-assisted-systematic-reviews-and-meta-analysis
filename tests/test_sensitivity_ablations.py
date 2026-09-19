from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows() -> list[dict[str, str]]:
    with (ROOT / "results/tables/sensitivity_ablations.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def find(metric: str) -> dict[str, str]:
    return next(row for row in rows() if row["metric"] == metric)


def test_unverifiable_exclusion_inflates_apparent_agreement() -> None:
    complete = float(find("correct_share")["value"])
    conditional = float(find("conditional_agreement")["value"])
    increase = float(find("percentage_point_increase")["value"])
    assert math.isclose(complete, 52_877 / 90_554)
    assert math.isclose(conditional, 52_877 / 53_673)
    assert math.isclose(increase, 100 * (conditional - complete))
    assert increase > 40


def test_eligibility_gate_reduces_naive_candidate_count_to_zero() -> None:
    assert int(float(find("cases_passing")["value"])) in {5, 7}
    assert int(float(find("cases_pending_verification")["value"])) == 4
    assert int(float(find("currently_eligible_cases")["value"])) == 0


def test_historical_extraction_cap_is_quantified() -> None:
    assert int(float(find("affected_cases")["value"])) == 5
    all_cases = find("share_of_all_included_records_not_extracted_due_to_cap")
    capped_cases = find("share_of_capped_case_included_records_not_extracted")
    assert int(all_cases["numerator"]) == 7_776
    assert int(all_cases["denominator"]) == 19_276
    assert math.isclose(float(all_cases["value"]), 7_776 / 19_276)
    assert int(capped_cases["numerator"]) == 7_776
    assert int(capped_cases["denominator"]) == 8_776
    assert math.isclose(float(capped_cases["value"]), 7_776 / 8_776)
