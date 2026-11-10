"""Offline tests for guided concept/keyword networks and their provenance."""
import hashlib
import io
import json
import re
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
import guided_workflow as guided
import guided_provider_search as search


CASES = ("ex1_health", "ex2_ubi", "ex3_microplastics", "ex4_csr")


def make_snapshots(directory):
    """Independent verified samples; metadata is present for two providers only."""
    snapshots = directory / "guided_provider_snapshots"
    snapshots.mkdir()
    cases = []
    for n, case_id in enumerate(CASES, 1):
        case = {"key": case_id, "label": f"case {n}", "question": "Fixed question",
                "query": f"historical query {n}", "inclusion_terms": [f"topic{n}"],
                "exclusion_terms": ["exclude-me"], "corpus_file": f"{n}.csv",
                "log_file": f"{n}.json"}
        cases.append(case)
        for provider in guided.GUIDED_PROVIDERS:
            metadata = provider in ("OpenAlex", "OpenAIRE")
            label = f"{provider} subject {n}"
            frame = pd.DataFrame([
                {"ID": f"{provider}-{n}-1", "Source": provider, "Title": f"topic{n} amber garden",
                 "Abstract": "orchard harvest", "Concepts": f"{label}; Common" if metadata else "",
                 "Authors": "Ada; Bob", "References": "10.1234/shared"},
                {"ID": f"{provider}-{n}-2", "Source": provider, "Title": f"topic{n} amber meadow",
                 "Abstract": "orchard ecology", "Concepts": f"{label}; Common" if metadata else "",
                 "Authors": "Ada; Bob", "References": "10.1234/shared"},
                {"ID": f"{provider}-{n}-3", "Source": provider, "Title": f"topic{n} exclude-me",
                 "Abstract": "excludedunique forbiddenword", "Concepts": "Excluded concept; Forbidden concept",
                 "Authors": "Excluded; Nobody", "References": "10.1234/shared"},
            ])
            slug = provider.lower().replace(" ", "_")
            stem = f"{case_id}__{slug}"
            path = snapshots / f"{stem}.csv"
            frame.to_csv(path, index=False)
            query = search.guided_query(case_id, provider)
            query_key = {"Crossref": "query", "OpenAlex": "search.title_and_abstract.exact",
                         "Europe PMC": "query", "OpenAIRE": "search"}[provider]
            log = {"case_key": case_id, "provider": provider, "source": provider,
                   "query": query, "endpoint": guided._ENDPOINTS[provider],
                   "parameters": {query_key: query}, "retrieved_at_utc": "2026-01-01T00:00:00Z",
                   "returned": 3, "corpus_file": path.name,
                   "corpus_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (snapshots / f"{stem}.json").write_text(json.dumps(log), encoding="utf-8")
    (directory / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    return snapshots


def simple_app(rows, provider=""):
    source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
              "import pandas as pd\nfrom guided_workflow import _render_network\n"
              f"_render_network(pd.DataFrame({rows!r}), 'test', {provider!r})\n")
    return AppTest.from_string(source, default_timeout=90)


class GuidedNetworkLogicTests(unittest.TestCase):
    def setUp(self):
        source = pd.DataFrame([
            {"Title": "keep amber garden", "Abstract": "blue orchard", "Concepts": "Real Alpha; Real Beta"},
            {"Title": "keep amber meadow", "Abstract": "blue tree", "Concepts": "Real Alpha; Real Beta"},
            {"Title": "keep exclude-me", "Abstract": "forbiddenword excludedunique",
             "Concepts": "Excluded; Forbidden"},
        ])
        self.included = guided.included_records(guided.screen_records(source, ["keep"], ["exclude-me"]))
        self.before = self.included.copy(deep=True)

    def test_automatic_prefers_metadata_and_threshold_falls_back_deterministically(self):
        graph, concept_graph = guided._build_guided_network(self.included, guided._NETWORK_AUTOMATIC, 25, 1)
        self.assertEqual(graph["kind"], "concepts")
        self.assertIs(graph, concept_graph)
        self.assertEqual(graph["records_with_data"], 2)
        self.assertEqual([(n["label"], n["frequency"]) for n in graph["nodes"]],
                         [("Real Alpha", 2), ("Real Beta", 2)])
        self.assertEqual([e["weight"] for e in graph["edges"]], [2])
        # At threshold 3 no concept pair qualifies, even though metadata exists.
        result, checked = guided._build_guided_network(self.included, guided._NETWORK_AUTOMATIC, 25, 3)
        self.assertEqual(result["kind"], "terms")
        self.assertEqual(checked["records_with_data"], 2)
        self.assertEqual(checked["edges"], [])
        self.assertEqual(result, guided._build_guided_network(self.included, guided._NETWORK_AUTOMATIC, 25, 3)[0])
        cap, checked = guided._build_guided_network(self.included, guided._NETWORK_AUTOMATIC, 1, 1)
        self.assertEqual(cap["kind"], "terms")
        self.assertEqual(checked["edges"], [])
        self.assertEqual(cap["edges"], [])
        self.assertNotIn("forbidden", str(graph).lower())
        self.assertNotIn("forbidden", str(result).lower())
        assert_frame_equal(self.included, self.before)

    def test_guided_network_renders_labels_without_community_suffixes(self):
        graph, _ = guided._build_guided_network(self.included, guided._NETWORK_AUTOMATIC, 25, 1)
        html = guided.day2_network_view.make_network_html(graph)
        match = re.search(r"const nodeData = (\[.*?\]);", html)
        self.assertIsNotNone(match)
        nodes = json.loads(match.group(1))
        self.assertEqual({node["id"]: node["label"] for node in nodes},
                         {node["id"]: node["label"] for node in graph["nodes"]})
        self.assertTrue(all("community" in node and "color" in node for node in nodes))
        self.assertIn("Community: C", html)

    def test_missing_metadata_falls_back_but_explicit_modes_never_do(self):
        no_metadata = self.included.drop(columns="Concepts")
        auto, concept_graph = guided._build_guided_network(no_metadata, guided._NETWORK_AUTOMATIC, 25, 1)
        self.assertEqual(auto["kind"], "terms")
        self.assertTrue(auto["edges"])
        self.assertEqual(concept_graph["records_with_data"], 0)
        self.assertEqual(auto["records_with_data"], 2)
        explicit_concepts, _ = guided._build_guided_network(no_metadata, guided._NETWORK_CONCEPTS, 25, 1)
        self.assertEqual(explicit_concepts["kind"], "concepts")
        self.assertEqual(explicit_concepts["nodes"], [])
        explicit_terms, _ = guided._build_guided_network(self.included, guided._NETWORK_TERMS, 25, 1)
        self.assertEqual(explicit_terms["kind"], "terms")
        self.assertTrue(explicit_terms["edges"])
        self.assertTrue(all("real alpha" != n["label"].lower() for n in explicit_terms["nodes"]))

    def test_concept_and_term_tables_identify_the_correct_units(self):
        for choice, node_column, edge_column in [
            (guided._NETWORK_CONCEPTS, "Included records containing concept", "Included records containing both concepts"),
            (guided._NETWORK_TERMS, "Included records with selected term", "Included records with both selected terms"),
        ]:
            graph, _ = guided._build_guided_network(self.included, choice, 25, 1)
            nodes, edges = guided._network_tables(graph, graph["kind"])
            self.assertIn(node_column, nodes.columns)
            self.assertIn(edge_column, edges.columns)
            self.assertNotIn("Shared references", edges.columns)
            self.assertEqual(nodes[node_column].tolist(), [n["frequency"] for n in graph["nodes"]])
            self.assertEqual(edges[edge_column].tolist(), [e["weight"] for e in graph["edges"]])
            self.assertEqual(pd.read_csv(io.BytesIO(guided.safe_csv_bytes(edges)))[edge_column].tolist(),
                             [e["weight"] for e in graph["edges"]])

    def test_real_saved_snapshots_are_included_only_and_default_graph_has_links(self):
        # Test the actual bundled data without reaching out to providers.
        for case in guided.load_guided_cases():
            for provider in guided.GUIDED_PROVIDERS:
                with self.subTest(case=case["key"], provider=provider):
                    crossref = provider == "Crossref"
                    directory = guided.GUIDED_DATA_DIR if crossref else guided.GUIDED_SNAPSHOT_DIR
                    corpus, _, errors = guided.load_provider_snapshot(case, provider, directory, legacy_override=crossref)
                    self.assertEqual(errors, [])
                    included = guided.included_records(guided.screen_records(corpus, case["inclusion_terms"], case["exclusion_terms"]))
                    graph, concepts = guided._build_guided_network(included, guided._NETWORK_AUTOMATIC, 25, 1)
                    self.assertEqual(graph["total_records"], len(included))
                    self.assertTrue(graph["edges"], "Insufficient real included data for a default graph")
                    self.assertEqual(graph["kind"], "concepts" if concepts["edges"] else "terms")
                    self.assertLessEqual(len(graph["nodes"]), 25)


class GuidedNetworkUITests(unittest.TestCase):
    def test_every_case_provider_and_day_shares_default_options_and_included_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = make_snapshots(root)
            source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
                      "from guided_workflow import render_guided_examples\n" +
                      "\n".join(f"render_guided_examples({day!r}, data_dir={str(root)!r}, snapshot_dir={str(snapshots)!r})"
                                for day in ("day1", "day2", "day3")))
            app = AppTest.from_string(source, default_timeout=90)
            sentinel = pd.DataFrame([{"Title": "private BYOD", "Concepts": "Forbidden; Leakage"}])
            app.session_state["byod_included_df"] = sentinel.copy(deep=True)
            with patch("day2_network_view.make_network_html", return_value="<html></html>"), \
                 patch("requests.get") as direct, patch("requests.Session.get") as session:
                for provider in guided.GUIDED_PROVIDERS:
                    if provider != "Crossref":
                        for day in ("day1", "day2", "day3"):
                            for n, case_id in enumerate(CASES, 1):
                                app.selectbox(key=f"guided_{day}_{case_id}_{n}_provider").set_value(provider)
                    app.run()
                    self.assertFalse(app.exception, [e.message for e in app.exception])
                    self.assertEqual(len(app.get("iframe")), 12)
                    for day in ("day1", "day2", "day3"):
                        for n, case_id in enumerate(CASES, 1):
                            prefix = f"guided_{day}_{case_id}_{n}"
                            if provider != "Crossref":
                                prefix += "_" + provider.lower().replace(" ", "_")
                            selector = app.selectbox(key=prefix + "_network_kind")
                            self.assertEqual(selector.value, guided._NETWORK_AUTOMATIC)
                            self.assertEqual(selector.options, list(guided._NETWORK_CHOICES))
                            self.assertEqual(app.slider(key=prefix + "_automatic_top").value, 25)
                            self.assertEqual(app.slider(key=prefix + "_automatic_minimum").value, 1)
                    metadata = provider in ("OpenAlex", "OpenAIRE")
                    column = "Included records containing both concepts" if metadata else "Included records with both selected terms"
                    tables = [x.value for x in app.dataframe if column in x.value.columns]
                    self.assertEqual(len(tables), 12)
                    for table in tables:
                        combined = " ".join(table.astype(str).to_numpy().flatten()).casefold()
                        self.assertNotIn("excluded", combined)
                        self.assertNotIn("forbidden", combined)
                        if metadata:
                            self.assertIn(provider.casefold(), combined)
                    text = " ".join(e.value for e in app.caption) + " " + " ".join(e.value for e in app.info)
                    self.assertIn("Text-derived keywords are not source-assigned concepts", text)
                    self.assertIn("TF-IDF input is title/abstract", text)
                    provenance = {"OpenAlex": "OpenAlex concept display names",
                                  "OpenAIRE": "OpenAIRE subjects are mapped to Concepts",
                                  "Crossref": "Crossref subjects, when supplied",
                                  "Europe PMC": "Europe PMC adapter currently does not populate Concepts"}
                    self.assertIn(provenance[provider], text)
                    if provider == "OpenAIRE":
                        self.assertIn("provider description, not necessarily a formal abstract", text)
                    if metadata:
                        self.assertIn("Automatic selection: source Concepts metadata", text)
                    else:
                        self.assertIn("Automatic fallback to TF-IDF title/abstract keywords", text)
                        self.assertIn("0 of 2 heuristic-included records", text)
                    self.assertFalse(app.text_input)
                    self.assertFalse(app.text_area)
                    assert_frame_equal(app.session_state["byod_included_df"], sentinel)
                direct.assert_not_called()
                session.assert_not_called()

    def test_explicit_modes_and_threshold_fallback_are_explained(self):
        rows = [{"Title": "amber garden", "Abstract": "blue orchard", "Concepts": "Alpha; Beta"},
                {"Title": "amber meadow", "Abstract": "blue tree", "Concepts": "Alpha; Beta"}]
        with patch("day2_network_view.make_network_html", return_value="<html></html>"):
            app = simple_app(rows).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key="test_network_kind").value, guided._NETWORK_AUTOMATIC)
            self.assertTrue(any("source Concepts metadata" in e.value for e in app.caption))
            self.assertEqual(len(app.get("iframe")), 1)
            app.slider(key="test_automatic_minimum").set_value(3).run()
            self.assertFalse(app.exception)
            infos = " ".join(x.value for x in app.info)
            self.assertIn("fallback to TF-IDF", infos)
            self.assertIn("produced no link at the current node cap and minimum weight", infos)
            self.assertIn("not source-assigned concepts", infos)
            self.assertIn("No links meet", infos)
            self.assertEqual(len(app.get("iframe")), 0)
            app.selectbox(key="test_network_kind").set_value(guided._NETWORK_TERMS).run()
            self.assertTrue(any("Included records with both selected terms" in x.value.columns for x in app.dataframe))
            self.assertTrue(any(x.key == "test_terms_links_csv" for x in app.get("download_button")))
            app.selectbox(key="test_network_kind").set_value(guided._NETWORK_CONCEPTS).run()
            self.assertTrue(any("Included records containing both concepts" in x.value.columns for x in app.dataframe))
            self.assertTrue(any(x.key == "test_concepts_links_csv" for x in app.get("download_button")))
            app.selectbox(key="test_network_kind").set_value("Co-authorship").run()
            self.assertTrue(any("No usable Authors" in x.value for x in app.info))
            app.selectbox(key="test_network_kind").set_value("Bibliographic coupling").run()
            self.assertTrue(any("No usable References" in x.value for x in app.info))

    def test_empty_no_metadata_no_text_and_no_links_are_explicit(self):
        with patch("day2_network_view.make_network_html", return_value="<html></html>") as render:
            empty = simple_app([]).run()
            self.assertFalse(empty.exception)
            self.assertTrue(any("no heuristic-included records to map" in x.value.lower() for x in empty.info))
            no_text = simple_app([{"Concepts": ""}]).run()
            self.assertFalse(no_text.exception)
            info = " ".join(x.value for x in no_text.info)
            self.assertIn("no usable Concepts metadata was present", info)
            self.assertIn("No usable title/abstract terms", info)
            self.assertTrue(any("0 of 1 heuristic-included records" in x.value for x in no_text.caption))
            no_text.selectbox(key="test_network_kind").set_value(guided._NETWORK_CONCEPTS).run()
            self.assertTrue(any("No usable Concepts metadata" in x.value for x in no_text.info))
            self.assertFalse(any("fallback" in x.value.lower() for x in no_text.info))
            single = simple_app([{"Title": "amber", "Concepts": "Only"}]).run()
            self.assertTrue(any("produced no link" in x.value for x in single.info))
            self.assertTrue(any("No links meet" in x.value for x in single.info))
            self.assertEqual(len(single.get("iframe")), 0)
            render.assert_not_called()

    def test_title_only_fallback_and_openaire_description_are_disclosed(self):
        rows = [{"Title": "amber meadow", "Abstract": "", "Concepts": ""}]
        with patch("day2_network_view.make_network_html", return_value="<html></html>"):
            app = simple_app(rows, "OpenAIRE").run()
            captions = " ".join(x.value for x in app.caption)
            self.assertIn("TF-IDF input is title-only", captions)
            self.assertIn("none have recorded abstract-field text", captions)
            self.assertIn("OpenAIRE subjects", captions)
            self.assertIn("not uniformly author keywords", captions)
            self.assertIn("provider description, not necessarily a formal abstract", captions)
            self.assertTrue(any("fallback to TF-IDF title-only keywords" in x.value for x in app.info))

    def test_live_selection_replaces_saved_network_and_excludes_byod_and_screen_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = make_snapshots(root)
            source = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
                      "from guided_workflow import render_guided_examples\n"
                      f"render_guided_examples('live', data_dir={str(root)!r}, snapshot_dir={str(snapshots)!r})\n")
            app = AppTest.from_string(source, default_timeout=90)
            app.session_state["byod_included_df"] = pd.DataFrame([{"Concepts": "Private; BYOD"}])
            live = pd.DataFrame([
                {"ID": "live-1", "Source": "OpenAlex", "Title": "topic1 live title", "Abstract": "",
                 "Concepts": "Fresh Alpha; Fresh Beta"},
                {"ID": "live-2", "Source": "OpenAlex", "Title": "topic1 exclude-me", "Abstract": "",
                 "Concepts": "Wrong Alpha; Wrong Beta"},
            ])
            log = {"query": "fixed", "endpoint": guided._ENDPOINTS["OpenAlex"],
                   "retrieved_at_utc": "2026-01-01T00:00:00Z", "parameters": {}, "returned": 2}
            with patch("day2_network_view.make_network_html", return_value="<html></html>"), \
                 patch.object(guided, "_render_live_retrieval", return_value=(live, log, "ok")):
                app.run()
                app.selectbox(key="guided_live_ex1_health_1_provider").set_value("OpenAlex").run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            tables = [x.value for x in app.dataframe if "Included records containing both concepts" in x.value.columns]
            self.assertEqual(len(tables), 1)
            labels = set(tables[0]["Source label"]) | set(tables[0]["Target label"])
            self.assertEqual(labels, {"Fresh Alpha", "Fresh Beta"})
            self.assertEqual(tables[0]["Included records containing both concepts"].tolist(), [1])
            self.assertEqual(app.session_state["byod_included_df"].iloc[0]["Concepts"], "Private; BYOD")


if __name__ == "__main__":
    unittest.main()
