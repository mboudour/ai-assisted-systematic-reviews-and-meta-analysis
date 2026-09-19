from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_repeatability_normalized.py"
SPEC = importlib.util.spec_from_file_location("repeatability_normalized", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_conservative_normalization_handles_surface_variants() -> None:
    assert MODULE.normalize_scalar(" Randomised-controlled / trial ") == "randomized controlled trial"
    assert MODULE.token_set("trial, controlled randomized") == "controlled randomized trial"
    assert MODULE.token_set("randomized controlled trial") == "controlled randomized trial"


def test_normalized_summary_separates_nulls_and_models() -> None:
    summary = json.loads(
        (ROOT / "results/tables/repeatability_normalized_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["scope"]["model"] == "gpt-5-mini"
    assert summary["scope"]["temperature_requested"] == 0
    assert summary["scope"]["temperature_effective_confirmed_by_provider"] is False
    assert summary["scope"]["historical_screening_model_status"] == "unresolved"
    assert len(summary["scope"]["historical_screening_conflicting_aliases"]) == 3
    assert summary["null_state_counts"]["all_null"] == 160
    assert summary["null_state_counts"]["all_nonnull"] == 304
    assert summary["null_state_counts"]["mixed_null"] == 36
    assert summary["null_state_counts"]["mixed_null_unweighted_rate"] == pytest.approx(0.072)
    assert summary["null_state_counts"]["mixed_null_by_declared_type"] == {
        "categorical": 23,
        "numeric": 13,
    }
    assert summary["null_state_design_weighted"]["mixed_null"][
        "weighted_estimate"
    ] == pytest.approx(0.019183154596048524)


def test_nonnull_normalization_materially_changes_categorical_result() -> None:
    summary = json.loads(
        (ROOT / "results/tables/repeatability_normalized_summary.json").read_text(
            encoding="utf-8"
        )
    )
    categorical = summary["all_nonnull_by_declared_type"]["categorical"]
    numeric = summary["all_nonnull_by_declared_type"]["numeric"]
    assert categorical["raw_exact"]["items"] == 154
    assert categorical["raw_exact"]["weighted_estimate"] == pytest.approx(
        0.21583328739180593
    )
    assert categorical["normalized_exact"]["weighted_estimate"] == pytest.approx(
        0.4613421751080956
    )
    assert categorical["token_set_exact"]["weighted_estimate"] == pytest.approx(
        0.47794412985438
    )
    assert numeric["raw_exact"]["items"] == 150
    assert numeric["normalized_exact"]["weighted_estimate"] == pytest.approx(
        0.8855479637897435
    )


def test_report_disclaims_historical_model_repeatability() -> None:
    report = (ROOT / "docs/step11_repeatability_sensitivity.md").read_text(
        encoding="utf-8"
    )
    assert "do not estimate repeatability of the historical models" in report
    assert "historical screening model is unresolved" in report
    assert "effective decoding configuration" in report
    assert "semantic-equivalence cutoffs" in report
    assert "largely, but not perfectly, stable" in report
    assert report.index("1.92%") < report.index("36 of 500")
