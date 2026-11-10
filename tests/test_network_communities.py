"""Shared weighted Louvain communities and fixed-size network rendering."""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import networkx as nx
import pandas as pd

from day2_networks import annotate_communities, build_network, community_partition
from day2_network_view import COMMUNITY_COLORS, NODE_RADIUS, community_colors, make_network_html


def embedded_data(html, name):
    """Parse only our script data, not arbitrary occurrences inside the library."""
    match = re.search(r"\bconst " + re.escape(name) + r" = (.*);\n", html)
    if not match:
        raise AssertionError(f"missing {name}")
    return json.loads(match.group(1))


def weighted_graph():
    return {
        "kind": "authors",
        "nodes": [{"id": node, "label": node, "frequency": freq}
                  for node, freq in [("a", 100), ("b", 3), ("c", 2), ("d", 1), ("z", 7)]],
        "edges": [{"source": "a", "target": "b", "weight": 10},
                  {"source": "c", "target": "d", "weight": 10},
                  {"source": "a", "target": "c", "weight": 1},
                  {"source": "b", "target": "d", "weight": 1}],
    }


class CommunityPartitionTests(unittest.TestCase):
    def test_weighted_louvain_and_isolate(self):
        graph = weighted_graph()
        with patch.object(nx.community, "louvain_communities", wraps=nx.community.louvain_communities) as algorithm:
            result = community_partition(graph)
        algorithm.assert_called_once()
        self.assertEqual(algorithm.call_args.kwargs, {"weight": "weight", "seed": 42})
        self.assertEqual(result, {"a": 1, "b": 1, "c": 2, "d": 2, "z": 3})
        self.assertEqual(set(algorithm.call_args.args[0].nodes), set(range(5)))
        self.assertEqual(sorted(d["weight"] for _, _, d in algorithm.call_args.args[0].edges(data=True)), [1, 1, 10, 10])
        # Reweighting the same topology changes the partition, while changing
        # node frequencies alone does not: Louvain uses edge weights, not sizes.
        changed = copy.deepcopy(graph)
        for edge in changed["edges"]:
            edge["weight"] = 1 if edge["weight"] == 10 else 10
        self.assertEqual(community_partition(changed), {"a": 1, "c": 1, "b": 2, "d": 2, "z": 3})
        changed = copy.deepcopy(graph)
        for node in changed["nodes"]:
            node["frequency"] *= 1000
        self.assertEqual(community_partition(changed), result)

    def test_input_order_hash_seed_and_annotation_are_stable(self):
        graph = weighted_graph()
        original = copy.deepcopy(graph)
        partition = community_partition(graph, seed=42)
        shuffled = copy.deepcopy(graph)
        shuffled["nodes"].reverse()
        shuffled["edges"].reverse()
        for edge in shuffled["edges"]:
            edge["source"], edge["target"] = edge["target"], edge["source"]
        self.assertEqual(community_partition(shuffled, seed=42), partition)
        annotation = annotate_communities(graph)
        self.assertEqual(graph, original)
        self.assertIsNot(annotation["nodes"], graph["nodes"])
        self.assertEqual({n["id"]: n["community"] for n in annotation["nodes"]}, partition)
        self.assertEqual(annotation["community_detection"], {"method": "weighted_louvain", "seed": 42,
                                                              "edge_weight": "weight", "resolution": 1, "count": 3})
        script = ("import json; from day2_networks import community_partition; "
                  f"g = json.loads({json.dumps(json.dumps(graph))}); "
                  "print(json.dumps(community_partition(g), sort_keys=True))")
        results = []
        for hash_seed in ("1", "97531"):
            env = {**os.environ, "PYTHONHASHSEED": hash_seed}
            results.append(json.loads(subprocess.check_output([sys.executable, "-c", script], env=env, text=True)))
        self.assertEqual(results, [partition, partition])

    def test_empty_and_edgeless_graphs_need_no_louvain(self):
        empty = {"nodes": [], "edges": [], "kind": "terms"}
        isolates = {"nodes": [{"id": x, "label": x, "frequency": 1} for x in ("b", "a", "c")],
                    "edges": [], "kind": "concepts"}
        with patch.object(nx.community, "louvain_communities", side_effect=AssertionError("must not run")):
            self.assertEqual(community_partition(empty), {})
            self.assertEqual(community_partition(isolates), {"a": 1, "b": 2, "c": 3})
            self.assertEqual(annotate_communities(empty)["community_detection"]["method"], "empty")
            self.assertEqual(annotate_communities(isolates)["community_detection"]["method"], "isolates")
        html = make_network_html(isolates)
        self.assertIn("Louvain was not run", embedded_data(html, "metricLabels")["note"])
        self.assertEqual(len(embedded_data(make_network_html(empty), "nodeData")), 0)

    def test_bad_edges_are_rejected_not_silently_reinterpreted(self):
        for edge in (
            {"source": "a", "target": "b", "weight": 0},
            {"source": "a", "target": "b", "weight": float("nan")},
            {"source": "a", "target": "unknown", "weight": 1},
            {"source": "a", "target": "a", "weight": 1},
        ):
            graph = weighted_graph()
            graph["edges"] = [edge]
            with self.subTest(edge=edge), self.assertRaises(ValueError):
                community_partition(graph)
        graph = weighted_graph()
        graph["edges"].append({"source": "b", "target": "a", "weight": 10})
        with self.assertRaises(ValueError):
            community_partition(graph)

    def test_no_false_louvain_fallback(self):
        with patch.object(nx.community, "louvain_communities", side_effect=RuntimeError("bad algorithm")):
            with self.assertRaisesRegex(RuntimeError, "bad algorithm"):
                annotate_communities(weighted_graph())


class SharedNetworkVisualizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = pd.DataFrame([
            {"Title": "solar wind", "Authors": "Alice; Bob", "Concepts": "Solar; Wind", "References": "W1; W2"},
            {"Title": "solar wind", "Authors": "Alice; Bob", "Concepts": "Solar; Wind", "References": "W1; W2"},
            {"Title": "ocean tide", "Authors": "Cleo", "Concepts": "Ocean", "References": "W2; W3"},
            {"Title": "glacier", "Authors": "Dara", "Concepts": "Glacier", "References": "W4"},
        ])

    def test_every_network_has_equal_size_community_color_and_hover_count(self):
        for kind in ("authors", "terms", "concepts", "coupling"):
            with self.subTest(kind=kind):
                graph = build_network(self.records, kind, min_cooccurrence=2)
                self.assertTrue(graph["nodes"])
                self.assertTrue(graph["edges"])
                self.assertTrue(len(set(n["frequency"] for n in graph["nodes"])) > 1)
                before = copy.deepcopy(graph)
                html = make_network_html(graph)
                nodes = embedded_data(html, "nodeData")
                edges = embedded_data(html, "edgeData")
                labels = embedded_data(html, "metricLabels")
                partition = community_partition(graph)
                self.assertEqual(graph, before)  # rendering never changes export data
                self.assertEqual({node["size"] for node in nodes}, {NODE_RADIUS})
                self.assertEqual({node["id"]: node["frequency"] for node in nodes},
                                 {node["id"]: node["frequency"] for node in graph["nodes"]})
                self.assertTrue(all("value" not in node for node in nodes))  # vis auto-scaling is disabled
                self.assertIn("shape:'dot'", html)
                self.assertIn("node.frequency", html)
                self.assertIn("metricLabels.node", html)
                self.assertIn("Community: C", html)
                self.assertIn("node.full_label", html)
                self.assertIn("Weighted Louvain (seed 42)", labels["note"])
                self.assertIn("singleton", labels["note"])
                self.assertIn("Unique reference IDs for this study" if kind == "coupling"
                              else "Records containing this item", labels["node"])
                self.assertIn("shared reference counts" if kind == "coupling"
                              else "co-occurring record counts", labels["note"])
                self.assertEqual({n["id"]: n["community"] for n in nodes}, partition)
                self.assertEqual({n["id"]: n["label"] for n in nodes},
                                 {n["id"]: n["label"] for n in graph["nodes"]})
                self.assertTrue(all(n["color"]["background"] == community_colors(max(partition.values()))[n["community"] - 1]
                                    for n in nodes))
                self.assertEqual([e["weight"] for e in edges], [e["weight"] for e in graph["edges"]])

    def test_every_builder_passes_its_link_weights_and_isolates_to_louvain(self):
        for kind in ("authors", "terms", "concepts", "coupling"):
            with self.subTest(kind=kind):
                graph = build_network(self.records, kind, min_cooccurrence=2)
                names = sorted(n["id"] for n in graph["nodes"])
                with patch.object(nx.community, "louvain_communities", wraps=nx.community.louvain_communities) as method:
                    partition = community_partition(graph)
                method.assert_called_once()
                used_graph = method.call_args.args[0]
                used_weights = {tuple(sorted((names[a], names[b]))): d["weight"]
                                for a, b, d in used_graph.edges(data=True)}
                expected = {tuple(sorted((e["source"], e["target"]))): e["weight"]
                            for e in graph["edges"]}
                self.assertEqual(used_weights, expected)
                self.assertEqual(set(partition), set(names))
                isolates = [names[i] for i in nx.isolates(used_graph)]
                self.assertTrue(isolates)
                for node in isolates:
                    self.assertEqual(list(partition.values()).count(partition[node]), 1)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to execute the embedded hover handlers")
    def test_hover_handler_executes_and_shows_exact_frequency(self):
        harness = r'''const fs = require('fs');
        const elements = {graph: {getBoundingClientRect: () => ({width: 800, height: 500})}, tip: {style: {}}, note: {}};
        global.document = {getElementById: id => elements[id]};
        global.window = {addEventListener: () => {}, ResizeObserver: undefined};
        global.requestAnimationFrame = callback => callback();
        class DataSet { constructor(items) { this.items = items; } }
        class Network {
          constructor(el, data, options) { this.data = data; this.options = options; this.events = {}; global.network = this; }
          on(event, callback) { this.events[event] = callback; }
          once(event, callback) { this.events[event] = callback; }
          redraw() {}
          fit() {}
        }
        global.vis = {DataSet, Network};
        eval(fs.readFileSync(0, 'utf8'));
        const node = network.data.nodes.items[0];
        network.events.hoverNode({node: node.id});
        console.log(JSON.stringify({node, tip: elements.tip.textContent, shown: elements.tip.style.display}));
        '''
        for kind in ("authors", "terms", "concepts", "coupling", "keywords"):
            with self.subTest(kind=kind):
                graph = (dict(weighted_graph(), kind="keywords") if kind == "keywords"
                         else build_network(self.records, kind, min_cooccurrence=2))
                html = make_network_html(graph)
                script = html.rsplit("<script>", 1)[1].split("</script>", 1)[0]
                result = json.loads(subprocess.check_output(["node", "-e", harness], input=script, text=True))
                expected = ("Unique reference IDs for this study: " if kind == "coupling"
                            else "Records containing this item: ")
                self.assertIn(expected + str(result["node"]["frequency"]), result["tip"])
                self.assertIn(f'Community: C{result["node"]["community"]}', result["tip"])
                self.assertEqual(result["shown"], "block")
                if kind == "coupling":
                    self.assertIn("recognized", result["tip"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to execute embedded layout handlers")
    def test_hidden_network_is_refitted_when_its_tab_becomes_visible(self):
        harness = r'''const fs = require('fs');
        let width = 0;
        const elements = {graph: {getBoundingClientRect: () => ({width, height: 500})},
                          tip: {style: {}}, note: {}};
        global.document = {getElementById: id => elements[id]};
        global.window = {addEventListener: () => {}, ResizeObserver: true};
        global.ResizeObserver = class {constructor(callback) {global.onResize = callback;} observe() {}};
        global.requestAnimationFrame = callback => callback();
        class DataSet {constructor(items) {this.items = items;}}
        class Network {
          constructor() {this.events = {}; this.fitCount = 0; global.network = this;}
          on(event, callback) {this.events[event] = callback;}
          once(event, callback) {this.events[event] = callback;}
          redraw() {}
          fit() {this.fitCount++;}
        }
        global.vis = {DataSet, Network};
        eval(fs.readFileSync(0, 'utf8'));
        const hidden = network.fitCount;
        width = 800; onResize();
        const visible = network.fitCount;
        onResize();
        const unchanged = network.fitCount;
        width = 900; onResize();
        console.log(JSON.stringify({hidden, visible, unchanged, resized: network.fitCount}));
        '''
        html = make_network_html(weighted_graph())
        script = html.rsplit("<script>", 1)[1].split("</script>", 1)[0]
        result = json.loads(subprocess.check_output(["node", "-e", harness], input=script, text=True))
        self.assertEqual(result, {"hidden": 0, "visible": 1, "unchanged": 1, "resized": 2})

    def test_legacy_keyword_graph_uses_same_renderer(self):
        graph = weighted_graph()
        graph["kind"] = "keywords"
        nodes = embedded_data(make_network_html(graph), "nodeData")
        self.assertEqual({n["community"] for n in nodes}, {1, 2, 3})
        self.assertEqual({n["size"] for n in nodes}, {NODE_RADIUS})
        self.assertEqual({n["id"]: n["label"] for n in nodes},
                         {n["id"]: n["label"] for n in graph["nodes"]})
        self.assertEqual({n["id"]: n["frequency"] for n in nodes},
                         {n["id"]: n["frequency"] for n in graph["nodes"]})

    def test_many_communities_have_unique_stable_colors_and_hover_ids(self):
        count = 60
        colors = community_colors(count)
        self.assertEqual(colors[:7], COMMUNITY_COLORS)
        self.assertEqual(len(set(colors)), count)
        self.assertEqual(colors[:12], community_colors(12))
        graph = {"kind": "keywords", "edges": [],
                 "nodes": [{"id": f"node-{i:03d}", "label": f"Node {i}", "frequency": i + 1}
                           for i in range(count)]}
        html = make_network_html(graph)
        nodes = embedded_data(html, "nodeData")
        self.assertEqual(len({n["color"]["background"] for n in nodes}), count)
        self.assertEqual(len({n["community"] for n in nodes}), count)
        self.assertEqual({n["id"]: n["label"] for n in nodes},
                         {n["id"]: n["label"] for n in graph["nodes"]})
        self.assertIn("hover to check the community", embedded_data(html, "metricLabels")["note"])

    def test_malicious_labels_are_safe_even_after_annotation(self):
        attack = "</script><script>window.attack=true</script>__EDGES__"
        graph = {"kind": "keywords", "nodes": [{"id": attack, "label": attack, "frequency": 2}], "edges": []}
        html = make_network_html(graph)
        self.assertNotIn(attack, html)
        self.assertIn("\\u003c/script\\u003e", html)
        self.assertIn("__EDGES__", html)
        self.assertIn("tip.textContent", html)
        self.assertNotIn("<script src=", html)


if __name__ == "__main__":
    unittest.main()
