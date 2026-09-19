#!/usr/bin/env python3
"""Analyze prospective screening repeatability without treating stability as accuracy."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q, method="linear"))


def analyze(
    calls: list[dict[str, str]],
    manifest: list[dict[str, str]],
    seed: int,
    bootstrap_draws: int,
) -> dict[str, Any]:
    metadata = {row["sample_id"]: row for row in manifest}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in calls:
        if row["task"] == "screening":
            grouped[row["sample_id"]].append(row)

    if not set(grouped).issubset(metadata):
        missing_manifest = sorted(set(grouped) - set(metadata))
        raise ValueError(
            f"Screening calls missing from sampling manifest: {missing_manifest[:3]}"
        )

    items: list[dict[str, Any]] = []
    adjacent = Counter()
    patterns = Counter()
    for sample_id, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: int(row["repeat_index"]))
        if len(rows) != 3:
            raise ValueError(f"{sample_id} has {len(rows)} calls; expected 3")
        if any(row["call_status"] != "ok" for row in rows):
            raise ValueError(f"{sample_id} has a non-successful call")
        outputs = [str(json.loads(row["output_value"])).upper() for row in rows]
        if any(value not in {"INCLUDE", "EXCLUDE"} for value in outputs):
            raise ValueError(f"{sample_id} has an unexpected label: {outputs}")
        stable = len(set(outputs)) == 1
        for left, right in zip(outputs, outputs[1:]):
            adjacent[(left, right)] += 1
        patterns[tuple(outputs)] += 1
        meta = metadata[sample_id]
        probability = float(meta["selection_probability"])
        if not 0 < probability <= 1:
            raise ValueError(f"Invalid selection probability for {sample_id}: {probability}")
        items.append(
            {
                "sample_id": sample_id,
                "case_id": int(meta["case_id"]),
                "weight": 1.0 / probability,
                "stable": stable,
                "historical_label": meta["historical_llm_decision"].upper(),
                "pattern": "-".join(outputs),
            }
        )

    weighted_stability = sum(row["weight"] * row["stable"] for row in items) / sum(
        row["weight"] for row in items
    )
    unweighted_stability = sum(row["stable"] for row in items) / len(items)

    by_case: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in items:
        by_case[row["case_id"]].append(row)
    case_ids = sorted(by_case)
    rng = np.random.default_rng(seed)
    bootstrap: list[float] = []
    for _ in range(bootstrap_draws):
        sampled_cases = rng.choice(case_ids, size=len(case_ids), replace=True)
        numerator = 0.0
        denominator = 0.0
        for case_id in sampled_cases:
            for row in by_case[int(case_id)]:
                numerator += row["weight"] * row["stable"]
                denominator += row["weight"]
        bootstrap.append(numerator / denominator)

    strata: dict[str, dict[str, Any]] = {}
    for historical_label in ("INCLUDE", "EXCLUDE"):
        subset = [row for row in items if row["historical_label"] == historical_label]
        strata[historical_label] = {
            "items": len(subset),
            "stable_items": sum(row["stable"] for row in subset),
            "unweighted_stability": sum(row["stable"] for row in subset) / len(subset),
            "design_weighted_stability": sum(
                row["weight"] * row["stable"] for row in subset
            )
            / sum(row["weight"] for row in subset),
        }

    return {
        "primary_estimand": "realized proportion of the 200-item deterministic repeatability subset with three identical screening labels",
        "weighted_sensitivity_estimand": "inverse-first-stage-probability weighted stability within the deterministic repeatability subset",
        "model_boundary": "prospective gpt-5-mini calls; not historical-model repeatability and not accuracy",
        "items": len(items),
        "calls": 3 * len(items),
        "successful_calls": 3 * len(items),
        "stable_items": sum(row["stable"] for row in items),
        "unweighted_stability": unweighted_stability,
        "design_weighted_stability": weighted_stability,
        "case_cluster_bootstrap_95_lower": percentile(bootstrap, 2.5),
        "case_cluster_bootstrap_95_upper": percentile(bootstrap, 97.5),
        "adjacent_transitions": {
            f"{left}_to_{right}": count
            for (left, right), count in sorted(adjacent.items())
        },
        "changed_adjacent_transitions": sum(
            count for (left, right), count in adjacent.items() if left != right
        ),
        "total_adjacent_transitions": sum(adjacent.values()),
        "three_call_patterns": {
            "-".join(pattern): count for pattern, count in sorted(patterns.items())
        },
        "historical_label_strata": strata,
        "bootstrap_draws": bootstrap_draws,
        "seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--calls", type=Path, default=Path("results/tables/repeatability_calls.csv")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/manifests/screening_sample_manifest.csv")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/tables/screening_repeatability_summary.json"),
    )
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--bootstrap-draws", type=int, default=10_000)
    args = parser.parse_args()
    root = args.root.resolve()
    result = analyze(
        read_csv(root / args.calls),
        read_csv(root / args.manifest),
        seed=args.seed,
        bootstrap_draws=args.bootstrap_draws,
    )
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
