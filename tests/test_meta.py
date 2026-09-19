from __future__ import annotations

import math

import pytest

from evidence_quality.meta import fixed_effect, random_effects_dl, random_effects_reml_hk


def test_fixed_effect_equal_variances() -> None:
    result = fixed_effect([0.1, 0.2, 0.3], [0.01, 0.01, 0.01])
    assert result["estimate"] == pytest.approx(0.2)
    assert result["standard_error"] == pytest.approx(math.sqrt(1 / 300))
    assert result["q"] == pytest.approx(2.0)
    assert result["i2"] == pytest.approx(0.0)
    assert sum(result["normalized_weights"]) == pytest.approx(1.0)


def test_dl_tau_is_zero_when_q_equals_degrees_of_freedom() -> None:
    result = random_effects_dl([0.1, 0.2, 0.3], [0.01, 0.01, 0.01])
    assert result["tau2"] == pytest.approx(0.0)
    assert result["estimate"] == pytest.approx(0.2)


def test_reml_hk_returns_finite_interval_and_prediction_interval() -> None:
    result = random_effects_reml_hk(
        [0.10, 0.35, -0.05, 0.22, 0.40],
        [0.01, 0.02, 0.015, 0.01, 0.03],
    )
    assert result["k"] == 5
    assert result["tau2"] >= 0
    assert result["ci_lower"] < result["estimate"] < result["ci_upper"]
    assert result["prediction_lower"] < result["estimate"] < result["prediction_upper"]
    assert sum(result["normalized_weights"]) == pytest.approx(1.0)


def test_invalid_variances_are_rejected() -> None:
    with pytest.raises(ValueError):
        fixed_effect([0.1, 0.2], [0.01, 0.0])
