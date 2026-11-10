"""Self-contained, safely embedded vis-network HTML for the workshop pages.

No user records or network details are sent to an external visualization service.
The local JavaScript packaged with pyvis is embedded directly into the HTML.
"""
from __future__ import annotations

from functools import lru_cache
import json
import math
import re
from pathlib import Path

from day2_networks import annotate_communities


NETWORK_COMMUNITY_RELEASE = 1
# Paul Tol's colorblind-friendly bright qualitative palette is the starting
# point. A dark outline and visible C-number identify communities even when
# colors are hard to distinguish, particularly for larger numbers of groups.
COMMUNITY_COLORS = ("#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#BBBBBB")
# vis-network's dot size is a radius in graph units; zoom scales all nodes alike.
NODE_RADIUS = 15


def _lab_views(color):
    """Approximate Lab colors under normal, protanopic and deuteranopic vision."""
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    matrices = (
        ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
         (-0.003882, -0.048116, 1.051998)),
        ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
         (-0.011820, 0.042940, 0.968881)),
    )
    views = []
    for matrix in matrices:
        r, g, b = (max(0.0, min(1.0, sum(a * v for a, v in zip(row, linear)))) for row in matrix)
        x = (0.4124564*r + 0.3575761*g + 0.1804375*b) / 0.95047
        y = 0.2126729*r + 0.7151522*g + 0.0721750*b
        z = (0.0193339*r + 0.1191920*g + 0.9503041*b) / 1.08883
        def pivot(value):
            return value ** (1 / 3) if value > (6 / 29) ** 3 else value / (3 * (6 / 29) ** 2) + 4 / 29
        fx, fy, fz = (pivot(value) for value in (x, y, z))
        views.append((116*fy - 16, 500*(fx - fy), 200*(fy - fz)))
    return views


def _vision_distance(left, right):
    # The closest simulated view limits the distinction of a pair of colors.
    return min(sum((a - b) ** 2 for a, b in zip(view_a, view_b))
               for view_a, view_b in zip(left, right))


@lru_cache(maxsize=128)
def community_colors(count):
    """Return a stable sequence of unique colors, not dependent on graph order.

    After the first seven curated colors, greedily maximize the minimum Lab
    separation under normal and two simulated color-vision deficiencies. For
    many groups, reliable color discrimination cannot be guaranteed; the
    renderer additionally prints a unique community number on every node.
    """
    if count < 0 or count > 0x1000000:
        raise ValueError("community count is outside the available RGB color space")
    selected = list(COMMUNITY_COLORS[:count])
    if count <= len(selected):
        return tuple(selected)
    levels = range(16, 256, 32)
    candidates = [f"#{r:02X}{g:02X}{b:02X}" for r in levels for g in levels for b in levels]
    candidates = [color for color in candidates if color not in selected]
    representations = {color: _lab_views(color) for color in candidates}
    seed_views = [_lab_views(color) for color in selected]
    distances = {color: min(_vision_distance(views, chosen) for chosen in seed_views)
                 for color, views in representations.items()}
    while len(selected) < count and distances:
        # Candidate insertion order breaks ties deterministically.
        color = max(distances, key=distances.get)
        selected.append(color)
        del distances[color]
        chosen = representations[color]
        for other in distances:
            distances[other] = min(distances[other], _vision_distance(representations[other], chosen))
    # Very large graphs can exhaust the optimized grid. The RGB-space permutation
    # still avoids reuse, but the C-number (not color) is the reliable identifier.
    if len(selected) < count:
        used = set(selected)
        for index in range(0x1000000):
            color = f"#{((index * 0x9E3779 + 0x6D2B79) & 0xFFFFFF):06X}"
            if color not in used:
                selected.append(color)
                used.add(color)
                if len(selected) == count:
                    break
    return tuple(selected)


def _json_for_script(value):
    """Encode untrusted data so it cannot terminate a script tag."""
    return (json.dumps(value, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def make_network_html(network: dict, seed: int = 42) -> str:
    """Build an interactive graph using the shared seeded community partition.

    Every dot has the same radius, with frequency shown only on hover. Accepts
    the usual builder schema and any other co-occurrence ``kind``, including
    ``keywords``. The partition is recomputed with ``seed`` even if the input
    was already annotated; use the same seed when annotating an export.
    Raises ValueError if required local community or visualization support is
    unavailable rather than labelling a fallback as Louvain.
    """
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

    annotated = annotate_communities(network, seed=seed)
    coupling = network.get("kind") == "coupling"
    colors = community_colors(annotated["community_detection"]["count"])
    nodes = []
    for item in annotated["nodes"]:
        freq = int(item["frequency"])
        community = item["community"]
        color = colors[community - 1]
        nodes.append({"id": item["id"], "label": f'{item["label"]}\n[C{community}]', "frequency": freq,
                      "full_label": item.get("full_label", item["label"]),
                      "community": community, "size": NODE_RADIUS,
                      "color": {"background": color, "border": "#1f2937",
                                "highlight": {"background": color, "border": "#1f2937"},
                                "hover": {"background": color, "border": "#1f2937"}}})
    edges = []
    for i, edge in enumerate(network["edges"]):
        weight = edge["weight"]
        edges.append({"id": i, "from": edge["source"], "to": edge["target"],
                      "weight": weight, "width": min(8, 1 + math.sqrt(weight))})

    method = annotated["community_detection"]["method"]
    if method == "weighted_louvain":
        weight_description = "shared reference counts" if coupling else "co-occurring record counts"
        community_note = (f"Weighted Louvain (seed {seed}) uses {weight_description} on shown links; "
                          "isolated nodes form singleton communities.")
    elif method == "isolates":
        community_note = "No links: each isolated node is its own community; Louvain was not run."
    else:
        community_note = "No nodes: Louvain was not run."
    colors_note = (" With many groups, use C numbers when colors look similar."
                   if annotated["community_detection"]["count"] > len(COMMUNITY_COLORS) else "")
    metrics = {
        "node": "Unique reference IDs for this study: " if coupling else "Records containing this item: ",
        "nodeSuffix": " (recognized)" if coupling else "",
        "edge": "Shared reference IDs: " if coupling else "Records containing both: ",
        "note": ("Equal node sizes. Colors and C numbers identify communities. " + community_note + colors_note
                 + " Drag nodes or scroll to zoom. Hover to see "
                 + ("full study titles and reference counts." if coupling else "record counts.")),
        "coupling": coupling,
    }

    # `textContent` rather than `innerHTML` is used for all participant data.
    page = r'''<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body { margin:0; padding:0; font-family:Arial,sans-serif; }
#graph { width:100%; height:500px; border:1px solid #d9e2ec; background:#fafcff; box-sizing:border-box; }
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
    nodes:{shape:'dot',borderWidth:2,borderWidthSelected:2,font:{size:metricLabels.coupling ? 11 : 14,color:'#1f2937'}},
    edges:{color:{color:'#8fa1b4',highlight:'#245b8c'},smooth:false},
    physics:{solver:'forceAtlas2Based',stabilization:{iterations:180},
      forceAtlas2Based:metricLabels.coupling ? {gravitationalConstant:-80,centralGravity:0.01,springLength:160,springConstant:0.04,avoidOverlap:0.8} : {}}
  });
  // Streamlit creates tabs/expanders before they are visible. A graph laid out
  // in a zero-width frame can otherwise remain clipped when the tab is opened.
  const container = document.getElementById('graph');
  let lastWidth = 0, lastHeight = 0;
  function fitVisibleGraph() {
    const rect = container.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    if (rect.width !== lastWidth || rect.height !== lastHeight) {
      lastWidth = rect.width; lastHeight = rect.height;
      graph.redraw();
      graph.fit({animation:false});
    }
  }
  if (window.ResizeObserver) new ResizeObserver(fitVisibleGraph).observe(container);
  window.addEventListener('resize', fitVisibleGraph);
  graph.once('stabilizationIterationsDone', function() {
    const rect = container.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) graph.fit({animation:false});
  });
  requestAnimationFrame(fitVisibleGraph);
  const tip = document.getElementById('tip');
  graph.on('hoverNode', function(p) {
    const node = byNode.get(p.node); if (!node) return;
    tip.textContent = node.full_label + '\n' + metricLabels.node + node.frequency + metricLabels.nodeSuffix + '\nCommunity: C' + node.community;
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
