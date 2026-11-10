"""Self-contained, safely embedded vis-network HTML for the workshop pages.

No user records or network details are sent to an external visualization service.
The local JavaScript packaged with pyvis is embedded directly into the HTML.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path


def _json_for_script(value):
    """Encode untrusted data so it cannot terminate a script tag."""
    return (json.dumps(value, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def make_network_html(network: dict) -> str:
    """Build an interactive network; raises ValueError if the local library is missing."""
    try:
        import pyvis
    except ImportError as exc:
        raise ValueError("The pyvis package is not installed in this environment.") from exc
    js_file = Path(pyvis.__file__).parent / "templates" / "lib" / "vis-9.1.2" / "vis-network.min.js"
    if not js_file.is_file():
        raise ValueError("The local vis-network library is missing; reinstall pyvis.")
    library = js_file.read_text(encoding="utf-8")
    if "</script" in library.lower():
        raise ValueError("The local network library cannot be safely embedded.")

    coupling = network.get("kind") == "coupling"
    nodes = []
    for item in network["nodes"]:
        freq = int(item["frequency"])
        nodes.append({"id": item["id"], "label": item["label"], "frequency": freq,
                      "full_label": item.get("full_label", item["label"]),
                      "size": min(30 if coupling else 40, 10 + math.sqrt(freq) * (2 if coupling else 3))})
    edges = []
    for i, edge in enumerate(network["edges"]):
        weight = int(edge["weight"])
        edges.append({"id": i, "from": edge["source"], "to": edge["target"],
                      "weight": weight, "width": min(8, 1 + math.sqrt(weight))})

    metrics = {
        "node": "Unique reference IDs for this study: " if coupling else "Records containing this item: ",
        "edge": "Shared reference IDs: " if coupling else "Records containing both: ",
        "note": "Drag nodes or scroll to zoom. Hover to see " + ("full study titles and reference counts." if coupling else "record counts."),
        "coupling": coupling,
    }

    # `textContent` rather than `innerHTML` is used for all participant data.
    page = r'''<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body { margin:0; padding:0; font-family:Arial,sans-serif; }
#graph { width:100%; height:550px; border:1px solid #d9e2ec; background:#fafcff; box-sizing:border-box; }
#tip { position:absolute; top:8px; left:10px; display:none; max-width:320px;
  background:white; color:#1f2937; border:1px solid #bdc8d2; border-radius:4px;
  padding:6px 9px; font-size:13px; white-space:pre-wrap; pointer-events:none; z-index:5; }
#note { font-size:12px; color:#465465; padding:6px 4px; }
</style><script>__VIS_LIBRARY__</script></head>
<body><div id="graph"></div><div id="tip"></div>
<div id="note"></div>
<script>
(function(){
  const nodeData = __NODES__;
  const edgeData = __EDGES__;
  const metricLabels = __METRICS__;
  document.getElementById('note').textContent = metricLabels.note;
  const byNode = new Map(nodeData.map(n => [n.id,n]));
  const byEdge = new Map(edgeData.map(e => [e.id,e]));
  const nodes = new vis.DataSet(nodeData);
  const edges = new vis.DataSet(edgeData);
  const graph = new vis.Network(document.getElementById('graph'), {nodes:nodes,edges:edges}, {
    layout:{randomSeed:42}, interaction:{hover:true,hoverConnectedEdges:false},
    nodes:{shape:'dot',color:{background:'#4c82bb',border:'#285177'},font:{size:metricLabels.coupling ? 11 : 14,color:'#1f2937'}},
    edges:{color:{color:'#8fa1b4',highlight:'#245b8c'},smooth:false},
    physics:{solver:'forceAtlas2Based',stabilization:{iterations:180},
      forceAtlas2Based:metricLabels.coupling ? {gravitationalConstant:-80,centralGravity:0.01,springLength:160,springConstant:0.04,avoidOverlap:0.8} : {}}
  });
  const tip = document.getElementById('tip');
  graph.on('hoverNode', function(p) {
    const node = byNode.get(p.node); if (!node) return;
    tip.textContent = node.full_label + '\n' + metricLabels.node + node.frequency;
    tip.style.display = 'block';
  });
  graph.on('blurNode', function(){ tip.style.display='none'; });
  graph.on('hoverEdge', function(p) {
    const edge = byEdge.get(p.edge); if (!edge) return;
    const left = byNode.get(edge.from), right = byNode.get(edge.to);
    tip.textContent = left.full_label + ' — ' + right.full_label + '\n' + metricLabels.edge + edge.weight;
    tip.style.display = 'block';
  });
  graph.on('blurEdge', function(){ tip.style.display='none'; });
})();
</script></body></html>'''
    # Substitute in one pass: placeholder-looking text in a label stays data.
    replacements = {"__VIS_LIBRARY__": library, "__NODES__": _json_for_script(nodes),
                    "__EDGES__": _json_for_script(edges), "__METRICS__": _json_for_script(metrics)}
    return re.sub(r"__VIS_LIBRARY__|__NODES__|__EDGES__|__METRICS__", lambda m: replacements[m.group()], page)
