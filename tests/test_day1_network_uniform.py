"""Day 1's BYOD keyword map delegates the original graph to the shared view."""
import ast
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock

import pandas as pd
from streamlit.testing.v1 import AppTest

from day2_network_view import make_network_html
from day2_networks import community_partition

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "1_Day1_Query_to_Corpus.py"


def page_helpers(renderer):
    """Load the real helper definitions without running the Streamlit page."""
    tree = ast.parse(PAGE.read_text(encoding="utf-8"), filename=str(PAGE))
    names = {"_build_cooccurrence_network", "generate_pyvis_html", "generate_vosviewer_json"}
    selected = [node for node in tree.body
                if (isinstance(node, ast.FunctionDef) and node.name in names)
                or (isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "_STOPWORDS"
                    for target in node.targets))]
    namespace = {"Counter": Counter, "combinations": combinations, "re": re,
                 "make_network_html": renderer, "community_partition": community_partition}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PAGE), "exec"), namespace)
    return namespace


def records():
    # Gamma and orphan have no qualifying edge at threshold 2. Repeated concepts
    # within one record must not inflate frequencies or co-occurrences.
    return pd.DataFrame([
        {"Title": "Alpha Beta", "Concepts": "alpha; beta; beta", "Abstract": "abstractonly"},
        {"Title": "Alpha Beta", "Concepts": "ALPHA; BETA", "Abstract": "abstractonly"},
        {"Title": "Alpha", "Concepts": "gamma", "Abstract": "abstractonly"},
        {"Title": "", "Concepts": "orphan; orphan", "Abstract": "abstractonly"},
    ])


class Day1NetworkAdapterTests(unittest.TestCase):
    def test_original_builder_output_is_forwarded_as_canonical_graph(self):
        renderer = Mock(return_value="<shared-network />")
        helpers = page_helpers(renderer)
        builder = Mock(wraps=helpers["_build_cooccurrence_network"])
        helpers["_build_cooccurrence_network"] = builder

        html, error = helpers["generate_pyvis_html"](records(), top_n=40, min_cooccurrence=2)
        self.assertEqual((html, error), ("<shared-network />", None))
        builder.assert_called_once_with(unittest.mock.ANY, top_n=40, min_cooccurrence=2)
        renderer.assert_called_once_with({
            "kind": "keywords",
            "nodes": [
                {"id": "alpha", "label": "alpha", "frequency": 3},
                {"id": "beta", "label": "beta", "frequency": 2},
            ],
            "edges": [{"source": "alpha", "target": "beta", "weight": 2}],
        })

    def test_threshold_and_top_n_continue_to_control_original_builder(self):
        renderer = Mock(return_value="html")
        helpers = page_helpers(renderer)
        helpers["generate_pyvis_html"](records(), top_n=40, min_cooccurrence=1)
        graph = renderer.call_args.args[0]
        self.assertEqual({n["id"]: n["frequency"] for n in graph["nodes"]},
                         {"alpha": 3, "beta": 2, "gamma": 1})
        self.assertEqual(graph["edges"], [
            {"source": "alpha", "target": "beta", "weight": 2},
            {"source": "alpha", "target": "gamma", "weight": 1},
        ])
        renderer.reset_mock()
        helpers["generate_pyvis_html"](records(), top_n=2, min_cooccurrence=1)
        self.assertEqual({n["id"] for n in renderer.call_args.args[0]["nodes"]}, {"alpha", "beta"})

    def test_empty_graph_skips_renderer_and_explains_threshold(self):
        renderer = Mock()
        helpers = page_helpers(renderer)
        for df, threshold in ((records(), 3), (pd.DataFrame(), 1)):
            html, error = helpers["generate_pyvis_html"](df, min_cooccurrence=threshold)
            self.assertIsNone(html)
            self.assertIn("lowering the minimum co-occurrence threshold", error)
        renderer.assert_not_called()

    def test_renderer_errors_are_returned_through_existing_interface(self):
        for exc in (ValueError("missing local library"), OSError("cannot read library"), ImportError()):
            with self.subTest(error=exc):
                renderer = Mock(side_effect=exc)
                html, error = page_helpers(renderer)["generate_pyvis_html"](records())
                self.assertIsNone(html)
                self.assertTrue(error)
                renderer.assert_called_once()

    def test_vosviewer_json_uses_the_connected_louvain_graph(self):
        renderer = Mock(side_effect=AssertionError("VOSviewer must not call the shared renderer"))
        helpers = page_helpers(renderer)
        vos = helpers["generate_vosviewer_json"](records(), top_n=40, min_cooccurrence=2)
        items = {item["label"]: item for item in vos["network"]["items"]}
        self.assertEqual(set(items), {"alpha", "beta"})
        self.assertEqual(items["alpha"]["weights"]["Occurrences"], 3)
        self.assertEqual(items["alpha"]["cluster"], items["beta"]["cluster"])
        self.assertEqual(len(vos["network"]["links"]), 1)
        self.assertEqual(vos["network"]["links"][0]["strength"], 2)
        self.assertEqual(vos["config"]["parameters"]["item_size_variation"], 0)
        self.assertFalse(vos["config"]["parameters"]["largest_component"])
        renderer.assert_not_called()

    def test_shared_renderer_escapes_untrusted_keyword_labels(self):
        attack = "</script><script>window.evil=1</script>"
        df = pd.DataFrame([{"Title": "Alpha", "Concepts": attack}] * 2)
        page, error = page_helpers(make_network_html)["generate_pyvis_html"](df)
        self.assertIsNone(error)
        self.assertNotIn(attack, page)
        self.assertIn("\\u003c/script\\u003e", page)
        self.assertIn("tip.textContent", page)

    def test_real_shared_html_has_uniform_nodes_and_louvain_communities(self):
        df = pd.DataFrame([
            {"Concepts": "alpha; beta"}, {"Concepts": "alpha; beta"},
            {"Concepts": "gamma; delta"}, {"Concepts": "gamma; delta"},
            {"Concepts": "alpha"},
        ])
        generate = page_helpers(make_network_html)["generate_pyvis_html"]
        html, error = generate(df)
        self.assertIsNone(error)
        node_match = re.search(r"const nodeData = (\[.*?\]);", html)
        edge_match = re.search(r"const edgeData = (\[.*?\]);", html)
        self.assertIsNotNone(node_match)
        self.assertIsNotNone(edge_match)
        nodes = {node["id"]: node for node in json.loads(node_match.group(1))}
        edges = json.loads(edge_match.group(1))
        self.assertEqual(len({node["size"] for node in nodes.values()}), 1)
        self.assertGreater(nodes["alpha"]["size"], 0)
        self.assertEqual(nodes["alpha"]["frequency"], 3)
        self.assertEqual(nodes["beta"]["frequency"], 2)
        self.assertNotIn("value", nodes["alpha"])
        self.assertEqual({node["label"] for node in nodes.values()}, set(nodes))
        self.assertTrue(all(not re.search(r"\[C\d+\]", node["label"]) for node in nodes.values()))
        self.assertEqual(nodes["alpha"]["community"], nodes["beta"]["community"])
        self.assertEqual(nodes["gamma"]["community"], nodes["delta"]["community"])
        self.assertNotEqual(nodes["alpha"]["community"], nodes["gamma"]["community"])
        self.assertEqual(nodes["alpha"]["color"], nodes["beta"]["color"])
        self.assertNotEqual(nodes["alpha"]["color"], nodes["gamma"]["color"])
        self.assertEqual([edge["weight"] for edge in edges], [2, 2])
        self.assertIn("metricLabels.node + node.frequency", html)
        self.assertIn("metricLabels.edge + edge.weight", html)
        second_html, second_error = generate(df)
        self.assertIsNone(second_error)
        self.assertEqual(node_match.group(1), re.search(r"const nodeData = (\[.*?\]);", second_html).group(1))


class Day1NetworkUITests(unittest.TestCase):
    def test_byod_network_and_threshold_controls(self):
        df = records().assign(Year=2020, Venue="Journal", Authors="", DOI="", Citations=0)
        app = AppTest.from_file(str(PAGE), default_timeout=90)
        app.session_state["byod_df"] = df
        app.session_state["byod_api"] = "Test data"
        app.session_state["byod_query"] = "Test query"
        app.run().sidebar.radio[0].set_value("🔎 BYOD — Your Own Query").run()
        self.assertEqual(len(app.exception), 0)
        content = "\n".join(item.value for item in app.markdown)
        self.assertIn("All nodes have the same size", content)
        self.assertIn("Louvain communities", content)
        self.assertIn("link's weight", content)
        self.assertTrue(any("separate VOSviewer JSON" in c.value for c in app.caption))
        self.assertEqual(len(app.get("iframe")), 1)
        self.assertIn('id="graph"', app.get("iframe")[0].proto.srcdoc)

        app.slider(key="pyvis_mincooc_byod").set_value(3).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get("iframe")), 0)
        self.assertTrue(any("Not enough co-occurring keywords" in w.value for w in app.warning))


if __name__ == "__main__":
    unittest.main()
