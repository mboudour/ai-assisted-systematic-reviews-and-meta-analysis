#!/usr/bin/env python3
"""Audit residual duplicate candidates in retained historical corpora.

The historical removed pairs are unavailable, so this script does not estimate
false merges. It creates a deterministic sample of retained exact-title and
high-similarity pairs for later blinded human review.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def normalize_doi(value: str) -> str:
    doi = (value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip()


def normalize_title(value: str) -> str:
    tokens = TOKEN_PATTERN.findall((value or "").lower())
    return " ".join(tokens)


def title_tokens(value: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall((value or "").lower()) if token not in STOPWORDS}


def simhash(tokens: set[str]) -> int:
    vector = [0] * 64
    for token in sorted(tokens):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], "big")
        for bit in range(64):
            vector[bit] += 1 if value & (1 << bit) else -1
    result = 0
    for bit, score in enumerate(vector):
        if score >= 0:
            result |= 1 << bit
    return result


def stable_rank(*parts: str) -> str:
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def clean_cell(value: str) -> str:
    return " ".join((value or "").split())


def pair_row(
    case_id: int,
    slug: str,
    left: dict[str, str],
    right: dict[str, str],
    left_row: int,
    right_row: int,
    rule: str,
) -> dict[str, Any]:
    left_title = clean_cell(left.get("title", "") or "")
    right_title = clean_cell(right.get("title", "") or "")
    left_tokens = title_tokens(left_title)
    right_tokens = title_tokens(right_title)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    char_ratio = difflib.SequenceMatcher(
        None, normalize_title(left_title), normalize_title(right_title), autojunk=False
    ).ratio()
    pair_id = stable_rank(str(case_id), str(left_row), str(right_row))[:20]
    return {
        "pair_id": pair_id,
        "case_id": case_id,
        "slug": slug,
        "match_rule": rule,
        "title_similarity": round(char_ratio, 6),
        "token_jaccard": round(jaccard, 6),
        "left_row_number": left_row,
        "right_row_number": right_row,
        "left_title": left_title,
        "right_title": right_title,
        "left_doi": clean_cell(left.get("doi", "") or ""),
        "right_doi": clean_cell(right.get("doi", "") or ""),
        "left_year": clean_cell(left.get("year", "") or ""),
        "right_year": clean_cell(right.get("year", "") or ""),
        "left_source": clean_cell(left.get("source", "") or ""),
        "right_source": clean_cell(right.get("source", "") or ""),
        "human_same_report": "",
        "human_same_study": "",
        "reviewer_id": "",
        "review_notes": "",
    }


def candidate_pairs(records: list[dict[str, str]], case_id: int, slug: str) -> list[dict[str, Any]]:
    exact_titles: dict[str, list[int]] = defaultdict(list)
    fuzzy_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    token_sets: list[set[str]] = []
    normalized_titles: list[str] = []

    for index, row in enumerate(records):
        normalized = normalize_title(row.get("title", "") or "")
        tokens = title_tokens(row.get("title", "") or "")
        normalized_titles.append(normalized)
        token_sets.append(tokens)
        if normalized:
            exact_titles[normalized].append(index)
        if len(normalized) >= 20 and len(tokens) >= 4:
            fingerprint = simhash(tokens)
            for band in range(4):
                fuzzy_buckets[(band, (fingerprint >> (16 * band)) & 0xFFFF)].append(index)

    pairs: dict[tuple[int, int], dict[str, Any]] = {}
    for indices in exact_titles.values():
        if len(indices) < 2:
            continue
        for left_index, right_index in itertools.combinations(indices, 2):
            pairs[(left_index, right_index)] = pair_row(
                case_id,
                slug,
                records[left_index],
                records[right_index],
                left_index + 2,
                right_index + 2,
                "exact_normalized_title",
            )

    fuzzy_pair_keys: set[tuple[int, int]] = set()
    for indices in fuzzy_buckets.values():
        unique_indices = sorted(set(indices))
        if len(unique_indices) > 200:
            continue
        for left_index, right_index in itertools.combinations(unique_indices, 2):
            key = (left_index, right_index)
            if key in pairs or key in fuzzy_pair_keys:
                continue
            left_normalized = normalized_titles[left_index]
            right_normalized = normalized_titles[right_index]
            length_ratio = min(len(left_normalized), len(right_normalized)) / max(
                len(left_normalized), len(right_normalized)
            )
            if length_ratio < 0.75:
                continue
            left_tokens = token_sets[left_index]
            right_tokens = token_sets[right_index]
            union = left_tokens | right_tokens
            jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
            if jaccard < 0.72:
                continue
            ratio = difflib.SequenceMatcher(
                None, left_normalized, right_normalized, autojunk=False
            ).ratio()
            if ratio < 0.90 and jaccard < 0.85:
                continue
            fuzzy_pair_keys.add(key)
            pairs[key] = pair_row(
                case_id,
                slug,
                records[left_index],
                records[right_index],
                left_index + 2,
                right_index + 2,
                "simhash_candidate",
            )
    return list(pairs.values())


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--removed-template", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    raw_dir = root / "data" / "raw_snapshot" / "legacy" / "raw"
    all_candidates: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for path in sorted(raw_dir.glob("case_*.csv")):
        case_id = int(path.name.split("_")[1])
        slug = path.stem.split(f"case_{case_id:02d}_", 1)[1]
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            records = list(csv.DictReader(handle))
        doi_counts = Counter(normalize_doi(row.get("doi", "") or "") for row in records)
        title_counts = Counter(normalize_title(row.get("title", "") or "") for row in records)
        doi_groups = sum(1 for value, count in doi_counts.items() if value and count > 1)
        doi_extra = sum(count - 1 for value, count in doi_counts.items() if value and count > 1)
        title_groups = sum(1 for value, count in title_counts.items() if value and count > 1)
        title_extra = sum(count - 1 for value, count in title_counts.items() if value and count > 1)
        candidates = candidate_pairs(records, case_id, slug)
        all_candidates.extend(candidates)
        summary_rows.append(
            {
                "case_id": case_id,
                "slug": slug,
                "retained_rows": len(records),
                "exact_duplicate_doi_groups": doi_groups,
                "extra_rows_in_duplicate_doi_groups": doi_extra,
                "exact_duplicate_title_groups": title_groups,
                "extra_rows_in_duplicate_title_groups": title_extra,
                "retained_candidate_pairs": len(candidates),
                "human_review_status": "pending",
                "removed_pair_audit_status": "unavailable_no_removed_pair_log",
            }
        )

    exact = [row for row in all_candidates if row["match_rule"] == "exact_normalized_title"]
    fuzzy = [row for row in all_candidates if row["match_rule"] == "simhash_candidate"]
    exact.sort(key=lambda row: stable_rank("exact", row["pair_id"]))
    fuzzy.sort(key=lambda row: stable_rank("fuzzy", row["pair_id"]))
    sample = exact[: args.sample_size]
    if len(sample) < args.sample_size:
        sample.extend(fuzzy[: args.sample_size - len(sample)])
    sample_pair_ids = {row["pair_id"] for row in sample}
    for row in summary_rows:
        row["sampled_retained_pairs"] = sum(
            1
            for pair in all_candidates
            if pair["case_id"] == row["case_id"] and pair["pair_id"] in sample_pair_ids
        )

    summary_fields = list(summary_rows[0].keys())
    pair_fields = list(all_candidates[0].keys()) if all_candidates else [
        "pair_id",
        "case_id",
        "slug",
        "match_rule",
        "title_similarity",
        "token_jaccard",
        "left_row_number",
        "right_row_number",
        "left_title",
        "right_title",
        "left_doi",
        "right_doi",
        "left_year",
        "right_year",
        "left_source",
        "right_source",
        "human_same_report",
        "human_same_study",
        "reviewer_id",
        "review_notes",
    ]
    write_csv(args.output, summary_rows, summary_fields)
    write_csv(args.sample, sample, pair_fields)
    removed_fields = [
        "pair_id",
        "case_id",
        "retained_record_id",
        "removed_record_id",
        "match_rule",
        "human_same_report",
        "human_same_study",
        "reviewer_id",
        "review_notes",
    ]
    write_csv(args.removed_template, [], removed_fields)

    exact_pairs = sum(
        int(row["extra_rows_in_duplicate_title_groups"]) for row in summary_rows
    )
    exact_doi = sum(
        int(row["extra_rows_in_duplicate_doi_groups"]) for row in summary_rows
    )
    lines = [
        "# Step 5 Deduplication Validation",
        "",
        "## Completed structural audit",
        "",
        f"Across 94,522 retained records, the audit found {exact_doi} extra rows in exact "
        f"normalized-DOI groups and {exact_pairs} extra rows in exact normalized-title groups. "
        f"The candidate generator produced {len(all_candidates):,} retained exact-title or "
        "high-similarity pairs for potential human review.",
        "",
        "String similarity is used only to prioritize candidates and is not treated as a duplicate "
        "label. The candidate generator uses normalized titles, deterministic SimHash blocking, "
        "token Jaccard similarity, and Python's `SequenceMatcher` ratio.[1]",
        "",
        "## Human-review form",
        "",
        f"A deterministic sample of {len(sample):,} retained candidate pairs was written to "
        "`annotations/forms/dedup_retained_pair_sample.csv`. Reviewers must label whether each pair "
        "is the same report and whether it represents the same underlying study. These are separate "
        "questions.",
        "",
        "## Historical limitation",
        "",
        "The historical archive contains neither the pre-deduplication rows nor a removed-pair log. "
        "Therefore the false-merge rate and positive predictive value of the historical removal rule "
        "cannot be estimated. An empty schema-correct form is provided at "
        "`annotations/forms/dedup_removed_pair_sample.csv` for use if those records are recovered.",
        "",
        "Until human pair judgments and the removed-pair log are available, the deduplication-accuracy "
        "estimand remains pending. Exact residual counts and candidate counts are descriptive audit "
        "results, not accuracy estimates.",
        "",
        "## References",
        "",
        "[1]: https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher \"Python SequenceMatcher Documentation\"",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
