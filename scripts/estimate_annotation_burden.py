#!/usr/bin/env python3
"""Calculate planned human-annotation counts under the frozen stratified design."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def load_cases(path: Path) -> dict[int, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(case["case_id"]): case for case in payload["cases"]}


def case_id_from_name(path: Path) -> int:
    return int(path.name.split("_")[1])


def count_screening(snapshot: Path, per_stratum: int) -> tuple[list[dict], int]:
    rows: list[dict] = []
    total = 0
    for path in sorted((snapshot / "legacy" / "screened").glob("case_*.csv")):
        case_id = case_id_from_name(path)
        counts: Counter[str] = Counter()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                counts[(row.get("llm_decision") or "").strip().upper()] += 1
        for decision in ("INCLUDE", "EXCLUDE"):
            population = counts[decision]
            sample = min(per_stratum, population)
            rows.append(
                {
                    "component": "screening",
                    "case_id": case_id,
                    "field_class": "",
                    "null_status": "",
                    "historical_verdict": decision,
                    "population_count": population,
                    "planned_initial_sample": sample,
                }
            )
            total += sample
    return rows, total


def count_extraction(
    snapshot: Path, cases: dict[int, dict], per_stratum: int
) -> tuple[list[dict], int]:
    rows: list[dict] = []
    total = 0
    for path in sorted((snapshot / "legacy" / "extracted").glob("case_*.csv")):
        case_id = case_id_from_name(path)
        fields = cases[case_id]["historical_extraction"]["fields"]
        field_classes = {field["name"]: field["audit_class"] for field in fields}
        counts: Counter[tuple[str, str, str]] = Counter()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for field_name, field_class in field_classes.items():
                    value = row.get(field_name)
                    null_status = "null" if value is None or not value.strip() else "nonnull"
                    verdict = (row.get(f"judge_{field_name}") or "").strip().upper() or "BLANK"
                    counts[(field_class, null_status, verdict)] += 1
        for (field_class, null_status, verdict), population in sorted(counts.items()):
            sample = min(per_stratum, population)
            rows.append(
                {
                    "component": "extraction",
                    "case_id": case_id,
                    "field_class": field_class,
                    "null_status": null_status,
                    "historical_verdict": verdict,
                    "population_count": population,
                    "planned_initial_sample": sample,
                }
            )
            total += sample
    return rows, total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--screening-per-stratum", type=int, default=30)
    parser.add_argument("--extraction-per-stratum", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    snapshot = root / "data" / "raw_snapshot"
    cases = load_cases(root / "config" / "cases.json")
    screening_rows, screening_total = count_screening(
        snapshot, args.screening_per_stratum
    )
    extraction_rows, extraction_total = count_extraction(
        snapshot, cases, args.extraction_per_stratum
    )
    rows = screening_rows + extraction_rows
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "screening_population_records": sum(
            int(row["population_count"]) for row in screening_rows
        ),
        "screening_initial_sample_records": screening_total,
        "extraction_population_fields": sum(
            int(row["population_count"]) for row in extraction_rows
        ),
        "extraction_initial_sample_fields": extraction_total,
        "screening_strata": len(screening_rows),
        "extraction_nonempty_strata": len(extraction_rows),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
