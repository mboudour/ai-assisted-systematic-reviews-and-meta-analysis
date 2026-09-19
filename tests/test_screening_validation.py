from __future__ import annotations

import csv
import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_screening_validation.py"
SPEC = importlib.util.spec_from_file_location("screening_validation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_historical_decision_profile_is_not_labeled_accuracy() -> None:
    rows = read_rows("results/tables/screening_decision_profile.csv")
    assert len(rows) == 20
    assert sum(int(row["screened_records"]) for row in rows) == 94_522
    assert sum(int(row["historical_include_records"]) for row in rows) == 19_276
    assert all(row["accuracy_status"] == "pending_human_adjudication" for row in rows)


def test_screening_metric_output_is_empty_until_human_labels_exist() -> None:
    assert read_rows("results/tables/screening_validation_metrics.csv") == []


def test_weighted_confusion_metrics() -> None:
    rows = [
        {"human_screening_label": "include", "historical_llm_decision": "INCLUDE", "weight": 2},
        {"human_screening_label": "include", "historical_llm_decision": "EXCLUDE", "weight": 1},
        {"human_screening_label": "exclude", "historical_llm_decision": "INCLUDE", "weight": 1},
        {"human_screening_label": "exclude", "historical_llm_decision": "EXCLUDE", "weight": 6},
    ]
    metrics = MODULE.confusion_metrics(rows)
    assert metrics["tp"] == 2
    assert metrics["fn"] == 1
    assert metrics["fp"] == 1
    assert metrics["tn"] == 6
    assert math.isclose(metrics["sensitivity"], 2 / 3)
    assert math.isclose(metrics["specificity"], 6 / 7)
    assert math.isclose(metrics["precision"], 2 / 3)
    assert math.isclose(metrics["negative_predictive_value"], 6 / 7)
    assert math.isclose(metrics["f1"], 2 / 3)
