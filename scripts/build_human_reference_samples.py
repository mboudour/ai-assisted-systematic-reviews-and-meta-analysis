#!/usr/bin/env python3
"""Create deterministic, blinded human-reference samples and annotation forms."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

MASTER_SEED = 20260919


def stable_hash(*parts: Any) -> str:
    payload = "|".join(str(part) for part in (MASTER_SEED, *parts)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_doi(value: str) -> str:
    doi = (value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip()


def normalize_text(value: str) -> str:
    return " ".join((value or "").split())


def normalize_year(value: str) -> str:
    year = normalize_text(value)
    if not year:
        return ""
    try:
        numeric = float(year)
        return str(int(numeric)) if numeric.is_integer() else year
    except ValueError:
        return year


def record_id(row: dict[str, str], case_id: int, row_number: int, extracted: bool = False) -> str:
    doi = normalize_doi(row.get("_doi" if extracted else "doi", "") or "")
    title = normalize_text(row.get("_title" if extracted else "title", "") or "").lower()
    year = normalize_year(row.get("_year" if extracted else "year", "") or "")
    identity = f"doi:{doi}" if doi else f"title_year:{stable_hash(title, year)}"
    return stable_hash(case_id, row_number, identity)[:24]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        if not rows:
            raise ValueError(f"fieldnames required for empty file: {path}")
        fieldnames = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_cases(path: Path) -> dict[int, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(case["case_id"]): case for case in payload["cases"]}


def build_screening_sample(
    root: Path, cases: dict[int, dict], per_stratum: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_rows: list[dict[str, Any]] = []
    packet_rows: list[dict[str, Any]] = []
    screened_dir = root / "data" / "raw_snapshot" / "legacy" / "screened"
    for path in sorted(screened_dir.glob("case_*.csv")):
        case_id = int(path.name.split("_")[1])
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        strata: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
        for row_number, row in enumerate(rows, start=2):
            decision = (row.get("llm_decision") or "").strip().upper()
            if decision not in {"INCLUDE", "EXCLUDE"}:
                continue
            strata[decision].append((row_number, row))
        for decision in ("INCLUDE", "EXCLUDE"):
            members = strata[decision]
            members.sort(key=lambda item: stable_hash("screening", case_id, decision, item[0]))
            selected = members[: min(per_stratum, len(members))]
            selection_probability = len(selected) / len(members)
            for row_number, row in selected:
                rec_id = record_id(row, case_id, row_number)
                sample_id = f"SCR-{case_id:02d}-{stable_hash(rec_id, decision)[:12]}"
                manifest_rows.append(
                    {
                        "sample_id": sample_id,
                        "case_id": case_id,
                        "record_id": rec_id,
                        "source_row_number": row_number,
                        "historical_llm_decision": decision,
                        "stratum_population": len(members),
                        "stratum_sample": len(selected),
                        "selection_probability": selection_probability,
                        "master_seed": MASTER_SEED,
                    }
                )
                packet_rows.append(
                    {
                        "sample_id": sample_id,
                        "case_id": case_id,
                        "record_id": rec_id,
                        "inclusion_criteria": cases[case_id]["historical_screening"]["inclusion_criteria"],
                        "title": normalize_text(row.get("title", "") or ""),
                        "abstract": normalize_text(row.get("abstract", "") or ""),
                        "reviewer_id": "",
                        "human_screening_label": "",
                        "primary_exclusion_reason": "",
                        "confidence_1_to_5": "",
                        "review_notes": "",
                    }
                )
    return manifest_rows, packet_rows


def build_extraction_sample(
    root: Path, cases: dict[int, dict], per_stratum: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_rows: list[dict[str, Any]] = []
    packet_rows: list[dict[str, Any]] = []
    extracted_dir = root / "data" / "raw_snapshot" / "legacy" / "extracted"
    screened_dir = root / "data" / "raw_snapshot" / "legacy" / "screened"
    for path in sorted(extracted_dir.glob("case_*.csv")):
        case_id = int(path.name.split("_")[1])
        screened_path = next(screened_dir.glob(f"case_{case_id:02d}_*_screened.csv"))
        with screened_path.open("r", encoding="utf-8-sig", newline="") as handle:
            screened_rows = list(csv.DictReader(handle))
        screened_by_title = {
            normalize_text(row.get("title", "") or "").lower(): row for row in screened_rows
        }
        fields = cases[case_id]["historical_extraction"]["fields"]
        strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                title = normalize_text(row.get("_title", "") or "")
                source_row = screened_by_title.get(title.lower(), {})
                rec_id = record_id(row, case_id, row_number, extracted=True)
                for field in fields:
                    field_name = field["name"]
                    value = (row.get(field_name) or "").strip()
                    null_status = "null" if not value else "nonnull"
                    verdict = (row.get(f"judge_{field_name}") or "").strip().upper() or "BLANK"
                    member = {
                        "case_id": case_id,
                        "record_id": rec_id,
                        "source_row_number": row_number,
                        "field_name": field_name,
                        "field_class": field["audit_class"],
                        "declared_type": field["declared_type"],
                        "null_status": null_status,
                        "historical_verdict": verdict,
                        "title": title,
                        "abstract": normalize_text(source_row.get("abstract", "") or ""),
                        "extracted_value": value,
                    }
                    strata[(field["audit_class"], null_status, verdict)].append(member)
        for stratum, members in sorted(strata.items()):
            members.sort(
                key=lambda item: stable_hash(
                    "extraction",
                    case_id,
                    *stratum,
                    item["record_id"],
                    item["field_name"],
                )
            )
            selected = members[: min(per_stratum, len(members))]
            selection_probability = len(selected) / len(members)
            for member in selected:
                sample_id = (
                    f"EXT-{case_id:02d}-"
                    f"{stable_hash(member['record_id'], member['field_name'], *stratum)[:12]}"
                )
                manifest_rows.append(
                    {
                        "sample_id": sample_id,
                        "case_id": case_id,
                        "record_id": member["record_id"],
                        "source_row_number": member["source_row_number"],
                        "field_name": member["field_name"],
                        "field_class": member["field_class"],
                        "declared_type": member["declared_type"],
                        "extracted_null_status": member["null_status"],
                        "historical_evaluator_verdict": member["historical_verdict"],
                        "stratum_population": len(members),
                        "stratum_sample": len(selected),
                        "selection_probability": selection_probability,
                        "master_seed": MASTER_SEED,
                    }
                )
                packet_rows.append(
                    {
                        "sample_id": sample_id,
                        "case_id": case_id,
                        "record_id": member["record_id"],
                        "field_name": member["field_name"],
                        "declared_type": member["declared_type"],
                        "title": member["title"],
                        "abstract": member["abstract"],
                        "extracted_value": member["extracted_value"],
                        "reviewer_id": "",
                        "source_status": "",
                        "human_field_label": "",
                        "corrected_value": "",
                        "corrected_unit": "",
                        "evidence_quote": "",
                        "confidence_1_to_5": "",
                        "review_notes": "",
                    }
                )
    return manifest_rows, packet_rows


def reviewer_packet(rows: list[dict[str, Any]], reviewer_id: str) -> list[dict[str, Any]]:
    packet = [dict(row, reviewer_id=reviewer_id) for row in rows]
    packet.sort(key=lambda row: stable_hash(reviewer_id, row["sample_id"]))
    return packet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--screening-per-stratum", type=int, default=30)
    parser.add_argument("--extraction-per-stratum", type=int, default=10)
    args = parser.parse_args()
    root = args.root.resolve()
    cases = load_cases(root / "config" / "cases.json")
    screening_manifest, screening_packet = build_screening_sample(
        root, cases, args.screening_per_stratum
    )
    extraction_manifest, extraction_packet = build_extraction_sample(
        root, cases, args.extraction_per_stratum
    )

    write_csv(root / "data/manifests/screening_sample_manifest.csv", screening_manifest)
    write_csv(root / "data/manifests/extraction_sample_manifest.csv", extraction_manifest)
    local_dir = root / "data" / "interim" / "annotation_packets"
    for reviewer_id in ("A", "B"):
        write_csv(
            local_dir / f"screening_reviewer_{reviewer_id.lower()}.csv",
            reviewer_packet(screening_packet, reviewer_id),
        )
        write_csv(
            local_dir / f"extraction_reviewer_{reviewer_id.lower()}.csv",
            reviewer_packet(extraction_packet, reviewer_id),
        )

    screening_template_fields = [
        "sample_id",
        "reviewer_id",
        "human_screening_label",
        "primary_exclusion_reason",
        "confidence_1_to_5",
        "review_notes",
    ]
    extraction_template_fields = [
        "sample_id",
        "reviewer_id",
        "source_status",
        "human_field_label",
        "corrected_value",
        "corrected_unit",
        "evidence_quote",
        "confidence_1_to_5",
        "review_notes",
    ]
    write_csv(
        root / "annotations/forms/screening_annotation_template.csv",
        [],
        screening_template_fields,
    )
    write_csv(
        root / "annotations/forms/extraction_annotation_template.csv",
        [],
        extraction_template_fields,
    )
    summary = {
        "master_seed": MASTER_SEED,
        "screening_population_records": 94522,
        "screening_sample_records": len(screening_manifest),
        "extraction_population_fields": 90554,
        "extraction_sample_fields": len(extraction_manifest),
        "reviewers": 2,
        "local_packet_directory": "data/interim/annotation_packets",
        "reviewer_blinding": {
            "screening_historical_decision_hidden": True,
            "extraction_historical_evaluator_verdict_hidden": True,
        },
    }
    (root / "data/manifests/human_reference_sample.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
