from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_screening_repeatability_is_reported_with_its_design_weighted_estimand() -> None:
    result = json.loads(
        (ROOT / "results/tables/screening_repeatability_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["items"] == 200
    assert result["calls"] == 600
    assert result["successful_calls"] == 600
    assert result["stable_items"] == 190
    assert math.isclose(result["unweighted_stability"], 0.95)
    assert math.isclose(result["design_weighted_stability"], 0.9538347000385159)
    assert 0.90 < result["case_cluster_bootstrap_95_lower"] < 0.93
    assert 0.98 < result["case_cluster_bootstrap_95_upper"] < 1.00
    assert result["changed_adjacent_transitions"] == 13
    assert result["total_adjacent_transitions"] == 400
    assert result["adjacent_transitions"]["INCLUDE_to_EXCLUDE"] == 7
    assert result["adjacent_transitions"]["EXCLUDE_to_INCLUDE"] == 6
    assert "not historical-model repeatability" in result["model_boundary"]
    assert "not accuracy" in result["model_boundary"]


def test_verdict_cube_recomputes_every_headline_count() -> None:
    rows = read_csv("results/tables/evaluator_verdict_cube.csv")
    assert len(rows) == 20 * 2 * 2 * 3
    assert {int(row["case_id"]) for row in rows} == set(range(1, 21))
    assert {row["field_type"] for row in rows} == {"categorical", "numeric"}
    assert {row["null_status"] for row in rows} == {"null", "nonnull"}
    assert {row["verdict"] for row in rows} == {
        "CORRECT",
        "INCORRECT",
        "UNVERIFIABLE",
    }

    verdict = Counter()
    cross = Counter()
    for row in rows:
        count = int(row["count"])
        verdict[row["verdict"]] += count
        cross[(row["null_status"], row["verdict"])] += count

    assert sum(verdict.values()) == 90_554
    assert verdict == Counter(CORRECT=52_877, INCORRECT=796, UNVERIFIABLE=36_881)
    assert cross[("null", "UNVERIFIABLE")] == 36_423
    assert cross[("null", "CORRECT")] == 198
    assert cross[("null", "INCORRECT")] == 20
    assert cross[("nonnull", "UNVERIFIABLE")] == 458
    assert cross[("nonnull", "CORRECT")] == 52_679
    assert cross[("nonnull", "INCORRECT")] == 776
