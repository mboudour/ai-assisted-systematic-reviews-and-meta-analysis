from __future__ import annotations

import csv
import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_extraction_evaluator_validation.py"
SPEC = importlib.util.spec_from_file_location("extraction_validation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_historical_evaluator_profile_retains_all_field_cells() -> None:
    rows = read_rows("results/tables/extraction_evaluator_profile.csv")
    assert len(rows) == 159
    assert sum(int(row["field_cells"]) for row in rows) == 90_554
    assert sum(int(row["evaluator_correct"]) for row in rows) == 52_877
    assert sum(int(row["evaluator_incorrect"]) for row in rows) == 796
    assert sum(int(row["evaluator_unverifiable"]) for row in rows) == 36_881
    assert all(row["human_accuracy_status"] == "pending_human_adjudication" for row in rows)


def test_extraction_metric_output_is_empty_until_human_labels_exist() -> None:
    assert read_rows("results/tables/extraction_validation_metrics.csv") == []


def test_weighted_extraction_and_evaluator_metrics() -> None:
    rows = [
        {"human_field_label": "incorrect", "historical_evaluator_verdict": "INCORRECT", "weight": 2},
        {"human_field_label": "incorrect", "historical_evaluator_verdict": "CORRECT", "weight": 1},
        {"human_field_label": "correct", "historical_evaluator_verdict": "CORRECT", "weight": 6},
        {"human_field_label": "correct", "historical_evaluator_verdict": "INCORRECT", "weight": 1},
        {"human_field_label": "correct", "historical_evaluator_verdict": "UNVERIFIABLE", "weight": 1},
        {"human_field_label": "not_assessable", "historical_evaluator_verdict": "UNVERIFIABLE", "weight": 2},
    ]
    metrics = MODULE.validation_metrics(rows)
    assert metrics["weighted_total"] == 13
    assert metrics["weighted_assessable"] == 11
    assert metrics["weighted_not_assessable"] == 2
    assert metrics["weighted_correct"] == 8
    assert metrics["weighted_incorrect"] == 3
    assert math.isclose(metrics["extraction_error_rate"], 3 / 11)
    assert math.isclose(metrics["evaluator_sensitivity"], 2 / 3)
    assert math.isclose(metrics["evaluator_specificity"], 6 / 8)
    assert math.isclose(metrics["evaluator_abstention_rate"], 1 / 11)
