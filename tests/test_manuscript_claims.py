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
    rows = read_csv(ROOT / "results" / "tables" / "evaluator_verdict_cube.csv")
    correct = sum(int(row["count"]) for row in rows if row["verdict"] == "CORRECT")
    incorrect = sum(int(row["count"]) for row in rows if row["verdict"] == "INCORRECT")
    unverifiable = sum(
        int(row["count"]) for row in rows if row["verdict"] == "UNVERIFIABLE"
    )
    requested = sum(int(row["count"]) for row in rows)

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
    assert "strict synthesis gate" not in text
    assert "each of four required fields is individually absent from all 20 schemas" in text


def test_screening_repeatability_and_retrieval_limits_are_reported() -> None:
    screening = json.loads(
        (ROOT / "results/tables/screening_repeatability_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert screening["items"] == 200
    assert screening["calls"] == 600
    assert screening["stable_items"] == 190
    assert screening["changed_adjacent_transitions"] == 13

    text = PAPER.read_text(encoding="utf-8")
    for expected in ("190 retained the same label", "95.00\\%", "13 changed label", "seven INCLUDE-to-EXCLUDE", "six EXCLUDE-to-INCLUDE"):
        assert expected in text
    for expected in (
        "up to 30 records within each case-by-historical-label stratum",
        "seeded SHA-256",
        "1,192 frame records",
        "96 historical INCLUDE (48.00\\%) and 104 historical EXCLUDE",
        "20.39\\% archive prevalence",
    ):
        assert expected in text
    supplement = SUPPLEMENT.read_text(encoding="utf-8")
    for expected in (
        "3 & OpenAlex & 6,000 & 6,000",
        "5 & OpenAlex & 4,500 & 4,600",
        "8 & OpenAlex & 8,000 & 8,000",
        "11 & OpenAlex & 5,000 & 5,000",
        "15 & OpenAlex & 6,000 & 6,000",
        "20 & OpenAlex & 10,000 & 10,000",
    ):
        assert expected in supplement


def test_ccs_and_prior_work_are_blinded_for_review() -> None:
    text = PAPER.read_text(encoding="utf-8")
    bibliography = (ROOT / "manuscript/references.bib").read_text(encoding="utf-8")
    assert "printccs=true" in text
    assert "\\ccsdesc[500]{Information systems~Data provenance}" in text
    assert "\\ccsdesc[500]{Information systems~Data extraction and integration}" in text
    assert "A prior report used the same archive" in text
    assert "\\cite{anonymous2026prior}" in text
    assert "Citation withheld for double-anonymous review" in bibliography
    for forbidden in ("publicly posted", "Boudourides", "7346302", "boudourides2026ssrn"):
        assert forbidden.casefold() not in (text + bibliography).casefold()
    assert "unsuccessful attempt" not in text


def test_anonymity_and_post_outcome_disclosure() -> None:
    combined = PAPER.read_text(encoding="utf-8") + SUPPLEMENT.read_text(encoding="utf-8")
    forbidden = ("Northwestern", "mboudour", "@northwestern", "ANONYMOUS-ARTIFACT-URL")
    assert not any(value.casefold() in combined.casefold() for value in forbidden)
    assert "\\author{Anonymous Author(s)}" in PAPER.read_text(encoding="utf-8")
    assert "\\institution{Anonymous Institution}" in PAPER.read_text(encoding="utf-8")
    assert "post-outcome" in combined
    assert "not preregistered" in combined
    assert "separate prospective question" in combined
    assert combined.startswith("\\documentclass[acmsmall,anonymous,review]{acmart}")


def test_amendments_and_cross_document_references_are_accurate() -> None:
    paper = PAPER.read_text(encoding="utf-8")
    supplement = SUPPLEMENT.read_text(encoding="utf-8")
    assert "Supplement Table~S1" not in paper
    assert "the supplement's retrieval-limit table" in paper
    assert "amendments are summarized in the supplement and supplied verbatim" in paper
    assert "config/amendments.jsonl" in supplement
    assert "earlier manuscript" not in paper
    assert "earlier manuscript" not in supplement
    assert "Prior report, Section 4.5.1" not in supplement
    assert "Screening labels and null states are largely stable" in paper
    assert "11.45\\% design-weighted non-agreement" in paper


def test_noel_storr_reference_is_corrected() -> None:
    bibliography = (ROOT / "manuscript/references.bib").read_text(encoding="utf-8")
    assert "Noel-Storr, Anna" in bibliography
    assert "Norl-Storr" not in bibliography


def test_paper_leads_with_measured_consequences() -> None:
    text = PAPER.read_text(encoding="utf-8")
    denominator = text.index("Denominator-explicit reporting")
    repeatability = text.index("Representation- and null-aware repeatability")
    schema = text.index("Downstream-first schema design")
    provenance = text.index("Provenance and failure incidence are not reconstructable")
    assert denominator < repeatability < schema < provenance
