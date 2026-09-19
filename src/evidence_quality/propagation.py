"""Calibrated error propagation for verified meta-analysis datasets."""

from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np

from .meta import random_effects_reml_hk


def derived_seed(master_seed: int, namespace: str, case_id: int, replicate: int) -> int:
    payload = f"{master_seed}|{namespace}|{case_id}|{replicate}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def apply_mechanism(
    yi: list[float],
    vi: list[float],
    mechanism: dict[str, Any],
    rng: np.random.Generator,
) -> tuple[list[float], list[float]]:
    effects = np.asarray(yi, dtype=float).copy()
    variances = np.asarray(vi, dtype=float).copy()
    probability = float(mechanism["probability"])
    affected = rng.random(effects.size) < probability
    mechanism_id = mechanism["id"]
    parameters = mechanism.get("parameters", {})
    keep = np.ones(effects.size, dtype=bool)
    if mechanism_id in {"screening_omission", "technical_failure"}:
        keep &= ~affected
    elif mechanism_id == "additive_effect_error":
        effects[affected] += rng.normal(
            float(parameters.get("mean", 0.0)),
            float(parameters["sd"]),
            int(np.sum(affected)),
        )
    elif mechanism_id == "multiplicative_ratio_error":
        effects[affected] += rng.normal(
            float(parameters.get("log_mean", 0.0)),
            float(parameters["log_sd"]),
            int(np.sum(affected)),
        )
    elif mechanism_id == "variance_error":
        variances[affected] *= rng.lognormal(
            float(parameters.get("log_mean", 0.0)),
            float(parameters["log_sd"]),
            int(np.sum(affected)),
        )
    elif mechanism_id == "wrong_target_selection":
        effects[affected] += rng.normal(
            float(parameters.get("mean_shift", 0.0)),
            float(parameters["shift_sd"]),
            int(np.sum(affected)),
        )
    elif mechanism_id == "joint_pipeline_error":
        effects[affected] += rng.normal(
            float(parameters.get("mean_shift", 0.0)),
            float(parameters["shift_sd"]),
            int(np.sum(affected)),
        )
        variances[affected] *= rng.lognormal(
            float(parameters.get("variance_log_mean", 0.0)),
            float(parameters["variance_log_sd"]),
            int(np.sum(affected)),
        )
        drop_probability = float(parameters.get("conditional_drop_probability", 0.0))
        dropped = affected & (rng.random(effects.size) < drop_probability)
        keep &= ~dropped
    else:
        raise ValueError(f"Unsupported mechanism: {mechanism_id}")
    return effects[keep].tolist(), variances[keep].tolist()


def simulate_scenario(
    yi: list[float],
    vi: list[float],
    mechanism: dict[str, Any],
    case_id: int,
    master_seed: int,
    draws: int,
) -> dict[str, Any]:
    baseline = random_effects_reml_hk(yi, vi)
    shifts = []
    tau2_shifts = []
    conclusion_changes = 0
    invalid_draws = 0
    baseline_crosses = baseline["ci_lower"] <= 0 <= baseline["ci_upper"]
    for replicate in range(draws):
        rng = np.random.Generator(
            np.random.PCG64DXSM(
                derived_seed(master_seed, mechanism["id"], case_id, replicate)
            )
        )
        changed_yi, changed_vi = apply_mechanism(yi, vi, mechanism, rng)
        if len(changed_yi) < 2:
            invalid_draws += 1
            continue
        result = random_effects_reml_hk(changed_yi, changed_vi)
        shifts.append(result["estimate"] - baseline["estimate"])
        tau2_shifts.append(result["tau2"] - baseline["tau2"])
        crosses = result["ci_lower"] <= 0 <= result["ci_upper"]
        conclusion_changes += crosses != baseline_crosses
    if not shifts:
        raise ValueError("All simulation draws were invalid")
    shift_array = np.asarray(shifts)
    tau_array = np.asarray(tau2_shifts)
    return {
        "case_id": case_id,
        "mechanism": mechanism["id"],
        "requested_draws": draws,
        "valid_draws": len(shifts),
        "invalid_draws": invalid_draws,
        "baseline_estimate": baseline["estimate"],
        "mean_estimate_shift": float(np.mean(shift_array)),
        "median_estimate_shift": float(np.median(shift_array)),
        "shift_p025": float(np.quantile(shift_array, 0.025)),
        "shift_p975": float(np.quantile(shift_array, 0.975)),
        "mean_tau2_shift": float(np.mean(tau_array)),
        "conclusion_change_probability": conclusion_changes / len(shifts),
    }
