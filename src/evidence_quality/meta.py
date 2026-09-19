"""Transparent inverse-variance meta-analysis estimators."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import norm, t


def _arrays(yi: list[float], vi: list[float]) -> tuple[np.ndarray, np.ndarray]:
    effects = np.asarray(yi, dtype=float)
    variances = np.asarray(vi, dtype=float)
    if effects.ndim != 1 or variances.ndim != 1 or effects.size != variances.size:
        raise ValueError("yi and vi must be one-dimensional arrays of equal length")
    if effects.size < 2:
        raise ValueError("at least two estimates are required")
    if not np.all(np.isfinite(effects)) or not np.all(np.isfinite(variances)):
        raise ValueError("yi and vi must be finite")
    if np.any(variances <= 0):
        raise ValueError("all variances must be positive")
    return effects, variances


def heterogeneity_q(yi: np.ndarray, vi: np.ndarray) -> tuple[float, float, float]:
    weights = 1.0 / vi
    pooled = float(np.sum(weights * yi) / np.sum(weights))
    q = float(np.sum(weights * (yi - pooled) ** 2))
    df = yi.size - 1
    i2 = 0.0 if q <= 0 else max(0.0, (q - df) / q)
    return pooled, q, i2


def tau2_dl(yi: list[float], vi: list[float]) -> float:
    effects, variances = _arrays(yi, vi)
    weights = 1.0 / variances
    _, q, _ = heterogeneity_q(effects, variances)
    df = effects.size - 1
    denominator = float(np.sum(weights) - np.sum(weights**2) / np.sum(weights))
    return max(0.0, (q - df) / denominator) if denominator > 0 else 0.0


def tau2_reml(yi: list[float], vi: list[float]) -> float:
    effects, variances = _arrays(yi, vi)

    def objective(tau2: float) -> float:
        weights = 1.0 / (variances + tau2)
        pooled = np.sum(weights * effects) / np.sum(weights)
        residual = np.sum(weights * (effects - pooled) ** 2)
        return float(
            0.5
            * (
                np.sum(np.log(variances + tau2))
                + math.log(float(np.sum(weights)))
                + residual
            )
        )

    upper = max(float(np.var(effects, ddof=1)) * 100, float(np.max(variances)) * 100, 1.0)
    result = minimize_scalar(objective, bounds=(0.0, upper), method="bounded")
    if not result.success:
        raise RuntimeError(f"REML optimization failed: {result.message}")
    return 0.0 if result.x < 1e-10 else float(result.x)


def _weighted_result(
    effects: np.ndarray,
    variances: np.ndarray,
    tau2: float,
    critical: float,
    hk_scale: bool,
) -> dict[str, Any]:
    weights = 1.0 / (variances + tau2)
    pooled = float(np.sum(weights * effects) / np.sum(weights))
    if hk_scale:
        scale = float(np.sum(weights * (effects - pooled) ** 2) / (effects.size - 1))
        standard_error = math.sqrt(scale / float(np.sum(weights)))
    else:
        scale = 1.0
        standard_error = math.sqrt(1.0 / float(np.sum(weights)))
    lower = pooled - critical * standard_error
    upper = pooled + critical * standard_error
    _, q, i2 = heterogeneity_q(effects, variances)
    return {
        "k": int(effects.size),
        "estimate": pooled,
        "standard_error": standard_error,
        "ci_lower": lower,
        "ci_upper": upper,
        "tau2": tau2,
        "q": q,
        "i2": i2,
        "hk_scale": scale,
        "normalized_weights": (weights / np.sum(weights)).tolist(),
    }


def fixed_effect(yi: list[float], vi: list[float], alpha: float = 0.05) -> dict[str, Any]:
    effects, variances = _arrays(yi, vi)
    critical = float(norm.ppf(1 - alpha / 2))
    result = _weighted_result(effects, variances, 0.0, critical, hk_scale=False)
    result["model"] = "fixed_effect_inverse_variance"
    result["prediction_lower"] = math.nan
    result["prediction_upper"] = math.nan
    return result


def random_effects_dl(yi: list[float], vi: list[float], alpha: float = 0.05) -> dict[str, Any]:
    effects, variances = _arrays(yi, vi)
    tau2 = tau2_dl(yi, vi)
    critical = float(norm.ppf(1 - alpha / 2))
    result = _weighted_result(effects, variances, tau2, critical, hk_scale=False)
    result["model"] = "random_effects_der_simonian_laird"
    prediction_se = math.sqrt(tau2 + result["standard_error"] ** 2)
    result["prediction_lower"] = result["estimate"] - critical * prediction_se
    result["prediction_upper"] = result["estimate"] + critical * prediction_se
    return result


def random_effects_reml_hk(
    yi: list[float], vi: list[float], alpha: float = 0.05
) -> dict[str, Any]:
    effects, variances = _arrays(yi, vi)
    tau2 = tau2_reml(yi, vi)
    critical = float(t.ppf(1 - alpha / 2, df=effects.size - 1))
    result = _weighted_result(effects, variances, tau2, critical, hk_scale=True)
    result["model"] = "random_effects_reml_hartung_knapp"
    prediction_df = max(1, effects.size - 2)
    prediction_critical = float(t.ppf(1 - alpha / 2, df=prediction_df))
    prediction_se = math.sqrt(tau2 + result["standard_error"] ** 2)
    result["prediction_lower"] = result["estimate"] - prediction_critical * prediction_se
    result["prediction_upper"] = result["estimate"] + prediction_critical * prediction_se
    return result


def run_all_models(yi: list[float], vi: list[float], alpha: float = 0.05) -> list[dict[str, Any]]:
    return [
        fixed_effect(yi, vi, alpha),
        random_effects_dl(yi, vi, alpha),
        random_effects_reml_hk(yi, vi, alpha),
    ]
