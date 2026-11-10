"""Offline tests for provider snapshots, optional live retrieval, and isolation."""
import hashlib
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


def frame(case, provider, saved=False):
    n = CASES.index(case) + 1
    marker = f"{'SAVED-' if saved else 'LIVE-'}{provider}-{case}"
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


def fixture_cases(directory):
    snapshots = directory / "guided_provider_snapshots"
    snapshots.mkdir()
    cases = []
    for index, name in enumerate(CASES, 1):
        case = {"key": name, "label": f"Case {index}", "question": f"Question {index}",
                "query": f"historical Crossref query {index}", "inclusion_terms": [f"topic{index}"],
                "exclusion_terms": ["exclude-me"], "corpus_file": f"{index}.csv", "log_file": f"{index}.json"}
        cases.append(case)
        for provider in guided.GUIDED_PROVIDERS:
            slug = provider.lower().replace(" ", "_")
            stem = f"{name}__{slug}"
            corpus_path = snapshots / (stem + ".csv")
            frame(name, provider, saved=True).to_csv(corpus_path, index=False)
            query = search.guided_query(name, provider)
            query_key = {"Crossref": "query", "OpenAlex": "search.title_and_abstract.exact",
                         "Europe PMC": "query", "OpenAIRE": "search"}[provider]
            log = {"case_key": name, "provider": provider, "source": provider,
                   "query": query, "endpoint": guided._ENDPOINTS[provider],
                   "parameters": {query_key: query, "page_size": 3},
                   "retrieved_at_utc": "2026-01-01T00:00:00Z", "returned": 3,
                   "total_matches": 100, "possibly_truncated": True,
                   "corpus_file": corpus_path.name,
                   "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
                   "abstract_note": "Abstracts may be missing due to unconfirmed reuse rights."}
            (snapshots / (stem + ".json")).write_text(json.dumps(log), encoding="utf-8")
    (directory / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    return cases


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
    records = []
    for _, row in frame(case, "OpenAlex").iterrows():
        records.append({"id": row["ID"], "doi": row["DOI"], "title": row["Title"],
                        "publication_year": int(row["Year"]),
                        "abstract_inverted_index": {"Results": [0], "increased.": [1]},
                        "authorships": [{"author": {"display_name": name}}
                                        for name in row["Authors"].split("; ")],
                        "referenced_works": ["https://openalex.org/W123"]})
    return records, {"query": query, "fetched_at_utc": "2026-01-01T00:00:00.000Z",
                     "pages_fetched": 1, "total_matches": 100, "possibly_truncated": True,
                     "api_key": SECRET, "authorization": SECRET}


def app_for(directory, context="providers"):
    source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
              "from guided_workflow import render_guided_examples\n"
              f"render_guided_examples({context!r}, data_dir={str(directory)!r})\n")
    return AppTest.from_string(source, default_timeout=90)


def prefix(index):
    return f"guided_providers_{CASES[index - 1]}_{index}"


def extraction_tables(app):
    return [element.value for element in app.dataframe if "Candidate finding excerpt" in element.value.columns]


class SnapshotVerificationTests(unittest.TestCase):
    def test_all_case_provider_pairs_verify_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = fixture_cases(root)
            for case in cases:
                for provider in guided.GUIDED_PROVIDERS:
                    with self.subTest(case=case["key"], provider=provider):
                        corpus, log, errors = guided.load_provider_snapshot(case, provider, root / "guided_provider_snapshots")
                        self.assertEqual(errors, [])
                        self.assertEqual(len(corpus), 3)
                        self.assertEqual(set(corpus.Source), {provider})
                        self.assertTrue(all(case["key"] in value for value in corpus.ID))
                        self.assertEqual(log["query"], search.guided_query(case["key"], provider))

    def test_mismatched_provenance_filename_checksum_count_and_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = fixture_cases(root)[0]
            snapshots = root / "guided_provider_snapshots"
            path = snapshots / "ex1_health__europe_pmc.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            mutations = [
                {"case_key": CASES[1]}, {"provider": "Crossref"}, {"source": "Crossref"},
                {"query": "another query"}, {"parameters": {"query": "another query"}},
                {"corpus_file": "ex1_health__crossref.csv"}, {"corpus_file": "../escape.csv"},
                {"log_file": "ex1_health__crossref.json"},
                {"corpus_sha256": "a" * 64}, {"corpus_sha256": None}, {"returned": 2},
                {"returned": True}, {"endpoint": guided._ENDPOINTS["Crossref"]},
                {"retrieved_at_utc": "not a timestamp"}, {"nested": {"api_key": SECRET}},
                {"nested": {"token": SECRET}}, {"request_url": "https://example.org/?api_key=" + SECRET},
            ]
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    path.write_text(json.dumps({**original, **mutation}), encoding="utf-8")
                    corpus, log, errors = guided.load_provider_snapshot(case, "Europe PMC", snapshots)
                    self.assertIsNone(corpus)
                    self.assertIsNone(log)
                    self.assertTrue(errors)
                    self.assertNotIn(SECRET, str(errors))
            path.write_text(json.dumps(original), encoding="utf-8")
            csv = snapshots / original["corpus_file"]
            corrupt = pd.read_csv(csv, dtype=str, keep_default_na=False)
            corrupt["Source"] = "Crossref"
            corrupt.to_csv(csv, index=False)
            original["corpus_sha256"] = hashlib.sha256(csv.read_bytes()).hexdigest()
            path.write_text(json.dumps(original), encoding="utf-8")
            corpus, _, errors = guided.load_provider_snapshot(case, "Europe PMC", snapshots)
            self.assertIsNone(corpus)
            self.assertIn("record source mismatch", errors[0])

    def test_nonlocal_case_and_missing_pair_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = fixture_cases(root)[0]
            for bad in ({**case, "key": "../escape"}, {**case, "key": CASES[1]}):
                if bad["key"] == CASES[1]:
                    (root / "guided_provider_snapshots" / (CASES[1] + "__openalex.csv")).unlink()
                corpus, log, errors = guided.load_provider_snapshot(bad, "OpenAlex", root / "guided_provider_snapshots")
                self.assertIsNone(corpus)
                self.assertIsNone(log)
                self.assertTrue(errors)


class GuidedProviderUITests(unittest.TestCase):
    def assert_ok(self, app):
        self.assertEqual([e.message for e in app.exception], [])

    def test_all_four_saved_providers_all_cases_and_same_stages_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory)
            sentinel = pd.DataFrame([{"Title": "Private BYOD sentinel"}])
            app.session_state["byod_df"] = sentinel.copy(deep=True)
            app.session_state["byod_log"] = {"sentinel": "untouched"}
            with patch("requests.get") as direct, patch("requests.Session.get") as session, \
                 patch.object(search, "fetch_guided") as fetch, \
                 patch("browser_openalex.render_browser_openalex") as browser:
                for provider in guided.GUIDED_PROVIDERS:
                    if provider != "Crossref":
                        for i in range(1, 5):
                            app.selectbox(key=prefix(i) + "_provider").set_value(provider)
                    app.run()
                    self.assert_ok(app)
                    self.assertEqual(len(app.expander), 4)
                    self.assertEqual(len(app.tabs), 16)
                    self.assertEqual(len(app.text_input), 0)
                    self.assertEqual(len(app.text_area), 0)
                    self.assertFalse(app.error)
                    tables = extraction_tables(app)
                    self.assertEqual(len(tables), 4)
                    decisions = [e.value for e in app.dataframe if guided.SCREEN_DECISION in e.value.columns]
                    years = [e.value for e in app.dataframe if list(e.value.columns) == ["Year", "Included records"]]
                    links = [e.value for e in app.dataframe if "Shared studies" in e.value.columns]
                    for i, case in enumerate(CASES):
                        marker = f"SAVED-{provider}-{case}"
                        self.assertEqual(tables[i]["ID"].tolist(), [f"{marker}-1", f"{marker}-2"])
                        self.assertEqual(tables[i]["Source"].tolist(), [provider, provider])
                        self.assertEqual(decisions[i][guided.SCREEN_DECISION].tolist(), ["Include", "Include", "Exclude"])
                        self.assertEqual(decisions[i]["ID"].iloc[:2].tolist(), tables[i]["ID"].tolist())
                        self.assertEqual(years[i]["Included records"].sum(), 2)
                        self.assertEqual(links[i]["Shared studies"].tolist(), [2])
                        self.assertEqual(set(links[i]["Source label"]) | set(links[i]["Target label"]),
                                         {f"{marker} Alice", f"{marker} Bob"})
                        self.assertIn(search.guided_query(case, provider), [e.value for e in app.code])
                    captions = " ".join(e.value for e in app.caption)
                    self.assertIn("reuse rights", captions)
                    self.assertIn("verified saved snapshot", captions)
                    self.assertTrue(any("one-page" in e.value and "not an exhaustive" in e.value for e in app.warning))
                    self.assertEqual(len([e for e in app.get("download_button") if e.label == "Download capture log (JSON)"]), 4)
                    displayed = [json.loads(e.value) for e in app.json]
                    markdown = [e.value for e in app.markdown]
                    self.assertEqual(markdown.count(f"Recorded source: {provider}"), 4)
                    self.assertEqual(markdown.count("Retrieval timestamp: 2026-01-01T00:00:00Z"), 4)
                    for case in CASES:
                        slug = provider.lower().replace(" ", "_")
                        log = json.loads((directory / "guided_provider_snapshots" / f"{case}__{slug}.json").read_text(encoding="utf-8"))
                        self.assertIn(log, displayed)
                        self.assertIn(log["parameters"], displayed)
                    if provider == "OpenAIRE":
                        self.assertEqual(sum("OpenAIRE limitations" in item.value for item in app.warning), 4)
                direct.assert_not_called()
                session.assert_not_called()
                fetch.assert_not_called()
                browser.assert_not_called()
                assert_frame_equal(app.session_state["byod_df"], sentinel)
                self.assertEqual(app.session_state["byod_log"], {"sentinel": "untouched"})
                self.assertNotIn("byod_included_df", app.session_state)
                self.assertNotIn("byod_query", app.session_state)

    def test_success_failed_and_empty_retries_choose_correct_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory).run()
            p = prefix(1)
            app.selectbox(key=p + "_provider").set_value("Europe PMC").run()
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            with patch.object(search, "fetch_guided", side_effect=fake_fetch):
                app.button(key=p + "_europe_pmc_run").click().run()
            self.assert_ok(app)
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("LIVE-"))
            self.assertTrue(any("successful live retrieval" in e.value for e in app.caption))
            state = app.session_state[p + "_provider_europe_pmc_result"]
            self.assertEqual(state["log"]["query"], search.guided_query(CASES[0], "Europe PMC"))
            self.assertNotIn(SECRET, json.dumps(state["log"]))
            app.button(key=p + "_europe_pmc_use_saved").click().run()
            self.assert_ok(app)
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            with patch.object(search, "fetch_guided", side_effect=fake_fetch):
                app.button(key=p + "_europe_pmc_run").click().run()
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("LIVE-"))
            with patch.object(search, "fetch_guided", side_effect=RuntimeError("network " + SECRET)):
                app.button(key=p + "_europe_pmc_run").click().run()
            self.assert_ok(app)
            self.assertTrue(any("failed" in item.value and "previous live result" in item.value for item in app.warning))
            self.assertEqual(app.session_state[p + "_provider_europe_pmc_result"], {"status": "error"})
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            self.assertFalse(any("LIVE-Europe PMC" in str(e.value) for e in app.dataframe))
            empty = frame(CASES[0], "Europe PMC").iloc[0:0]
            meta = {"query": search.guided_query(CASES[0], "Europe PMC"), "timestamp_utc": "2026-01-01T00:00:00Z"}
            with patch.object(search, "fetch_guided", return_value=(empty, meta)):
                app.button(key=p + "_europe_pmc_run").click().run()
            self.assert_ok(app)
            self.assertTrue(any("returned no records" in item.value for item in app.info))
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            self.assertNotIn(SECRET, str(app.session_state._state.filtered_state))
            app.selectbox(key=p + "_provider").set_value("OpenAIRE").run()
            self.assertEqual(extraction_tables(app)[0]["Source"].tolist(), ["OpenAIRE"] * 2)
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-OpenAIRE"))
            with patch.object(search, "fetch_guided", side_effect=fake_fetch):
                app.button(key=p + "_openaire_run").click().run()
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("LIVE-OpenAIRE"))
            with patch.object(search, "fetch_guided", side_effect=RuntimeError("timeout")):
                app.button(key=p + "_openaire_run").click().run()
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-OpenAIRE"))
            self.assertTrue(any("OpenAIRE limitations" in e.value for e in app.warning))

    def test_browser_retry_falls_back_without_stale_result_or_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory).run()
            p = prefix(1)
            app.selectbox(key=p + "_provider").set_value("OpenAlex").run()
            with patch("browser_openalex.render_browser_openalex", side_effect=fake_browser):
                app.button(key=p + "_openalex_start").click().run()
            self.assert_ok(app)
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("LIVE-"))
            with patch("browser_openalex.render_browser_openalex", return_value=None):
                app.button(key=p + "_openalex_start").click().run()
            self.assert_ok(app)
            self.assertNotIn(p + "_provider_openalex_result", app.session_state)
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            self.assertTrue(any("No optional OpenAlex live search" in e.value for e in app.info))
            with patch("browser_openalex.render_browser_openalex", return_value=([], {"error": SECRET})):
                app.run()
            self.assert_ok(app)
            self.assertEqual(app.session_state[p + "_provider_openalex_result"], {"status": "error"})
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            self.assertNotIn(SECRET, str(app.session_state._state.filtered_state))

    def test_invalid_or_absent_snapshot_does_not_load_production_or_other_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            snap = directory / "guided_provider_snapshots"
            (snap / "ex1_health__openalex.csv").unlink()
            log = snap / "ex2_ubi__openalex.json"
            value = json.loads(log.read_text(encoding="utf-8"))
            value["corpus_sha256"] = "f" * 64
            log.write_text(json.dumps(value), encoding="utf-8")
            app = app_for(directory).run()
            for i in (1, 2):
                app.selectbox(key=prefix(i) + "_provider").set_value("OpenAlex")
            app.run()
            self.assert_ok(app)
            self.assertTrue(any("snapshot unavailable" in e.value for e in app.warning))
            self.assertTrue(any("SHA-256 mismatch" in e.value for e in app.warning))
            self.assertTrue(any("no successful live" in e.value for e in app.error))
            self.assertEqual(len(extraction_tables(app)), 2)
            self.assertFalse(any("ex1_health" in str(e.value) or "ex2_ubi" in str(e.value)
                                 for e in app.dataframe if "Candidate finding excerpt" in e.value.columns))

    def test_exact_search_plans_and_credential_filtering(self):
        for case in CASES:
            for provider in ("Europe PMC", "OpenAIRE", "OpenAlex"):
                query, params = guided._live_plan(case, provider)
                self.assertEqual(query, search.guided_query(case, provider))
                self.assertIn(query, params.values())
                self.assertEqual(params["cursorMark" if provider == "Europe PMC" else "cursor"], "*")
                self.assertEqual(params["per-page" if provider == "OpenAlex" else "pageSize"],
                                 50 if provider == "OpenAlex" else search.PAGE_SIZE)
                self.assertNotIn("filter", params)
        case, provider = CASES[0], "Europe PMC"
        query, params = guided._live_plan(case, provider)
        source = frame(case, provider).assign(api_key=SECRET, authorization=SECRET)
        metadata = {"case_key": case, "provider": provider, "query": query,
                    "parameters": params, "timestamp_utc": "2026-01-01T00:00:00Z",
                    "secret": SECRET, "nested": {"api_key": SECRET}}
        result = guided._prepare_live_result(case, provider, query, params, source, metadata)
        self.assertNotIn(SECRET, result["corpus"].to_string())
        self.assertNotIn(SECRET, json.dumps(result["log"]))
        for changed in ({**metadata, "provider": "Crossref"}, {**metadata, "query": "other"},
                        {**metadata, "parameters": {"query": "other"}}, {**metadata, "endpoint": guided._ENDPOINTS["Crossref"]}):
            with self.assertRaises(ValueError):
                guided._prepare_live_result(case, provider, query, params, source, changed)
        with self.assertRaises(ValueError):
            guided._prepare_live_result(case, provider, query, params, source.assign(Source="Crossref"), metadata)


class _OpenAlexResponse:
    def __init__(self, status=200, payload=None, invalid_json=False):
        self.status_code = status
        self.payload = payload
        self.invalid_json = invalid_json

    def json(self):
        if self.invalid_json:
            raise ValueError("invalid body " + SECRET)
        return self.payload


def _anonymous_http(endpoint, **kwargs):
    """Exercise the shared client, without sending any real request."""
    assert endpoint == "https://api.openalex.org/works"
    params = kwargs["params"]
    query = params["search.title_and_abstract.exact"]
    assert query in [search.guided_query(case, "OpenAlex") for case in CASES]
    assert params == {"search.title_and_abstract.exact": query, "per-page": 50,
                      "cursor": "*", "select": search.OPENALEX_SELECT}
    headers = kwargs.get("headers") or {}
    assert not any(name.lower() == "authorization" for name in headers)
    assert "email" not in str(params).lower() and "mailto" not in str(params).lower()
    records, _ = fake_browser(query, per_page=50, max_pages=1, year_from=None, year_to=None,
                              publication_types=(), search_scope="title_abstract_exact", require_abstract=False)
    records[0]["api_key"] = SECRET  # Unexpected response fields must not enter state or logs.
    return _OpenAlexResponse(payload={"results": records, "meta": {"count": 100, "next_cursor": "next",
                                                                     "api_key": SECRET}})


class GuidedAnonymousUITests(unittest.TestCase):
    def assert_ok(self, app):
        self.assertEqual([item.message for item in app.exception], [])

    def test_explicit_no_key_search_all_days_and_cases_stays_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            sentinel = pd.DataFrame([{"Title": "Private BYOD sentinel"}])
            # Four different cases, spanning all guided day contexts.
            for context, numbers in (("day1", (1, 4)), ("day2", (2,)), ("day3", (3,))):
                with self.subTest(context=context), \
                     patch("requests.Session.get", side_effect=_anonymous_http) as http, \
                     patch("browser_openalex.render_browser_openalex") as browser, \
                     patch.object(search, "fetch_guided") as other_fetch:
                    app = app_for(directory, context)
                    app.session_state["byod_df"] = sentinel.copy(deep=True)
                    app.session_state["byod_log"] = {"sentinel": "untouched"}
                    app.run()
                    for number in range(1, 5):
                        p = f"guided_{context}_{CASES[number-1]}_{number}"
                        app.selectbox(key=p + "_provider").set_value("OpenAlex")
                    app.run()
                    self.assert_ok(app)
                    http.assert_not_called()
                    self.assertTrue(all(table["ID"].iloc[0].startswith("SAVED-OpenAlex")
                                        for table in extraction_tables(app)))
                    warnings = " ".join(item.value for item in app.warning)
                    for text in ("no-key LIVE", "server IP", "one page", "50 works", "change over time"):
                        self.assertIn(text, warnings)
                    for number in numbers:
                        case = CASES[number - 1]
                        p = f"guided_{context}_{case}_{number}"
                        app.button(key=p + "_openalex_anonymous_run").click().run()
                        self.assert_ok(app)
                        live = extraction_tables(app)[number - 1]
                        self.assertEqual(live["ID"].tolist(), [f"LIVE-OpenAlex-{case}-1", f"LIVE-OpenAlex-{case}-2"])
                        self.assertEqual(live["Source"].tolist(), ["OpenAlex", "OpenAlex"])
                        self.assertEqual(live["Candidate finding excerpt"].tolist(), ["Results increased."] * 2)
                        decisions = [e.value for e in app.dataframe if guided.SCREEN_DECISION in e.value.columns]
                        self.assertEqual(decisions[number - 1][guided.SCREEN_DECISION].tolist(), ["Include", "Include", "Exclude"])
                        years = [e.value for e in app.dataframe if list(e.value.columns) == ["Year", "Included records"]]
                        links = [e.value for e in app.dataframe if "Shared studies" in e.value.columns]
                        self.assertEqual(years[number - 1]["Included records"].sum(), 2)
                        self.assertEqual(links[number - 1]["Shared studies"].tolist(), [2])
                        self.assertEqual(set(links[number - 1]["Source label"]) | set(links[number - 1]["Target label"]),
                                         {f"LIVE-OpenAlex-{case} Alice", f"LIVE-OpenAlex-{case} Bob"})
                        result = app.session_state[p + "_provider_openalex_result"]
                        self.assertEqual(result["log"]["query"], search.guided_query(case, "OpenAlex"))
                        self.assertEqual(result["log"]["parameters"]["per-page"], 50)
                        self.assertEqual(result["log"]["pages_fetched"], 1)
                        self.assertEqual(result["log"]["total_matches"], 100)
                        self.assertTrue(result["log"]["possibly_truncated"])
                        self.assertIn("no API key or email", result["log"]["access_mode"])
                        self.assertNotIn(SECRET, json.dumps(result["log"]))
                        self.assertNotIn(SECRET, result["corpus"].to_string())
                    for index, table in enumerate(extraction_tables(app), 1):
                        self.assertTrue(table["ID"].iloc[0].startswith("LIVE-" if index in numbers else "SAVED-"))
                    self.assertEqual(http.call_count, len(numbers))
                    browser.assert_not_called()
                    other_fetch.assert_not_called()
                    assert_frame_equal(app.session_state["byod_df"], sentinel)
                    self.assertEqual(app.session_state["byod_log"], {"sentinel": "untouched"})
                    self.assertNotIn(SECRET, str(app.session_state._state.filtered_state))

    def test_same_session_different_days_never_share_a_live_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            cases = fixture_cases(directory)
            source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
                      "from guided_workflow import render_guided_examples\n"
                      f"render_guided_examples('day1', data_dir={str(directory)!r})\n"
                      f"render_guided_examples('day2', data_dir={str(directory)!r})\n")
            day1 = f"guided_day1_{CASES[0]}_1"
            day2 = f"guided_day2_{CASES[0]}_1"

            def day2_response(*args, **kwargs):
                response = _anonymous_http(*args, **kwargs)
                for record in response.payload["results"]:
                    record["id"] += "-day2"
                return response

            # Rendering one representative case per day keeps this isolation
            # test small while both day namespaces share a single session.
            with patch.object(guided, "load_guided_cases", return_value=cases[:1]):
                app = AppTest.from_string(source, default_timeout=90).run()
                app.selectbox(key=day1 + "_provider").set_value("OpenAlex")
                app.selectbox(key=day2 + "_provider").set_value("OpenAlex")
                app.run()
                with patch("requests.Session.get", side_effect=_anonymous_http):
                    app.button(key=day1 + "_openalex_anonymous_run").click().run()
                self.assert_ok(app)
                first, second = extraction_tables(app)
                self.assertTrue(first["ID"].iloc[0].startswith("LIVE-"))
                self.assertTrue(second["ID"].iloc[0].startswith("SAVED-"))
                with patch("requests.Session.get", side_effect=day2_response):
                    app.button(key=day2 + "_openalex_anonymous_run").click().run()
                self.assert_ok(app)
                first, second = extraction_tables(app)
                self.assertFalse(first["ID"].iloc[0].endswith("-day2"))
                self.assertTrue(second["ID"].iloc[0].endswith("-day2"))
                app.button(key=day2 + "_openalex_use_saved").click().run()
                self.assert_ok(app)
                first, second = extraction_tables(app)
                self.assertTrue(first["ID"].iloc[0].startswith("LIVE-"))
                self.assertTrue(second["ID"].iloc[0].startswith("SAVED-"))

    def test_anonymous_failure_empty_and_browser_pending_all_use_correct_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture_cases(directory)
            app = app_for(directory).run()
            p = prefix(1)
            app.selectbox(key=p + "_provider").set_value("OpenAlex").run()
            # An anonymous search must unmount a pending browser component.
            with patch("browser_openalex.render_browser_openalex", return_value=None):
                app.button(key=p + "_openalex_start").click().run()
            self.assertTrue(app.session_state[p + "_openalex_active"])
            with patch("requests.Session.get", side_effect=_anonymous_http), \
                 patch("browser_openalex.render_browser_openalex") as browser:
                app.button(key=p + "_openalex_anonymous_run").click().run()
                browser.assert_not_called()
            self.assert_ok(app)
            self.assertFalse(app.session_state[p + "_openalex_active"])
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("LIVE-"))

            for status in (401, 429):
                # Establish a fresh live sample before each failed retry.
                with patch("requests.Session.get", side_effect=_anonymous_http):
                    app.button(key=p + "_openalex_anonymous_run").click().run()
                with patch("requests.Session.get", return_value=_OpenAlexResponse(status, {"error": SECRET})):
                    app.button(key=p + "_openalex_anonymous_run").click().run()
                self.assert_ok(app)
                self.assertTrue(any(f"HTTP {status}" in item.value and "saved sample" in item.value
                                    for item in app.warning))
                self.assertEqual(app.session_state[p + "_provider_openalex_result"], {"status": "error", "reason": str(status)})
                self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
                self.assertFalse(any("LIVE-OpenAlex-ex1_health" in str(e.value) for e in app.dataframe))

            empty = _OpenAlexResponse(payload={"results": [], "meta": {"count": 0, "next_cursor": None}})
            with patch("requests.Session.get", return_value=empty):
                app.button(key=p + "_openalex_anonymous_run").click().run()
            self.assert_ok(app)
            self.assertTrue(any("returned no records" in item.value for item in app.info))
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            self.assertIsNone(app.session_state[p + "_provider_openalex_result"]["log"]["total_matches"])
            with patch("requests.Session.get", return_value=_OpenAlexResponse(invalid_json=True)):
                app.button(key=p + "_openalex_anonymous_run").click().run()
            self.assert_ok(app)
            self.assertTrue(extraction_tables(app)[0]["ID"].iloc[0].startswith("SAVED-"))
            self.assertNotIn(SECRET, str(app.session_state._state.filtered_state))
            self.assertNotIn(SECRET, " ".join(item.value for item in app.warning))

            # No saved file means no fabricated or substituted corpus on error.
            (directory / "guided_provider_snapshots" / "ex1_health__openalex.csv").unlink()
            app.run()
            self.assert_ok(app)
            self.assertTrue(any("no successful live result" in item.value for item in app.error))
            self.assertEqual(len(extraction_tables(app)), 3)
            self.assertFalse(any("ex1_health" in str(element.value) for element in app.dataframe))


if __name__ == "__main__":
    unittest.main()
