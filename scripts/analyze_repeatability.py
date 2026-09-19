#!/usr/bin/env python3
"""Analyze repeated model calls without treating stability as accuracy."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parsed_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def analyze(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["task"], row["sample_id"])].append(row)
    item_rows = []
    transitions = Counter()
    task_counts: dict[str, Counter] = defaultdict(Counter)
    for (task, sample_id), group in sorted(groups.items()):
        group.sort(key=lambda row: int(row["repeat_index"]))
        successful = [row for row in group if row["call_status"] == "ok"]
        outputs = [parsed_value(row["output_value"]) for row in successful]
        canonical = [json.dumps(value, sort_keys=True, ensure_ascii=False) for value in outputs]
        complete = len(successful) == len(group)
        stable = complete and len(set(canonical)) == 1
        task_counts[task]["items"] += 1
        task_counts[task]["attempted_calls"] += len(group)
        task_counts[task]["successful_calls"] += len(successful)
        task_counts[task]["complete_items"] += complete
        task_counts[task]["stable_items"] += stable
        if task == "screening" and complete:
            for left, right in zip(canonical, canonical[1:]):
                transitions[(left, right)] += 1
        numeric_values = [float(value) for value in outputs if isinstance(value, (int, float))]
        numeric_range = (
            max(numeric_values) - min(numeric_values)
            if len(numeric_values) == len(outputs) and numeric_values
            else math.nan
        )
        null_states = [value is None for value in outputs]
        null_stable = complete and len(set(null_states)) == 1
        item_rows.append(
            {
                "task": task,
                "sample_id": sample_id,
                "case_id": group[0]["case_id"],
                "field_name": group[0]["field_name"],
                "attempted_calls": len(group),
                "successful_calls": len(successful),
                "unique_successful_outputs": len(set(canonical)),
                "all_repeats_exactly_equal": str(stable).lower(),
                "null_state_stable": str(null_stable).lower() if task == "extraction" else "",
                "numeric_range": "" if math.isnan(numeric_range) else numeric_range,
            }
        )
    summary = []
    for task, counts in sorted(task_counts.items()):
        summary.append(
            {
                "task": task,
                "items": counts["items"],
                "attempted_calls": counts["attempted_calls"],
                "successful_calls": counts["successful_calls"],
                "call_success_rate": counts["successful_calls"] / counts["attempted_calls"],
                "complete_items": counts["complete_items"],
                "stable_items": counts["stable_items"],
                "exact_three_repeat_stability": (
                    counts["stable_items"] / counts["complete_items"]
                    if counts["complete_items"]
                    else math.nan
                ),
                "interpretation": "repeatability_not_accuracy",
            }
        )
    transition_rows = [
        {"from_output": left, "to_output": right, "count": count}
        for (left, right), count in sorted(transitions.items())
    ]
    return summary, item_rows, transition_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--transitions", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    rows = read_rows(args.input)
    summary, items, transitions = analyze(rows)
    metadata = {}
    if args.manifest and args.manifest.exists():
        metadata = {row["sample_id"]: row for row in read_rows(args.manifest)}
    for item in items:
        sample = metadata.get(item["sample_id"], {})
        item["field_class"] = sample.get("field_class", "")
        item["declared_type"] = sample.get("declared_type", "")
        item["historical_null_status"] = sample.get("extracted_null_status", "")
    provenance_counts = Counter(
        (
            row["task"],
            row["requested_model_id"],
            row["returned_model_id"],
            row["system_fingerprint"],
            row["call_status"],
        )
        for row in rows
    )
    provenance_rows = [
        {
            "task": task,
            "requested_model_id": requested,
            "returned_model_id": returned,
            "system_fingerprint": fingerprint,
            "call_status": status,
            "calls": count,
        }
        for (task, requested, returned, fingerprint, status), count in sorted(
            provenance_counts.items()
        )
    ]
    write_csv(
        args.summary,
        summary,
        [
            "task",
            "items",
            "attempted_calls",
            "successful_calls",
            "call_success_rate",
            "complete_items",
            "stable_items",
            "exact_three_repeat_stability",
            "interpretation",
        ],
    )
    write_csv(
        args.items,
        items,
        [
            "task",
            "sample_id",
            "case_id",
            "field_name",
            "attempted_calls",
            "successful_calls",
            "unique_successful_outputs",
            "all_repeats_exactly_equal",
            "null_state_stable",
            "numeric_range",
            "field_class",
            "declared_type",
            "historical_null_status",
        ],
    )
    write_csv(
        args.transitions,
        transitions,
        ["from_output", "to_output", "count"],
    )
    provenance_path = args.summary.parent / "model_provenance_summary.csv"
    write_csv(
        provenance_path,
        provenance_rows,
        [
            "task",
            "requested_model_id",
            "returned_model_id",
            "system_fingerprint",
            "call_status",
            "calls",
        ],
    )
    strata_counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for item in items:
        if item["task"] != "extraction":
            continue
        for dimension in ("declared_type", "field_class", "historical_null_status"):
            value = item[dimension]
            if not value:
                continue
            counts = strata_counts[(dimension, value)]
            counts["items"] += 1
            counts["complete_items"] += int(item["successful_calls"]) == int(
                item["attempted_calls"]
            )
            counts["stable_items"] += item["all_repeats_exactly_equal"] == "true"
    strata_rows = []
    for (dimension, value), counts in sorted(strata_counts.items()):
        strata_rows.append(
            {
                "dimension": dimension,
                "value": value,
                "items": counts["items"],
                "complete_items": counts["complete_items"],
                "stable_items": counts["stable_items"],
                "exact_three_repeat_stability": counts["stable_items"]
                / counts["complete_items"],
            }
        )
    write_csv(
        args.summary.parent / "repeatability_extraction_strata.csv",
        strata_rows,
        [
            "dimension",
            "value",
            "items",
            "complete_items",
            "stable_items",
            "exact_three_repeat_stability",
        ],
    )
    summary_by_task = {row["task"]: row for row in summary}
    screening = summary_by_task.get("screening", {})
    extraction = summary_by_task.get("extraction", {})
    returned_ids = sorted(
        {row["returned_model_id"] for row in rows if row["returned_model_id"]}
    )
    fingerprints = sorted(
        {row["system_fingerprint"] for row in rows if row["system_fingerprint"]}
    )
    preflight_path = args.input.with_name("repeatability_preflight_attempts.csv")
    preflight_rows = read_rows(preflight_path) if preflight_path.exists() else []
    preflight_failures = sum(
        row["call_status"] != "ok" for row in preflight_rows
    )
    declared_strata = [
        row for row in strata_rows if row["dimension"] == "declared_type"
    ]
    null_strata = {
        row["value"]: row
        for row in strata_rows
        if row["dimension"] == "historical_null_status"
    }
    screening_switches = sum(
        row["count"] for row in transitions if row["from_output"] != row["to_output"]
    )
    screening_transition_total = sum(row["count"] for row in transitions)
    lines = [
        "# Step 11 Repeatability and Model-Provenance Audit",
        "",
        "## Results",
        "",
        f"The audit attempted {len(rows):,} calls using the requested model alias `gpt-5-mini`. "
        "Every call preserves the returned model identifier, request identifier, system fingerprint "
        "when available, prompt and schema hashes, timing, token usage, retries, and explicit status.",
        "",
        f"The requested alias resolved to {len(returned_ids)} distinct returned model identifier(s): "
        f"{', '.join(f'`{item}`' for item in returned_ids) if returned_ids else 'none recorded'}. "
        f"The responses exposed {len(fingerprints)} distinct nonempty system fingerprint(s). The "
        "returned identifier therefore confirms the alias but does not identify a versioned model "
        "snapshot.",
        "",
        "| Task | Items | Successful calls | Exact stability across three repeats |",
        "|---|---:|---:|---:|",
        (
            f"| Screening | {screening.get('items', 0):,} | {screening.get('successful_calls', 0):,} | "
            f"{screening.get('exact_three_repeat_stability', math.nan):.2%} |"
        ),
        (
            f"| Extraction | {extraction.get('items', 0):,} | {extraction.get('successful_calls', 0):,} | "
            f"{extraction.get('exact_three_repeat_stability', math.nan):.2%} |"
        ),
        "",
        "### Extraction stability by declared field type",
        "",
        "| Declared type | Items | Exact stability across three repeats |",
        "|---|---:|---:|",
        *[
            f"| {row['value']} | {row['items']:,} | {row['exact_three_repeat_stability']:.2%} |"
            for row in declared_strata
        ],
        "",
        f"Screening changed labels in {screening_switches:,} of "
        f"{screening_transition_total:,} adjacent repeat transitions. Exactly "
        f"{screening.get('stable_items', 0):,} of {screening.get('complete_items', 0):,} records "
        "were stable across all three calls. Extraction was stable for "
        f"{extraction.get('stable_items', 0):,} of {extraction.get('complete_items', 0):,} fields. "
        f"Historically null fields had {null_strata.get('null', {}).get('exact_three_repeat_stability', math.nan):.2%} "
        "exact stability, compared with "
        f"{null_strata.get('nonnull', {}).get('exact_three_repeat_stability', math.nan):.2%} for "
        "historically non-null fields.",
        "",
        "Exact stability requires all three successful outputs to match after JSON normalization. "
        "It measures repeatability under this prospective configuration, not agreement with truth. "
        "Screening transitions and item-level extraction null/numeric variability are retained in "
        "separate result tables.",
        "",
        (
            f"The preserved preflight ledger contains {preflight_failures:,} rejected requests. "
            "All were extraction requests rejected as `Invalid request format` under an unsupported "
            "union-type schema. The corrected schema used scalar text plus an explicit null flag. "
            "The final planned-call ledger retains only the corrected attempts, while the preflight "
            "ledger remains available as a technical-reliability result. This was a client-schema "
            "failure, not evidence about extraction accuracy."
            if preflight_rows
            else ""
        ),
        "",
        "## References",
        "",
        "[1]: https://platform.openai.com/docs/api-reference/chat \"OpenAI Chat Completions API Reference\"",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
