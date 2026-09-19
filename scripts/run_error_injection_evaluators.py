#!/usr/bin/env python3
"""Run blinded evaluator calls for a prepared error-injection design."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYSTEM_PROMPT = (
    "You are an evidence-synthesis data auditor. Compare one candidate field value with the supplied "
    "source text. Return CORRECT only when the value and its meaning, scale, unit, direction, outcome, "
    "comparator, subgroup, and time point are supported. Return INCORRECT when contradicted. Return "
    "UNVERIFIABLE when the source is insufficient."
)

OUTPUT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "field_verdict",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["CORRECT", "INCORRECT", "UNVERIFIABLE"],
                },
                "evidence": {"type": "string"},
            },
            "required": ["verdict", "evidence"],
            "additionalProperties": False,
        },
    },
}

RESULT_FIELDS = [
    "experiment_item_id",
    "case_id",
    "record_id",
    "field_name",
    "error_type",
    "arm",
    "expected_verdict",
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
    "verdict",
    "evidence",
    "input_tokens",
    "output_tokens",
    "error_type_name",
    "error_message_redacted",
]


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def prompt_for(row: dict[str, str]) -> str:
    return (
        f"Field: {clean(row['field_name'])}\n"
        f"Candidate value: {clean(row['candidate_value'])}\n"
        f"Source text:\n{clean(row['source_text'])}"
    )


def evaluate_one(row: dict[str, str], model_id: str, raw_dir: Path) -> dict[str, Any]:
    from openai import OpenAI

    prompt = prompt_for(row)
    started = datetime.now(timezone.utc)
    status = "api_error"
    error_type_name = ""
    error_message = ""
    response = None
    attempts = 0
    for attempts in range(1, 4):
        try:
            client = OpenAI()
            kwargs: dict[str, Any] = {
                "model": model_id,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "response_format": OUTPUT_SCHEMA,
            }
            if model_id.startswith("gpt-"):
                kwargs["max_completion_tokens"] = 500
            elif model_id.startswith("gemini-"):
                kwargs["max_tokens"] = 500
            response = client.chat.completions.create(**kwargs)
            status = "ok"
            break
        except Exception as exc:
            error_type_name = type(exc).__name__
            error_message = clean(str(exc))[:300]
            if attempts < 3:
                time.sleep(2**attempts)
    ended = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        key: row.get(key, "")
        for key in (
            "experiment_item_id",
            "case_id",
            "record_id",
            "field_name",
            "error_type",
            "arm",
            "expected_verdict",
        )
    }
    result.update(
        {
            "requested_model_id": model_id,
            "returned_model_id": "",
            "call_status": status,
            "attempts": attempts,
            "started_utc": started.isoformat(),
            "ended_utc": ended.isoformat(),
            "latency_ms": int((ended - started).total_seconds() * 1000),
            "request_id": "",
            "system_fingerprint": "",
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "schema_sha256": hashlib.sha256(
                json.dumps(OUTPUT_SCHEMA, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "verdict": "",
            "evidence": "",
            "input_tokens": "",
            "output_tokens": "",
            "error_type_name": error_type_name,
            "error_message_redacted": error_message,
        }
    )
    if response is not None:
        message = json.loads(response.choices[0].message.content)
        result["returned_model_id"] = response.model
        result["request_id"] = getattr(response, "id", "") or ""
        result["system_fingerprint"] = getattr(response, "system_fingerprint", "") or ""
        result["verdict"] = message["verdict"]
        result["evidence"] = clean(message["evidence"])
        usage = getattr(response, "usage", None)
        if usage:
            result["input_tokens"] = getattr(usage, "prompt_tokens", "")
            result["output_tokens"] = getattr(usage, "completion_tokens", "")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{row['experiment_item_id']}__{model_id}.json"
        raw_path.write_text(response.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    design = json.loads((root / "config/error_injection_experiment.json").read_text(encoding="utf-8"))
    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        items = list(csv.DictReader(handle))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not items:
        with args.output.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=RESULT_FIELDS, lineterminator="\n").writeheader()
        return
    expected_items = len(design["error_types"]) * (
        design["initial_injected_items_per_error_type"]
        + design["matched_unchanged_controls_per_error_type"]
    )
    if len(items) != expected_items and not args.allow_partial:
        raise ValueError(f"Expected {expected_items} prepared items, found {len(items)}")
    models = [item["model_id"] for item in design["models"]]
    tasks = [(row, model) for row in items for model in models]
    raw_dir = root / "data/interim/error_injection/raw_responses"
    with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(
            executor.map(lambda pair: evaluate_one(pair[0], pair[1], raw_dir), tasks)
        )
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    main()
