#!/usr/bin/env python3
"""Audit retrieval provenance and corpus quality without altering historical data."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: str) -> str:
    doi = (value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip()


def load_csv_index(path: Path) -> dict[int, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {int(row["case_id"]): row for row in csv.DictReader(handle)}


def integer(row: dict[str, str] | None, field: str) -> int | None:
    if not row or not row.get(field):
        return None
    return int(float(row[field]))


def percent(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def audit_file(path: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "rows": 0,
        "title_present": 0,
        "abstract_present": 0,
        "doi_present": 0,
        "doi_valid": 0,
        "year_present": 0,
        "year_valid": 0,
        "source_present": 0,
        "case_id_present": 0,
        "language_column_present": False,
        "source_record_id_column_present": False,
    }
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        metrics["language_column_present"] = "language" in columns
        metrics["source_record_id_column_present"] = bool(
            columns & {"source_id", "openalex_id", "pmid", "paper_id", "core_id"}
        )
        for row in reader:
            metrics["rows"] += 1
            title = (row.get("title") or "").strip()
            abstract = (row.get("abstract") or "").strip()
            doi = normalize_doi(row.get("doi") or "")
            year_text = (row.get("year") or "").strip()
            source = (row.get("source") or "").strip()
            case_text = (row.get("case_id") or "").strip()
            metrics["title_present"] += bool(title)
            metrics["abstract_present"] += bool(abstract)
            metrics["doi_present"] += bool(doi)
            metrics["doi_valid"] += bool(doi and DOI_PATTERN.match(doi))
            metrics["year_present"] += bool(year_text)
            if year_text:
                try:
                    year = int(float(year_text))
                    metrics["year_valid"] += 1600 <= year <= 2027
                except ValueError:
                    pass
            metrics["source_present"] += bool(source)
            metrics["case_id_present"] += bool(case_text)
    return metrics


def format_rate(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--current-counts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    cases = {
        int(case["case_id"]): case
        for case in json.loads((root / "config" / "cases.json").read_text(encoding="utf-8"))["cases"]
    }
    prior_retrieval = load_csv_index(
        root / "previous" / "empirical_evaluation" / "outputs" / "retrieval_summary.csv"
    )
    file_manifest = load_csv_index(root / "data" / "manifests" / "cases.csv")
    current_counts = load_csv_index(args.current_counts)
    rows: list[dict[str, Any]] = []

    for case_id, case in sorted(cases.items()):
        raw_path = next(
            (root / "data" / "raw_snapshot" / "legacy" / "raw").glob(
                f"case_{case_id:02d}_*.csv"
            )
        )
        metrics = audit_file(raw_path)
        retrieval = case["historical_retrieval"]
        prior = prior_retrieval.get(case_id)
        manifest = file_manifest.get(case_id)
        current = current_counts.get(case_id)
        historical_pre_dedup = integer(prior, "raw")
        post_dedup = metrics["rows"]
        duplicates_removed = (
            None if historical_pre_dedup is None else historical_pre_dedup - post_dedup
        )
        configured_max = int(retrieval["configured_max_records"])
        limit_reached = bool(
            historical_pre_dedup is not None and historical_pre_dedup >= configured_max
        )
        historical_status = (
            "configured_limit_reached"
            if limit_reached
            else "source_total_not_archived_cannot_confirm_completeness"
        )
        current_hits = integer(current, "current_source_reported_hits")
        current_status = current.get("status", "missing") if current else "missing"
        current_exceeds_configured = bool(
            current_hits is not None and current_hits > configured_max
        )
        rows.append(
            {
                "case_id": case_id,
                "slug": case["slug"],
                "domain": case["domain_assignment"],
                "source": retrieval["source"],
                "query_semantics": retrieval["query_semantics"],
                "configured_max_records": configured_max,
                "historical_pre_dedup_rows_reported": historical_pre_dedup,
                "historical_post_dedup_rows": post_dedup,
                "duplicates_removed_reported": duplicates_removed,
                "deduplication_rate": (
                    "" if historical_pre_dedup in (None, 0) else duplicates_removed / historical_pre_dedup
                ),
                "configured_limit_reached": str(limit_reached).lower(),
                "historical_completeness_status": historical_status,
                "current_source_reported_hits": "" if current_hits is None else current_hits,
                "current_count_status": current_status,
                "current_hits_exceed_historical_configured_max": str(
                    current_exceeds_configured
                ).lower(),
                "current_to_historical_post_dedup_ratio": (
                    "" if current_hits is None or post_dedup == 0 else current_hits / post_dedup
                ),
                "title_completeness": percent(metrics["title_present"], post_dedup),
                "abstract_completeness": percent(metrics["abstract_present"], post_dedup),
                "doi_completeness": percent(metrics["doi_present"], post_dedup),
                "doi_validity_among_all_rows": percent(metrics["doi_valid"], post_dedup),
                "year_completeness": percent(metrics["year_present"], post_dedup),
                "year_validity_among_all_rows": percent(metrics["year_valid"], post_dedup),
                "source_completeness": percent(metrics["source_present"], post_dedup),
                "case_id_completeness": percent(metrics["case_id_present"], post_dedup),
                "language_status": (
                    "collected" if metrics["language_column_present"] else "not_collected"
                ),
                "source_record_id_status": (
                    "collected" if metrics["source_record_id_column_present"] else "not_collected"
                ),
                "duplicate_doi_rows_in_retained_file": int(manifest["raw_duplicate_doi_rows"]),
                "duplicate_title_rows_in_retained_file": int(manifest["raw_duplicate_title_rows"]),
                "deduplication_accuracy_status": "not_yet_human_audited",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    total_pre = sum(int(row["historical_pre_dedup_rows_reported"]) for row in rows)
    total_post = sum(int(row["historical_post_dedup_rows"]) for row in rows)
    total_removed = total_pre - total_post
    limited = [str(row["case_id"]) for row in rows if row["configured_limit_reached"] == "true"]
    current_ok = [row for row in rows if row["current_count_status"] == "ok"]
    current_failed = [
        str(row["case_id"]) for row in rows if row["current_count_status"] != "ok"
    ]
    current_over_limit = [
        str(row["case_id"])
        for row in rows
        if row["current_hits_exceed_historical_configured_max"] == "true"
    ]
    pooled = {}
    for field in (
        "title_completeness",
        "abstract_completeness",
        "doi_completeness",
        "year_completeness",
        "year_validity_among_all_rows",
    ):
        weighted = sum(float(row[field]) * int(row["historical_post_dedup_rows"]) for row in rows)
        pooled[field] = weighted / total_post

    lines = [
        "# Step 4 Retrieval and Corpus-Quality Audit",
        "",
        "## Main findings",
        "",
        f"The archived summaries report {total_pre:,} records before within-case deduplication and "
        f"{total_post:,} retained records. The reported {total_removed:,} removals correspond to "
        f"{100 * total_removed / total_pre:.2f}% of the pre-deduplication total.",
        "",
        f"Cases {', '.join(limited)} reached or exceeded their configured retrieval limit. They "
        "must be described as truncated by the project configuration unless historical source-total "
        "evidence proves otherwise. No case can currently be certified complete because the original "
        "source-reported hit totals were not archived.",
        "",
        "A current source-count check is a temporal reproducibility audit, not a reconstruction of "
        "the historical count. It succeeded for "
        f"{len(current_ok)} cases. Cases {', '.join(current_failed) if current_failed else 'none'} "
        "could not be checked automatically and retain explicit failure statuses.[1] [2] [3] [4] [5]",
        "",
        f"For successful current checks, Cases {', '.join(current_over_limit)} now return more "
        "hits than the historical configured maximum. This supports a risk-of-truncation flag but "
        "does not prove the source total at the historical run date.",
        "",
        "## Pooled metadata completeness",
        "",
        "| Field | Complete or valid among retained rows |",
        "|---|---:|",
        f"| Title | {format_rate(pooled['title_completeness'])} |",
        f"| Abstract | {format_rate(pooled['abstract_completeness'])} |",
        f"| DOI | {format_rate(pooled['doi_completeness'])} |",
        f"| Year | {format_rate(pooled['year_completeness'])} |",
        f"| Valid year | {format_rate(pooled['year_validity_among_all_rows'])} |",
        "",
        "Language and source-native record identifiers were not collected in the archived corpus. "
        "Their completeness is therefore **not measurable from these files** and is not zero.",
        "",
        "## Deduplication limitation",
        "",
        "The archive contains only post-deduplication records. It does not contain the removed pairs "
        "or pre-deduplication rows required to estimate false merges. Exact duplicate DOI and title "
        "checks can detect residual duplicates, but they cannot validate the historical deduplication "
        "algorithm. Step 5 will therefore produce an executable audit protocol and mark the empirical "
        "false-merge estimate as pending source-pair recovery.",
        "",
        "## Interpretation rule",
        "",
        "Current source counts must not replace historical counts. Bibliographic indexes change over "
        "time, and the audit uses the historical query strings through current source interfaces. "
        "Differences may reflect index growth, metadata change, query-semantics change, or historical "
        "retrieval truncation.",
        "",
        "## Outputs",
        "",
        "- `results/tables/retrieval_corpus_quality.csv` contains case-level historical and current audit measures.",
        "- `results/tables/current_source_count_audit.csv` contains request status, query hashes, timestamps, and response hashes.",
        "- Raw current count responses are retained in ignored `data/interim/retrieval_count_audit/` files.",
        "",
        "## References",
        "",
        "[1]: https://docs.openalex.org/api-entities/works \"OpenAlex Works API\"",
        "[2]: https://www.ncbi.nlm.nih.gov/books/NBK25501/ \"NCBI Entrez Programming Utilities Help\"",
        "[3]: https://europepmc.org/RestfulWebService \"Europe PMC RESTful Web Service\"",
        "[4]: https://api.semanticscholar.org/api-docs/graph \"Semantic Scholar Academic Graph API\"",
        "[5]: https://api.core.ac.uk/docs/v3 \"CORE API Documentation\"",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
