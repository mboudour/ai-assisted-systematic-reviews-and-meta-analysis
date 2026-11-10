"""
Day 1 — From Query to Corpus
Four self-contained guided cases and a separate BYOD workflow.
Each guided case offers fixed searches for all four supported providers.
No coding required.

APIs covered: OpenAlex, Crossref, Europe PMC, and OpenAIRE
BYOD inputs: provider-specific API search, RIS file upload, Zotero connection
Outputs: CSV download, RIS export, Query Log, VOSviewer bibliometric network link,
         pyvis interactive keyword co-occurrence network
"""

import io
import re
import json
import time
import pathlib
import sys
import hashlib
import html
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
from itertools import combinations
from sklearn.feature_extraction.text import TfidfVectorizer

# pyvis — optional import with graceful fallback
try:
    from pyvis.network import Network as PyvisNetwork
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

st.set_page_config(
    page_title="Day 1 — From Query to Corpus",
    page_icon="📥",
    layout="wide",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from openalex_client import OpenAlexError, fetch_works
from openaire_client import OpenAIREError, fetch_openaire
from openaire_notice import OPENAIRE_LIMITATIONS, source_column_mentions_openaire
from day2_networks import build_network
from day2_network_view import make_network_html
from guided_loader import load_guided_workflow

guided_workflow = load_guided_workflow()

OPENAIRE_CHOICE = "OpenAIRE (multidisciplinary; no participant key)"


def forget_openalex_credentials():
    """Clear only this browser session's masked credential widgets."""
    st.session_state.pop("openalex_email_widget", None)
    st.session_state.pop("openalex_key_widget", None)


# ── Stopwords for keyword extraction ──────────────────────────────────────────
_STOPWORDS = {
    "the","a","an","and","or","of","in","to","for","with","on","at","by","from",
    "is","are","was","were","be","been","being","have","has","had","do","does",
    "did","will","would","could","should","may","might","shall","this","that",
    "these","those","it","its","as","but","not","no","so","if","than","then",
    "also","which","who","whom","what","when","where","how","all","both","each",
    "more","most","other","some","such","into","through","during","before",
    "after","above","below","between","out","about","up","down","over","under",
    "again","further","once","study","studies","research","results","analysis",
    "data","paper","article","review","systematic","meta","based","using","used",
    "associated","among","across","within","between","compared","including",
    "however","therefore","thus","hence","while","although","despite","whether",
    "effect","effects","impact","impacts","evidence","approach","methods","method",
    "findings","conclusion","conclusions","objective","objectives","background",
    "introduction","discussion","aim","aims","purpose","sample","samples",
    "number","total","high","low","significant","significantly","p","ci",
    "95","mean","median","sd","se","n","vs","et","al","doi","journal",
}

# ── pyvis network helpers ──────────────────────────────────────────────────────

def _build_cooccurrence_network(df, top_n=40, min_cooccurrence=2):
    """Extract keyword co-occurrence edges from a corpus DataFrame."""
    all_docs_keywords = []
    for _, row in df.iterrows():
        doc_keywords = set()
        concepts = str(row.get("Concepts", "") or "")
        if concepts and concepts != "nan":
            for c in concepts.split(";"):
                kw = c.strip().lower()
                if kw and len(kw) > 3 and kw not in _STOPWORDS:
                    doc_keywords.add(kw)
        title = str(row.get("Title", "") or "")
        if title and title != "nan":
            for w in re.findall(r'\b[a-zA-Z]{4,}\b', title.lower()):
                if w not in _STOPWORDS:
                    doc_keywords.add(w)
        if doc_keywords:
            all_docs_keywords.append(doc_keywords)

    freq = Counter()
    for doc_kws in all_docs_keywords:
        for kw in doc_kws:
            freq[kw] += 1

    top_keywords = {kw for kw, _ in freq.most_common(top_n)}

    cooc = Counter()
    for doc_kws in all_docs_keywords:
        filtered = doc_kws & top_keywords
        for pair in combinations(sorted(filtered), 2):
            cooc[pair] += 1

    edges = [(a, b, cnt) for (a, b), cnt in cooc.items() if cnt >= min_cooccurrence]
    return freq, edges, top_keywords


def generate_pyvis_html(df, top_n=40, min_cooccurrence=2):
    """Return (html_string, error_message). error_message is None on success.

    Builds a fully self-contained HTML string with vis-network inlined from the
    local pyvis package — no CDN calls, no external resources.  This is required
    because Streamlit Community Cloud's Content Security Policy blocks external
    script/style loads inside components.html iframes.
    """
    freq, edges, top_keywords = _build_cooccurrence_network(df, top_n=top_n, min_cooccurrence=min_cooccurrence)

    if not edges:
        return None, (
            "Not enough co-occurring keywords to build a network with the current settings. "
            "Try lowering the minimum co-occurrence threshold or using a larger corpus."
        )

    # ── Louvain community detection (via networkx built-in — no extra package) ──
    try:
        import networkx as nx

        G = nx.Graph()
        nodes_in_edges = set()
        for a, b, cnt in edges:
            nodes_in_edges.add(a)
            nodes_in_edges.add(b)
            G.add_edge(a, b, weight=cnt)

        # nx.community.louvain_communities is available in networkx >= 3.0
        communities = nx.community.louvain_communities(G, weight='weight', seed=42)
        # Sort communities by size descending so the largest gets colour 0
        communities = sorted(communities, key=len, reverse=True)
        partition = {}
        for i, comm in enumerate(communities):
            for node in comm:
                partition[node] = i
        num_communities = len(communities)
        PALETTE = [
            "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
            "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#00bcd4",
            "#8bc34a", "#ff5722",
        ]
        def community_color(node):
            return PALETTE[partition.get(node, 0) % len(PALETTE)]
        louvain_ok = True
    except Exception:
        louvain_ok = False
        nodes_in_edges = set()
        for a, b, _ in edges:
            nodes_in_edges.add(a)
            nodes_in_edges.add(b)
        # Use only the actually-drawn nodes (nodes_in_edges) for quartile thresholds
        # so that community colours respond correctly to slider changes.
        drawn_freqs = sorted([freq[kw] for kw in nodes_in_edges]) if nodes_in_edges else [1]
        q1 = drawn_freqs[max(0, len(drawn_freqs) // 4)]
        q2 = drawn_freqs[max(0, len(drawn_freqs) // 2)]
        q3 = drawn_freqs[max(0, 3 * len(drawn_freqs) // 4)]
        def _freq_group(node):
            f = freq.get(node, 1)
            if f >= q3: return 3
            if f >= q2: return 2
            if f >= q1: return 1
            return 0
        partition = {n: _freq_group(n) for n in nodes_in_edges}
        def community_color(node):
            g = partition.get(node, 0)
            return ["#95a5a6", "#3498db", "#e67e22", "#e74c3c"][g]
        num_communities = 4

    # ── Build node / edge data as JSON ────────────────────────────────────────
    import json as _json
    import html as _html

    # Pre-compute degree (number of distinct neighbours) for each node
    _degree: dict = {}
    for a, b, _ in edges:
        _degree[a] = _degree.get(a, 0) + 1
        _degree[b] = _degree.get(b, 0) + 1

    nodes_data = []
    for kw in nodes_in_edges:
        f = freq.get(kw, 1)
        deg = _degree.get(kw, 0)
        size = max(10, min(45, 8 + f * 2))
        cid = partition.get(kw, 0)
        color = community_color(kw)
        # Always include Community — use Louvain id when available,
        # otherwise use the frequency-quartile group (1-4) as a proxy.
        if louvain_ok:
            community_label = cid + 1
        else:
            # frequency-quartile group already encoded in color choice (1-4)
            community_label = cid + 1  # cid set below via partition fallback
        tooltip = (
            f"<b>{_html.escape(kw)}</b><br/>"
            f"Frequency: {f}<br/>"
            f"Degree: {deg}<br/>"
            f"Community: {community_label}"
        )
        nodes_data.append({
            "id": kw, "label": kw, "title": tooltip,
            "size": size,
            "color": {"background": color, "border": "#333333",
                      "highlight": {"background": color, "border": "#000000"}},
            "font": {"size": 13, "color": "#222222"},
            "shape": "dot", "borderWidth": 2,
        })

    max_cooc = max(cnt for _, _, cnt in edges) if edges else 1
    edges_data = []
    for idx, (a, b, cnt) in enumerate(edges):
        width = max(1, min(8, 1 + (cnt / max_cooc) * 7))
        same_comm = louvain_ok and partition.get(a, -1) == partition.get(b, -2)
        opacity = 0.65 if same_comm else 0.3
        edges_data.append({
            "id": idx, "from": a, "to": b, "value": cnt,
            "title": f"Co-occurrences: {cnt}",
            "width": width,
            "color": {"opacity": opacity},
        })

    # Data may come from user uploads; prevent a label from ending the script tag.
    nodes_json = _json.dumps(nodes_data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    edges_json = _json.dumps(edges_data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    legend_note = f" ({num_communities} Louvain communities detected)" if louvain_ok else ""

    # ── Load vis-network JS from the local pyvis package (no CDN) ─────────────
    import pathlib as _pl
    import pyvis as _pyvis_mod
    _vis_js_path = (
        _pl.Path(_pyvis_mod.__file__).parent
        / "templates" / "lib" / "vis-9.1.2" / "vis-network.min.js"
    )
    if _vis_js_path.exists():
        _vis_js = _vis_js_path.read_text(encoding="utf-8")
    else:
        # Absolute fallback: use CDN (will fail under strict CSP but better than nothing)
        _vis_js = None

    if _vis_js:
        vis_script_tag = f'<script type="text/javascript">\n{_vis_js}\n</script>'
    else:
        vis_script_tag = (
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/'
            'dist/vis-network.min.js" crossorigin="anonymous"></script>'
        )

    # ── Build fully self-contained HTML ───────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: #fafafa; }}
  #mynetwork {{
    width: 100%;
    height: 560px;
    background-color: #fafafa;
    border: 1px solid #e0e0e0;
    position: relative;
  }}
</style>
{vis_script_tag}
</head>
<body>
<div id="mynetwork"></div>
<div style="position:absolute;bottom:8px;left:12px;font-size:11px;
     color:#555;font-family:sans-serif;">
  Node colour = Louvain community{legend_note}. Node size = keyword frequency.
</div>
<script type="text/javascript">
(function() {{
  // Script runs synchronously at end of <body> — DOM is already ready.
  // Store tooltip HTML strings in a lookup; leave node.title undefined so
  // vis.js does NOT attempt its own (broken) tooltip rendering.
  var nodesRaw = {nodes_json};
  var edgesRaw = {edges_json};

  var nodeTooltip = {{}};
  nodesRaw.forEach(function(n) {{
    if (n.title) {{ nodeTooltip[n.id] = n.title; n.title = undefined; }}
  }});
  var edgeTooltip = {{}};
  edgesRaw.forEach(function(e) {{
    if (e.title) {{ edgeTooltip[e.id] = e.title; e.title = undefined; }}
  }});

  var nodes = new vis.DataSet(nodesRaw);
  var edges = new vis.DataSet(edgesRaw);
  var container = document.getElementById('mynetwork');

  var options = {{
    physics: {{
      forceAtlas2Based: {{
        gravitationalConstant: -120,
        centralGravity: 0.015,
        springLength: 100,
        springConstant: 0.08,
        damping: 0.9
      }},
      solver: 'forceAtlas2Based',
      stabilization: {{ iterations: 200, updateInterval: 25 }}
    }},
    nodes: {{ font: {{ size: 13, color: '#222222' }}, borderWidth: 2, borderWidthSelected: 3 }},
    edges: {{ color: {{ opacity: 0.4 }}, smooth: {{ type: 'continuous' }} }},
    interaction: {{ hover: true, tooltipDelay: 150 }}
  }};

  var network = new vis.Network(container, {{ nodes: nodes, edges: edges }}, options);

  // Create tooltip div AFTER vis.Network() — vis.js clears container innerHTML on init,
  // so any div appended before this point would be destroyed.
  var tip = document.createElement('div');
  tip.style.cssText = [
    'position:absolute', 'display:none', 'pointer-events:none',
    'background:#fff', 'border:1px solid #bbb', 'border-radius:5px',
    'padding:6px 10px', 'font-size:13px', 'line-height:1.6',
    'max-width:260px', 'box-shadow:2px 2px 6px rgba(0,0,0,.15)',
    'z-index:9999', 'font-family:sans-serif'
  ].join(';');
  container.appendChild(tip);

  // Use canvas mousemove + getNodeAt/getEdgeAt for reliable tooltip detection.
  // vis.js hoverNode/blurNode events require pointer events to propagate through
  // the Streamlit iframe stack; canvas-level mousemove is more reliable.
  var canvas = container.querySelector('canvas');
  var lastNodeId = null;
  var lastEdgeId = null;

  function positionTip(x, y) {{
    var cx = x + 14;
    var cy = y - 14;
    if (cx + 270 > container.offsetWidth) cx = x - 270;
    if (cy < 0) cy = 4;
    tip.style.left = cx + 'px';
    tip.style.top  = cy + 'px';
  }}

  // Wait for canvas to be ready (network may still be stabilizing)
  function attachMouseHandlers() {{
    var c = container.querySelector('canvas');
    if (!c) {{ setTimeout(attachMouseHandlers, 100); return; }}
    c.addEventListener('mousemove', function(e) {{
      var rect = c.getBoundingClientRect();
      var domPos = {{ x: e.clientX - rect.left, y: e.clientY - rect.top }};
      var nodeId = network.getNodeAt(domPos);
      var edgeId = nodeId ? null : network.getEdgeAt(domPos);
      if (nodeId !== undefined && nodeId !== null) {{
        var html = nodeTooltip[nodeId];
        if (html) {{
          tip.innerHTML = html;
          tip.style.display = 'block';
          positionTip(domPos.x, domPos.y);
        }} else {{
          tip.style.display = 'none';
        }}
        lastNodeId = nodeId; lastEdgeId = null;
      }} else if (edgeId !== undefined && edgeId !== null) {{
        var html = edgeTooltip[edgeId];
        if (html) {{
          tip.innerHTML = html;
          tip.style.display = 'block';
          positionTip(domPos.x, domPos.y);
        }} else {{
          tip.style.display = 'none';
        }}
        lastEdgeId = edgeId; lastNodeId = null;
      }} else {{
        tip.style.display = 'none';
        lastNodeId = null; lastEdgeId = null;
      }}
    }});
    c.addEventListener('mouseleave', function() {{ tip.style.display = 'none'; }});
  }}
  attachMouseHandlers();
}})();
</script>
</body>
</html>"""

    return html, None


def render_pyvis_network(df, session_key):
    """Render the interactive keyword co-occurrence network section."""
    st.markdown("#### 🕸️ Interactive Keyword Co-occurrence Network")
    st.markdown("""
This network maps the **most frequent keywords** in the corpus and draws a link between
any two keywords that appear together in the same paper. **Node colour = Louvain community**
(nodes of the same colour belong to the same thematic cluster, detected automatically by the
Louvain algorithm). Larger nodes = more frequent; thicker edges = more papers share both
keywords. **Drag nodes, scroll to zoom, hover for community and frequency details.**
    """)

    col_opts, _ = st.columns([2, 1])
    with col_opts:
        top_n = st.slider(
            "Number of top keywords to display",
            min_value=10, max_value=60, value=40, step=5,
            key=f"pyvis_topn_{session_key}",
        )
        min_cooc = st.slider(
            "Minimum co-occurrence threshold",
            min_value=1, max_value=10, value=2, step=1,
            key=f"pyvis_mincooc_{session_key}",
        )

    html, err = generate_pyvis_html(df, top_n=top_n, min_cooccurrence=min_cooc)
    if err:
        st.warning(f"⚠️ Network could not be generated: {err}")
    else:
        components.html(html, height=540, scrolling=False)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_tfidf_keywords(texts, top_n=8):
    """Extract top TF-IDF keywords per document from a list of abstract texts.
    Returns a list of lists (one list of keyword strings per document).
    Documents with no usable text get an empty list.
    """
    # Build a per-document keyword list using TF-IDF
    clean = [t if isinstance(t, str) and len(t.strip()) > 20 else "" for t in texts]
    # If fewer than 2 non-empty docs, fall back to simple frequency
    non_empty = [t for t in clean if t]
    if len(non_empty) < 2:
        results = []
        for t in clean:
            if not t:
                results.append([])
                continue
            words = re.findall(r'\b[a-zA-Z]{4,}\b', t.lower())
            stop = {"this","that","with","from","have","been","were","they",
                    "their","which","also","more","than","into","such","when",
                    "study","paper","research","results","using","used","based",
                    "show","showed","found","data","analysis","method","methods"}
            kws = [w for w in words if w not in stop]
            freq = Counter(kws)
            results.append([w for w, _ in freq.most_common(top_n)])
        return results
    try:
        vec = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            stop_words="english",
            min_df=1,
            token_pattern=r'\b[a-zA-Z]{4,}\b',
        )
        tfidf_matrix = vec.fit_transform(clean)
        feature_names = vec.get_feature_names_out()
        results = []
        for i, text in enumerate(clean):
            if not text:
                results.append([])
                continue
            row = tfidf_matrix[i].toarray().flatten()
            top_indices = row.argsort()[::-1][:top_n]
            kws = [feature_names[idx] for idx in top_indices if row[idx] > 0]
            results.append(kws)
        return results
    except Exception:
        return [[] for _ in texts]


def df_to_ris(df):
    """Convert a corpus DataFrame to RIS format string.
    Keywords (KW tags) are populated from the Concepts column when available;
    for rows without concepts, TF-IDF keywords are extracted from the abstract
    so that VOSviewer's Co-occurrence analysis is always enabled.
    """
    # Pre-compute TF-IDF fallback keywords for all rows in one vectorisation pass
    abstracts = [str(row.get("Abstract", "") or "") for _, row in df.iterrows()]
    tfidf_kws = _extract_tfidf_keywords(abstracts, top_n=8)

    lines = []
    for i, (_, row) in enumerate(df.iterrows()):
        is_openaire_record = str(row.get("Source", "")).strip().casefold() == "openaire"
        lines.append("TY  - GEN" if is_openaire_record else "TY  - JOUR")
        if is_openaire_record:
            lines.append("DB  - OpenAIRE")
        title = str(row.get("Title", "")).strip()
        if title:
            lines.append(f"TI  - {title}")
        year = str(row.get("Year", "")).strip()
        if year and year != "nan":
            lines.append(f"PY  - {year}")
        authors = str(row.get("Authors", "")).strip()
        if authors and authors != "nan":
            for author in authors.split(";"):
                a = author.strip()
                if a:
                    lines.append(f"AU  - {a}")
        venue = str(row.get("Venue", "")).strip()
        if venue and venue != "nan":
            lines.append(f"JO  - {venue}")
        doi = str(row.get("DOI", "")).strip()
        if doi and doi != "nan":
            lines.append(f"DO  - {doi}")
        abstract = str(row.get("Abstract", "")).strip()
        if abstract and abstract != "nan":
            lines.append(f"AB  - {abstract}")
        # Keywords: prefer structured Concepts; fall back to TF-IDF from abstract
        concepts = str(row.get("Concepts", "") or "").strip()
        if concepts and concepts != "nan":
            for kw in concepts.split(";"):
                kw = kw.strip()
                if kw:
                    lines.append(f"KW  - {kw}")
        else:
            for kw in tfidf_kws[i]:
                lines.append(f"KW  - {kw}")
        lines.append("ER  - ")
        lines.append("")
    return "\n".join(lines)



def generate_vosviewer_json(df, top_n=40, min_cooccurrence=2):
    """Build a VOSviewer-format JSON dict from the corpus keyword co-occurrence network."""
    import math
    freq, edges, top_keywords = _build_cooccurrence_network(df, top_n=top_n, min_cooccurrence=min_cooccurrence)
    if not edges:
        return None

    # Assign cluster IDs via simple greedy community detection (connected components)
    from collections import defaultdict
    adj = defaultdict(set)
    for a, b, _ in edges:
        adj[a].add(b)
        adj[b].add(a)

    cluster_map = {}
    cluster_id = 1
    for kw in top_keywords:
        if kw not in cluster_map:
            # BFS
            queue = [kw]
            visited = set()
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                cluster_map[node] = cluster_id
                for nb in adj.get(node, []):
                    if nb not in visited and nb in top_keywords:
                        queue.append(nb)
            cluster_id += 1

    # Lay out nodes on a circle (VOSviewer will re-layout, but needs x/y)
    kw_list = sorted(top_keywords)
    n = len(kw_list)
    items = []
    for i, kw in enumerate(kw_list):
        angle = 2 * math.pi * i / max(n, 1)
        items.append({
            "id": i + 1,
            "label": kw,
            "x": round(math.cos(angle), 4),
            "y": round(math.sin(angle), 4),
            "cluster": cluster_map.get(kw, 1),
            "weights": {"Occurrences": int(freq.get(kw, 1))},
        })

    kw_to_id = {kw: i + 1 for i, kw in enumerate(kw_list)}
    links = []
    for a, b, cnt in edges:
        if a in kw_to_id and b in kw_to_id:
            links.append({
                "source_id": kw_to_id[a],
                "target_id": kw_to_id[b],
                "strength": int(cnt),
            })

    vos_json = {
        "network": {
            "items": items,
            "links": links,
        },
        "config": {
            "parameters": {
                "largest_component": True,
                "attraction": 2,
                "repulsion": 1,
            },
            "terminology": {
                "item": "keyword",
                "items": "keywords",
                "link": "co-occurrence",
                "links": "co-occurrences",
                "link_strength": "co-occurrence strength",
                "total_link_strength": "total co-occurrence strength",
            },
        },
        "info": {
            "title": "Keyword Co-occurrence Network",
            "description": f"Built from {len(df)} records. Nodes = keywords; edges = co-occurrence in titles/abstracts.",
        },
    }
    return vos_json

def render_vosviewer_section(df, session_key):
    """Render the VOSviewer bibliometric network section.
    Generate a downloadable JSON without publishing participant data online.
    """
    import json as _json

    st.markdown("#### 🔬 Bibliometric Network Map — VOSviewer")
    st.markdown("""
[VOSviewer](https://www.vosviewer.com) is the standard free tool for creating
**keyword co-occurrence networks**, **citation networks**, and **bibliographic coupling maps**
when the input contains suitable data. This app's RIS export does not supply a cited-reference
network to VOSviewer; it cannot by itself produce citation, bibliographic-coupling or co-citation
maps. Use the in-app coupling network when the corpus contains reference IDs. VOSviewer is
available in two versions:
- **VOSviewer Online** (`app.vosviewer.com`) — browser-based, no installation needed.
- **VOSviewer Desktop** — full application (Windows / Mac / Linux), for larger corpora and offline use.
    """)

    # Do not upload participant research data to a public third-party URL.
    vos_data = generate_vosviewer_json(df)

    # ── Buttons row ───────────────────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])

    with col2:
        st.link_button(
            "🌐 Open VOSviewer Online",
            "https://app.vosviewer.com",
            use_container_width=True,
        )
        st.caption("Load the downloaded JSON file via the folder icon on the site. The app does not publish it automatically.")
        st.markdown("")
        st.link_button(
            "⬇️ VOSviewer Desktop",
            "https://www.vosviewer.com/download",
            use_container_width=True,
        )
        st.caption("For larger corpora & offline use")

    with col1:
        # Download VOSviewer JSON directly
        if vos_data is not None:
            vos_json_bytes = _json.dumps(vos_data, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "⬇️ Download VOSviewer JSON (load via folder icon on app.vosviewer.com)",
                vos_json_bytes,
                f"{session_key}_vosviewer_network.json",
                "application/json",
                key=f"dl_vos_json_{session_key}",
            )
            st.caption(
                "This JSON file contains the keyword co-occurrence network in VOSviewer format. "
                "Load it via the folder icon on app.vosviewer.com or in VOSviewer Desktop."
            )
        # Also keep the RIS download for users who want to create maps from scratch
        ris_str = df_to_ris(df)
        ris_bytes = ris_str.encode("utf-8")
        st.download_button(
            "⬇️ Download RIS file (for creating custom maps in VOSviewer Desktop)",
            ris_bytes,
            f"{session_key}_corpus_for_vosviewer.ris",
            "application/x-research-info-systems",
            key=f"dl_ris_vos_{session_key}",
        )
        st.caption(
            "The RIS file contains titles, authors, years, venues, DOIs, and abstracts "
            "for all records in this corpus. VOSviewer reads this format natively."
        )


def render_bibliometric_networks(df, session_key):
    """Display author or study coupling networks using only the supplied metadata."""
    st.markdown("#### Co-authorship and bibliographic coupling")
    choice = st.selectbox(
        "Choose a bibliometric network",
        ["Select a network", "Co-authorship", "Bibliographic coupling (shared references)"],
        key=f"d1_bib_kind_{session_key}",
    )
    if choice == "Select a network":
        st.caption("Choose a network to explore this corpus. Coupling requires reference lists; none are inferred when they are absent.")
        return
    kind = "authors" if choice == "Co-authorship" else "coupling"
    if kind == "authors":
        st.caption("Nodes are authors; a link counts records they co-authored. Names are matched by case and whitespace, not disambiguated. Names must be semicolon-separated. Providers and older datasets may omit or truncate authors; a comma-separated list is treated as one name.")
    else:
        st.caption("Nodes are studies; a link counts their distinct shared reference IDs. Hover over a node for its full title. References can be a JSON array of DOI, OpenAlex work IDs or prefixed PMIDs, or a semicolon-separated list when no ID itself contains a semicolon. Incomplete reference lists yield incomplete networks; DOI and OpenAlex IDs are not matched across namespaces. When the node limit is reached, studies with the most reference IDs are shown first, which can bias the map.")
    left, right = st.columns(2)
    with left:
        top_n = st.slider("Maximum network nodes", 10, 60, 25, 5, key=f"d1_bib_nodes_{session_key}")
    with right:
        label = "Minimum shared references per link" if kind == "coupling" else "Minimum co-authored records per link"
        minimum = st.slider(label, 1, 10, 1, 1, key=f"d1_bib_min_{session_key}")
    graph = build_network(df, kind, top_n=top_n, min_cooccurrence=minimum)
    if kind == "coupling":
        st.caption(f"Records with usable reference IDs: {graph['records_with_data']} of {graph['total_records']}. Shown: {len(graph['nodes'])} studies and {len(graph['edges'])} links; {graph['records_omitted_by_node_limit']} reference-bearing studies omitted by the node cap.")
    else:
        st.caption(f"Usable authors: {graph['records_with_data']} of {graph['total_records']} records. Shown: {len(graph['nodes'])} authors and {len(graph['edges'])} links.")
    if not graph["edges"]:
        if kind == "coupling" and not graph["records_with_data"]:
            st.info("No usable reference identifiers are available in these records, so bibliographic coupling cannot be calculated. Search OpenAlex or Crossref, or upload a CSV with a References column; references are never invented.")
        elif kind == "coupling":
            st.info(f"No study pair shares at least {minimum} recognized reference ID(s) among the shown studies. Missing references, incompatible identifier namespaces, or the node cap may hide matches; lower the threshold or increase the node limit where possible.")
        else:
            st.info("No co-author pairs are available at these settings. Check the Authors field, lower the threshold, or increase the node limit.")
        return
    try:
        graph_html = make_network_html(graph)
    except ValueError as exc:
        st.warning(f"Unable to display the network: {exc}")
    else:
        components.html(graph_html, height=590, scrolling=False)
    nodes = {node["id"]: node for node in graph["nodes"]}
    metric = "Shared references" if kind == "coupling" else "Co-authored records"
    edges = pd.DataFrame([
        {"Source": nodes[e["source"]].get("full_label", nodes[e["source"]]["label"]),
         "Target": nodes[e["target"]].get("full_label", nodes[e["target"]]["label"]),
         metric: e["weight"],
         **({"Source DOI": nodes[e["source"]].get("doi", ""), "Target DOI": nodes[e["target"]].get("doi", "")} if kind == "coupling" else {})}
        for e in graph["edges"]
    ]).sort_values([metric, "Source", "Target"], ascending=[False, True, True])
    node_rows = pd.DataFrame([
        {"Node": node.get("full_label", node["label"]),
         ("Available unique reference IDs" if kind == "coupling" else "Records containing author"): node["frequency"],
         **({"Record ID": node.get("record_id", ""), "DOI": node.get("doi", "")} if kind == "coupling" else {})}
        for node in graph["nodes"]
    ])
    with st.expander("View and download bibliometric network data"):
        st.caption("Files contain the displayed nodes and links only. Duplicate reference IDs within a study count once.")
        st.dataframe(edges, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download network links (CSV)", edges.to_csv(index=False).encode("utf-8"),
                               f"{session_key}_{kind}_links.csv", "text/csv", key=f"d1_bib_edges_{session_key}")
        with col2:
            st.download_button("Download network nodes (CSV)", node_rows.to_csv(index=False).encode("utf-8"),
                               f"{session_key}_{kind}_nodes.csv", "text/csv", key=f"d1_bib_nodefile_{session_key}")


def display_corpus(df, source_label, session_key):
    """Show stats, preview, year chart, pyvis network, VOSviewer section, and download buttons."""
    st.success(f"✅ Corpus loaded: **{len(df)} records** from {source_label}.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total records", len(df))
    col2.metric("With abstracts", int(df["Abstract"].fillna("").str.strip().str.len().gt(20).sum()))
    col3.metric("Unique venues", int(df["Venue"].nunique()) if "Venue" in df.columns else "—")

    st.markdown("#### Preview (first 20 rows)")
    st.dataframe(df.head(20), use_container_width=True)

    if "Year" in df.columns and df["Year"].notna().any():
        year_counts = (
            df["Year"]
            .dropna()
            .astype(str)
            .str[:4]
            .pipe(lambda s: pd.to_numeric(s, errors="coerce"))
            .dropna()
            .astype(int)
            .value_counts()
            .sort_index()
        )
        st.markdown("#### Publication Year Distribution")
        st.bar_chart(year_counts)

    # ── pyvis interactive keyword co-occurrence network ────────────────────────
    render_pyvis_network(df, session_key)

    # ── Study coupling / co-authorship, using supplied metadata only ───────────
    render_bibliometric_networks(df, session_key)

    # ── VOSviewer bibliometric network section ─────────────────────────────────
    render_vosviewer_section(df, session_key)

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown("#### Export")
    col_a, col_b = st.columns(2)
    with col_a:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download corpus as CSV",
            csv_bytes,
            f"{session_key}_corpus.csv",
            "text/csv",
            key=f"dl_csv_{session_key}",
        )
    with col_b:
        ris_str = df_to_ris(df)
        st.download_button(
            "⬇️ Export as RIS (for Zotero / reference managers)",
            ris_str.encode("utf-8"),
            f"{session_key}_corpus.ris",
            "application/x-research-info-systems",
            key=f"dl_ris_{session_key}",
        )

    st.info("For Day 2 BYOD, use a corpus saved from a live search or explicitly sent from a CSV upload in this session, or download this CSV and upload it in Day 2 BYOD.")


# ── Live API helpers (BYOD only) ───────────────────────────────────────────────

class CrossrefError(Exception):
    """Safe participant-facing Crossref retrieval error."""


def _provider_list(value):
    return value if isinstance(value, list) else []


def _provider_mapping(value):
    return value if isinstance(value, dict) else {}


def _provider_text(value):
    return value.strip() if isinstance(value, str) else ""


def _first_provider_text(value):
    if isinstance(value, str):
        return _provider_text(value)
    return next((text for entry in _provider_list(value) if (text := _provider_text(entry))), "")


def _openalex_reference_id(value):
    """Normalize an explicitly supplied OpenAlex Work ID, not a DOI or a guess."""
    if not isinstance(value, str):
        return ""
    match = re.fullmatch(
        r"(?:(?:https?://openalex\.org/)|(?:https?://api\.openalex\.org/works/)|openalex:)?W([0-9]+)/?",
        value.strip(), flags=re.IGNORECASE,
    )
    return f"openalex:W{match.group(1)}" if match else ""


def _crossref_reference_doi(value):
    """Normalize a DOI while preserving its complete suffix and namespace.

    Resolver URLs are percent-decoded once; bare DOI values are treated as
    literal DOI names. Semicolons and percent signs remain part of the DOI;
    JSON array serialization keeps semicolons distinct from separators.
    """
    from urllib.parse import unquote, urlsplit

    if not isinstance(value, str):
        return ""
    doi = re.sub(r"^doi:\s*", "", value.strip(), flags=re.IGNORECASE)
    # urlsplit removes some embedded control characters; reject them instead of
    # silently turning malformed input into a different DOI.
    if any(not char.isprintable() or char.isspace() for char in doi):
        return ""
    if re.match(r"^https?://", doi, flags=re.IGNORECASE):
        try:
            parsed = urlsplit(doi)
            if (parsed.netloc.casefold() not in {"doi.org", "dx.doi.org"}
                    or parsed.query or parsed.fragment or not parsed.path.startswith("/")
                    or re.search(r"%(?![0-9a-fA-F]{2})", parsed.path)):
                return ""
            doi = unquote(parsed.path[1:], encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError):
            return ""
    # This is a syntax check, not proof that a DOI exists. Do not strip suffix
    # punctuation, which can be part of a legitimate DOI.
    if (not re.fullmatch(r"10\.[0-9]+/.+", doi, flags=re.IGNORECASE)
            or any(not char.isprintable() or char.isspace() for char in doi)):
        return ""
    return f"doi:{doi.lower()}"


def _reference_string(values):
    """Serialize unique identifiers, in provider order, as a JSON array string.

    OpenAlex Work IDs and DOIs are separate namespaces and cannot be matched
    across providers without a verified mapping. An empty result means no
    usable identifiers were supplied, not necessarily that a work cites none.
    """
    seen = set()
    identifiers = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            identifiers.append(value)
    return json.dumps(identifiers, ensure_ascii=False) if identifiers else ""


def _openalex_references(record):
    return _reference_string(
        _openalex_reference_id(value)
        for value in _provider_list(record.get("referenced_works"))
    )


def _crossref_references(record):
    # Only DOI fields on explicit reference entries count; unstructured
    # citations and the citing paper's own DOI are not inferred references.
    identifiers = []
    for reference in _provider_list(record.get("reference")):
        reference = _provider_mapping(reference)
        identifier = (_crossref_reference_doi(reference.get("DOI"))
                      or _crossref_reference_doi(reference.get("doi")))
        identifiers.append(identifier)
    return _reference_string(identifiers)


def query_crossref_live(search_query, per_page=50, include_log=False):
    base = "https://api.crossref.org/works"
    params = {
        "query": search_query,
        "rows": per_page,
        "select": "DOI,title,author,published,container-title,abstract,reference",
    }
    try:
        r = requests.get(base, params=params, timeout=30)
        r.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 429:
            raise CrossrefError("Crossref rate-limited this request (HTTP 429). Wait a moment and try again.") from None
        raise CrossrefError("Crossref could not complete this search. Please retry or use another provider.") from None
    except requests.RequestException:
        raise CrossrefError("Crossref could not be reached. Please retry or use another provider.") from None
    try:
        payload = r.json()
    except ValueError:
        raise CrossrefError("Crossref returned an invalid response. Please retry or use another provider.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
        raise CrossrefError("Crossref returned an invalid response. Please retry or use another provider.")
    message = payload["message"]
    items = message.get("items", [])
    if not isinstance(items, list):
        raise CrossrefError("Crossref returned an invalid response. Please retry or use another provider.")
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _first_provider_text(item.get("title"))
        authors_list = _provider_list(item.get("author"))
        authors = "; ".join(
            name for a in authors_list
            if (name := " ".join(filter(None, (
                _provider_text(_provider_mapping(a).get("family")),
                _provider_text(_provider_mapping(a).get("given")),
            ))))
        )
        date_parts = _provider_list(_provider_mapping(item.get("published")).get("date-parts"))
        parts = _provider_list(date_parts[0]) if date_parts else []
        year_value = parts[0] if parts else ""
        year = str(year_value) if isinstance(year_value, (str, int)) and not isinstance(year_value, bool) else ""
        venue = _first_provider_text(item.get("container-title"))
        abstract = _provider_text(item.get("abstract"))
        # Crossref abstracts often contain JATS/XML markup rather than plain text.
        abstract = " ".join(html.unescape(re.sub(r"</?[A-Za-z][^>]*>", " ", abstract)).split())
        rows.append({
            "ID": _provider_text(item.get("DOI")),
            "DOI": _provider_text(item.get("DOI")),
            "Title": title,
            "Year": year,
            "Authors": authors,
            "Venue": venue,
            "Abstract": abstract,
            "Citations": "",
            "Concepts": "",
            "References": _crossref_references(item),
        })
    df = pd.DataFrame(rows, columns=["ID", "DOI", "Title", "Year", "Authors", "Venue",
                                      "Abstract", "Citations", "Concepts", "References"])
    total = message.get("total-results")
    total = total if isinstance(total, int) else None
    log = {
        "endpoint": base, "pages_fetched": 1, "scope": "provider-specific relevance search",
        "filters": [], "pagination": "one page only", "total_matches": total,
        "returned": len(rows),
        "possibly_truncated": (total > len(rows)) if total is not None else (len(rows) >= per_page),
    }
    return (df, log) if include_log else df


def query_europepmc_live(search_query, per_page=50):
    base = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": search_query,
        "resultType": "core",
        "pageSize": per_page,
        "format": "json",
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    items = r.json().get("resultList", {}).get("result", [])
    rows = []
    for item in items:
        author_list = _provider_list(_provider_mapping(item.get("authorList")).get("author"))
        names = [_provider_text(_provider_mapping(author).get("fullName")) for author in author_list]
        authors = "; ".join(name for name in names if name)
        # A free-form authorString may use commas in ambiguous ways. Keep it as
        # one label rather than guessing how to split individual names.
        if not authors:
            authors = _provider_text(item.get("authorString"))
        rows.append({
            "ID": item.get("id", ""),
            "DOI": item.get("doi", "") or "",
            "Title": (item.get("title", "") or "").strip(),
            "Year": item.get("pubYear", ""),
            "Authors": authors,
            "Venue": item.get("journalTitle", "") or "",
            "Abstract": item.get("abstractText", "") or "",
            "Citations": item.get("citedByCount", 0),
            "Concepts": "",
        })
    return pd.DataFrame(rows)


def openalex_to_df(records):
    rows = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        raw_aii = _provider_mapping(r.get("abstract_inverted_index"))
        words = {}
        for word, positions in raw_aii.items():
            if not isinstance(word, str):
                continue
            for pos in _provider_list(positions):
                if isinstance(pos, int) and not isinstance(pos, bool) and pos >= 0:
                    words[pos] = word
        # Sparse or malformed positions cannot cause an enormous allocation.
        abstract = " ".join(words[pos] for pos in sorted(words))
        authors = "; ".join(
            name for a in _provider_list(r.get("authorships"))
            if (name := _provider_text(_provider_mapping(
                _provider_mapping(a).get("author")).get("display_name")))
        )
        loc = _provider_mapping(r.get("primary_location"))
        source = _provider_mapping(loc.get("source"))
        venue = _provider_text(source.get("display_name"))
        concepts = "; ".join(
            name for c in _provider_list(r.get("concepts"))[:5]
            if (name := _provider_text(_provider_mapping(c).get("display_name")))
        )
        rows.append({
            "ID": _provider_text(r.get("id")),
            "DOI": _provider_text(r.get("doi")),
            "Title": _provider_text(r.get("title")),
            "Year": r.get("publication_year", ""),
            "Authors": authors,
            "Venue": venue,
            "Abstract": abstract,
            "Citations": r.get("cited_by_count", 0),
            "Concepts": concepts,
            "References": _openalex_references(r),
            "Publication Type": r.get("type", ""),
        })
    return pd.DataFrame(rows, columns=["ID", "DOI", "Title", "Year", "Authors", "Venue",
                                        "Abstract", "Citations", "Concepts", "References",
                                        "Publication Type"])


def deduplicate_df(df):
    if df.empty:
        return df
    df = df.copy()
    df["DOI"] = df["DOI"].fillna("").str.strip()
    has_doi = df[df["DOI"].str.len() > 0].drop_duplicates(subset=["DOI"], keep="first")
    no_doi = df[df["DOI"].str.len() == 0].copy()
    if not no_doi.empty:
        no_doi["_t"] = no_doi["Title"].str.lower().str.strip()
        no_doi = no_doi.drop_duplicates(subset=["_t"], keep="first").drop(columns=["_t"])
    return pd.concat([has_doi, no_doi], ignore_index=True)


def parse_ris_file(content):
    """Parse a RIS file content string into a DataFrame."""
    rows = []
    current = {}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("TY  -"):
            current = {"ID": "", "DOI": "", "Title": "", "Year": "", "Authors": "",
                       "Venue": "", "Abstract": "", "Citations": "", "Concepts": ""}
        elif line.startswith("TI  -"):
            current["Title"] = line[6:].strip()
        elif line.startswith("T1  -") and not current.get("Title"):
            current["Title"] = line[6:].strip()
        elif line.startswith("PY  -"):
            current["Year"] = line[6:].strip()[:4]
        elif line.startswith("Y1  -") and not current.get("Year"):
            current["Year"] = line[6:].strip()[:4]
        elif line.startswith("AU  -"):
            a = line[6:].strip()
            current["Authors"] = (current["Authors"] + "; " + a).strip("; ")
        elif line.startswith("JO  -") or line.startswith("JF  -") or line.startswith("T2  -"):
            if not current.get("Venue"):
                current["Venue"] = line[6:].strip()
        elif line.startswith("DO  -"):
            current["DOI"] = line[6:].strip()
        elif line.startswith("AB  -"):
            current["Abstract"] = line[6:].strip()
        elif line.startswith("ER  -"):
            if current.get("Title"):
                rows.append(current)
            current = {}
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("Day 1 Navigation")
section = st.sidebar.radio(
    "Select section",
    ["Overview", "📌 Guided Examples", "🔎 BYOD — Your Own Query"],
    key="day1_section",
)

# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if section == "Overview":
    st.title("📥 Day 1 — From Query to Corpus")
    st.markdown("""
**Theme:** Understand how to use open APIs for programmatic literature collection and
how to automatically deduplicate records — all in a **no-code** environment.

### What You Will Do Today

The first day introduces the logic of programmatic literature collection. The session
begins with the formulation of search strategies — such as the **PICO framework** for
health sciences or **SPIDER** for social sciences — and the identification of suitable
open APIs, including **OpenAlex**, **Crossref**, **Europe PMC**, and **OpenAIRE**.
OpenAIRE supports multidisciplinary discovery without a participant key; rate limits and
incomplete metadata can affect results, as explained in each OpenAIRE search.

Participants are shown how API-based retrieval differs from manual database searching
and how it facilitates reproducibility. Because APIs evolve and results may change over
time, reproducibility requires logging queries and timestamps — a practice the app
supports automatically.

The guided path presents four complete cases. At the top of each case, choose OpenAlex,
Crossref, Europe PMC or OpenAIRE. Crossref uses a recorded sample; the other providers run
their own fixed searches on request. Each case shows retrieval, fixed keyword screening,
source-linked extraction, descriptive synthesis and bibliometric maps together. A bounded
result set is not an exhaustive review search. The guided cases are independent of BYOD.

### Open APIs Covered

| API | Discipline Focus | Strengths |
|-----|-----------------|-----------|
| **OpenAlex** | All disciplines | 250M+ works, fully open, rich metadata including concepts and citations |
| **Crossref** | All disciplines | DOI-centric, strong for journal articles and conference papers |
| **Europe PMC** | Life sciences, health | Full-text access for many articles, strong for biomedical reviews |
| **OpenAIRE** | Multidisciplinary research | No participant key; combines scholarly metadata, with coverage and rate-limit caveats |

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Introduce the logic of programmatic literature collection. Clarify the difference between manual database searches and open API retrieval. Present discipline-spanning examples and explain how query timestamps are logged for reproducibility. |
| **Hour 2** | Demonstrate query building and API access. Show how to translate research questions into provider-specific searches and retrieve metadata from OpenAlex, Crossref, Europe PMC, and OpenAIRE. |
| **Hour 3** | Use the Streamlit app to run automated deduplication. Participants inspect the output, compare field completeness, explore the corpus using the **interactive keyword co-occurrence network** (pyvis), export a clean CSV or RIS file, and create a **VOSviewer** bibliometric map. |

### Input Flexibility: Multiple Entry Points

Participants do not need to start from a Boolean query. The BYOD section accepts:

| Input Type | When to Use |
|------------|-------------|
| **Boolean Query** | Starting a review from scratch |
| **RIS File** | Already searched traditional databases (PubMed, Scopus, Web of Science) |
| **Corpus CSV** | A saved corpus, including optional reference IDs for coupling |
| **Zotero Integration** | Already using a reference manager — connect your cloud or self-hosted library |

### Visualisation Options

The guided cases show the full workflow together. In BYOD, available maps depend on the
fields supplied with your corpus:

1. **Interactive keyword co-occurrence network (pyvis)** — built directly in this app.
   Drag nodes, scroll to zoom, hover for details. Instantly shows which topics cluster together.

2. **Co-authorship and bibliographic coupling** — use the in-app selector below a corpus.
   Coupling needs reference lists and may be unavailable when a source does not supply them.
   VOSviewer can also create certain maps from suitable input, but this app's RIS export
   cannot supply cited-reference links for citation, coupling, or co-citation analyses.

### Learning Outcome

By the end of Day 1, you should be able to formulate a search strategy, understand how
open APIs retrieve bibliographic metadata, follow the logic by which the app converts API
responses into a clean, deduplicated corpus ready for screening, and produce both an
interactive keyword network and a VOSviewer bibliometric map of your corpus.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Query**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 1 — Guided Examples")
    guided_workflow.render_guided_examples("day1")

# ══════════════════════════════════════════════════════════════════════════════
# BYOD — BRING YOUR OWN DATA
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Your Own Query":
    st.title("🔎 Day 1 — Bring Your Own Data")
    st.markdown("""
Use this section to build a corpus from **your own research question**.
Choose your preferred input method below. No coding required.

These input methods produce a deduplicated corpus table,
a publication year chart, an **interactive keyword co-occurrence network** (pyvis),
a RIS export for Zotero, and a RIS file ready for **VOSviewer** bibliometric network analysis.
    """)

    input_method = st.radio(
        "How would you like to provide your literature?",
        [
            "🔍 Search open APIs live",
            "📄 Upload RIS file",
            "📊 Upload corpus CSV",
            "🗂️ Zotero Integration",
        ],
        horizontal=True,
    )

    # ── Option 1: API search ──────────────────────────────────────────────────
    if input_method == "🔍 Search open APIs live":
        st.markdown("#### Search Open APIs")
        # Drop any obsolete Semantic Scholar widget state from earlier deployments.
        st.session_state.pop("semantic_scholar_key_widget", None)
        if str(st.session_state.get("byod_api_widget", "")).startswith("Semantic Scholar"):
            st.session_state["byod_api_widget"] = OPENAIRE_CHOICE
        api_choice = st.selectbox(
            "Select API",
            [
                "OpenAlex (recommended for most disciplines)",
                "Crossref (DOI-centric, all disciplines)",
                "Europe PMC (Life sciences, health)",
                OPENAIRE_CHOICE,
            ],
            key="byod_api_widget",
        )
        is_openalex = api_choice.startswith("OpenAlex")
        is_openaire = api_choice.startswith("OpenAIRE")
        browser_result = None
        browser_mode = False
        st.caption("Each provider has its own search syntax and usage limits. OpenAlex and OpenAIRE support uppercase AND, OR and NOT, parentheses and quoted phrases, but search different fields.")
        query_input = st.text_input(
            "Search query",
            placeholder='e.g. ("creativity" OR "creative") AND "artificial intelligence"',
            key="byod_query_widget",
        )
        per_page = st.slider("Records per page", min_value=10, max_value=100, value=50, step=10)
        if is_openalex:
            scope_label = st.selectbox(
                "Search scope",
                ["Title and abstract (no stemming)", "Broad: title, abstract, full text and keywords"],
                key="byod_scope_widget",
            )
            st.caption("Quoted phrases are retained. OpenAlex's broad search may match full text or keywords not visible in a title/abstract. Unquoted words default to AND.")
            require_abstract = st.checkbox("Only include works with an abstract", value=True, key="byod_abstract_widget")
            max_pages = st.slider("Maximum number of pages to retrieve", min_value=1, max_value=5, value=2)
            st.caption("The app retrieves at most records per page × maximum pages. A larger search may have more matches than are downloaded.")
            use_year_filter = st.checkbox("Filter by publication year range", value=False, key="byod_use_year")
            if use_year_filter:
                current_year = time.gmtime().tm_year
                byod_year_from, byod_year_to = st.slider(
                    "Publication year range", min_value=1900, max_value=current_year,
                    value=(2010, current_year), step=1, key="byod_yr_slider",
                )
            else:
                byod_year_from, byod_year_to = None, None
            byod_pub_types = st.multiselect(
                "OpenAlex publication types (leave empty for all types)",
                ["article", "book-chapter", "conference-paper", "preprint", "review", "report"],
                default=[], key="byod_type_widget",
            )
            st.caption("OpenAlex calls journal articles ‘article’. Year, type and abstract filters are applied to the API request before records are returned.")
            st.markdown("#### Your OpenAlex credentials")
            st.markdown("Create a free account at [OpenAlex](https://openalex.org/signup), verify your email, and copy your key from [API settings](https://openalex.org/settings/api-key). This app uses a key for OpenAlex searches.")
            credential_method = st.radio(
                "How would you like to provide your OpenAlex credentials?",
                ["Local JSON file (browser only)", "Masked manual entry (app server)"],
                key="byod_openalex_credential_method",
            )
            browser_mode = credential_method.startswith("Local JSON")
            if browser_mode:
                st.caption("The browser reads your local file and sends the key directly to OpenAlex over HTTPS. The app receives the returned records, not your credentials. This depends on trusting the app's supplied code, your browser and its extensions.")
                run_query = False
                if query_input.strip():
                    from browser_openalex import render_browser_openalex
                    browser_result = render_browser_openalex(
                        query_input.strip(), key="byod_openalex_browser",
                        per_page=per_page, max_pages=max_pages,
                        year_from=byod_year_from, year_to=byod_year_to,
                        publication_types=byod_pub_types,
                        search_scope="title_abstract_exact" if scope_label.startswith("Title") else "broad",
                        require_abstract=require_abstract,
                    )
                    if browser_result is not None:
                        request_id = browser_result[1]["request_id"]
                        run_query = request_id != st.session_state.get("byod_browser_last_request_id")
                else:
                    st.info("Enter your search query above to show the browser-local file picker.")
            else:
                st.caption("Both fields are masked and held in this session's Streamlit state. The app server receives the key, and its operator may be able to access it. The key is sent to OpenAlex over HTTPS; the email is not sent with searches. Neither is included in downloads or query logs.")
                with st.form("openalex_private_credentials"):
                    openalex_email = st.text_input("Verified OpenAlex account email", type="password", key="openalex_email_widget")
                    openalex_key = st.text_input("OpenAlex API key", type="password", key="openalex_key_widget")
                    run_query = st.form_submit_button("▶ Run My Query")
                st.button("Forget my OpenAlex credentials", on_click=forget_openalex_credentials, key="forget_openalex")
        else:
            if "Crossref" in api_choice:
                st.info("Crossref needs no account, API key, or email. It retrieves one page; year and publication-type filters are not available in this app. Relevance search may not obey Boolean syntax, and abstracts are often missing.")
            elif is_openaire:
                st.warning(OPENAIRE_LIMITATIONS)
                st.caption('For Boolean operators, wrap every search value in double quotes, e.g. ("creativity" OR "creative") AND "artificial intelligence". Use uppercase operators. The query is sent to OpenAIRE as entered; review the returned records and save the query log.')
            else:
                st.info("This provider currently retrieves one page. Year and publication-type filters are not available here. Query interpretation is provider-specific; Boolean syntax is not guaranteed.")
            if is_openaire:
                max_pages = st.slider("Maximum number of OpenAIRE pages", min_value=1, max_value=3, value=1, key="openaire_max_pages")
                st.caption("At most records per page × maximum pages are retrieved; each page is another request against the rate limit.")
            else:
                max_pages = 1
            byod_year_from, byod_year_to = None, None
            byod_pub_types = []
            run_query = st.button("▶ Run My Query", key="run_byod_other")

        if run_query:
            if not query_input.strip():
                st.warning("Please enter a search query above.")
            elif is_openalex and not browser_mode and (not openalex_key.strip() or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", openalex_email.strip())):
                st.warning("Enter your OpenAlex API key and a valid account email. OpenAlex must have verified the email associated with the key.")
            else:
                # Avoid presenting an earlier successful corpus as the result of a failed new query.
                for state_key in ("byod_df", "byod_log", "byod_query", "byod_api", "byod_year_from", "byod_year_to", "byod_pub_types", "byod_screening_run", "byod_included_df"):
                    st.session_state.pop(state_key, None)
                with st.spinner(f"Querying {api_choice.split('(')[0].strip()}…"):
                    try:
                        api_name = api_choice.split("(")[0].strip()
                        if is_openalex:
                            if browser_mode:
                                records, request_log = browser_result
                                st.session_state["byod_browser_last_request_id"] = request_log["request_id"]
                            else:
                                records, request_log = fetch_works(
                                    query_input.strip(), openalex_key.strip(),
                                    per_page=per_page, max_pages=max_pages,
                                    year_from=byod_year_from, year_to=byod_year_to,
                                    publication_types=byod_pub_types,
                                    search_scope="title_abstract_exact" if scope_label.startswith("Title") else "broad",
                                    require_abstract=require_abstract,
                                )
                            df = openalex_to_df(records)
                        elif "Crossref" in api_choice:
                            df, request_log = query_crossref_live(query_input.strip(), per_page=per_page, include_log=True)
                        elif is_openaire:
                            df, request_log = fetch_openaire(query_input.strip(), per_page=per_page, max_pages=max_pages)
                            df["Source"] = "OpenAIRE"
                        elif "Europe PMC" in api_choice:
                            df = query_europepmc_live(query_input.strip(), per_page=per_page)
                            request_log = {"endpoint": "https://www.ebi.ac.uk/europepmc/webservices/rest/search", "pages_fetched": 1, "scope": "provider-specific search", "filters": []}
                        else:
                            df = pd.DataFrame()
                            request_log = {}

                        before = len(df)
                        df = deduplicate_df(df)
                        after = len(df)
                        st.info(f"Deduplication removed {before - after} duplicate records ({before} → {after}).")
                        st.session_state["byod_df"] = df
                        st.session_state["byod_api"] = api_name
                        st.session_state["byod_query"] = query_input.strip()
                        st.session_state["byod_year_from"] = int(byod_year_from) if byod_year_from else None
                        st.session_state["byod_year_to"] = int(byod_year_to) if byod_year_to else None
                        st.session_state["byod_pub_types"] = byod_pub_types

                        log = {
                            "query": query_input.strip(),
                            "api": api_name,
                            "per_page": per_page,
                            "max_pages": max_pages,
                            "records_retrieved": before,
                            "records_after_dedup": after,
                            "year_from": int(byod_year_from) if byod_year_from else None,
                            "year_to": int(byod_year_to) if byod_year_to else None,
                            "publication_types": byod_pub_types,
                            "request": request_log,
                            "deduplication": "Same DOI, or same lowercased title for records without DOI; first retained.",
                            "corpus_csv_sha256": hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest(),
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                        }
                        if is_openaire:
                            log["provider_limitations"] = OPENAIRE_LIMITATIONS
                        st.session_state["byod_log"] = log
                        if request_log.get("possibly_truncated"):
                            st.warning("More records may be available; this saved corpus may not be the complete result set. See the query log for how retrieval ended.")
                    except OpenAlexError as exc:
                        st.error(f"{exc}. For authentication errors, check the key and verify its account email. For rate limits, wait before retrying.")
                    except OpenAIREError as exc:
                        st.error(str(exc))
                    except CrossrefError as exc:
                        st.error(str(exc))
                    except Exception:
                        st.error("Unable to retrieve or process the results. Check the selected provider and query, then try again. No credentials are included in this message.")

        _legacy_snapshot = st.session_state.get("byod_log", {}).get("source") == "cached teaching snapshot"
        if _legacy_snapshot:
            st.info("A teaching snapshot left by an older version is not used as a BYOD result. Run your own search or upload your own corpus.")
        if "byod_df" in st.session_state and st.session_state["byod_df"] is not None and not _legacy_snapshot:
            df = st.session_state["byod_df"]
            _yr_from = st.session_state.get("byod_year_from")
            _yr_to = st.session_state.get("byod_year_to")
            _ptypes = st.session_state.get("byod_pub_types", [])
            _snapshot = st.session_state.get("byod_log", {}).get("source") == "cached teaching snapshot"
            _period = "Not recorded" if _snapshot else (f"{_yr_from}–{_yr_to}" if _yr_from and _yr_to else ("from " + str(_yr_from) if _yr_from else ("up to " + str(_yr_to) if _yr_to else "All years")))
            _types_disp = "Not recorded" if _snapshot else ("OpenAIRE publications (all subtypes)" if st.session_state.get("byod_api") == "OpenAIRE" else (", ".join(_ptypes) if _ptypes else "All types"))
            st.markdown(
                f"**API source:** {st.session_state.get('byod_api', '')} &nbsp;|&nbsp; "
                f"**Query:** `{st.session_state.get('byod_query', '')}`  \n"
                f"**Time period:** {_period} &nbsp;|&nbsp; **Publication types:** {_types_disp}"
            )
            st.caption("Results below are from the last successfully completed search or saved BYOD corpus, not from unsubmitted changes to the menus.")
            if st.session_state.get("byod_api") == "OpenAIRE":
                st.warning(OPENAIRE_LIMITATIONS)
            if df.empty:
                st.warning("The search returned no records with these settings. Consider a broader query, different search scope, or removing a filter.")
            else:
                display_corpus(df, f"Custom query: '{st.session_state.get('byod_query', '')}'", "byod")
            if "byod_log" in st.session_state:
                st.markdown("#### Query Log (for reproducibility)")
                st.json(st.session_state["byod_log"])
                log_bytes = json.dumps(st.session_state["byod_log"], indent=2).encode("utf-8")
                st.download_button(
                    "⬇️ Download Query Log",
                    log_bytes, "query_log.json", "application/json",
                    key="dl_log",
                )

    # ── Option 2: RIS Upload ──────────────────────────────────────────────────
    elif input_method == "📄 Upload RIS file":
        st.markdown("""
#### Upload an Existing RIS File

If you have already searched traditional databases (PubMed, Scopus, Web of Science,
CINAHL, PsycINFO, etc.) and exported the results as a **RIS** file,
upload it here. The app will parse the file, deduplicate the records, and produce
the same corpus preview, year chart, interactive keyword co-occurrence network,
VOSviewer bibliometric network export, and download options for your own corpus.
        """)
        uploaded_file = st.file_uploader(
            "Upload your RIS file",
            type=["ris", "txt"],
            key="ris_upload",
        )
        if uploaded_file is not None:
            content = uploaded_file.read().decode("utf-8", errors="replace")
            with st.spinner("Parsing file…"):
                df = parse_ris_file(content)
            if df.empty:
                st.error("Could not parse the file. Please ensure it is a valid RIS file.")
            else:
                before = len(df)
                df = deduplicate_df(df)
                after = len(df)
                st.info(f"Parsed {before} records. Deduplication removed {before - after} duplicates ({before} → {after}).")
                display_corpus(df, f"Uploaded file: {uploaded_file.name}", "byod_ris")

    # ── Option 3: Corpus CSV with optional reference lists ──────────────────────
    elif input_method == "📊 Upload corpus CSV":
        st.markdown("#### Upload a Corpus CSV")
        st.caption('Use a CSV with a Title column. Optional Authors values should be separated by semicolons. For bibliographic coupling add a References column containing JSON arrays of DOI, OpenAlex work IDs or prefixed PMIDs (for example ["doi:10.1234/a", "openalex:W123"]). A semicolon-separated list is also supported if the identifiers themselves contain no semicolons. Save the original source and query log separately.')
        uploaded_csv = st.file_uploader("Upload your corpus CSV", type=["csv"], key="corpus_csv_upload")
        if uploaded_csv is not None:
            try:
                raw_csv = uploaded_csv.getvalue()
                df = pd.read_csv(io.BytesIO(raw_csv))
                if "Title" not in df.columns:
                    st.error("The CSV needs a Title column. Column names are case-sensitive.")
                elif df.empty:
                    st.warning("The uploaded CSV has no records.")
                else:
                    for col in ("ID", "DOI", "Title", "Authors", "Venue", "Abstract", "Concepts", "References"):
                        if col not in df.columns:
                            df[col] = ""
                        df[col] = df[col].fillna("").astype(str)
                    if "Year" not in df.columns:
                        df["Year"] = ""
                    if "Citations" not in df.columns:
                        df["Citations"] = ""
                    if source_column_mentions_openaire(df):
                        st.warning(OPENAIRE_LIMITATIONS)
                    before = len(df)
                    df = deduplicate_df(df)
                    st.info(f"Loaded {before} records; retained {len(df)} after deduplication.")
                    if st.button("Use this CSV in Day 2 BYOD", key="send_csv_to_day2"):
                        st.session_state.pop("byod_screening_run", None)
                        st.session_state.pop("byod_included_df", None)
                        st.session_state["byod_df"] = df.copy()
                        st.session_state["byod_api"] = "User-supplied CSV"
                        st.session_state["byod_query"] = "Not recorded in the CSV"
                        st.session_state["byod_year_from"] = None
                        st.session_state["byod_year_to"] = None
                        st.session_state["byod_pub_types"] = []
                        st.session_state["byod_log"] = {"source": "user-supplied CSV", "filename": uploaded_csv.name,
                                                        "file_sha256": hashlib.sha256(raw_csv).hexdigest(),
                                                        "records_after_dedup": len(df)}
                        st.success("CSV copied to this session. Open Day 2 → BYOD to screen it.")
                    display_corpus(df, f"Uploaded file: {uploaded_csv.name}", "byod_csv")
            except (pd.errors.ParserError, UnicodeDecodeError, ValueError):
                st.error("Could not read this CSV. Check that it is a UTF-8 comma-separated file with a Title column.")

    # ── Option 4: Zotero ──────────────────────────────────────────────────────
    elif input_method == "🗂️ Zotero Integration":
        st.markdown("""
#### Connect Your Zotero Library

You can retrieve records directly from your **Zotero** cloud library using the
Zotero Web API. You will need your **User ID** and a **Personal API Key**, both
of which are available from your [Zotero account settings](https://www.zotero.org/settings/keys).

**How to find your credentials:**
1. Log in at [zotero.org](https://www.zotero.org) → click your username (top right) → **Settings**
2. Click **Feeds/API** → note your **User ID** (a number, e.g. `1234567`)
3. Click **Create new private key** → give it a name → tick **Allow library access** → **Save Key**
4. Copy the key and paste it below (it is only shown once)
        """)

        zotero_user_id = st.text_input("Zotero User ID", placeholder="e.g. 1234567")
        zotero_api_key = st.text_input("Zotero API Key", type="password",
                                        placeholder="Paste your personal API key here")
        zotero_collection = st.text_input(
            "Collection key (optional — leave blank to retrieve entire library)",
            placeholder="e.g. ABC12DEF",
        )

        if st.button("▶ Retrieve from Zotero", key="run_zotero"):
            if not zotero_user_id.strip() or not zotero_api_key.strip():
                st.warning("Please provide both your Zotero User ID and API Key.")
            else:
                with st.spinner("Connecting to Zotero…"):
                    try:
                        headers = {"Zotero-API-Key": zotero_api_key.strip()}
                        uid = zotero_user_id.strip()
                        if zotero_collection.strip():
                            url = f"https://api.zotero.org/users/{uid}/collections/{zotero_collection.strip()}/items"
                        else:
                            url = f"https://api.zotero.org/users/{uid}/items"
                        params = {"format": "json", "itemType": "journalArticle || conferencePaper || preprint", "limit": 100}
                        r = requests.get(url, headers=headers, params=params, timeout=30)
                        r.raise_for_status()
                        items = r.json()
                        rows = []
                        for item in items:
                            data = item.get("data", {})
                            if data.get("itemType") not in ("journalArticle", "conferencePaper", "preprint", "report"):
                                continue
                            authors = "; ".join(
                                f"{c.get('lastName', '')} {c.get('firstName', '')}".strip()
                                for c in data.get("creators", [])
                                if c.get("creatorType") == "author"
                            )
                            rows.append({
                                "ID": item.get("key", ""),
                                "DOI": data.get("DOI", "") or "",
                                "Title": (data.get("title", "") or "").strip(),
                                "Year": str(data.get("date", ""))[:4],
                                "Authors": authors,
                                "Venue": data.get("publicationTitle", "") or data.get("conferenceName", "") or "",
                                "Abstract": data.get("abstractNote", "") or "",
                                "Citations": "",
                                "Concepts": "",
                            })
                        df = pd.DataFrame(rows)
                        if df.empty:
                            st.warning("No journal articles, conference papers, or preprints found in this library/collection.")
                        else:
                            before = len(df)
                            df = deduplicate_df(df)
                            after = len(df)
                            st.info(f"Retrieved {before} records from Zotero. Deduplication removed {before - after} duplicates ({before} → {after}).")
                            st.session_state["byod_zotero_df"] = df
                    except requests.HTTPError as e:
                        st.error(f"Zotero API error: {e}. Check your User ID and API Key.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        if "byod_zotero_df" in st.session_state and st.session_state["byod_zotero_df"] is not None:
            df = st.session_state["byod_zotero_df"]
            display_corpus(df, "Zotero library", "byod_zotero")
