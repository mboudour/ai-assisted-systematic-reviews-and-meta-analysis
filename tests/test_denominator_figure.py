from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_denominator_figure_artifacts_are_rendered() -> None:
    png = ROOT / "results/figures/denominator_ledger.png"
    pdf = ROOT / "results/figures/denominator_ledger.pdf"
    assert png.stat().st_size > 100_000
    assert pdf.stat().st_size > 10_000
    with Image.open(png) as image:
        assert image.width >= 2_000
        assert image.height >= 1_000
        assert image.mode in {"RGB", "RGBA"}
    assert pdf.read_bytes().startswith(b"%PDF-")


def test_figure_script_contains_the_three_headline_measurements() -> None:
    script = (ROOT / "scripts/build_denominator_figure.py").read_text(encoding="utf-8")
    assert "+40.12 percentage points" in script
    assert "95,292" not in script  # values are derived from audited tables, not hard-coded labels
    assert "Neither percentage is an accuracy estimate" in script
