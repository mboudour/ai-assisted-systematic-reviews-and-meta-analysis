from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_error_injection.py"
SPEC = importlib.util.spec_from_file_location("error_injection_analysis", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_frozen_error_injection_design_has_expected_size() -> None:
    design = json.loads(
        (ROOT / "config/error_injection_experiment.json").read_text(encoding="utf-8")
    )
    assert len(design["error_types"]) == 11
    assert len(design["models"]) == 2
    assert design["planned_calls_per_model"] == 660
    assert design["planned_total_calls"] == 1_320


def test_no_calls_are_made_without_human_verified_inputs() -> None:
    assert read_rows("results/tables/error_injection_calls.csv") == []
    assert read_rows("results/tables/error_injection_metrics.csv") == []


def test_detection_and_false_alarm_summaries_remain_separate() -> None:
    rows = [
        {
            "requested_model_id": "model-a",
            "error_type": "small_numeric_error",
            "arm": "injected",
            "call_status": "ok",
            "verdict": "INCORRECT",
        },
        {
            "requested_model_id": "model-a",
            "error_type": "small_numeric_error",
            "arm": "injected",
            "call_status": "ok",
            "verdict": "UNVERIFIABLE",
        },
        {
            "requested_model_id": "model-a",
            "error_type": "small_numeric_error",
            "arm": "injected",
            "call_status": "api_error",
            "verdict": "",
        },
        {
            "requested_model_id": "model-a",
            "error_type": "small_numeric_error",
            "arm": "control",
            "call_status": "ok",
            "verdict": "CORRECT",
        },
    ]
    output = MODULE.summarize(rows)
    injected = next(row for row in output if row["arm"] == "injected")
    control = next(row for row in output if row["arm"] == "control")
    assert injected["attempted_calls"] == 3
    assert injected["successful_calls"] == 2
    assert injected["failed_calls"] == 1
    assert math.isclose(injected["target_rate"], 0.5)
    assert control["target_rate"] == 0
