from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_offline_pipeline_dry_run_lists_all_stages() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--root", ".", "--dry-run"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "[02 inventory]" in completed.stdout
    assert "[16 environment]" in completed.stdout
    assert "[16 manifest]" in completed.stdout
    assert "run_error_injection_evaluators.py" not in completed.stdout
    assert "run_repeatability_audit.py" not in completed.stdout


def test_environment_manifest_records_declared_packages_without_secrets() -> None:
    payload = json.loads((ROOT / "results/environment.json").read_text(encoding="utf-8"))
    assert set(payload["packages"]) == {"numpy", "openai", "pytest", "scipy"}
    serialized = json.dumps(payload).upper()
    assert "API_KEY" not in serialized
    assert "BEARER" not in serialized


def test_artifact_manifest_hashes_match_current_files() -> None:
    payload = json.loads(
        (ROOT / "results/artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert payload["file_count"] == len(payload["files"])
    assert payload["file_count"] >= 60
    included_roots = ["config", "data/manifests", "results", "docs", "annotations"]
    actual_paths = {
        path.relative_to(ROOT).as_posix()
        for directory in included_roots
        for path in (ROOT / directory).rglob("*")
        if path.is_file() and path != ROOT / "results/artifact_manifest.json"
    }
    manifest_paths = {item["path"] for item in payload["files"]}
    assert manifest_paths == actual_paths
    for item in payload["files"]:
        path = ROOT / item["path"]
        assert path.is_file()
        assert path.stat().st_size == item["bytes"]
        assert sha256_file(path) == item["sha256"]
