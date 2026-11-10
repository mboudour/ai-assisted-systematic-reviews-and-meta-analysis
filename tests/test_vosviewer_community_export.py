"""Regression tests for the Day 1 VOSviewer keyword-network export.

Load the real page helpers without executing the Streamlit UI. The synthetic
corpus has a weak bridge between two dense communities, a smaller disconnected
component, and keywords omitted by the edge threshold.
"""
import ast
from collections import Counter
from itertools import combinations
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import Mock

import networkx as nx
import pandas as pd

from network_loader_v1 import community_partition


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "1_Day1_Query_to_Corpus.py"


def page_helpers(renderer=None, partition=community_partition):
    """Extract the real page functions without importing/running the page UI."""
    tree = ast.parse(PAGE.read_text(encoding="utf-8"), filename=str(PAGE))
    names = {"_build_cooccurrence_network", "generate_pyvis_html", "generate_vosviewer_json"}
    selected = [
        node for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in names)
        or (isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_STOPWORDS"
            for target in node.targets
        ))
    ]
    namespace = {
        "Counter": Counter,
        "combinations": combinations,
        "re": re,
        "make_network_html": renderer,
        "community_partition": partition,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PAGE), "exec"), namespace)
    return namespace


def records():
    """Two five-weight triangles joined by a two-weight bridge, plus a pair."""
    rows = (
        [{"Title": "Alpha alpha", "Concepts": "alpha; bravo; charlie; alpha"}] * 5
        + [{"Title": "", "Concepts": "delta; echo; foxtrot"}] * 5
        + [{"Title": "", "Concepts": "charlie; delta"}] * 2
        + [{"Title": "", "Concepts": "alpha"}] * 4
        + [{"Title": "", "Concepts": "orphan"}] * 3
        + [{"Title": "", "Concepts": "golf; hotel"}] * 2
        + [{"Title": "", "Concepts": "alpha; epsilon"}]
    )
    return pd.DataFrame(rows)


def decoded_export(vos):
    """Convert VOS numeric endpoints to the shared graph's keyword IDs."""
    items = vos["network"]["items"]
    by_id = {item["id"]: item for item in items}
    assert len(by_id) == len(items), "export IDs must be unique"
    return {
        "kind": "keywords",
        "nodes": [
            {"id": item["label"], "label": item["label"],
             "frequency": item["weights"]["Occurrences"]}
            for item in items
        ],
        "edges": sorted([
            {"source": min(by_id[link["source_id"]]["label"], by_id[link["target_id"]]["label"]),
             "target": max(by_id[link["source_id"]]["label"], by_id[link["target_id"]]["label"]),
             "weight": link["strength"]}
            for link in vos["network"]["links"]
        ], key=lambda edge: (edge["source"], edge["target"])),
    }


class VosviewerCommunityExportTests(unittest.TestCase):
    def test_exact_export_graph_uses_shared_weighted_louvain_not_components(self):
        renderer = Mock(return_value="<network>")
        partition = Mock(wraps=community_partition)
        helpers = page_helpers(renderer=renderer, partition=partition)
        df = records()
        result, error = helpers["generate_pyvis_html"](df, top_n=40, min_cooccurrence=2)
        self.assertEqual((result, error), ("<network>", None))
        graph = renderer.call_args.args[0]
        vos = helpers["generate_vosviewer_json"](df, top_n=40, min_cooccurrence=2)

        partition.assert_called_once_with(graph)
        self.assertEqual(decoded_export(vos), graph)
        items = {item["label"]: item for item in vos["network"]["items"]}
        self.assertEqual({label: item["cluster"] for label, item in items.items()},
                         community_partition(decoded_export(vos)))
        self.assertEqual({label: item["cluster"] for label, item in items.items()}, {
            "alpha": 1, "bravo": 1, "charlie": 1,
            "delta": 2, "echo": 2, "foxtrot": 2,
            "golf": 3, "hotel": 3,
        })
        graph_nx = nx.Graph()
        graph_nx.add_weighted_edges_from((e["source"], e["target"], e["weight"])
                                         for e in graph["edges"])
        self.assertTrue(nx.has_path(graph_nx, "alpha", "foxtrot"))
        self.assertNotEqual(items["alpha"]["cluster"], items["foxtrot"]["cluster"])
        self.assertEqual(graph_nx["charlie"]["delta"]["weight"], 2)
        self.assertEqual(graph_nx["alpha"]["bravo"]["weight"], 5)
        self.assertEqual(len(list(nx.connected_components(graph_nx))), 2)
        self.assertEqual(len({item["cluster"] for item in items.values()}), 3)

    def test_frequency_is_preserved_and_only_linked_nodes_are_exported(self):
        helpers = page_helpers()
        df = records()
        freq, edges, top = helpers["_build_cooccurrence_network"](df, top_n=40, min_cooccurrence=2)
        vos = helpers["generate_vosviewer_json"](df, top_n=40, min_cooccurrence=2)
        items = {item["label"]: item for item in vos["network"]["items"]}
        self.assertTrue({"orphan", "epsilon"} <= top)
        self.assertEqual(set(items), {endpoint for a, b, _ in edges for endpoint in (a, b)})
        self.assertNotIn("orphan", items)
        self.assertNotIn("epsilon", items)
        self.assertEqual({label: item["weights"]["Occurrences"] for label, item in items.items()},
                         {label: freq[label] for label in items})
        self.assertEqual({label: item["weights"]["Occurrences"] for label, item in items.items()}, {
            "alpha": 10, "bravo": 5, "charlie": 7, "delta": 7,
            "echo": 5, "foxtrot": 5, "golf": 2, "hotel": 2,
        })
        for label, item in items.items():
            self.assertEqual(item["description"], f"Records containing this keyword: {freq[label]}")
        self.assertIsNone(helpers["generate_vosviewer_json"](df, min_cooccurrence=100))
        self.assertIsNone(helpers["generate_vosviewer_json"](pd.DataFrame()))

    def test_nondefault_top_n_and_threshold_partition_only_the_exported_graph(self):
        df = records()
        for top_n, threshold, expected_nodes, expected_links in (
            (40, 3, {"alpha", "bravo", "charlie", "delta", "echo", "foxtrot"}, 6),
            (3, 2, {"alpha", "charlie", "delta"}, 2),
        ):
            with self.subTest(top_n=top_n, threshold=threshold):
                renderer = Mock(return_value="<network>")
                partition = Mock(wraps=community_partition)
                helpers = page_helpers(renderer=renderer, partition=partition)
                helpers["generate_pyvis_html"](df, top_n=top_n, min_cooccurrence=threshold)
                graph = renderer.call_args.args[0]
                vos = helpers["generate_vosviewer_json"](df, top_n=top_n, min_cooccurrence=threshold)
                partition.assert_called_once_with(graph)
                self.assertEqual(decoded_export(vos), graph)
                self.assertEqual({node["id"] for node in graph["nodes"]}, expected_nodes)
                self.assertEqual(len(graph["edges"]), expected_links)
                self.assertEqual({item["label"]: item["cluster"] for item in vos["network"]["items"]},
                                 community_partition(graph))

    def test_item_and_cluster_ids_stable_across_order_and_python_hash_seeds(self):
        generate = page_helpers()["generate_vosviewer_json"]
        df = records()

        def ids(vos):
            return {item["label"]: (item["id"], item["cluster"])
                    for item in vos["network"]["items"]}

        expected = ids(generate(df))
        self.assertEqual(ids(generate(df)), expected)
        self.assertEqual(ids(generate(df.iloc[::-1].reset_index(drop=True))), expected)
        self.assertEqual(ids(generate(df.sample(frac=1, random_state=10))), expected)
        script = (
            "import json, runpy; "
            f"m = runpy.run_path({str(Path(__file__).resolve())!r}); "
            "v = m['page_helpers']()['generate_vosviewer_json'](m['records']()); "
            "print(json.dumps({x['label']: [x['id'], x['cluster']] "
            "for x in v['network']['items']}, sort_keys=True))"
        )
        for hash_seed in ("1", "97531"):
            with self.subTest(hash_seed=hash_seed):
                output = subprocess.check_output(
                    [sys.executable, "-c", script], cwd=ROOT, text=True,
                    env={**os.environ, "PYTHONHASHSEED": hash_seed},
                )
                self.assertEqual(json.loads(output), {k: list(v) for k, v in expected.items()})

    def test_serialized_json_config_requests_equal_size_cluster_colors_and_all_components(self):
        vos = page_helpers()["generate_vosviewer_json"](records())
        payload = json.loads(json.dumps(vos, ensure_ascii=False))
        params = payload["config"]["parameters"]
        self.assertEqual(params["item_size"], 3)
        self.assertEqual(params["item_size_variation"], 0)
        self.assertEqual(params["item_color"], 1)
        self.assertIs(params["largest_component"], False)
        self.assertTrue(all(isinstance(item["cluster"], int) and item["cluster"] >= 1
                            for item in payload["network"]["items"]))
        self.assertEqual(decoded_export(payload), decoded_export(vos))


if __name__ == "__main__":
    unittest.main()
