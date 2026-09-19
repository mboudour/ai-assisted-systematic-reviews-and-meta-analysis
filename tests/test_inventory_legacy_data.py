from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_legacy_data.py"
SPEC = importlib.util.spec_from_file_location("inventory_legacy_data", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_normalize_year_removes_csv_float_artifact() -> None:
    assert MODULE.normalize_year("2014") == "2014"
    assert MODULE.normalize_year("2014.0") == "2014"
    assert MODULE.normalize_year("") == ""


def test_normalize_doi_removes_resolver_prefix() -> None:
    assert MODULE.normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert MODULE.normalize_doi("doi:10.1000/ABC") == "10.1000/abc"


def test_identity_is_stable_across_raw_and_screened_csv_types() -> None:
    raw = {"title": "Example Study", "year": "2014", "doi": ""}
    screened = {"title": "Example Study", "year": "2014.0", "doi": ""}
    assert MODULE.identity_key(raw, "raw") == MODULE.identity_key(screened, "screened")


def test_identity_prefers_normalized_doi() -> None:
    raw = {"title": "First title", "year": "2020", "doi": "https://doi.org/10.1/XYZ"}
    screened = {"title": "Changed title", "year": "2021.0", "doi": "10.1/xyz"}
    assert MODULE.identity_key(raw, "raw") == MODULE.identity_key(screened, "screened")


def test_snapshot_manifest_matches_the_frozen_upload() -> None:
    with (ROOT / "data/manifests/snapshot.json").open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    assert snapshot["source_archive_sha256"] == (
        "619cb3d2d0d1f558454f77fd6b0aee98b476a648ec90e793d270c31005282f7c"
    )
    assert snapshot["stage_file_counts"] == {"raw": 20, "screened": 20, "extracted": 20}
    assert snapshot["stage_row_counts"] == {
        "raw": 94_522,
        "screened": 94_522,
        "extracted": 11_500,
    }


def test_case_manifest_has_expected_structural_lineage() -> None:
    with (ROOT / "data/manifests/cases.csv").open(encoding="utf-8", newline="") as handle:
        cases = list(csv.DictReader(handle))
    assert len(cases) == 20
    partial = [
        row["case_id"]
        for row in cases
        if row["lineage_status"] == "partial_extraction_coverage"
    ]
    assert partial == ["16", "17", "18", "19", "20"]


def test_inventory_has_no_critical_structural_anomaly() -> None:
    with (ROOT / "data/manifests/anomalies.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        assert not any(row["severity"] == "critical" for row in csv.DictReader(handle))
