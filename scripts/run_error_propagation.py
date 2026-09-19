#!/usr/bin/env python3
"""Run calibrated Monte Carlo error propagation only when required inputs exist."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evidence_quality.propagation import simulate_scenario

OUTPUT_FIELDS = [
    "case_id",
    "mechanism",
    "requested_draws",
    "valid_draws",
    "invalid_draws",
    "baseline_estimate",
    "mean_estimate_shift",
    "median_estimate_shift",
    "shift_p025",
    "shift_p975",
    "mean_tau2_shift",
    "conclusion_change_probability",
    "status",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--error-model", type=Path, required=True)
    parser.add_argument("--verified-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=10000)
    parser.add_argument("--master-seed", type=int, default=20260919)
    args = parser.parse_args()
    error_model = json.loads(args.error_model.read_text(encoding="utf-8"))
    data = read_rows(args.verified_data)
    calibrated = error_model["calibration_status"] == "calibrated"
    eligible_rows = [
        row
        for row in data
        if row.get("analysis_eligibility") == "verified_and_eligible"
        and row.get("human_verified", "").lower() == "true"
        and row.get("independent_study_verified", "").lower() == "true"
        and row.get("common_estimand_verified", "").lower() == "true"
    ]
    if not calibrated or not eligible_rows:
        write_csv(args.output, [])
        reasons = []
        if not calibrated:
            reasons.append("human validation has not calibrated the error model")
        if not eligible_rows:
            reasons.append("no verified case passes the meta-analysis gate")
        report = [
            "# Step 14 Monte Carlo Error Propagation",
            "",
            "## No inferential simulation was run",
            "",
            "The propagation engine is implemented and tested, but calibrated results were not "
            f"generated because {' and '.join(reasons)}. The output table is intentionally empty.",
            "",
            "Running arbitrary perturbation rates would create a sensitivity illustration rather "
            "than an empirically calibrated result. The frozen paper claims require observed human "
            "disagreement and prospective technical-failure rates, so no replacement values were "
            "invented.",
            "",
            "Once both gates are satisfied, each scenario uses 10,000 or more deterministic PCG64DXSM "
            "draws with independent SHA-256-derived streams. The primary REML Hartung–Knapp model is "
            "refit in every valid draw. Outputs include pooled-estimate shifts, tau-squared shifts, "
            "95% simulation intervals, invalid-draw counts, and conclusion-change probabilities.[1]",
            "",
            "## References",
            "",
            "[1]: https://numpy.org/doc/stable/reference/random/bit_generators/pcg64dxsm.html \"NumPy PCG64DXSM Bit Generator\"",
        ]
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(report) + "\n", encoding="utf-8")
        return

    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in eligible_rows:
        groups[int(row["case_id"])].append(row)
    results = []
    for case_id, rows in sorted(groups.items()):
        yi = [float(row["yi"]) for row in rows]
        vi = [float(row["vi"]) for row in rows]
        for mechanism in error_model["mechanisms"]:
            if mechanism["probability"] is None:
                raise ValueError(f"Calibrated model has null probability: {mechanism['id']}")
            result = simulate_scenario(
                yi, vi, mechanism, case_id, args.master_seed, args.draws
            )
            result["status"] = "calibrated_simulation"
            results.append(result)
    write_csv(args.output, results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        "# Step 14 Monte Carlo Error Propagation\n\nCalibrated simulations completed. See the result table.\n\n"
        "## References\n\n"
        "[1]: https://numpy.org/doc/stable/reference/random/bit_generators/pcg64dxsm.html \"NumPy PCG64DXSM Bit Generator\"\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
