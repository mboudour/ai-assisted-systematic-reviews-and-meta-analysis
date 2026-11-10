"""Regression tests for the Day 3 extraction-table term network."""
import ast
import json
import re
import unittest
from collections import Counter
from itertools import combinations
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
from streamlit.testing.v1 import AppTest

from day2_network_view import make_network_html

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "3_Day3_Studies_to_Evidence.py"


def load_network_helpers(renderer=make_network_html):
    """Load the real helpers without running the Streamlit page's top-level UI."""
    tree = ast.parse(PAGE.read_text(encoding="utf-8"), filename=str(PAGE))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_STOPWORDS" for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {
            "_build_cooccurrence_network", "generate_pyvis_html"
        }:
            selected.append(node)
    namespace = {"re": re, "Counter": Counter, "combinations": combinations,
                 "make_network_html": renderer}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PAGE), "exec"), namespace)
    return namespace


def records():
    return pd.DataFrame([
        {"Title": "Alpha alpha beta gamma", "Country": "Canada", "Population": "Patients alpha",
         "Intervention": "Exercise", "Outcome": "Recovery", "Concepts": "sourceconcept",
         "Abstract": "abstractonly"},
        {"Title": "Alpha beta", "Country": "Canada", "Population": "Patients",
         "Intervention": "Exercise", "Outcome": "Recovery", "Concepts": "sourceconcept",
         "Abstract": "abstractonly"},
        {"Title": "Alpha gamma zebra", "Concepts": "sourceconcept", "Abstract": "abstractonly"},
        {"Title": "Alpha"},
    ]).fillna("")


def html_data(html, name):
    match = re.search(r"const " + re.escape(name) + r"\s*=\s*(\[.*?\]);", html, re.DOTALL)
    if not match:
        raise AssertionError(f"Cannot find {name} in rendered HTML")
    return json.loads(match.group(1))


class Day3NetworkTests(unittest.TestCase):
    def test_graph_preserves_builder_frequencies_edges_and_omits_isolates(self):
        renderer = Mock(return_value="shared html")
        helpers = load_network_helpers(renderer)
        build, generate = helpers["_build_cooccurrence_network"], helpers["generate_pyvis_html"]
        df = records()
        freq, edges, selected = build(df, top_n=50, min_cooccurrence=2)
        self.assertEqual(freq["alpha"], 4)  # repeated words/fields count once per study
        self.assertEqual(freq["beta"], 2)
        self.assertEqual(freq["gamma"], 2)
        self.assertEqual(freq["zebra"], 1)
        self.assertNotIn("sourceconcept", freq)
        self.assertNotIn("abstractonly", freq)
        self.assertIn("zebra", selected)

        html, err = generate(df, top_n=50, min_cooccurrence=2)
        self.assertEqual((html, err), ("shared html", None))
        graph = renderer.call_args.args[0]
        self.assertEqual(set(graph), {"kind", "nodes", "edges"})
        self.assertEqual(graph["kind"], "keywords")
        drawn = {a for a, _, _ in edges} | {b for _, b, _ in edges}
        self.assertNotIn("zebra", drawn)
        self.assertEqual(graph["nodes"], [
            {"id": term, "label": term, "frequency": freq[term]} for term in sorted(drawn)
        ])
        self.assertEqual(graph["edges"], [
            {"source": a, "target": b, "weight": n} for a, b, n in sorted(edges)
        ])
        self.assertIn({"source": "alpha", "target": "beta", "weight": 2}, graph["edges"])
        self.assertIn({"source": "alpha", "target": "gamma", "weight": 2}, graph["edges"])

    def test_threshold_and_top_n_are_passed_to_existing_builder(self):
        renderer = Mock(return_value="ok")
        helpers = load_network_helpers(renderer)
        df = pd.DataFrame({"Title": ["alpha beta gamma delta", "alpha beta gamma",
                                      "alpha beta", "alpha"]})
        self.assertEqual(helpers["generate_pyvis_html"](df, top_n=2, min_cooccurrence=3), ("ok", None))
        graph = renderer.call_args.args[0]
        self.assertEqual(graph["nodes"], [
            {"id": "alpha", "label": "alpha", "frequency": 4},
            {"id": "beta", "label": "beta", "frequency": 3},
        ])
        self.assertEqual(graph["edges"], [{"source": "alpha", "target": "beta", "weight": 3}])

    def test_empty_network_keeps_warning_and_skips_renderer(self):
        renderer = Mock()
        generate = load_network_helpers(renderer)["generate_pyvis_html"]
        expected = ("Not enough co-occurring keywords to build a network with the current settings. "
                    "Try lowering the minimum co-occurrence threshold or using a larger corpus.")
        for df, top_n, minimum in ((pd.DataFrame(), 30, 2), (records(), 0, 1), (records(), 50, 5)):
            with self.subTest(top_n=top_n, minimum=minimum):
                self.assertEqual(generate(df, top_n=top_n, min_cooccurrence=minimum), (None, expected))
        renderer.assert_not_called()

    def test_shared_renderer_failure_returns_an_error_instead_of_crashing(self):
        renderer = Mock(side_effect=ValueError("Local library unavailable"))
        generate = load_network_helpers(renderer)["generate_pyvis_html"]
        self.assertEqual(generate(records(), min_cooccurrence=2), (None, "Local library unavailable"))

    def test_shared_output_is_safe_offline_and_uniform_with_frequency(self):
        helpers = load_network_helpers()
        # Inject a hostile builder result to test the rendering boundary, even though
        # the actual title tokenizer accepts only alphabetic words.
        attack = '</script><img src=x onerror=alert(1)>'
        helpers["_build_cooccurrence_network"] = Mock(
            return_value=(Counter({attack: 5, "safe": 1}), [(attack, "safe", 1)], {attack, "safe"})
        )
        html, err = helpers["generate_pyvis_html"](pd.DataFrame())
        self.assertIsNone(err)
        self.assertNotIn(attack, html)
        self.assertIn(r"\u003c/script\u003e", html)
        self.assertNotIn("<script src=", html.lower())
        self.assertIn("textContent", html)
        nodes = html_data(html, "nodeData")
        self.assertEqual({node["id"]: node["frequency"] for node in nodes}, {attack: 5, "safe": 1})
        self.assertEqual(len({node["size"] for node in nodes}), 1)
        self.assertEqual(html_data(html, "edgeData")[0]["weight"], 1)

    def test_shared_colors_are_deterministic_for_disconnected_term_groups(self):
        generate = load_network_helpers()["generate_pyvis_html"]
        df = pd.DataFrame({"Title": ["alpha alpha beta", "alpha beta", "alpha beta",
                                      "delta omega", "delta omega", "delta omega"]})
        first, err = generate(df, min_cooccurrence=2)
        self.assertIsNone(err)
        second, err = generate(df.iloc[::-1], min_cooccurrence=2)
        self.assertIsNone(err)
        nodes = {n["id"]: n for n in html_data(first, "nodeData")}
        other = {n["id"]: n for n in html_data(second, "nodeData")}
        self.assertEqual({node["label"] for node in nodes.values()}, set(nodes))
        self.assertTrue(all(not re.search(r"\[C\d+\]", node["label"]) for node in nodes.values()))
        self.assertEqual({k: (v["community"], v["color"]) for k, v in nodes.items()},
                         {k: (v["community"], v["color"]) for k, v in other.items()})
        self.assertEqual(nodes["alpha"]["community"], nodes["beta"]["community"])
        self.assertEqual(nodes["delta"]["community"], nodes["omega"]["community"])
        self.assertNotEqual(nodes["alpha"]["community"], nodes["delta"]["community"])
        self.assertEqual(len({node["size"] for node in nodes.values()}), 1)
        self.assertEqual([edge["weight"] for edge in html_data(first, "edgeData")], [3, 3])

    def test_byod_text_and_empty_warning_follow_slider(self):
        app = AppTest.from_file(str(PAGE), default_timeout=90)
        app.session_state["byod_included_df"] = records()
        app.run().sidebar.radio[0].set_value("🔎 BYOD — Your Own Synthesis").run()
        self.assertEqual([item.message for item in app.exception], [])
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Country, Population,", markdown)
        self.assertIn("source-tagged **Concepts**", markdown)
        self.assertIn("does **not** use abstracts", markdown)
        self.assertIn("Circles are equal in size", markdown)
        self.assertEqual(len(app.get("iframe")), 1)
        nodes = {node["id"]: node for node in html_data(app.get("iframe")[0].proto.srcdoc, "nodeData")}
        self.assertEqual(nodes["alpha"]["frequency"], 4)
        self.assertEqual(nodes["canada"]["frequency"], 2)
        self.assertNotIn("sourceconcept", nodes)
        self.assertNotIn("abstractonly", nodes)
        self.assertNotIn("zebra", nodes)  # isolated after the default threshold
        app.slider(key="pyvis_mincooc_byod").set_value(5).run()
        self.assertEqual([item.message for item in app.exception], [])
        self.assertTrue(any("Not enough co-occurring keywords" in item.value for item in app.warning))
        self.assertEqual(len(app.get("iframe")), 0)


if __name__ == "__main__":
    unittest.main()
