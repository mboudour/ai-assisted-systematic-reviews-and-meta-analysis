from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "manuscript" / "jdiq_experience_paper.tex"
SUPPLEMENT = ROOT / "manuscript" / "jdiq_online_supplement.tex"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_headline_denominator_claims_match_derived_table() -> None:
    rows = read_csv(ROOT / "results" / "tables" / "failure_missingness_audit.csv")
    correct = sum(int(row["judge_correct_cells"]) for row in rows)
    incorrect = sum(int(row["judge_incorrect_cells"]) for row in rows)
    unverifiable = sum(int(row["judge_unverifiable_cells"]) for row in rows)
    requested = sum(int(row["requested_field_cells"]) for row in rows)

    assert (correct, incorrect, unverifiable, requested) == (52_877, 796, 36_881, 90_554)
    assert round(100 * correct / requested, 2) == 58.39
    assert round(100 * correct / (correct + incorrect), 2) == 98.52

    text = PAPER.read_text(encoding="utf-8")
    for expected in ("52,877", "90,554", "36,881", "58.39\\%", "98.52\\%", "40.12"):
        assert expected in text


def test_headline_repeatability_claims_match_derived_table() -> None:
    result = json.loads(
        (ROOT / "results" / "tables" / "repeatability_normalized_summary.json").read_text(
            encoding="utf-8"
        )
    )
    mixed = result["null_state_design_weighted"]["mixed_null"]
    categorical = result["all_nonnull_by_declared_type"]["categorical"]

    assert round(100 * mixed["weighted_estimate"], 2) == 1.92
    assert round(100 * mixed["cluster_bootstrap_95_lower"], 2) == 0.60
    assert round(100 * mixed["cluster_bootstrap_95_upper"], 2) == 4.34
    assert result["null_state_counts"]["mixed_null"] == 36
    assert round(100 * categorical["raw_exact"]["weighted_estimate"], 2) == 21.58
    assert round(100 * categorical["normalized_exact"]["weighted_estimate"], 2) == 46.13

    text = PAPER.read_text(encoding="utf-8")
    for expected in ("1.92\\%", "0.60\\%--4.34\\%", "36 of 500", "21.58\\%", "46.13\\%"):
        assert expected in text
    assert text.index("1.92\\%") < text.index("36 of 500")


def test_schema_claims_match_derived_tables() -> None:
    audit = read_csv(ROOT / "results" / "tables" / "meta_analysis_input_audit.csv")
    coverage = {
        row["requirement"]: int(row["cases_with_required_field"])
        for row in read_csv(ROOT / "results" / "tables" / "schema_requirement_coverage.csv")
    }

    assert sum(int(row["complete_estimate_ci_rows"]) for row in audit) == 927
    for requirement in (
        "study-level linkage identifier",
        "effect-measure label",
        "variance or standard error",
        "dependence or clustering identifier",
    ):
        assert coverage[requirement] == 0

    text = PAPER.read_text(encoding="utf-8")
    assert "927" in text
    assert "0/20" in text
    assert "does not establish synthesis readiness" in text


def test_anonymity_and_post_outcome_disclosure() -> None:
    combined = PAPER.read_text(encoding="utf-8") + SUPPLEMENT.read_text(encoding="utf-8")
    forbidden = (
        "Moses",
        "Boudour",
        "Northwestern",
        "mboudour",
        "@northwestern",
        "ANONYMOUS-ARTIFACT-URL",
    )
    assert not any(value.casefold() in combined.casefold() for value in forbidden)
    assert "post-outcome" in combined
    assert "not preregistered" in combined
    assert "separate prospective question" in combined
    assert combined.startswith("\\documentclass[acmsmall,anonymous,review]{acmart}")


def test_paper_leads_with_measured_consequences() -> None:
    text = PAPER.read_text(encoding="utf-8")
    denominator = text.index("Denominator-explicit reporting")
    repeatability = text.index("Representation- and null-aware repeatability")
    schema = text.index("Downstream-first schema design")
    provenance = text.index("Provenance and failure incidence are not reconstructable")
    assert denominator < repeatability < schema < provenance
