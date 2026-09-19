from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_builder_excludes_historical_and_identity_bearing_material(tmp_path: Path) -> None:
    target = tmp_path / "artifact"
    archive = tmp_path / "artifact.zip"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_anonymous_review_artifact.py"),
            "--root",
            str(ROOT),
            "--target",
            str(target),
            "--zip",
            str(archive),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert archive.stat().st_size > 100_000
    assert not (target / "previous").exists()
    assert not (target / "manuscript").exists()
    assert not (target / ".git").exists()
    assert not list(target.rglob("*.tex"))
    assert not list(target.rglob("*.docx"))

    manifest = json.loads((target / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["identity_scan"] == "passed"
    assert manifest["network_calls_required"] is False
    assert manifest["model_calls_required"] is False

    subprocess.run(
        ["make", "-C", str(target), "all"],
        check=True,
        capture_output=True,
        text=True,
    )
    for entry in manifest["files"]:
        digest = hashlib.sha256((target / entry["path"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"], entry["path"]

    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in target.rglob("*")
        if path.is_file() and path.suffix in {".md", ".py", ".json", ".csv", ".toml"}
    ).casefold()
    assert "mboudour" not in combined
    assert "northwestern" not in combined
    assert "ai-assisted-systematic-reviews-and-meta-analysis" not in combined
