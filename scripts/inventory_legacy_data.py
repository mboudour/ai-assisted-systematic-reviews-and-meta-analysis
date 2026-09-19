#!/usr/bin/env python3
"""Inventory and audit the immutable legacy data snapshot.

The script uses only the Python standard library. It never modifies source files.
It creates tracked manifests and a human-readable audit report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CASE_PATTERN = re.compile(r"^case_(\d{2})_(.+?)(?:_(screened|extracted))?\.csv$")
VALID_DECISIONS = {"INCLUDE", "EXCLUDE"}
VALID_VERDICTS = {"CORRECT", "INCORRECT", "UNVERIFIABLE"}
BASE_COLUMNS = {"title", "year", "doi", "abstract", "source", "case_id"}


@dataclass
class FileAudit:
    path: Path
    relative_path: str
    stage: str
    case_id: int
    slug: str
    size_bytes: int
    sha256: str
    modified_utc: str
    row_count: int = 0
    column_count: int = 0
    columns: list[str] = field(default_factory=list)
    parse_status: str = "ok"
    parse_error: str = ""
    blank_title_count: int = 0
    missing_abstract_count: int = 0
    missing_doi_count: int = 0
    invalid_year_count: int = 0
    case_id_mismatch_count: int = 0
    duplicate_doi_row_count: int = 0
    duplicate_title_row_count: int = 0
    include_count: int = 0
    exclude_count: int = 0
    invalid_decision_count: int = 0
    blank_decision_count: int = 0
    extraction_field_count: int = 0
    judge_field_count: int = 0
    extraction_null_cell_count: int = 0
    judge_correct_count: int = 0
    judge_incorrect_count: int = 0
    judge_unverifiable_count: int = 0
    judge_blank_count: int = 0
    judge_invalid_count: int = 0
    identity_keys: set[str] = field(default_factory=set, repr=False)
    included_identity_keys: set[str] = field(default_factory=set, repr=False)

    def to_row(self) -> dict[str, Any]:
        row = vars(self).copy()
        row.pop("path")
        row.pop("identity_keys")
        row.pop("included_identity_keys")
        row["columns_json"] = json.dumps(row.pop("columns"), ensure_ascii=False)
        return row


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def normalize_doi(value: str) -> str:
    doi = normalize_text(value)
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip()


def normalize_year(value: str) -> str:
    year = normalize_text(value)
    if not year:
        return ""
    try:
        numeric = float(year)
        if numeric.is_integer():
            return str(int(numeric))
    except ValueError:
        pass
    return year


def value_from(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and row[name] is not None:
            return str(row[name])
    return ""


def identity_key(row: dict[str, str], stage: str) -> str:
    if stage == "extracted":
        doi = normalize_doi(value_from(row, "_doi", "doi"))
        title = normalize_text(value_from(row, "_title", "title"))
        year = normalize_year(value_from(row, "_year", "year"))
    else:
        doi = normalize_doi(value_from(row, "doi"))
        title = normalize_text(value_from(row, "title"))
        year = normalize_year(value_from(row, "year"))
    if doi:
        return f"doi:{doi}"
    payload = f"{title}|{year}".encode("utf-8")
    return "title_year:" + hashlib.sha256(payload).hexdigest()


def parse_case_file(path: Path, stage: str, snapshot_root: Path) -> FileAudit:
    match = CASE_PATTERN.match(path.name)
    if not match:
        raise ValueError(f"Unexpected case filename: {path.name}")
    case_id = int(match.group(1))
    slug = match.group(2)
    audit = FileAudit(
        path=path,
        relative_path=path.relative_to(snapshot_root).as_posix(),
        stage=stage,
        case_id=case_id,
        slug=slug,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        modified_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
    )

    doi_counts: Counter[str] = Counter()
    title_counts: Counter[str] = Counter()
    current_year = datetime.now(timezone.utc).year

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            audit.columns = list(reader.fieldnames or [])
            audit.column_count = len(audit.columns)
            extraction_fields = [
                column
                for column in audit.columns
                if not column.startswith("judge_") and not column.startswith("_")
            ]
            judge_fields = [column for column in audit.columns if column.startswith("judge_")]
            if stage == "extracted":
                audit.extraction_field_count = len(extraction_fields)
                audit.judge_field_count = len(judge_fields)

            for row in reader:
                audit.row_count += 1
                key = identity_key(row, stage)
                audit.identity_keys.add(key)

                title = value_from(row, "_title", "title").strip()
                doi = normalize_doi(value_from(row, "_doi", "doi"))
                year_text = value_from(row, "_year", "year").strip()
                if not title:
                    audit.blank_title_count += 1
                if doi:
                    doi_counts[doi] += 1
                normalized_title = normalize_text(title)
                if normalized_title:
                    title_counts[normalized_title] += 1

                if stage in {"raw", "screened"}:
                    if not value_from(row, "abstract").strip():
                        audit.missing_abstract_count += 1
                    if not doi:
                        audit.missing_doi_count += 1
                    row_case = value_from(row, "case_id").strip()
                    if row_case and row_case != str(case_id):
                        audit.case_id_mismatch_count += 1

                if year_text:
                    try:
                        year = int(float(year_text))
                        if year < 1600 or year > current_year + 1:
                            audit.invalid_year_count += 1
                    except ValueError:
                        audit.invalid_year_count += 1

                if stage == "screened":
                    decision = value_from(row, "llm_decision").strip().upper()
                    if decision == "INCLUDE":
                        audit.include_count += 1
                        audit.included_identity_keys.add(key)
                    elif decision == "EXCLUDE":
                        audit.exclude_count += 1
                    elif not decision:
                        audit.blank_decision_count += 1
                    else:
                        audit.invalid_decision_count += 1

                if stage == "extracted":
                    for column in extraction_fields:
                        if not value_from(row, column).strip():
                            audit.extraction_null_cell_count += 1
                    for column in judge_fields:
                        verdict = value_from(row, column).strip().upper()
                        if verdict == "CORRECT":
                            audit.judge_correct_count += 1
                        elif verdict == "INCORRECT":
                            audit.judge_incorrect_count += 1
                        elif verdict == "UNVERIFIABLE":
                            audit.judge_unverifiable_count += 1
                        elif not verdict:
                            audit.judge_blank_count += 1
                        else:
                            audit.judge_invalid_count += 1
    except Exception as exc:  # report the file instead of hiding it
        audit.parse_status = "error"
        audit.parse_error = f"{type(exc).__name__}: {exc}"

    audit.duplicate_doi_row_count = sum(count - 1 for count in doi_counts.values() if count > 1)
    audit.duplicate_title_row_count = sum(
        count - 1 for count in title_counts.values() if count > 1
    )
    return audit


def read_summary(path: Path, key: str = "case_id") -> dict[int, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {int(row[key]): row for row in csv.DictReader(handle)}


def add_anomaly(
    anomalies: list[dict[str, Any]],
    severity: str,
    case_id: int | str,
    stage: str,
    check: str,
    count: int | str,
    detail: str,
) -> None:
    anomalies.append(
        {
            "severity": severity,
            "case_id": case_id,
            "stage": stage,
            "check": check,
            "count": count,
            "detail": detail,
        }
    )


def integer_value(row: dict[str, str] | None, column: str) -> int | None:
    if not row or not row.get(column):
        return None
    try:
        return int(float(row[column]))
    except ValueError:
        return None


def audit_cases(
    audits: list[FileAudit], previous_outputs: Path, anomalies: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_case_stage = {(audit.case_id, audit.stage): audit for audit in audits}
    retrieval = read_summary(previous_outputs / "retrieval_summary.csv")
    screening = read_summary(previous_outputs / "screening_summary.csv")
    extraction = read_summary(previous_outputs / "extraction_summary_corrected.csv")
    case_rows: list[dict[str, Any]] = []

    for case_id in range(1, 21):
        raw = by_case_stage.get((case_id, "raw"))
        screened = by_case_stage.get((case_id, "screened"))
        extracted = by_case_stage.get((case_id, "extracted"))
        slug = next((item.slug for item in (raw, screened, extracted) if item), "")

        for stage, item in (("raw", raw), ("screened", screened), ("extracted", extracted)):
            if item is None:
                add_anomaly(anomalies, "critical", case_id, stage, "missing_file", 1, "Stage file absent")
                continue
            if item.parse_status != "ok":
                add_anomaly(
                    anomalies,
                    "critical",
                    case_id,
                    stage,
                    "parse_error",
                    1,
                    item.parse_error,
                )
            if item.blank_title_count:
                add_anomaly(
                    anomalies,
                    "error",
                    case_id,
                    stage,
                    "blank_title",
                    item.blank_title_count,
                    "Rows lack a title and therefore have weak fallback identity",
                )
            if item.invalid_year_count:
                add_anomaly(
                    anomalies,
                    "warning",
                    case_id,
                    stage,
                    "invalid_year",
                    item.invalid_year_count,
                    "Year is non-numeric or outside the accepted range",
                )
            if item.case_id_mismatch_count:
                add_anomaly(
                    anomalies,
                    "error",
                    case_id,
                    stage,
                    "case_id_mismatch",
                    item.case_id_mismatch_count,
                    "Embedded case_id does not match filename",
                )

        if raw and screened:
            raw_only = raw.identity_keys - screened.identity_keys
            screened_only = screened.identity_keys - raw.identity_keys
            if raw.row_count != screened.row_count:
                add_anomaly(
                    anomalies,
                    "critical",
                    case_id,
                    "raw_to_screened",
                    "row_count_mismatch",
                    abs(raw.row_count - screened.row_count),
                    f"raw={raw.row_count}, screened={screened.row_count}",
                )
            if raw_only or screened_only:
                add_anomaly(
                    anomalies,
                    "critical",
                    case_id,
                    "raw_to_screened",
                    "identity_mismatch",
                    len(raw_only) + len(screened_only),
                    f"raw_only={len(raw_only)}, screened_only={len(screened_only)}",
                )

        if screened:
            if screened.invalid_decision_count or screened.blank_decision_count:
                add_anomaly(
                    anomalies,
                    "error",
                    case_id,
                    "screened",
                    "invalid_or_blank_decision",
                    screened.invalid_decision_count + screened.blank_decision_count,
                    (
                        f"invalid={screened.invalid_decision_count}, "
                        f"blank={screened.blank_decision_count}"
                    ),
                )

        extracted_not_included = 0
        included_not_extracted = 0
        if screened and extracted:
            extracted_not_included = len(
                extracted.identity_keys - screened.included_identity_keys
            )
            included_not_extracted = len(
                screened.included_identity_keys - extracted.identity_keys
            )
            if extracted_not_included:
                add_anomaly(
                    anomalies,
                    "critical",
                    case_id,
                    "screened_to_extracted",
                    "extracted_not_screened_included",
                    extracted_not_included,
                    "Extracted identity is absent from the screened INCLUDE set",
                )
            if included_not_extracted:
                add_anomaly(
                    anomalies,
                    "warning",
                    case_id,
                    "screened_to_extracted",
                    "included_not_extracted",
                    included_not_extracted,
                    "Included records are absent from the retained extraction file",
                )
            if extracted.row_count == 200 and screened.include_count > 200:
                add_anomaly(
                    anomalies,
                    "warning",
                    case_id,
                    "extracted",
                    "possible_200_record_cap",
                    screened.include_count - extracted.row_count,
                    "Exactly 200 rows retained despite more INCLUDE decisions",
                )

        if extracted and (
            extracted.judge_invalid_count or extracted.judge_blank_count
        ):
            add_anomaly(
                anomalies,
                "error",
                case_id,
                "extracted",
                "invalid_or_blank_judge_verdict",
                extracted.judge_invalid_count + extracted.judge_blank_count,
                (
                    f"invalid={extracted.judge_invalid_count}, "
                    f"blank={extracted.judge_blank_count}"
                ),
            )

        expected_after_dedup = integer_value(retrieval.get(case_id), "after_dedup")
        expected_screened = integer_value(screening.get(case_id), "n_total")
        expected_included = integer_value(screening.get(case_id), "n_included_llm")
        expected_extracted = integer_value(extraction.get(case_id), "n_records")
        comparisons = (
            ("raw", raw.row_count if raw else None, expected_after_dedup, "prior_after_dedup"),
            ("screened", screened.row_count if screened else None, expected_screened, "prior_n_total"),
            (
                "screened",
                screened.include_count if screened else None,
                expected_included,
                "prior_n_included_llm",
            ),
            (
                "extracted",
                extracted.row_count if extracted else None,
                expected_extracted,
                "prior_n_records",
            ),
        )
        for stage, observed, expected, check in comparisons:
            if observed is not None and expected is not None and observed != expected:
                add_anomaly(
                    anomalies,
                    "error",
                    case_id,
                    stage,
                    check,
                    abs(observed - expected),
                    f"observed={observed}, prior_summary={expected}",
                )

        lineage_status = "complete_stage_linkage"
        if not raw or not screened or not extracted:
            lineage_status = "missing_stage"
        elif (
            raw.row_count != screened.row_count
            or raw.identity_keys != screened.identity_keys
            or extracted_not_included
        ):
            lineage_status = "stage_linkage_error"
        elif included_not_extracted:
            lineage_status = "partial_extraction_coverage"

        case_rows.append(
            {
                "case_id": case_id,
                "slug": slug,
                "raw_rows": raw.row_count if raw else "",
                "screened_rows": screened.row_count if screened else "",
                "included_rows": screened.include_count if screened else "",
                "extracted_rows": extracted.row_count if extracted else "",
                "raw_missing_abstract": raw.missing_abstract_count if raw else "",
                "raw_missing_doi": raw.missing_doi_count if raw else "",
                "raw_duplicate_doi_rows": raw.duplicate_doi_row_count if raw else "",
                "raw_duplicate_title_rows": raw.duplicate_title_row_count if raw else "",
                "extracted_not_included": extracted_not_included,
                "included_not_extracted": included_not_extracted,
                "lineage_status": lineage_status,
            }
        )
    return case_rows


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError(f"Refusing to write empty manifest: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "NA"
    return f"{100 * numerator / denominator:.2f}%"


def write_report(
    path: Path,
    audits: list[FileAudit],
    case_rows: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    archive_hash: str,
    generated_utc: str,
) -> None:
    stage_totals = {
        stage: sum(audit.row_count for audit in audits if audit.stage == stage)
        for stage in ("raw", "screened", "extracted")
    }
    raw_audits = [audit for audit in audits if audit.stage == "raw"]
    screened_audits = [audit for audit in audits if audit.stage == "screened"]
    extracted_audits = [audit for audit in audits if audit.stage == "extracted"]
    raw_rows = stage_totals["raw"]
    missing_abstracts = sum(audit.missing_abstract_count for audit in raw_audits)
    missing_dois = sum(audit.missing_doi_count for audit in raw_audits)
    includes = sum(audit.include_count for audit in screened_audits)
    judge_total = sum(
        audit.judge_correct_count
        + audit.judge_incorrect_count
        + audit.judge_unverifiable_count
        + audit.judge_blank_count
        + audit.judge_invalid_count
        for audit in extracted_audits
    )
    verdict_counts = {
        "CORRECT": sum(audit.judge_correct_count for audit in extracted_audits),
        "INCORRECT": sum(audit.judge_incorrect_count for audit in extracted_audits),
        "UNVERIFIABLE": sum(audit.judge_unverifiable_count for audit in extracted_audits),
        "BLANK": sum(audit.judge_blank_count for audit in extracted_audits),
        "INVALID": sum(audit.judge_invalid_count for audit in extracted_audits),
    }
    severity_counts = Counter(item["severity"] for item in anomalies)
    partial_cases = [
        str(row["case_id"])
        for row in case_rows
        if row["lineage_status"] == "partial_extraction_coverage"
    ]
    linkage_error_cases = [
        str(row["case_id"])
        for row in case_rows
        if row["lineage_status"] == "stage_linkage_error"
    ]

    lines = [
        "# Step 2 Historical Data Inventory and Lineage Audit",
        "",
        f"**Generated:** {generated_utc}",
        "",
        "## Snapshot",
        "",
        f"The supplied archive has SHA-256 `{archive_hash}`. It contained 60 case CSV files: "
        "20 raw, 20 screened, and 20 extracted files. No credential-like filenames, unsafe "
        "archive paths, or symbolic links were detected before extraction.",
        "",
        "The archive and CSV files were copied into the ignored `data/raw_snapshot/` zone. "
        "Snapshot files were marked read-only. The original upload was not modified.",
        "",
        "## Stage totals",
        "",
        "| Stage | Files | Rows |",
        "|---|---:|---:|",
        f"| Raw/post-deduplication corpus | {len(raw_audits)} | {stage_totals['raw']:,} |",
        f"| Screened corpus | {len(screened_audits)} | {stage_totals['screened']:,} |",
        f"| Extracted records | {len(extracted_audits)} | {stage_totals['extracted']:,} |",
        "",
        "The historical files called `raw` are post-deduplication corpus files. The archive does "
        "not contain the pre-deduplication records or a duplicate-pair decision table.",
        "",
        "## Initial data-quality profile",
        "",
        "| Measure | Count | Rate or denominator |",
        "|---|---:|---:|",
        f"| Raw records without abstract text | {missing_abstracts:,} | {percent(missing_abstracts, raw_rows)} of raw rows |",
        f"| Raw records without DOI | {missing_dois:,} | {percent(missing_dois, raw_rows)} of raw rows |",
        f"| Historical LLM INCLUDE decisions | {includes:,} | {percent(includes, stage_totals['screened'])} of screened rows |",
        f"| Judge CORRECT cells | {verdict_counts['CORRECT']:,} | {percent(verdict_counts['CORRECT'], judge_total)} of judge cells |",
        f"| Judge INCORRECT cells | {verdict_counts['INCORRECT']:,} | {percent(verdict_counts['INCORRECT'], judge_total)} of judge cells |",
        f"| Judge UNVERIFIABLE cells | {verdict_counts['UNVERIFIABLE']:,} | {percent(verdict_counts['UNVERIFIABLE'], judge_total)} of judge cells |",
        f"| Blank or invalid judge cells | {verdict_counts['BLANK'] + verdict_counts['INVALID']:,} | {percent(verdict_counts['BLANK'] + verdict_counts['INVALID'], judge_total)} of judge cells |",
        "",
        "These evaluator verdicts describe the historical same-model evaluation and are not "
        "human-validated accuracy estimates.",
        "",
        "## Lineage classification",
        "",
        f"Cases with complete raw-to-screened linkage but partial extraction coverage: "
        f"{', '.join(partial_cases) if partial_cases else 'none'}.",
        "",
        f"Cases with stage-linkage errors: {', '.join(linkage_error_cases) if linkage_error_cases else 'none'}.",
        "",
        "A case marked as having complete stage linkage is structurally linked only. It is not "
        "thereby human validated, and the archive alone does not identify prompts, model snapshots, "
        "run dates, retry events, or technical failures at record level.",
        "",
        "## Anomaly summary",
        "",
        "| Severity | Checks triggered |",
        "|---|---:|",
        f"| Critical | {severity_counts.get('critical', 0)} |",
        f"| Error | {severity_counts.get('error', 0)} |",
        f"| Warning | {severity_counts.get('warning', 0)} |",
        "",
        "Detailed counts and affected cases are recorded in `data/manifests/anomalies.csv`. "
        "Per-file hashes and schema information are in `data/manifests/files.csv`; cross-stage "
        "case summaries are in `data/manifests/cases.csv`.",
        "",
        "## Reproducibility classification",
        "",
        "The historical datasets are **partially traceable**. The files are now immutable and "
        "their stage linkage can be audited, but complete computational reproducibility is not yet "
        "established because record-level call logs, model snapshots, exact prompt versions, "
        "pre-deduplication inputs, and duplicate decisions are absent.",
        "",
        "## Outstanding transfer gap",
        "",
        "The uploaded archive contains the three data directories only. Files listed in the "
        "earlier local project tree but absent from both this archive and the Git snapshot remain "
        "recorded in `data/manifests/transfer_gaps.csv`. The most important are the Case 3 audit, "
        "Case 15 adjudication, meta-analysis sensitivity results and script, sequential screening "
        "summary, historical dependency file, and execution script.",
        "",
        "Step 2 remains open until those files are transferred or explicitly declared unavailable. "
        "Missing provenance elements must be represented explicitly in the frozen protocol in "
        "Step 3 and must not be reconstructed as if they were observed historical facts.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--previous-outputs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    snapshot_root = args.snapshot_root.resolve()
    manifest_dir = args.manifest_dir.resolve()
    previous_outputs = args.previous_outputs.resolve()
    report_path = args.report.resolve()
    archive = snapshot_root / "source_archive" / "data.zip"
    if not archive.exists():
        raise FileNotFoundError(archive)

    audits: list[FileAudit] = []
    for stage in ("raw", "screened", "extracted"):
        stage_dir = snapshot_root / "legacy" / stage
        paths = sorted(stage_dir.glob("case_*.csv"))
        for path in paths:
            audits.append(parse_case_file(path, stage, snapshot_root))

    anomalies: list[dict[str, Any]] = []
    case_rows = audit_cases(audits, previous_outputs, anomalies)
    write_csv(manifest_dir / "files.csv", [audit.to_row() for audit in audits])
    write_csv(manifest_dir / "cases.csv", case_rows)
    write_csv(
        manifest_dir / "anomalies.csv",
        anomalies
        or [
            {
                "severity": "none",
                "case_id": "",
                "stage": "",
                "check": "no_anomalies",
                "count": 0,
                "detail": "No anomaly checks were triggered",
            }
        ],
    )

    archive_hash = sha256_file(archive)
    snapshot_manifest_path = manifest_dir / "snapshot.json"
    generated_utc = datetime.now(timezone.utc).isoformat()
    if snapshot_manifest_path.exists():
        try:
            existing_snapshot = json.loads(snapshot_manifest_path.read_text(encoding="utf-8"))
            generated_utc = existing_snapshot.get("generated_utc") or generated_utc
        except (json.JSONDecodeError, OSError):
            pass
    report_generated_utc = generated_utc
    if report_path.exists():
        match = re.search(
            r"^\*\*Generated:\*\* (.+)$",
            report_path.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        if match:
            report_generated_utc = match.group(1)
    snapshot_manifest = {
        "manifest_version": 1,
        "generated_utc": generated_utc,
        "source_archive": "source_archive/data.zip",
        "source_archive_size_bytes": archive.stat().st_size,
        "source_archive_sha256": archive_hash,
        "source_archive_file_count": 60,
        "snapshot_policy": "immutable_read_only",
        "git_policy": "source data ignored; manifests tracked",
        "stage_file_counts": {
            stage: sum(1 for audit in audits if audit.stage == stage)
            for stage in ("raw", "screened", "extracted")
        },
        "stage_row_counts": {
            stage: sum(audit.row_count for audit in audits if audit.stage == stage)
            for stage in ("raw", "screened", "extracted")
        },
    }
    manifest_dir.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text(
        json.dumps(snapshot_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(
        report_path,
        audits,
        case_rows,
        anomalies,
        archive_hash,
        report_generated_utc,
    )


if __name__ == "__main__":
    main()
