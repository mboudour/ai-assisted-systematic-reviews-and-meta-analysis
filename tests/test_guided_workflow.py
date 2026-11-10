"""Tests use temporary captured-data fixtures, never live APIs or BYOD handoffs."""
import io
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import guided_workflow as guided


def fixture_cases(directory: Path) -> list[dict]:
    cases = []
    for number in range(1, 5):
        marker = f"topic{number}"
        case = {
            "key": f"case{number}", "label": f"Fixed case {number}",
            "question": f"What is known about {marker}?", "query": f"query {marker}",
            "inclusion_terms": [marker], "exclusion_terms": ["exclude-me"],
            "corpus_file": f"{number}.csv", "log_file": f"{number}.json",
        }
        rows = [
            {"ID": f"id-{number}-a", "DOI": f"10.1234/{number}a", "Title": f"{marker} paper A",
             "Year": "2020", "Authors": f"Alice {number}; Bob {number}",
             "Abstract": "Methods were varied. Results increased slightly. More detail follows.",
             "References": json.dumps(["10.7777/shared", f"10.7777/extra{number}"])},
            {"ID": f"id-{number}-b", "DOI": f"10.1234/{number}b", "Title": f"{marker.upper()} paper B",
             "Year": "", "Authors": f"Alice {number}; Bob {number}",
             "Abstract": "A neutral description without any cue.",
             "References": json.dumps(["https://doi.org/10.7777/SHARED"])},
            {"ID": f"id-{number}-c", "DOI": f"10.1234/{number}c", "Title": f"{marker} paper C",
             "Year": "1999", "Authors": f"Alice {number}; Excluded {number}",
             "Abstract": "exclude-me. Results must not enter the included data.",
             "References": json.dumps(["10.7777/shared"])},
            {"ID": f"id-{number}-d", "DOI": f"10.1234/{number}d", "Title": "Unrelated",
             "Year": "2000", "Authors": f"Excluded {number}; Other {number}",
             "Abstract": "No matching subject.", "References": ""},
        ]
        pd.DataFrame(rows).assign(Source="Crossref").to_csv(directory / case["corpus_file"], index=False)
        log = {"case_key": case["key"], "source": "Crossref", "endpoint": "https://api.crossref.org/works", "query": case["query"],
               "retrieved_at_utc": "2026-01-01T12:00:00Z", "parameters": {"query": case["query"], "rows": 4},
               "returned": 4, "total_matches": 100, "possibly_truncated": True,
               "corpus_file": case["corpus_file"],
               "corpus_sha256": hashlib.sha256((directory / case["corpus_file"]).read_bytes()).hexdigest()}
        (directory / case["log_file"]).write_text(json.dumps(log), encoding="utf-8")
        cases.append(case)
    (directory / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    return cases


def app_for(directory: Path, context="test") -> AppTest:
    source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
              "from guided_workflow import render_guided_examples\n"
              f"render_guided_examples({context!r}, data_dir={str(directory)!r})\n")
    return AppTest.from_string(source, default_timeout=60)


class ScreeningTests(unittest.TestCase):
    def test_rule_is_deterministic_case_insensitive_and_exclusions_override(self):
        records = pd.DataFrame([
            {"Title": "  CLIMATE   change ", "Abstract": "Green ENERGY and data"},
            {"Title": "climate change", "Abstract": "EXCLUDE me"},
            {"Title": "Unrelated", "Abstract": "energy helps"},
            {"Title": None, "Abstract": None},
            {"Title": pd.NA, "Abstract": ""},
        ], index=[7, 8, 9, 10, 11])
        before = records.copy(deep=True)
        first = guided.screen_records(records, [" climate change ", "ENERGY", "energy", ""], ["exclude ME", ""])
        second = guided.screen_records(records, [" climate change ", "ENERGY", "energy", ""], ["exclude ME", ""])
        assert_frame_equal(first, second)
        assert_frame_equal(records, before)
        self.assertEqual(first[guided.SCREEN_DECISION].tolist(), ["Include", "Exclude", "Include", "Exclude", "Exclude"])
        self.assertEqual(first.loc[7, guided.INCLUSION_MATCHES], "climate change [title] | ENERGY [abstract]")
        self.assertEqual(first.loc[8, guided.EXCLUSION_MATCHES], "exclude ME [abstract]")
        self.assertEqual(first.loc[10, guided.INCLUSION_MATCHES], "")
        self.assertEqual(guided.screen_records(records, [], [])[guided.SCREEN_DECISION].tolist(), ["Exclude"] * 5)

    def test_matching_is_field_specific_and_literal_not_stemming(self):
        frame = pd.DataFrame([{"Title": "green", "Abstract": "energy"},
                              {"Title": "green energy", "Abstract": ""},
                              {"Title": "cats", "Abstract": ""}])
        out = guided.screen_records(frame, ["green energy", "cat"], [])
        self.assertEqual(out[guided.SCREEN_DECISION].tolist(), ["Exclude", "Include", "Include"])
        self.assertEqual(out.loc[1, guided.INCLUSION_MATCHES], "green energy [title]")

    def test_empty_and_missing_columns_are_safe(self):
        empty = guided.screen_records(pd.DataFrame(), ["x"], ["y"])
        self.assertEqual(len(empty), 0)
        self.assertIn(guided.SCREEN_DECISION, empty)
        out = guided.screen_records(pd.DataFrame([{"Authors": None}]), ["x"], [])
        self.assertEqual(out.iloc[0][guided.SCREEN_DECISION], "Exclude")
        extracted = guided.extract_bibliography(guided.included_records(empty))
        self.assertEqual(list(extracted.columns), ["Title", "Year", "DOI", "Authors", "Abstract", "Abstract_License",
                                                   "Abstract availability", "Candidate finding excerpt",
                                                   guided.INCLUSION_MATCHES, guided.EXCLUSION_MATCHES])
        self.assertTrue(extracted.empty)
        self.assertTrue(guided.year_summary(guided.included_records(empty)).empty)

    def test_excerpts_are_literal_first_cue_and_not_claims(self):
        abstract = "Methods first. The RESULTS were associated with change! Conclusions are elsewhere."
        candidate = guided.candidate_finding_excerpt(abstract)
        self.assertEqual(candidate, "The RESULTS were associated with change!")
        self.assertIn(candidate, abstract)
        self.assertEqual(guided.candidate_finding_excerpt("Methods only. Background only."), "Not available")
        self.assertEqual(guided.candidate_finding_excerpt(None), "Not available")
        self.assertEqual(guided.candidate_finding_excerpt("Some finding without final punctuation"),
                         "Some finding without final punctuation")
        self.assertEqual(guided.candidate_finding_excerpt("The increase was not significant."),
                         "The increase was not significant.")

    def test_extraction_and_year_summary_use_exact_selected_rows(self):
        source = pd.DataFrame([
            {"Title": "x A", "DOI": "a", "Year": "2022", "Abstract": "The result was mixed."},
            {"Title": "x B", "DOI": "b", "Year": None, "Abstract": None},
            {"Title": "x C", "DOI": "c", "Year": "1901", "Abstract": "bad. Results positive."},
            {"Title": "Unrelated", "DOI": "d", "Year": "1999", "Abstract": "Results positive."},
        ])
        screened = guided.screen_records(source, ["x"], ["bad"])
        included = guided.included_records(screened)
        extracted = guided.extract_bibliography(included)
        self.assertEqual(extracted["DOI"].tolist(), ["a", "b"])
        self.assertEqual(extracted["Candidate finding excerpt"].tolist(), ["The result was mixed.", "Not available"])
        self.assertEqual(extracted["Abstract availability"].tolist(), ["Available", "Not available"])
        self.assertEqual(extracted["Authors"].tolist(), ["", ""])
        counts = guided.year_summary(included)
        self.assertEqual(dict(zip(counts["Year"], counts["Included records"])),
                         {"2022": 1, "Not recorded / not a four-digit year": 1})
        self.assertEqual(counts["Included records"].sum(), len(included))

    def test_csv_neutralizes_formula_cells_and_headers_without_mutating_data(self):
        source = pd.DataFrame({"=header": ["=1+1", "  +SUM(A1:A2)", "@evil", "-1", "\tplain", "normal"],
                               "number": [1, 2, 3, 4, 5, 6]})
        before = source.copy(deep=True)
        result = pd.read_csv(io.BytesIO(guided.safe_csv_bytes(source)), dtype=str, keep_default_na=False)
        self.assertEqual(result.columns.tolist(), ["'=header", "number"])
        self.assertEqual(result["'=header"].tolist(), ["'=1+1", "'  +SUM(A1:A2)", "'@evil", "'-1", "'\tplain", "normal"])
        self.assertEqual(result["number"].tolist(), ["1", "2", "3", "4", "5", "6"])
        assert_frame_equal(source, before)


class GuidedFileTests(unittest.TestCase):
    def test_saved_ai_illustrations_match_the_included_source_and_reject_tampering(self):
        cases = guided.load_guided_cases()
        for case in cases:
            corpus, _, errors = guided.load_case_data(case)
            self.assertEqual(errors, [])
            included = guided.included_records(guided.screen_records(
                corpus, case["inclusion_terms"], case["exclusion_terms"]))
            demo, error = guided.load_ai_illustration(case, included)
            self.assertEqual(error, "")
            self.assertIsNotNone(demo)
            changed = included.copy(deep=True)
            changed.loc[changed["ID"] == demo["source"]["record_id"], "Abstract"] = "Changed"
            rejected, error = guided.load_ai_illustration(case, changed)
            self.assertIsNone(rejected)
            self.assertIn("could not be verified", error)
            without = included.loc[included["ID"] != demo["source"]["record_id"]]
            rejected, error = guided.load_ai_illustration(case, without)
            self.assertIsNone(rejected)
            self.assertIn("included records", error)

    def test_each_case_loads_its_own_csv_and_actual_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            cases = fixture_cases(directory)
            loaded = guided.load_guided_cases(directory)
            self.assertEqual(len(loaded), 4)
            for case in cases:
                corpus, log, errors = guided.load_case_data(case, directory)
                self.assertEqual(errors, [])
                self.assertEqual(log["query"], case["query"])
                self.assertEqual(log["returned"], len(corpus))
                self.assertEqual(len(guided.included_records(guided.screen_records(
                    corpus, case["inclusion_terms"], case["exclusion_terms"]))), 2)
                self.assertTrue(all(case["inclusion_terms"][0].casefold() in title.casefold()
                                    for title in corpus["Title"].iloc[:3]))

    def test_missing_invalid_and_nonlocal_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            corpus, log, errors = guided.load_case_data({"corpus_file": "../elsewhere.csv", "log_file": "missing.json"}, directory)
            self.assertIsNone(corpus)
            self.assertIsNone(log)
            self.assertEqual(len(errors), 2)
            (directory / "bad.json").write_text("[1]", encoding="utf-8")
            _, log, errors = guided.load_case_data({"corpus_file": "1.csv", "log_file": "bad.json"}, directory)
            self.assertIsNone(log)
            self.assertIn("JSON object", errors[0])
            (directory / "cases.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                guided.load_guided_cases(directory)

    def test_supplied_corpus_checksum_binds_screening_to_the_captured_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            case = fixture_cases(directory)[0]
            log_path = directory / case["log_file"]
            log = json.loads(log_path.read_text(encoding="utf-8"))
            log["corpus_file"] = case["corpus_file"]
            log["corpus_sha256"] = hashlib.sha256((directory / case["corpus_file"]).read_bytes()).hexdigest()
            log_path.write_text(json.dumps(log), encoding="utf-8")
            corpus, _, errors = guided.load_case_data(case, directory)
            self.assertEqual(len(corpus), 4)
            self.assertEqual(errors, [])
            with (directory / case["corpus_file"]).open("a", encoding="utf-8") as handle:
                handle.write("\n")
            corpus, _, errors = guided.load_case_data(case, directory)
            self.assertIsNone(corpus)
            self.assertIn("integrity check failed", errors[0])


class GuidedUITests(unittest.TestCase):
    def assert_app_ok(self, app):
        self.assertEqual([item.message for item in app.exception], [])

    def test_four_cases_have_four_complete_stages_and_no_byod_state_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory)
            stale = pd.DataFrame([{"Title": "STALE BYOD", "Authors": "Wrong; Person", "References": "10.1/wrong"}])
            app.session_state["byod_included_df"] = stale.copy(deep=True)
            app.session_state["byod_extracted_df_PICO (Health Sciences)"] = stale.copy(deep=True)
            app.run()
            self.assert_app_ok(app)
            self.assertEqual(len(app.expander), 4)
            self.assertEqual(len(app.tabs), 16)
            self.assertEqual(len(app.text_input), 0)
            self.assertEqual(len(app.text_area), 0)
            self.assertEqual(len(app.selectbox), 8)
            for index in range(1, 5):
                selector = app.selectbox(key=f"guided_test_case{index}_{index}_provider")
                self.assertEqual(selector.value, "Crossref")
                self.assertEqual(selector.options, ["Crossref", "OpenAlex", "Europe PMC", "OpenAIRE"])
            self.assertEqual(len(app.slider), 8)
            self.assertEqual(len(app.get("iframe")), 4)
            self.assertEqual([e.value for e in app.code], [f"query topic{i}" for i in range(1, 5)])
            extraction = [e.value for e in app.dataframe if "Candidate finding excerpt" in e.value.columns]
            self.assertEqual(len(extraction), 4)
            for i, table in enumerate(extraction, 1):
                self.assertEqual(table["DOI"].tolist(), [f"10.1234/{i}a", f"10.1234/{i}b"])
                self.assertEqual(table["Candidate finding excerpt"].tolist(), ["Results increased slightly.", "Not available"])
                self.assertNotIn("STALE BYOD", str(table))
            year_tables = [e.value for e in app.dataframe if list(e.value.columns) == ["Year", "Included records"]]
            self.assertEqual(len(year_tables), 4)
            self.assertTrue(all(table["Included records"].sum() == 2 for table in year_tables))
            links = [e.value for e in app.dataframe if "Shared studies" in e.value.columns]
            self.assertEqual(len(links), 4)
            for i, table in enumerate(links, 1):
                self.assertEqual(table["Shared studies"].tolist(), [2])
                self.assertEqual(set(table["Source label"]) | set(table["Target label"]), {f"Alice {i}", f"Bob {i}"})
            captions = "\n".join(item.value for item in app.caption)
            self.assertIn("table is not AI-generated", captions)
            self.assertIn("nonvalidated teaching screen", captions)
            self.assertIn("Verify the candidate manually", captions)
            self.assertIn("Captured records: 4; heuristic includes: 2; heuristic excludes: 2", captions)
            assert_frame_equal(app.session_state["byod_included_df"], stale)
            assert_frame_equal(app.session_state["byod_extracted_df_PICO (Health Sciences)"], stale)
            self.assertTrue(any(e.key == "guided_test_case1_1_bibliography_csv" for e in app.get("download_button")))

    def test_coupling_uses_only_included_references_and_zero_links_hide_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory).run()
            app.selectbox(key="guided_test_case1_1_network_kind").set_value("Bibliographic coupling").run()
            self.assert_app_ok(app)
            links = [e.value for e in app.dataframe if "Shared references" in e.value.columns]
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0]["Shared references"].tolist(), [1])
            self.assertEqual(set(links[0]["Source record ID"]) | set(links[0]["Target record ID"]), {"id-1-a", "id-1-b"})
            self.assertEqual(len(app.get("iframe")), 4)
            app.slider(key="guided_test_case1_1_coupling_minimum").set_value(2).run()
            self.assert_app_ok(app)
            self.assertEqual(len(app.get("iframe")), 3)
            self.assertTrue(any("No links meet" in e.value for e in app.info))
            self.assertFalse(any(e.key == "guided_test_case1_1_coupling_links_csv" for e in app.get("download_button")))

    def test_missing_references_and_empty_or_missing_corpus_are_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            cases = fixture_cases(directory)
            frame = pd.read_csv(directory / "1.csv", dtype=str, keep_default_na=False)
            frame["References"] = ""
            frame.to_csv(directory / "1.csv", index=False)
            pd.DataFrame(columns=frame.columns).to_csv(directory / "2.csv", index=False)
            for number in (1, 2):
                path = directory / f"{number}.json"
                log = json.loads(path.read_text(encoding="utf-8"))
                log["corpus_sha256"] = hashlib.sha256((directory / f"{number}.csv").read_bytes()).hexdigest()
                log["returned"] = 4 if number == 1 else 0
                path.write_text(json.dumps(log), encoding="utf-8")
            (directory / "3.csv").unlink()
            (directory / "4.json").unlink()
            app = app_for(directory).run()
            app.selectbox(key="guided_test_case1_1_network_kind").set_value("Bibliographic coupling").run()
            self.assert_app_ok(app)
            self.assertEqual(len(app.tabs), 16)
            self.assertTrue(any("No usable References" in e.value for e in app.info))
            self.assertTrue(any("no heuristic-included records to map" in e.value.lower() for e in app.info))
            self.assertTrue(any("snapshot unavailable" in e.value.lower() for e in app.warning))
            self.assertTrue(any("actual query, source, date and parameters cannot be verified" in e.value for e in app.error))
            self.assertEqual(len(guided.load_case_data(cases[1], directory)[0]), 0)

    def test_contexts_namespace_all_widgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
                      "from guided_workflow import render_guided_examples\n"
                      f"render_guided_examples('day1', data_dir={str(directory)!r})\n"
                      f"render_guided_examples('day3', data_dir={str(directory)!r})\n")
            app = AppTest.from_string(source, default_timeout=60).run()
            self.assert_app_ok(app)
            for context in ("day1", "day3"):
                for index in range(1, 5):
                    self.assertEqual(app.selectbox(key=f"guided_{context}_case{index}_{index}_network_kind").value, "Co-authorship")


if __name__ == "__main__":
    unittest.main()
