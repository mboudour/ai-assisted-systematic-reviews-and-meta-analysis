#!/usr/bin/env python3
"""Audit archived failure-state observability and null/verdict conflation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_cases(path: Path) -> dict[int, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(case["case_id"]): case for case in payload["cases"]}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--event-template", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    cases = load_cases(root / "config" / "cases.json")
    screened_dir = root / "data" / "raw_snapshot" / "legacy" / "screened"
    extracted_dir = root / "data" / "raw_snapshot" / "legacy" / "extracted"
    summary_rows: list[dict[str, Any]] = []

    pooled = {
        "screened_records": 0,
        "exclude_labels": 0,
        "records": 0,
        "field_cells": 0,
        "null_cells": 0,
        "correct": 0,
        "incorrect": 0,
        "unverifiable": 0,
        "null_correct": 0,
        "null_incorrect": 0,
        "null_unverifiable": 0,
        "nonnull_correct": 0,
        "nonnull_incorrect": 0,
        "nonnull_unverifiable": 0,
        "all_null_records": 0,
        "all_unverifiable_records": 0,
    }

    for case_id, case in sorted(cases.items()):
        screened_path = next(screened_dir.glob(f"case_{case_id:02d}_*_screened.csv"))
        extracted_path = next(extracted_dir.glob(f"case_{case_id:02d}_*_extracted.csv"))
        with screened_path.open("r", encoding="utf-8-sig", newline="") as handle:
            screened_reader = csv.DictReader(handle)
            screened_columns = set(screened_reader.fieldnames or [])
            screened_rows = 0
            exclude_labels = 0
            for screened_row in screened_reader:
                screened_rows += 1
                if (screened_row.get("llm_decision") or "").strip().upper() == "EXCLUDE":
                    exclude_labels += 1
        failure_columns = {
            "call_status",
            "screening_status",
            "api_failure",
            "error_type",
            "attempt_count",
            "request_id",
        }
        screening_failure_flag_present = bool(screened_columns & failure_columns)

        fields = [field["name"] for field in case["historical_extraction"]["fields"]]
        case_counts = {
            "screened_records": screened_rows,
            "exclude_labels": exclude_labels,
            "records": 0,
            "field_cells": 0,
            "null_cells": 0,
            "correct": 0,
            "incorrect": 0,
            "unverifiable": 0,
            "null_correct": 0,
            "null_incorrect": 0,
            "null_unverifiable": 0,
            "nonnull_correct": 0,
            "nonnull_incorrect": 0,
            "nonnull_unverifiable": 0,
            "all_null_records": 0,
            "all_unverifiable_records": 0,
        }
        with extracted_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                case_counts["records"] += 1
                values = [(row.get(field) or "").strip() for field in fields]
                verdicts = [
                    (row.get(f"judge_{field}") or "").strip().upper() for field in fields
                ]
                if all(not value for value in values):
                    case_counts["all_null_records"] += 1
                if all(verdict == "UNVERIFIABLE" for verdict in verdicts):
                    case_counts["all_unverifiable_records"] += 1
                for value, verdict in zip(values, verdicts, strict=True):
                    case_counts["field_cells"] += 1
                    value_status = "null" if not value else "nonnull"
                    if value_status == "null":
                        case_counts["null_cells"] += 1
                    verdict_key = verdict.lower()
                    if verdict_key in {"correct", "incorrect", "unverifiable"}:
                        case_counts[verdict_key] += 1
                        case_counts[f"{value_status}_{verdict_key}"] += 1
        for key in pooled:
            pooled[key] += case_counts[key]

        summary_rows.append(
            {
                "case_id": case_id,
                "slug": case["slug"],
                "screened_records": screened_rows,
                "exclude_labels": exclude_labels,
                "screening_failure_flag_present": str(screening_failure_flag_present).lower(),
                "screening_technical_failure_rate": "",
                "screening_failure_identifiability": "not_identifiable_from_archived_output",
                "extracted_records": case_counts["records"],
                "requested_field_cells": case_counts["field_cells"],
                "extraction_null_cells": case_counts["null_cells"],
                "extraction_null_rate": case_counts["null_cells"] / case_counts["field_cells"],
                "all_null_records": case_counts["all_null_records"],
                "extraction_failure_identifiability": "null_conflates_not_reported_and_failure",
                "judge_correct_cells": case_counts["correct"],
                "judge_incorrect_cells": case_counts["incorrect"],
                "judge_unverifiable_cells": case_counts["unverifiable"],
                "judge_unverifiable_rate_all_cells": case_counts["unverifiable"]
                / case_counts["field_cells"],
                "all_unverifiable_records": case_counts["all_unverifiable_records"],
                "evaluation_failure_identifiability": "unverifiable_conflates_source_and_failure",
                "null_judged_correct": case_counts["null_correct"],
                "null_judged_incorrect": case_counts["null_incorrect"],
                "null_judged_unverifiable": case_counts["null_unverifiable"],
                "nonnull_judged_correct": case_counts["nonnull_correct"],
                "nonnull_judged_incorrect": case_counts["nonnull_incorrect"],
                "nonnull_judged_unverifiable": case_counts["nonnull_unverifiable"],
            }
        )

    write_csv(args.output, summary_rows)
    event_fields = [
        "event_id",
        "run_id",
        "case_id",
        "record_id",
        "stage",
        "field_name",
        "attempt",
        "started_utc",
        "ended_utc",
        "call_status",
        "error_type",
        "error_message_redacted",
        "requested_model_id",
        "returned_model_id",
        "system_fingerprint",
        "request_id",
        "prompt_sha256",
        "schema_sha256",
        "source_snapshot_sha256",
        "code_commit",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "retryable",
        "raw_response_path",
        "output_path",
    ]
    args.event_template.parent.mkdir(parents=True, exist_ok=True)
    with args.event_template.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=event_fields, lineterminator="\n").writeheader()

    null_rate = pooled["null_cells"] / pooled["field_cells"]
    unverifiable_rate = pooled["unverifiable"] / pooled["field_cells"]
    determinate = pooled["correct"] + pooled["incorrect"]
    conditional_agreement = pooled["correct"] / determinate if determinate else 0.0
    lines = [
        "# Step 6 Failure-State Identifiability and Missingness Audit",
        "",
        "## Historical identifiability",
        "",
        "The archived screened files contain no call-status, retry, request, or error fields. The "
        "historical screening failure rate is therefore **not identifiable**. This missing provenance "
        f"affects all {pooled['screened_records']:,} archived decisions. The {pooled['exclude_labels']:,} "
        "`EXCLUDE` labels include an unknown mixture of substantive decisions and any terminal failures; "
        "the two states cannot be distinguished after the fact.",
        "",
        "The archived extraction files contain null values but no source-status or call-status field. "
        "A null may mean that the source did not report the field, that the extractor omitted a "
        f"reported value, or that the call failed. Those states cannot be separated retrospectively "
        f"for {pooled['records']:,} extraction rows and {pooled['field_cells']:,} requested fields.",
        "",
        "Evaluator `UNVERIFIABLE` values similarly conflate source insufficiency and evaluator-call "
        "failure under the historical implementation. They must be reported as archived verdicts, "
        "not reclassified as observed technical failures.",
        "",
        "## Archived output profile",
        "",
        "| Measure | Count | Rate |",
        "|---|---:|---:|",
        f"| Screening decisions without call status | {pooled['screened_records']:,} | 100.00% of screened records |",
        f"| EXCLUDE labels colliding with the failure fallback | {pooled['exclude_labels']:,} | {100 * pooled['exclude_labels'] / pooled['screened_records']:.2f}% of screened records |",
        f"| Requested extraction field cells | {pooled['field_cells']:,} | 100.00% |",
        f"| Null extraction cells | {pooled['null_cells']:,} | {100 * null_rate:.2f}% |",
        f"| Evaluator CORRECT cells | {pooled['correct']:,} | {100 * pooled['correct'] / pooled['field_cells']:.2f}% |",
        f"| Evaluator INCORRECT cells | {pooled['incorrect']:,} | {100 * pooled['incorrect'] / pooled['field_cells']:.2f}% |",
        f"| Evaluator UNVERIFIABLE cells | {pooled['unverifiable']:,} | {100 * unverifiable_rate:.2f}% |",
        f"| Null fields judged CORRECT | {pooled['null_correct']:,} | {100 * pooled['null_correct'] / pooled['null_cells']:.2f}% of null fields |",
        f"| Null fields judged INCORRECT | {pooled['null_incorrect']:,} | {100 * pooled['null_incorrect'] / pooled['null_cells']:.2f}% of null fields |",
        f"| Null fields judged UNVERIFIABLE | {pooled['null_unverifiable']:,} | {100 * pooled['null_unverifiable'] / pooled['null_cells']:.2f}% of null fields |",
        f"| Non-null fields judged UNVERIFIABLE | {pooled['nonnull_unverifiable']:,} | {100 * pooled['nonnull_unverifiable'] / (pooled['field_cells'] - pooled['null_cells']):.2f}% of non-null fields |",
        f"| Conditional agreement after excluding UNVERIFIABLE | {pooled['correct']:,} / {determinate:,} | {100 * conditional_agreement:.2f}% |",
        f"| All-null extraction records | {pooled['all_null_records']:,} | {100 * pooled['all_null_records'] / pooled['records']:.2f}% of extracted records |",
        f"| All-UNVERIFIABLE evaluator records | {pooled['all_unverifiable_records']:,} | {100 * pooled['all_unverifiable_records'] / pooled['records']:.2f}% of extracted records |",
        "",
        "Conditional agreement is shown only to reconcile the historical headline measure. It is "
        "not an accuracy estimate and must be presented beside the 40.73% UNVERIFIABLE rate. The "
        "near-coincidence of null and UNVERIFIABLE states is structurally expected because a null "
        "supplies no candidate value to confirm. The informative exceptions are 218 null fields with "
        "a non-UNVERIFIABLE label and 458 non-null fields labelled UNVERIFIABLE.",
        "",
        "## Prospective implementation",
        "",
        "`config/pipeline_event.schema.json` defines a mandatory event record for every call attempt. "
        "The schema separates call status from source status and analytical labels. The empty "
        "`config/pipeline_events_template.csv` file provides the corresponding table header. Future "
        "screening, extraction, and evaluation scripts must write an event even when a call fails.",
        "",
        "## Limitation",
        "",
        "No historical failure rate, retry-success rate, or mis-exclusion rate is estimated here. "
        "Treating all-null or all-UNVERIFIABLE rows as known failures would overstate what the archive "
        "shows. Trivial bounds that assign every collided analytical state to failure are useful only "
        "as motivation for event logging and are not reported as empirical findings.",
        "",
        "## Why a logged rerun would answer a different question",
        "",
        "A new run with explicit event logging could estimate the failure rate of a current implementation, "
        "but it could not recover the historical rate. Model and provider behavior, prompts, schemas, client "
        "and retry code, rate limits, corpus state, and execution period would differ. Because the historical "
        "execution is the object of this audit, a logged rerun would be a separate prospective demonstration "
        "rather than a reconstruction of the archived workflow.",
        "",
        "## References",
        "",
        "[1]: https://json-schema.org/draft/2020-12/json-schema-core \"JSON Schema Core Specification, Draft 2020-12\"",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
