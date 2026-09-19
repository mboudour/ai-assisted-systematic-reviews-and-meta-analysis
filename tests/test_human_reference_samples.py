from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_human_reference_sample_counts_are_frozen() -> None:
    summary = json.loads(
        (ROOT / "data/manifests/human_reference_sample.json").read_text(encoding="utf-8")
    )
    assert summary["screening_sample_records"] == 1_192
    assert summary["extraction_sample_fields"] == 1_504
    assert summary["reviewers"] == 2
    assert summary["reviewer_blinding"]["screening_historical_decision_hidden"] is True
    assert summary["reviewer_blinding"]["extraction_historical_evaluator_verdict_hidden"] is True


def test_screening_sample_has_expected_strata_and_probabilities() -> None:
    rows = read_rows("data/manifests/screening_sample_manifest.csv")
    assert len(rows) == 1_192
    assert len({row["sample_id"] for row in rows}) == len(rows)
    strata = Counter((row["case_id"], row["historical_llm_decision"]) for row in rows)
    assert len(strata) == 40
    assert max(strata.values()) == 30
    assert all(0 < float(row["selection_probability"]) <= 1 for row in rows)
    assert "title" not in rows[0]
    assert "abstract" not in rows[0]


def test_extraction_sample_has_expected_strata_and_probabilities() -> None:
    rows = read_rows("data/manifests/extraction_sample_manifest.csv")
    assert len(rows) == 1_504
    assert len({row["sample_id"] for row in rows}) == len(rows)
    strata = Counter(
        (
            row["case_id"],
            row["field_class"],
            row["extracted_null_status"],
            row["historical_evaluator_verdict"],
        )
        for row in rows
    )
    assert len(strata) == 191
    assert max(strata.values()) == 10
    assert all(0 < float(row["selection_probability"]) <= 1 for row in rows)
    assert "title" not in rows[0]
    assert "abstract" not in rows[0]
    assert "extracted_value" not in rows[0]


def test_annotation_import_templates_start_empty() -> None:
    assert read_rows("annotations/forms/screening_annotation_template.csv") == []
    assert read_rows("annotations/forms/extraction_annotation_template.csv") == []
