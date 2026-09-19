#!/usr/bin/env python3
"""Build a minimal, identity-free repository for double-anonymous review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Iterable


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_file(root: Path, target: Path, relative: str) -> None:
    source = root / relative
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def write_csv(path: Path, rows: Iterable[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def git_config(key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--get", key],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def scan_text(target: Path, forbidden: list[str]) -> None:
    text_suffixes = {
        ".csv",
        ".json",
        ".md",
        ".py",
        ".toml",
        ".txt",
        ".yml",
        ".yaml",
        "",
    }
    violations: list[str] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").casefold()
        for term in forbidden:
            if term and term.casefold() in text:
                violations.append(f"{path.relative_to(target)}:{term}")
    if violations:
        raise RuntimeError("Identity-bearing terms found: " + ", ".join(violations))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    target = args.target.resolve()
    zip_path = args.zip.resolve()

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    copied = [
        "scripts/analyze_screening_repeatability.py",
        "scripts/analyze_repeatability_normalized.py",
        "scripts/build_claim_consequence_matrix.py",
        "scripts/build_denominator_figure.py",
        "tests/test_screening_and_verdict_cube.py",
        "tests/test_repeatability_normalized.py",
        "tests/test_claim_consequence_matrix.py",
        "tests/test_denominator_figure.py",
        "config/historical_prompts.json",
        "results/tables/evaluator_verdict_cube.csv",
        "results/tables/meta_analysis_input_audit.csv",
        "results/tables/screening_repeatability_summary.json",
        "results/tables/repeatability_normalized_items.csv",
        "results/tables/repeatability_normalized_summary.json",
        "results/tables/sensitivity_ablations.csv",
        "results/tables/claim_consequence_matrix.csv",
        "results/tables/schema_requirement_coverage.csv",
        "results/figures/denominator_ledger.png",
        "results/figures/denominator_ledger.pdf",
        "docs/claim_consequence_matrix.md",
        "docs/step11_repeatability_sensitivity.md",
    ]
    for relative in copied:
        copy_file(root, target, relative)

    calls = read_csv(root / "results/tables/repeatability_calls.csv")
    call_fields = ["task", "sample_id", "call_status", "repeat_index", "output_value"]
    analysis_calls = [
        row for row in calls if row["task"] in {"screening", "extraction"}
    ]
    write_csv(
        target / "results/tables/repeatability_calls.csv",
        analysis_calls,
        call_fields,
    )

    sample = read_csv(root / "data/manifests/extraction_sample_manifest.csv")
    sample_fields = [
        "sample_id",
        "case_id",
        "field_name",
        "field_class",
        "declared_type",
        "selection_probability",
    ]
    write_csv(
        target / "data/manifests/extraction_sample_manifest.csv",
        sample,
        sample_fields,
    )

    screening_sample_ids = {
        row["sample_id"] for row in calls if row["task"] == "screening"
    }
    screening_sample = [
        row
        for row in read_csv(root / "data/manifests/screening_sample_manifest.csv")
        if row["sample_id"] in screening_sample_ids
    ]
    screening_fields = [
        "sample_id",
        "case_id",
        "historical_llm_decision",
        "selection_probability",
    ]
    write_csv(
        target / "data/manifests/screening_sample_manifest.csv",
        screening_sample,
        screening_fields,
    )

    case_rows = read_csv(root / "data/manifests/cases.csv")
    case_fields = [
        "case_id",
        "slug",
        "raw_rows",
        "screened_rows",
        "included_rows",
        "extracted_rows",
        "included_not_extracted",
        "lineage_status",
    ]
    write_csv(target / "data/manifests/cases.csv", case_rows, case_fields)

    retrieval = read_csv(root / "results/tables/retrieval_corpus_quality.csv")
    retrieval_fields = [
        "case_id",
        "slug",
        "source",
        "configured_max_records",
        "historical_pre_dedup_rows_reported",
        "historical_post_dedup_rows",
        "configured_limit_reached",
    ]
    write_csv(
        target / "results/tables/retrieval_corpus_quality.csv",
        retrieval,
        retrieval_fields,
    )

    cases = json.loads((root / "config/cases.json").read_text(encoding="utf-8"))
    pruned_cases = {
        "artifact_scope": "Only fields required to audit historical extraction-schema coverage are retained.",
        "cases": [
            {
                "case_id": case["case_id"],
                "slug": case["slug"],
                "historical_extraction": {
                    "fields": case["historical_extraction"]["fields"]
                },
            }
            for case in cases["cases"]
        ],
    }
    config_path = target / "config/cases.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(pruned_cases, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    readme = """# Double-Anonymous Review Artifact

This repository contains the minimal derived data, analysis scripts, figure, and tests needed to reproduce the reported measurements in the accompanying manuscript:

1. the evaluator-denominator contrast from 58.39% to 98.52%;
2. the all-non-null categorical normalization contrast from 21.58% to 46.13%, together with the design-weighted 1.92% mixed-null estimate; and
3. the schema audit showing 927 complete estimate-and-interval rows but no study-level linkage or variance field.

It also reproduces the prospective screening result: 190 of 200 records retained the same label across all three calls (95.00%), with 13 changed adjacent transitions among 400 comparisons. The aggregate `evaluator_verdict_cube.csv` contains case-by-field-type-by-null-status-by-verdict counts and no source text; it recomputes the 52,877 CORRECT, 796 INCORRECT, 36,881 UNVERIFIABLE, and null-cross-tab totals used in the paper.

The artifact does not contain author names, affiliations, acknowledgments, Git history, raw bibliographic records, old manuscripts, or the historical repository snapshot. Historical failure incidence and historical screening-model identity are not estimable from the retained archive and are not represented as effect sizes.

## Reproduce

```bash
python3 -m pip install -e '.[dev]'
make all
```

The build performs only offline analysis of the included derived tables. It makes no network requests and no model calls.
"""
    (target / "README.md").write_text(readme, encoding="utf-8")

    scope = """# Artifact Scope

This is a deliberately minimal review artifact. It excludes identity-bearing and nonessential historical materials, including old manuscripts and binary documents, because text-only anonymization cannot sanitize embedded binary metadata reliably. It also excludes raw titles and abstracts. The included extraction-call ledger is reduced to the fields used by the repeatability analysis.

A later logged rerun would estimate the failure behavior of a different execution. It would not recover the historical failure rate, which remains non-identifiable from the archived outputs.
"""
    (target / "ARTIFACT_SCOPE.md").write_text(scope, encoding="utf-8")

    pyproject = """[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "anonymous-evidence-quality-artifact"
version = "1.0.0"
description = "Double-anonymous reproducibility artifact for a ground-truth-free data-quality audit"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "matplotlib>=3.9",
  "numpy>=2.0",
  "pandas>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.hatch.build.targets.wheel]
packages = []

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
"""
    (target / "pyproject.toml").write_text(pyproject, encoding="utf-8")

    makefile = """.PHONY: all analysis figure test

all: analysis figure test

analysis:
	python3 scripts/analyze_screening_repeatability.py --root .
	python3 scripts/analyze_repeatability_normalized.py
\tpython3 scripts/build_claim_consequence_matrix.py --root .

figure:
\tpython3 scripts/build_denominator_figure.py --root .

test:
\tpython3 -m pytest -q
"""
    (target / "Makefile").write_text(makefile, encoding="utf-8")
    (target / ".gitignore").write_text(
        "__pycache__/\n.pytest_cache/\n*.py[cod]\n.venv/\n",
        encoding="utf-8",
    )

    forbidden = [
        "mboudour",
        "northwestern",
        "ai-assisted-systematic-reviews-and-meta-analysis",
        "/home/ubuntu",
    ]
    for candidate in (git_config("user.name"), git_config("user.email")):
        if candidate and candidate.casefold() not in {"anonymous", "anonymous@example.invalid"}:
            forbidden.append(candidate)
    scan_text(target, forbidden)

    manifest_rows = []
    for path in sorted(target.rglob("*")):
        if path.is_file():
            manifest_rows.append(
                {
                    "path": path.relative_to(target).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    manifest = {
        "artifact_version": "1.0.0",
        "identity_scan": "passed",
        "network_calls_required": False,
        "model_calls_required": False,
        "files": manifest_rows,
    }
    (target / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(target.rglob("*")):
            if path.is_file():
                archive.write(path, Path("anonymous-review-artifact") / path.relative_to(target))

    print(
        json.dumps(
            {
                "target": str(target),
                "zip": str(zip_path),
                "file_count": len(manifest_rows) + 1,
                "zip_sha256": sha256(zip_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
