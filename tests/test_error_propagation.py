from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from evidence_quality.propagation import apply_mechanism, derived_seed, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_derived_seeds_are_stable_and_namespace_specific() -> None:
    seed = derived_seed(20260919, "variance_error", 3, 10)
    assert seed == derived_seed(20260919, "variance_error", 3, 10)
    assert seed != derived_seed(20260919, "technical_failure", 3, 10)
    assert seed != derived_seed(20260919, "variance_error", 3, 11)


def test_variance_error_changes_variance_not_effect() -> None:
    rng = np.random.Generator(np.random.PCG64DXSM(123))
    yi, vi = apply_mechanism(
        [0.1, 0.2, 0.3],
        [0.01, 0.01, 0.01],
        {
            "id": "variance_error",
            "probability": 1.0,
            "parameters": {"log_mean": 0.7, "log_sd": 0.0},
        },
        rng,
    )
    assert yi == [0.1, 0.2, 0.3]
    assert all(value > 0.01 for value in vi)


def test_simulation_is_reproducible_for_same_seed() -> None:
    mechanism = {
        "id": "additive_effect_error",
        "probability": 0.25,
        "parameters": {"mean": 0.0, "sd": 0.1},
    }
    first = simulate_scenario(
        [0.10, 0.20, 0.15, 0.25, 0.30],
        [0.01, 0.02, 0.015, 0.01, 0.03],
        mechanism,
        case_id=3,
        master_seed=20260919,
        draws=100,
    )
    second = simulate_scenario(
        [0.10, 0.20, 0.15, 0.25, 0.30],
        [0.01, 0.02, 0.015, 0.01, 0.03],
        mechanism,
        case_id=3,
        master_seed=20260919,
        draws=100,
    )
    assert first == second


def test_propagation_output_is_empty_until_both_gates_pass() -> None:
    with (ROOT / "results/tables/error_propagation_results.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        assert list(csv.DictReader(handle)) == []
