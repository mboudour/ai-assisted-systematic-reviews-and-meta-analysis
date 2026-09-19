#!/usr/bin/env python3
"""Aggregate archived evaluator outcomes without distributing bibliographic text."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from itertools import product
from pathlib import Path
from typing import Any


VERDICTS = ("CORRECT", "INCORRECT", "UNVERIFIABLE")
FIELD_TYPES = ("categorical", "numeric")
NULL_STATES = ("null", "nonnull")


def read_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/tables/evaluator_verdict_cube.csv"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    extracted_dir = root / "data/raw_snapshot/legacy/extracted"
    counts: Counter[tuple[int, str, str, str]] = Counter()

    cases = read_cases(root / "config/cases.json")
    for case in cases:
        case_id = int(case["case_id"])
        field_types = {
            field["name"]: field["declared_type"]
            for field in case["historical_extraction"]["fields"]
        }
        unexpected_types = set(field_types.values()) - set(FIELD_TYPES)
        if unexpected_types:
            raise ValueError(f"Case {case_id} has unexpected field types: {unexpected_types}")
        path = next(extracted_dir.glob(f"case_{case_id:02d}_*_extracted.csv"))
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for field_name, field_type in field_types.items():
                    value = (row.get(field_name) or "").strip()
                    null_state = "null" if not value else "nonnull"
                    verdict = (row.get(f"judge_{field_name}") or "").strip().upper()
                    if verdict not in VERDICTS:
                        raise ValueError(
                            f"Case {case_id}, field {field_name} has unexpected verdict {verdict!r}"
                        )
                    counts[(case_id, field_type, null_state, verdict)] += 1

    rows = [
        {
            "case_id": case_id,
            "field_type": field_type,
            "null_status": null_status,
            "verdict": verdict,
            "count": counts[(case_id, field_type, null_status, verdict)],
        }
        for case_id, field_type, null_status, verdict in product(
            range(1, 21), FIELD_TYPES, NULL_STATES, VERDICTS
        )
    ]
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(
        json.dumps(
            {
                "rows": len(rows),
                "field_cells": sum(row["count"] for row in rows),
                "verdict_totals": {
                    verdict: sum(
                        row["count"] for row in rows if row["verdict"] == verdict
                    )
                    for verdict in VERDICTS
                },
                "null_verdict_totals": {
                    f"{null_status}_{verdict}": sum(
                        row["count"]
                        for row in rows
                        if row["null_status"] == null_status
                        and row["verdict"] == verdict
                    )
                    for null_status in NULL_STATES
                    for verdict in VERDICTS
                },
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
