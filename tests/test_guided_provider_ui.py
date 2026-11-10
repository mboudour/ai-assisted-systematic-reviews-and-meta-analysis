"""Guided-only provider selection: no live network, credential or BYOD handoff."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import guided_provider_search as search
import guided_workflow as guided

CASES = ("ex1_health", "ex2_ubi", "ex3_microplastics", "ex4_csr")
SECRET = "not-for-logs-SECRET"


def fixture_cases(directory):
    cases = []
    for index, name in enumerate(CASES, 1):
        case = {"key": name, "label": f"Case {index}", "question": f"Question {index}",
                "query": f"captured query {index}", "inclusion_terms": [f"topic{index}"],
                "exclusion_terms": ["exclude-me"], "corpus_file": f"{index}.csv", "log_file": f"{index}.json"}
        frame(name, "Crossref").to_csv(directory / case["corpus_file"], index=False)
        log = {"source": "Crossref", "endpoint": "https://api.crossref.org/works", "query": case["query"],
               "timestamp_utc": "2026-01-01T00:00:00Z", "parameters": {"query": case["query"], "rows": 50},
               "returned": 3}
        (directory / case["log_file"]).write_text(json.dumps(log), encoding="utf-8")
        cases.append(case)
    (directory / "cases.json").write_text(json.dumps(cases), encoding="utf-8")


def frame(case, provider):
    n = CASES.index(case) + 1
    marker = f"{provider}-{case}"
    return pd.DataFrame([
        {"ID": f"{marker}-1", "DOI": f"10.1234/{marker}-1", "Title": f"topic{n} {marker} first",
         "Year": "2022", "Abstract": "Results increased.", "Authors": f"{marker} Alice; {marker} Bob",
         "References": '["openalex:W123"]', "Source": provider},
        {"ID": f"{marker}-2", "DOI": f"10.1234/{marker}-2", "Title": f"topic{n} {marker} second",
         "Year": "2023", "Abstract": "Results decreased.", "Authors": f"{marker} Alice; {marker} Bob",
         "References": '["openalex:W123"]', "Source": provider},
        {"ID": f"{marker}-3", "DOI": "", "Title": "Unrelated", "Year": "2020",
         "Abstract": "Nothing about the topic.", "Authors": "Must not enter; Network", "References": "", "Source": provider},
    ])


def fake_fetch(case, provider, api_key=""):
    assert api_key == ""
    return frame(case, provider), {"case_key": case, "provider": provider,
        "query": search.guided_query(case, provider), "timestamp_utc": "2026-01-01T00:00:00Z",
        "total_matches": 100, "pages_fetched": 1, "possibly_truncated": True,
        "api_key": SECRET, "authorization": SECRET, "unexpected": {"token": SECRET}}


def fake_browser(query, **kwargs):
    assert kwargs["per_page"] == 50 and kwargs["max_pages"] == 1
    assert kwargs["year_from"] is None and kwargs["year_to"] is None
    assert kwargs["publication_types"] == () and kwargs["search_scope"] == "title_abstract_exact"
    assert kwargs["require_abstract"] is False
    case = next(name for name in CASES if search.guided_query(name, "OpenAlex") == query)
    rows = frame(case, "OpenAlex")
    records = []
    for _, row in rows.iterrows():
        records.append({"id": row["ID"], "doi": row["DOI"], "title": row["Title"],
                        "publication_year": int(row["Year"]),
                        "abstract_inverted_index": {"Results": [0], "increased.": [1]},
                        "authorships": [{"author": {"display_name": name}}
                                        for name in row["Authors"].split("; ")],
                        "referenced_works": ["https://openalex.org/W123"]})
    return records, {"query": query, "fetched_at_utc": "2026-01-01T00:00:00.000Z",
                     "pages_fetched": 1, "total_matches": 100, "possibly_truncated": True,
                     "api_key": SECRET, "authorization": SECRET}


def app_for(directory):
    source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
              "from guided_workflow import render_guided_examples\n"
              f"render_guided_examples('providers', data_dir={str(directory)!r})\n")
    return AppTest.from_string(source, default_timeout=90)


def prefix(index):
    return f"guided_providers_{CASES[index - 1]}_{index}"


def extraction_tables(app):
    return [element.value for element in app.dataframe if "Candidate finding excerpt" in element.value.columns]


class GuidedProviderUITests(unittest.TestCase):
    def assert_ok(self, app):
        self.assertEqual([e.message for e in app.exception], [])

    def test_all_four_providers_all_four_cases_and_scoped_networks(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory)
            sentinel = pd.DataFrame([{"Title": "Private BYOD sentinel"}])
            app.session_state["byod_df"] = sentinel.copy(deep=True)
            app.session_state["byod_log"] = {"sentinel": "untouched"}
            with patch("requests.get") as direct, patch("requests.Session.get") as session, \
                 patch.object(search, "fetch_guided", side_effect=fake_fetch) as fetch, \
                 patch("browser_openalex.render_browser_openalex", side_effect=fake_browser) as browser:
                app.run()
                self.assert_ok(app)
                self.assertEqual(len(app.expander), 4)
                self.assertEqual(len(app.tabs), 16)
                self.assertEqual(len(app.text_input), 0)
                self.assertEqual(len(app.text_area), 0)
                self.assertEqual(len(app.button), 0)
                # The captured Crossref corpus is selected by default for every case.
                for i, table in enumerate(extraction_tables(app), 1):
                    self.assertEqual(table["Source"].tolist(), ["Crossref", "Crossref"])
                    self.assertTrue(all(CASES[i - 1] in value for value in table["ID"]))
                direct.assert_not_called()
                session.assert_not_called()
                fetch.assert_not_called()
                browser.assert_not_called()
                for provider in ("Europe PMC", "OpenAIRE", "OpenAlex"):
                    for i in range(1, 5):
                        app.selectbox(key=prefix(i) + "_provider").set_value(provider)
                    app.run()
                    self.assert_ok(app)
                    self.assertEqual(len(extraction_tables(app)), 0)
                    self.assertEqual(len(app.text_input), 0)
                    self.assertEqual(len(app.text_area), 0)
                    for i, case in enumerate(CASES, 1):
                        self.assertIn(search.guided_query(case, provider), [e.value for e in app.code])
                        self.assertTrue(any(provider in item.value and "No" in item.value for item in app.info))
                    if provider == "OpenAIRE":
                        self.assertEqual(sum("OpenAIRE limitations" in item.value for item in app.warning), 4)
                    for i in range(1, 5):
                        suffix = "openalex_start" if provider == "OpenAlex" else provider.lower().replace(" ", "_") + "_run"
                        app.button(key=prefix(i) + "_" + suffix).click().run()
                        self.assert_ok(app)
                    tables = extraction_tables(app)
                    self.assertEqual(len(tables), 4)
                    for i, table in enumerate(tables, 1):
                        marker = f"{provider}-{CASES[i - 1]}"
                        self.assertEqual(table["Source"].tolist(), [provider, provider])
                        self.assertEqual(table["ID"].tolist(), [f"{marker}-1", f"{marker}-2"])
                        self.assertEqual(table["DOI"].tolist(), [f"10.1234/{marker}-1", f"10.1234/{marker}-2"])
                        state = app.session_state[prefix(i) + "_provider_" + provider.lower().replace(" ", "_") + "_result"]
                        self.assertEqual(state["log"]["query"], search.guided_query(CASES[i - 1], provider))
                        self.assertNotIn(SECRET, json.dumps(state["log"]))
                    links = [e.value for e in app.dataframe if "Shared studies" in e.value.columns]
                    self.assertEqual(len(links), 4)
                    for i, link in enumerate(links, 1):
                        marker = f"{provider}-{CASES[i - 1]}"
                        self.assertEqual(link["Shared studies"].tolist(), [2])
                        self.assertEqual(set(link["Source label"]) | set(link["Target label"]),
                                         {f"{marker} Alice", f"{marker} Bob"})
                    self.assertEqual(sum("provider-matched AI illustration" in item.value for item in app.info), 4)
                    if provider == "OpenAIRE":
                        self.assertEqual(sum("OpenAIRE limitations" in item.value for item in app.warning), 4)
                self.assertEqual(fetch.call_count, 8)
                self.assertEqual(browser.call_count, 4)
                direct.assert_not_called()
                session.assert_not_called()
                app.selectbox(key=prefix(1) + "_openalex_network_kind").set_value("Bibliographic coupling").run()
                self.assert_ok(app)
                coupling = [e.value for e in app.dataframe if "Shared references" in e.value.columns]
                self.assertEqual(len(coupling), 1)
                self.assertEqual(coupling[0]["Shared references"].tolist(), [1])
                self.assertEqual(set(coupling[0]["Source record ID"]) | set(coupling[0]["Target record ID"]),
                                 {"OpenAlex-ex1_health-1", "OpenAlex-ex1_health-2"})
                # Switching back recovers only that case/provider result, with no new fetch.
                app.selectbox(key=prefix(1) + "_provider").set_value("Europe PMC").run()
                self.assert_ok(app)
                selected = extraction_tables(app)[0]
                self.assertEqual(set(selected["Source"]), {"Europe PMC"})
                self.assertEqual(fetch.call_count, 8)
                assert_frame_equal(app.session_state["byod_df"], sentinel)
                self.assertEqual(app.session_state["byod_log"], {"sentinel": "untouched"})
                self.assertNotIn("byod_included_df", app.session_state)
                self.assertNotIn("byod_query", app.session_state)

    def test_failed_and_empty_retries_never_show_a_previous_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory).run()
            p = prefix(1)
            app.selectbox(key=p + "_provider").set_value("Europe PMC").run()
            with patch.object(search, "fetch_guided", side_effect=fake_fetch):
                app.button(key=p + "_europe_pmc_run").click().run()
            self.assert_ok(app)
            self.assertEqual(extraction_tables(app)[0]["Source"].tolist(), ["Europe PMC"] * 2)
            with patch.object(search, "fetch_guided", side_effect=RuntimeError("network " + SECRET)):
                app.button(key=p + "_europe_pmc_run").click().run()
            self.assert_ok(app)
            self.assertTrue(any("failed" in item.value and "previous result" in item.value for item in app.error))
            self.assertNotIn(SECRET, " ".join(item.value for item in app.error))
            self.assertEqual(app.session_state[p + "_provider_europe_pmc_result"], {"status": "error"})
            self.assertFalse(any("Europe PMC-" in str(e.value) for e in app.dataframe))
            empty = frame(CASES[0], "Europe PMC").iloc[0:0]
            meta = {"query": search.guided_query(CASES[0], "Europe PMC"), "timestamp_utc": "2026-01-01T00:00:00Z"}
            with patch.object(search, "fetch_guided", return_value=(empty, meta)):
                app.button(key=p + "_europe_pmc_run").click().run()
            self.assert_ok(app)
            self.assertTrue(any("returned no records" in item.value for item in app.info))
            self.assertEqual(len(app.session_state[p + "_provider_europe_pmc_result"]["corpus"]), 0)
            app.selectbox(key=p + "_provider").set_value("Crossref").run()
            self.assertEqual(extraction_tables(app)[0]["Source"].tolist(), ["Crossref"] * 2)

    def test_browser_retry_clears_result_before_any_new_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory).run()
            p = prefix(1)
            app.selectbox(key=p + "_provider").set_value("OpenAlex").run()
            with patch("browser_openalex.render_browser_openalex", side_effect=fake_browser):
                app.button(key=p + "_openalex_start").click().run()
            self.assert_ok(app)
            self.assertEqual(len(app.session_state[p + "_provider_openalex_result"]["corpus"]), 3)
            with patch("browser_openalex.render_browser_openalex", return_value=None):
                app.button(key=p + "_openalex_start").click().run()
            self.assert_ok(app)
            self.assertNotIn(p + "_provider_openalex_result", app.session_state)
            self.assertFalse(any("OpenAlex-" in str(e.value) for e in app.dataframe))
            self.assertTrue(any("No OpenAlex search has completed" in e.value for e in app.info))
            self.assertNotIn(SECRET, str(app.session_state._state.filtered_state))
            with patch("browser_openalex.render_browser_openalex", return_value=([], {"error": SECRET})):
                app.run()
            self.assert_ok(app)
            self.assertEqual(app.session_state[p + "_provider_openalex_result"], {"status": "error"})
            self.assertNotIn(SECRET, " ".join(item.value for item in app.error))
            self.assertTrue(any("search failed" in item.value for item in app.error))

    def test_exact_search_plans_are_fixed_and_match_provider_caps(self):
        for case in CASES:
            for provider in ("Europe PMC", "OpenAIRE", "OpenAlex"):
                query, params = guided._live_plan(case, provider)
                self.assertEqual(query, search.guided_query(case, provider))
                self.assertIn(query, params.values())
                self.assertEqual(params["cursorMark" if provider == "Europe PMC" else "cursor"], "*")
                self.assertEqual(params["per-page" if provider == "OpenAlex" else "pageSize"],
                                 50 if provider == "OpenAlex" else search.PAGE_SIZE)
                self.assertNotIn("filter", params)

    def test_mismatched_metadata_is_rejected_and_credential_fields_are_discarded(self):
        case, provider = CASES[0], "Europe PMC"
        query, params = guided._live_plan(case, provider)
        source = frame(case, provider).assign(api_key=SECRET, authorization=SECRET)
        metadata = {"case_key": case, "provider": provider, "query": query,
                    "parameters": params, "timestamp_utc": "2026-01-01T00:00:00Z",
                    "secret": SECRET, "nested": {"api_key": SECRET}}
        result = guided._prepare_live_result(case, provider, query, params, source, metadata)
        self.assertNotIn(SECRET, result["corpus"].to_string())
        self.assertNotIn(SECRET, json.dumps(result["log"]))
        self.assertEqual(result["log"]["retrieved_at_utc"], "2026-01-01T00:00:00Z")
        for changed in ({**metadata, "provider": "Crossref"}, {**metadata, "query": "other"},
                        {**metadata, "parameters": {"query": "other"}}):
            with self.assertRaises(ValueError):
                guided._prepare_live_result(case, provider, query, params, source, changed)


if __name__ == "__main__":
    unittest.main()
