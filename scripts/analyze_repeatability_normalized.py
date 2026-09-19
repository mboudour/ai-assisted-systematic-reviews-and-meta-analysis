#!/usr/bin/env python3
"""Analyze repeated extraction outputs without human labels or external model calls.

The script separates raw exact matching, conservative text normalization, token-set
matching, and lexical-similarity sensitivity. It reports all-null, all-non-null, and
mixed-null items separately. None of these metrics is semantic correctness.
"""

from __future__ import annotations

import itertools
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path.cwd()
OUT = ROOT / "results/tables/repeatability_normalized_summary.json"
ITEM_OUT = ROOT / "results/tables/repeatability_normalized_items.csv"
REPORT = ROOT / "docs/step11_repeatability_sensitivity.md"
SEED = 20260919
BOOTSTRAPS = 10_000

SPELLING_MAP = {
    "randomised": "randomized",
    "randomisation": "randomization",
    "programme": "program",
    "programmes": "programs",
    "behaviour": "behavior",
    "behavioural": "behavioral",
    "modelling": "modeling",
}


def parse_json_value(text: str):
    stripped = str(text).strip()
    if stripped == "" or stripped.casefold() == "null":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def normalize_scalar(value) -> str:
    if value is None:
        return "<NULL>"
    if isinstance(value, bool):
        return str(value).casefold()
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value).casefold()
        return format(float(value), ".15g")
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-–—/]", " ", text)
    text = re.sub(r"[^\w\s.%+]", " ", text)
    tokens = [SPELLING_MAP.get(token, token) for token in re.findall(r"[\w.%+]+", text)]
    return " ".join(tokens)


def token_set(value) -> str:
    normalized = normalize_scalar(value)
    if normalized == "<NULL>":
        return normalized
    return " ".join(sorted(set(normalized.split())))


def min_pairwise_similarity(values: list[str]) -> float:
    if len(values) < 2:
        return 1.0
    return min(
        SequenceMatcher(None, left, right, autojunk=False).ratio()
        for left, right in itertools.combinations(values, 2)
    )


def weighted_mean(frame: pd.DataFrame, column: str) -> float:
    return float(np.average(frame[column].astype(float), weights=frame["weight"].astype(float)))


def cluster_bootstrap(frame: pd.DataFrame, column: str) -> dict[str, float | int]:
    frame = frame.copy()
    frame["case_id"] = frame["case_id"].astype(str)
    clusters = sorted(frame["case_id"].unique())
    observed = weighted_mean(frame, column)
    totals = (
        frame.assign(_num=frame[column].astype(float) * frame["weight"].astype(float))
        .groupby("case_id")
        .agg(numerator=("_num", "sum"), denominator=("weight", "sum"))
        .reindex(clusters)
    )
    rng = np.random.default_rng(SEED + len(frame) + sum(map(ord, column)))
    indices = rng.integers(0, len(clusters), size=(BOOTSTRAPS, len(clusters)))
    numerator = totals["numerator"].to_numpy()[indices].sum(axis=1)
    denominator = totals["denominator"].to_numpy()[indices].sum(axis=1)
    estimates = numerator / denominator
    low, high = np.quantile(estimates, [0.025, 0.975])
    return {
        "weighted_estimate": observed,
        "unweighted_estimate": float(frame[column].mean()),
        "cluster_bootstrap_95_lower": float(low),
        "cluster_bootstrap_95_upper": float(high),
        "items": int(len(frame)),
        "cases": int(len(clusters)),
    }


def summarize(frame: pd.DataFrame, metrics: list[str]) -> dict[str, dict[str, float | int]]:
    return {metric: cluster_bootstrap(frame, metric) for metric in metrics}


def main() -> None:
    calls = pd.read_csv(ROOT / "results/tables/repeatability_calls.csv", keep_default_na=False)
    manifest = pd.read_csv(ROOT / "data/manifests/extraction_sample_manifest.csv", keep_default_na=False)
    calls = calls[(calls["task"] == "extraction") & (calls["call_status"] == "ok")].copy()
    manifest = manifest[
        [
            "sample_id",
            "case_id",
            "field_name",
            "field_class",
            "declared_type",
            "selection_probability",
        ]
    ].copy()

    rows: list[dict[str, object]] = []
    for sample_id, group in calls.groupby("sample_id", sort=True):
        if len(group) != 3:
            continue
        values = [parse_json_value(value) for value in group.sort_values("repeat_index")["output_value"]]
        raw = [json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values]
        normalized = [normalize_scalar(value) for value in values]
        tokenized = [token_set(value) for value in values]
        nulls = [value is None for value in values]
        null_pattern = "".join("N" if is_null else "V" for is_null in nulls)
        nonnull_normalized = [value for value, is_null in zip(normalized, nulls) if not is_null]
        rows.append(
            {
                "sample_id": sample_id,
                "raw_exact": len(set(raw)) == 1,
                "normalized_exact": len(set(normalized)) == 1,
                "token_set_exact": len(set(tokenized)) == 1,
                "all_null": all(nulls),
                "all_nonnull": not any(nulls),
                "mixed_null": any(nulls) and not all(nulls),
                "null_pattern": null_pattern,
                "adjacent_null_transitions": sum(
                    left != right for left, right in zip(nulls, nulls[1:])
                ),
                "min_pairwise_lexical_similarity": min_pairwise_similarity(normalized),
                "min_pairwise_nonnull_lexical_similarity": (
                    min_pairwise_similarity(nonnull_normalized)
                    if len(nonnull_normalized) >= 2
                    else math.nan
                ),
            }
        )

    items = pd.DataFrame(rows).merge(manifest, on="sample_id", how="left", validate="one_to_one")
    items["weight"] = 1.0 / items["selection_probability"].astype(float)
    for threshold in (0.70, 0.80, 0.90):
        items[f"lexical_at_least_{int(threshold * 100)}"] = (
            items["min_pairwise_lexical_similarity"] >= threshold
        )
        items[f"nonnull_lexical_at_least_{int(threshold * 100)}"] = (
            items["min_pairwise_nonnull_lexical_similarity"] >= threshold
        )

    metrics = [
        "raw_exact",
        "normalized_exact",
        "token_set_exact",
        "lexical_at_least_70",
        "lexical_at_least_80",
        "lexical_at_least_90",
    ]
    nonnull_metrics = [
        "raw_exact",
        "normalized_exact",
        "token_set_exact",
        "nonnull_lexical_at_least_70",
        "nonnull_lexical_at_least_80",
        "nonnull_lexical_at_least_90",
    ]

    results: dict[str, object] = {
        "scope": {
            "model": "gpt-5-mini",
            "historical_screening_model_status": "unresolved",
            "historical_screening_conflicting_aliases": [
                "gpt-4.1-mini in committed script",
                "gpt-4o-mini in repository README",
                "gpt-4o in manuscript Section 4.5.1",
            ],
            "historical_extraction_evaluator_declared_alias": "gpt-4o-mini; no per-call verification",
            "comparability": "The prospective run is a separate gpt-5-mini experiment and does not estimate repeatability of the historical model outputs.",
            "temperature_requested": 0,
            "temperature_effective_confirmed_by_provider": False,
            "semantic_correctness_estimated": False,
            "normalization": "Unicode NFKC, case-folding, punctuation and separator normalization, whitespace normalization, and a small declared British-to-American spelling map.",
            "lexical_metric": "minimum pairwise difflib SequenceMatcher ratio across three runs; thresholds are sensitivity analyses, not validated semantic-equivalence cutoffs.",
        },
        "all_extraction_items": summarize(items, metrics),
        "null_state_counts": {
            "all_null": int(items["all_null"].sum()),
            "all_nonnull": int(items["all_nonnull"].sum()),
            "mixed_null": int(items["mixed_null"].sum()),
            "mixed_null_unweighted_rate": float(items["mixed_null"].mean()),
            "mixed_null_by_declared_type": {
                declared_type: int(
                    items.loc[items["declared_type"] == declared_type, "mixed_null"].sum()
                )
                for declared_type in ("categorical", "numeric")
            },
            "adjacent_null_transitions": int(items["adjacent_null_transitions"].sum()),
        },
        "null_state_design_weighted": summarize(
            items, ["all_null", "all_nonnull", "mixed_null"]
        ),
        "null_transition_patterns": {
            pattern: int(count)
            for pattern, count in items.loc[items["mixed_null"], "null_pattern"]
            .value_counts()
            .sort_index()
            .items()
        },
        "all_nonnull_by_declared_type": {},
        "all_null_by_declared_type": {},
    }

    for declared_type in ("categorical", "numeric"):
        all_nonnull = items[(items["declared_type"] == declared_type) & items["all_nonnull"]].copy()
        all_null = items[(items["declared_type"] == declared_type) & items["all_null"]].copy()
        results["all_nonnull_by_declared_type"][declared_type] = summarize(
            all_nonnull, nonnull_metrics
        )
        results["all_null_by_declared_type"][declared_type] = summarize(all_null, metrics)

    output_columns = [
        "sample_id",
        "case_id",
        "field_name",
        "field_class",
        "declared_type",
        "selection_probability",
        "raw_exact",
        "normalized_exact",
        "token_set_exact",
        "all_null",
        "all_nonnull",
        "mixed_null",
        "null_pattern",
        "adjacent_null_transitions",
        "min_pairwise_lexical_similarity",
        "min_pairwise_nonnull_lexical_similarity",
        "lexical_at_least_70",
        "lexical_at_least_80",
        "lexical_at_least_90",
    ]
    items[output_columns].to_csv(ITEM_OUT, index=False, lineterminator="\n")
    OUT.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    categorical_nonnull = results["all_nonnull_by_declared_type"]["categorical"]
    numeric_nonnull = results["all_nonnull_by_declared_type"]["numeric"]
    report_lines = [
        "# Step 11 Repeatability Sensitivity Analysis",
        "",
        "## Scope and model boundary",
        "",
        "This analysis uses the already completed `gpt-5-mini` calls. The historical screening "
        "model is unresolved: the committed script declares `gpt-4.1-mini`, the empirical README "
        "reports `gpt-4o-mini`, and manuscript Section 4.5.1 reports `gpt-4o`. Historical extraction "
        "and evaluator materials consistently declare `gpt-4o-mini` but lack per-call verification. "
        "The results therefore describe a separate prospective experiment on frozen historical "
        "inputs; they do not estimate repeatability of the historical models or validate their outputs.",
        "",
        "The client requested `temperature=0`, and the endpoint accepted every corrected call, but "
        "the retained responses do not expose the effective decoding configuration. The results are "
        "reported as observed same-request repeatability, not as evidence about nominally "
        "deterministic decoding.",
        "",
        "## Null-state decomposition",
        "",
        f"Of 500 extraction items, {results['null_state_counts']['all_null']} were null in all three "
        f"calls, {results['null_state_counts']['all_nonnull']} were non-null in all three calls, and "
        f"{results['null_state_counts']['mixed_null']} ({results['null_state_counts']['mixed_null_unweighted_rate']:.2%}) "
        "changed null status at least once. The mixed-null group contained "
        f"{results['null_state_counts']['mixed_null_by_declared_type']['categorical']} categorical and "
        f"{results['null_state_counts']['mixed_null_by_declared_type']['numeric']} numeric items and "
        f"accounted for {results['null_state_counts']['adjacent_null_transitions']} adjacent state changes. "
        "Its inverse-probability-weighted estimate was "
        f"{results['null_state_design_weighted']['mixed_null']['weighted_estimate']:.2%} "
        f"(case-cluster bootstrap 95% interval "
        f"{results['null_state_design_weighted']['mixed_null']['cluster_bootstrap_95_lower']:.2%}–"
        f"{results['null_state_design_weighted']['mixed_null']['cluster_bootstrap_95_upper']:.2%}). "
        "All-null items are trivially stable and are excluded from the primary non-null comparison.",
        "",
        "## All-non-null outputs",
        "",
        "| Declared type | Items | Raw exact, weighted | Normalized exact, weighted | "
        "Token-set exact, weighted | Minimum pairwise lexical similarity ≥0.80, weighted |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| Categorical | {categorical_nonnull['raw_exact']['items']} | "
            f"{categorical_nonnull['raw_exact']['weighted_estimate']:.2%} | "
            f"{categorical_nonnull['normalized_exact']['weighted_estimate']:.2%} | "
            f"{categorical_nonnull['token_set_exact']['weighted_estimate']:.2%} | "
            f"{categorical_nonnull['nonnull_lexical_at_least_80']['weighted_estimate']:.2%} |"
        ),
        (
            f"| Numeric | {numeric_nonnull['raw_exact']['items']} | "
            f"{numeric_nonnull['raw_exact']['weighted_estimate']:.2%} | "
            f"{numeric_nonnull['normalized_exact']['weighted_estimate']:.2%} | "
            f"{numeric_nonnull['token_set_exact']['weighted_estimate']:.2%} | "
            f"{numeric_nonnull['nonnull_lexical_at_least_80']['weighted_estimate']:.2%} |"
        ),
        "",
        "Normalization uses Unicode NFKC, case folding, punctuation and separator normalization, "
        "whitespace normalization, and a small declared British-to-American spelling map. Token-set "
        "equality additionally ignores token order and duplicate tokens. Lexical thresholds are "
        "reported only as sensitivity analyses; they are not validated semantic-equivalence cutoffs.",
        "",
        "The categorical raw exact rate is therefore not a defensible standalone measure of "
        "instability. Normalization approximately doubles its design-weighted estimate, while the "
        "remaining gap includes both wording variation and potentially substantive output changes. "
        "Numeric non-null outputs remain more stable, but this is a result for the prospective "
        "`gpt-5-mini` experiment only.",
    ]
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
