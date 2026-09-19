#!/usr/bin/env python3
"""Run a prospective three-repeat LLM stability audit on frozen sampled items."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_ID = "gpt-5-mini"
MASTER_SEED = 20260919

RESULT_FIELDS = [
    "task",
    "sample_id",
    "case_id",
    "field_name",
    "repeat_index",
    "requested_model_id",
    "returned_model_id",
    "call_status",
    "attempts",
    "started_utc",
    "ended_utc",
    "latency_ms",
    "request_id",
    "system_fingerprint",
    "prompt_sha256",
    "schema_sha256",
    "output_value",
    "output_reason",
    "input_tokens",
    "output_tokens",
    "error_type",
    "error_message_redacted",
]

SCREENING_SYSTEM = (
    "You are an expert systematic review screener. Apply only the supplied criteria to the title "
    "and abstract. Return INCLUDE or EXCLUDE and a concise reason."
)
EXTRACTION_SYSTEM = (
    "You are an expert data extractor for systematic reviews. Extract only the requested field from "
    "the title and abstract. Set is_null to true and value_text to an empty string when the field "
    "cannot be determined from the supplied text. Otherwise set is_null to false and return the "
    "value as plain text without extra commentary."
)


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def stable_rank(namespace: str, sample_id: str) -> str:
    return hashlib.sha256(
        f"{MASTER_SEED}|{namespace}|{sample_id}".encode("utf-8")
    ).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def schema_for(task: str) -> dict[str, Any]:
    if task == "screening":
        properties = {
            "decision": {"type": "string", "enum": ["INCLUDE", "EXCLUDE"]},
            "reason": {"type": "string"},
        }
        name = "screening_decision"
    else:
        properties = {
            "value_text": {"type": "string"},
            "is_null": {"type": "boolean"},
            "reason": {"type": "string"},
        }
        name = "single_field_extraction"
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


def prompt_for(task: str, row: dict[str, str]) -> str:
    if task == "screening":
        return (
            f"Inclusion criteria: {clean(row['inclusion_criteria'])}\n"
            f"Title: {clean(row['title'])}\n"
            f"Abstract: {clean(row['abstract'])}"
        )
    return (
        f"Requested field: {clean(row['field_name'])}\n"
        f"Declared type: {clean(row['declared_type'])}\n"
        f"Title: {clean(row['title'])}\n"
        f"Abstract: {clean(row['abstract'])}"
    )


def task_key(task: str, sample_id: str, repeat_index: int | str) -> tuple[str, str, int]:
    return task, sample_id, int(repeat_index)


def raw_path_for(raw_dir: Path, task: str, sample_id: str, repeat_index: int) -> Path:
    return raw_dir / f"{task}__{sample_id}__r{repeat_index}.json"


def base_result(
    task: str,
    row: dict[str, str],
    repeat_index: int,
    started: str,
    ended: str,
    latency_ms: int | str,
    attempts: int,
) -> dict[str, Any]:
    prompt = prompt_for(task, row)
    response_schema = schema_for(task)
    return {
        "task": task,
        "sample_id": row["sample_id"],
        "case_id": row["case_id"],
        "field_name": row.get("field_name", ""),
        "repeat_index": repeat_index,
        "requested_model_id": MODEL_ID,
        "returned_model_id": "",
        "call_status": "api_error",
        "attempts": attempts,
        "started_utc": started,
        "ended_utc": ended,
        "latency_ms": latency_ms,
        "request_id": "",
        "system_fingerprint": "",
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "schema_sha256": hashlib.sha256(
            json.dumps(response_schema, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "output_value": "",
        "output_reason": "",
        "input_tokens": "",
        "output_tokens": "",
        "error_type": "",
        "error_message_redacted": "",
    }


def populate_from_raw(
    result: dict[str, Any],
    task: str,
    raw: dict[str, Any],
    declared_type: str = "",
) -> dict[str, Any]:
    result["returned_model_id"] = raw.get("model", "") or ""
    result["request_id"] = raw.get("id", "") or ""
    result["system_fingerprint"] = raw.get("system_fingerprint", "") or ""
    usage = raw.get("usage") or {}
    result["input_tokens"] = usage.get("prompt_tokens", "")
    result["output_tokens"] = usage.get("completion_tokens", "")
    try:
        content = raw["choices"][0]["message"]["content"]
        payload = json.loads(content)
        if task == "screening":
            value = payload["decision"]
        elif payload["is_null"]:
            value = None
        elif declared_type == "numeric":
            try:
                value = float(payload["value_text"])
            except ValueError:
                value = payload["value_text"]
        else:
            value = payload["value_text"]
        result["output_value"] = json.dumps(value, ensure_ascii=False)
        result["output_reason"] = clean(payload["reason"])
        result["call_status"] = "ok"
    except Exception as exc:
        result["call_status"] = "response_parse_error"
        result["error_type"] = type(exc).__name__
        result["error_message_redacted"] = clean(str(exc))[:300]
    return result


def recover_raw(
    task: str,
    row: dict[str, str],
    repeat_index: int,
    raw_path: Path,
) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    created = raw.get("created")
    timestamp = (
        datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        if isinstance(created, (int, float))
        else ""
    )
    result = base_result(task, row, repeat_index, timestamp, timestamp, "", 1)
    return populate_from_raw(result, task, raw, row.get("declared_type", ""))


def one_call(
    task: str,
    row: dict[str, str],
    repeat_index: int,
    raw_dir: Path,
) -> dict[str, Any]:
    from openai import OpenAI

    prompt = prompt_for(task, row)
    response_schema = schema_for(task)
    started_dt = datetime.now(timezone.utc)
    response = None
    attempts = 0
    error_type = ""
    error_message = ""
    for attempts in range(1, 4):
        try:
            client = OpenAI(timeout=90.0, max_retries=0)
            response = client.chat.completions.create(
                model=MODEL_ID,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": SCREENING_SYSTEM if task == "screening" else EXTRACTION_SYSTEM,
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=response_schema,
                max_completion_tokens=400,
            )
            break
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = clean(str(exc))[:300]
            if attempts < 3:
                time.sleep(2**attempts)
    ended_dt = datetime.now(timezone.utc)
    result = base_result(
        task,
        row,
        repeat_index,
        started_dt.isoformat(),
        ended_dt.isoformat(),
        int((ended_dt - started_dt).total_seconds() * 1000),
        attempts,
    )
    result["error_type"] = error_type
    result["error_message_redacted"] = error_message
    if response is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_path_for(raw_dir, task, row["sample_id"], repeat_index)
        raw_path.write_text(response.model_dump_json(indent=2) + "\n", encoding="utf-8")
        result = populate_from_raw(
            result,
            task,
            json.loads(response.model_dump_json()),
            row.get("declared_type", ""),
        )
    return result


def write_results(path: Path, results_by_key: dict[tuple[str, str, int], dict[str, Any]]) -> None:
    rows = sorted(
        results_by_key.values(),
        key=lambda row: (row["task"], row["sample_id"], int(row["repeat_index"])),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--screening-n", type=int, default=200)
    parser.add_argument("--extraction-n", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    screening = read_rows(root / "data/interim/annotation_packets/screening_reviewer_a.csv")
    extraction = read_rows(root / "data/interim/annotation_packets/extraction_reviewer_a.csv")
    screening.sort(key=lambda row: stable_rank("screening", row["sample_id"]))
    extraction.sort(key=lambda row: stable_rank("extraction", row["sample_id"]))
    selected = [
        ("screening", row, repeat_index)
        for row in screening[: args.screening_n]
        for repeat_index in range(1, args.repeats + 1)
    ] + [
        ("extraction", row, repeat_index)
        for row in extraction[: args.extraction_n]
        for repeat_index in range(1, args.repeats + 1)
    ]
    selected_keys = {
        task_key(task, row["sample_id"], repeat_index)
        for task, row, repeat_index in selected
    }
    raw_dir = root / "data/interim/repeatability/raw_responses"
    results_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}

    if args.output.exists():
        for prior in read_rows(args.output):
            key = task_key(prior["task"], prior["sample_id"], prior["repeat_index"])
            if key in selected_keys and prior["call_status"] != "response_parse_error":
                results_by_key[key] = prior

    recovered = 0
    for task, row, repeat_index in selected:
        key = task_key(task, row["sample_id"], repeat_index)
        if key in results_by_key:
            continue
        raw_path = raw_path_for(raw_dir, task, row["sample_id"], repeat_index)
        if raw_path.exists():
            candidate = recover_raw(task, row, repeat_index, raw_path)
            if candidate["call_status"] == "ok":
                results_by_key[key] = candidate
                recovered += 1
    write_results(args.output, results_by_key)

    pending = [
        (task, row, repeat_index)
        for task, row, repeat_index in selected
        if task_key(task, row["sample_id"], repeat_index) not in results_by_key
    ]
    print(
        f"recovered={recovered} retained={len(results_by_key)} pending={len(pending)} total={len(selected)}",
        flush=True,
    )
    if not pending:
        return

    with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(one_call, task, row, repeat_index, raw_dir): (
                task,
                row["sample_id"],
                repeat_index,
            )
            for task, row, repeat_index in pending
        }
        for completed, future in enumerate(futures.as_completed(future_map), start=1):
            key = future_map[future]
            results_by_key[key] = future.result()
            if completed % 25 == 0 or completed == len(future_map):
                write_results(args.output, results_by_key)
            if completed % 100 == 0 or completed == len(future_map):
                print(
                    f"completed_this_run={completed}/{len(future_map)} total_retained={len(results_by_key)}/{len(selected)}",
                    flush=True,
                )
    write_results(args.output, results_by_key)


if __name__ == "__main__":
    main()
