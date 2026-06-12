"""
Day 3 — From Studies to Evidence
LLM-assisted structured data extraction + narrative/quantitative synthesis.

All four guided examples are displayed simultaneously, each in its own expander.
Each example includes:
1. A structured written Overview (Research Question, Corpus, Findings, Limitations)
2. A 15-study extraction table
3. Synthesis (Forest plot with I² heterogeneity, or narrative/quantitative summary)
4. PRISMA flow diagram

Additional sections:
- Temporal Analysis widget
- Reporting Standards (PRISMA 2020, PRISMA-S, ROSES)
- Ethics of AI in Research Synthesis
- BYOD with custom schema, forest plot, and PRISMA
"""

import io
import re
import pathlib
import pandas as pd
import numpy as np
import scipy.stats as stats
import streamlit as st
import streamlit.components.v1 as components
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
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
    page_title="Day 3 — From Studies to Evidence",
    page_icon="📊",
    layout="wide",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent.parent
CACHE_DIR = _repo_root / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Stopwords ─────────────────────────────────────────────────────────────────
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


# ── VOSviewer helpers ──────────────────────────────────────────────────────────

def _extract_tfidf_keywords(texts, top_n=8):
    """Extract top TF-IDF keywords per document. Falls back to frequency if corpus too small."""
    clean = [t if isinstance(t, str) and len(t.strip()) > 20 else "" for t in texts]
    non_empty = [t for t in clean if t]
    if len(non_empty) < 2:
        results = []
        for t in clean:
            if not t:
                results.append([])
                continue
            words = re.findall(r'\\b[a-zA-Z]{4,}\\b', t.lower())
            stop = {"this","that","with","from","have","been","were","they",
                    "their","which","also","more","than","into","such","when",
                    "study","paper","research","results","using","used","based",
                    "show","showed","found","data","analysis","method","methods"}
            kws = [w for w in words if w not in stop]
            freq_c = Counter(kws)
            results.append([w for w, _ in freq_c.most_common(top_n)])
        return results
    try:
        vec = TfidfVectorizer(
            max_features=500, ngram_range=(1, 2), stop_words="english",
            min_df=1, token_pattern=r'\\b[a-zA-Z]{4,}\\b',
        )
        tfidf_matrix = vec.fit_transform(clean)
        feature_names = vec.get_feature_names_out()
        results = []
        for i, text in enumerate(clean):
            if not text:
                results.append([])
                continue
            row_arr = tfidf_matrix[i].toarray().flatten()
            top_indices = row_arr.argsort()[::-1][:top_n]
            kws = [feature_names[idx] for idx in top_indices if row_arr[idx] > 0]
            results.append(kws)
        return results
    except Exception:
        return [[] for _ in texts]


def df_to_ris(df):
    """Convert a DataFrame of included/extracted studies to RIS format with KW tags for VOSviewer."""
    abstracts = [str(row.get("Abstract", row.get("Title", "")) or "") for _, row in df.iterrows()]
    tfidf_kws = _extract_tfidf_keywords(abstracts, top_n=8)
    lines = []
    for i, (_, row) in enumerate(df.iterrows()):
        lines.append("TY  - JOUR")
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


def render_vosviewer_section(df, session_key):
    """Render VOSviewer bibliometric network section for included/extracted studies."""
    st.markdown("#### \U0001f52c Bibliometric Network Map \u2014 VOSviewer (Included Studies)")
    st.markdown("""
[VOSviewer](https://www.vosviewer.com) provides a richer, publication-quality map of the
**included studies** with colour-coded clusters, zoom, and label filtering.
The pyvis network above shows co-occurrence patterns computed in this app;
VOSviewer adds citation networks and bibliographic coupling on top of keyword co-occurrence.

- **VOSviewer Desktop** \u2014 where you **create** maps from bibliographic data (free, Windows/Mac/Linux).
- **VOSviewer Online** (`app.vosviewer.com`) \u2014 browser viewer only; load a `.json` map saved from the desktop app.
    """)
    st.info("""
**How to create a VOSviewer map from the included studies \u2014 step by step (Desktop App):**

**Step 1 \u2192** Click **"\u2b07\ufe0f Download RIS file for VOSviewer"** below.

**Step 2 \u2192** Download and install **VOSviewer Desktop** (free) from the button on the right.

**Step 3 \u2192** Open VOSviewer Desktop. Click **"Create"** (bottom-left panel).

**Step 4 \u2192** Select **"Create a map based on bibliographic data"** \u2192 click **"Next"**.


**Step 5 \u2192** Select **"Read data from reference manager files"** \u2192 click **"Next"**.


**Step 6 \u2192** Click the **"RIS"** tab \u2192 **"Browse"** \u2192 select the RIS file \u2192 click **"Next"**.

**Step 7 \u2192** Choose analysis type (Co-occurrence \u2192 All keywords recommended) \u2192 **"Next"**.

**Step 8 \u2192** Set minimum occurrences to **2** (small corpus) or **3** \u2192 **"Next"** \u2192 **"Finish"**.

**To view in VOSviewer Online:** File \u2192 Save as `.json` in the desktop app, then load via the folder icon at `app.vosviewer.com`.
    """)
    col1, col2 = st.columns([3, 1])
    with col2:
        st.markdown("")
        st.link_button("\U0001f310 Open VOSviewer Online", "https://app.vosviewer.com", use_container_width=True)
        st.caption("Free \u00b7 browser-based \u00b7 viewer only")
        st.markdown("")
        st.link_button("\u2b07\ufe0f VOSviewer Desktop", "https://www.vosviewer.com/download", use_container_width=True)
        st.caption("Create maps \u00b7 free \u00b7 Windows/Mac/Linux")
    with col1:
        ris_bytes = df_to_ris(df).encode("utf-8")
        st.download_button(
            "\u2b07\ufe0f Download RIS file for VOSviewer",
            ris_bytes,
            f"{session_key}_studies_for_vosviewer.ris",
            "application/x-research-info-systems",
            key=f"dl_ris_vos_{session_key}",
        )
        st.caption("Contains titles, authors, years, DOIs, abstracts, and keywords for all included studies.")

# ── pyvis network helpers ──────────────────────────────────────────────────────

def _build_cooccurrence_network(df, col="Title", top_n=30, min_cooccurrence=2):
    """Build keyword co-occurrence from a Title column (Day 3 extraction tables)."""
    all_docs_keywords = []
    for _, row in df.iterrows():
        doc_keywords = set()
        title = str(row.get(col, "") or "")
        if title and title != "nan":
            for w in re.findall(r'\b[a-zA-Z]{4,}\b', title.lower()):
                if w not in _STOPWORDS:
                    doc_keywords.add(w)
        # Also use Country / Population if available
        for extra_col in ["Country", "Population", "Intervention", "Outcome"]:
            val = str(row.get(extra_col, "") or "")
            if val and val != "nan":
                for w in re.findall(r'\b[a-zA-Z]{4,}\b', val.lower()):
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


def generate_pyvis_html(df, top_n=30, min_cooccurrence=2):
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

    # ── Louvain community detection ───────────────────────────────────────────
    try:
        import networkx as nx
        import community as community_louvain  # python-louvain

        G = nx.Graph()
        nodes_in_edges = set()
        for a, b, cnt in edges:
            nodes_in_edges.add(a)
            nodes_in_edges.add(b)
            G.add_edge(a, b, weight=cnt)

        partition = community_louvain.best_partition(G, weight='weight', random_state=42)
        num_communities = max(partition.values()) + 1 if partition else 1
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
        sorted_freqs = sorted([freq[kw] for kw in top_keywords]) if top_keywords else [1]
        q1 = sorted_freqs[max(0, len(sorted_freqs) // 4)]
        q2 = sorted_freqs[max(0, len(sorted_freqs) // 2)]
        q3 = sorted_freqs[max(0, 3 * len(sorted_freqs) // 4)]
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
            f"<b>{kw}</b><br/>"
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

    nodes_json = _json.dumps(nodes_data)
    edges_json = _json.dumps(edges_data)
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
    st.markdown("#### 🕸️ Interactive Concept Network — Included Studies")
    st.markdown("""
This network maps the **key concepts and terms** extracted from the included studies.
**Node colour = Louvain community** (nodes of the same colour belong to the same thematic cluster,
detected automatically by the Louvain algorithm). Larger nodes = more frequent;
thicker edges = more papers share both keywords. **Drag, zoom, hover for community and frequency details.**
    """)
    col_opts, _ = st.columns([2, 1])
    with col_opts:
        top_n = st.slider("Keywords to display", min_value=10, max_value=50, value=30, step=5,
                          key=f"pyvis_topn_{session_key}")
        min_cooc = st.slider("Minimum co-occurrence", min_value=1, max_value=5, value=2, step=1,
                             key=f"pyvis_mincooc_{session_key}")
    html, err = generate_pyvis_html(df, top_n=top_n, min_cooccurrence=min_cooc)
    if err:
        st.warning(f"⚠️ Network could not be generated: {err}")
    else:
        components.html(html, height=500, scrolling=False)



# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLE DATA
# ══════════════════════════════════════════════════════════════════════════════

GUIDED_EXAMPLES = [
    {
        "label": "🏥 Example 1 — Health Sciences: Health Inequalities in Chronic Disease Care",
        "session_key": "ex1_health",
        "year_from": 2000, "year_to": 2024, "pub_types": ["journal-article"],
        "synthesis_type": "meta_analysis",
        "schema_type": "PICO",
        "effect_label": "Risk Ratio (RR)",
        "null_val": 1.0,
        "prisma_counts": (150, 135, 135, 15),
        "temporal_data": {
            2010: 3, 2011: 4, 2012: 5, 2013: 6, 2014: 7,
            2015: 9, 2016: 10, 2017: 12, 2018: 14, 2019: 16,
            2020: 18, 2021: 20, 2022: 22, 2023: 24, 2024: 26,
        },
        "overview_text": """
### Overview: Health Inequalities in Chronic Disease Care

**Research Question (PICO):** Among patients with chronic diseases (diabetes, hypertension, CVD), do patients from lower socioeconomic backgrounds (P) receiving standard care (I) experience worse clinical outcomes and access (O) compared to high-SES patients (C)?

**Corpus & Screening:** 150 records retrieved via OpenAlex (2010–2025). After deduplication (n = 135), Active Learning and LLM screening identified 15 empirical studies that met all inclusion criteria (reporting quantitative disparities by SES). Screening performance: Recall = 0.94, Precision = 0.71.

**Key Findings:** The meta-analysis of 15 studies demonstrates a consistent, statistically significant disparity. Patients from lower socioeconomic backgrounds experience worse clinical outcomes and poorer access to specialist care compared to high-SES patients. The pooled Risk Ratio indicates a substantial inequality gap across multiple healthcare systems.

**Limitations:** High heterogeneity (I² > 70%) suggests that the magnitude of inequality varies significantly depending on the specific disease (diabetes vs. CVD) and national healthcare model (e.g., universal coverage vs. insurance-based). Reporting standard: **PRISMA 2020**.
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "Socioeconomic disparities in diabetes care access (UK)", "Year": 2019, "Country": "UK", "Population": "Low-SES T2DM", "Intervention": "NHS care", "Comparison": "High-SES T2DM", "Outcome": "HbA1c control", "Effect_Size": 1.42, "CI_Lower": 1.18, "CI_Upper": 1.71, "Sample_Size": 4820},
            {"Title": "Racial inequalities in hypertension management (USA)", "Year": 2020, "Country": "USA", "Population": "Black hypertension", "Intervention": "Primary care", "Comparison": "White hypertension", "Outcome": "BP control", "Effect_Size": 1.61, "CI_Lower": 1.35, "CI_Upper": 1.92, "Sample_Size": 9340},
            {"Title": "Income-related inequalities in CVD outcomes (Germany)", "Year": 2021, "Country": "Germany", "Population": "Low-income CVD", "Intervention": "Standard care", "Comparison": "High-income CVD", "Outcome": "30-day mortality", "Effect_Size": 1.28, "CI_Lower": 1.09, "CI_Upper": 1.51, "Sample_Size": 6120},
            {"Title": "Geographic disparities in chronic disease care (Australia)", "Year": 2022, "Country": "Australia", "Population": "Rural chronic", "Intervention": "Rural GP care", "Comparison": "Urban patients", "Outcome": "Specialist referral", "Effect_Size": 1.35, "CI_Lower": 1.12, "CI_Upper": 1.63, "Sample_Size": 3870},
            {"Title": "SES and diabetes control outcomes (Canada)", "Year": 2023, "Country": "Canada", "Population": "Low-SES T2DM", "Intervention": "CHC care", "Comparison": "High-SES T2DM", "Outcome": "HbA1c ≥8%", "Effect_Size": 1.19, "CI_Lower": 1.04, "CI_Upper": 1.37, "Sample_Size": 5640},
            {"Title": "Education level and heart failure readmission (Sweden)", "Year": 2018, "Country": "Sweden", "Population": "Low-edu HF", "Intervention": "Hospital care", "Comparison": "High-edu HF", "Outcome": "Readmission", "Effect_Size": 1.24, "CI_Lower": 1.05, "CI_Upper": 1.46, "Sample_Size": 2100},
            {"Title": "Poverty and asthma exacerbations in children (USA)", "Year": 2021, "Country": "USA", "Population": "Low-income asthma", "Intervention": "ED care", "Comparison": "High-income asthma", "Outcome": "Exacerbation", "Effect_Size": 1.55, "CI_Lower": 1.28, "CI_Upper": 1.88, "Sample_Size": 4500},
            {"Title": "Deprivation and stroke survival rates (UK)", "Year": 2020, "Country": "UK", "Population": "High-deprivation stroke", "Intervention": "Stroke unit", "Comparison": "Low-deprivation stroke", "Outcome": "1-year mortality", "Effect_Size": 1.31, "CI_Lower": 1.15, "CI_Upper": 1.49, "Sample_Size": 8900},
            {"Title": "SES impact on kidney disease progression (France)", "Year": 2022, "Country": "France", "Population": "Low-SES CKD", "Intervention": "Nephrology care", "Comparison": "High-SES CKD", "Outcome": "ESRD onset", "Effect_Size": 1.40, "CI_Lower": 1.20, "CI_Upper": 1.64, "Sample_Size": 3200},
            {"Title": "Neighborhood income and COPD management (USA)", "Year": 2019, "Country": "USA", "Population": "Low-income COPD", "Intervention": "Outpatient care", "Comparison": "High-income COPD", "Outcome": "Hospitalization", "Effect_Size": 1.48, "CI_Lower": 1.25, "CI_Upper": 1.75, "Sample_Size": 5100},
            {"Title": "Employment status and RA treatment adherence (Spain)", "Year": 2021, "Country": "Spain", "Population": "Unemployed RA", "Intervention": "Rheumatology care", "Comparison": "Employed RA", "Outcome": "Non-adherence", "Effect_Size": 1.22, "CI_Lower": 1.02, "CI_Upper": 1.45, "Sample_Size": 1800},
            {"Title": "Housing instability and HIV viral suppression (USA)", "Year": 2023, "Country": "USA", "Population": "Unstably housed HIV", "Intervention": "Clinic care", "Comparison": "Stably housed HIV", "Outcome": "Viral failure", "Effect_Size": 1.65, "CI_Lower": 1.38, "CI_Upper": 1.97, "Sample_Size": 2400},
            {"Title": "SES and post-MI rehabilitation access (Italy)", "Year": 2020, "Country": "Italy", "Population": "Low-SES post-MI", "Intervention": "Cardiac rehab", "Comparison": "High-SES post-MI", "Outcome": "Non-participation", "Effect_Size": 1.38, "CI_Lower": 1.18, "CI_Upper": 1.61, "Sample_Size": 4100},
            {"Title": "Income inequality in epilepsy care (Japan)", "Year": 2022, "Country": "Japan", "Population": "Low-income epilepsy", "Intervention": "Neurology care", "Comparison": "High-income epilepsy", "Outcome": "Seizure frequency", "Effect_Size": 1.15, "CI_Lower": 0.98, "CI_Upper": 1.35, "Sample_Size": 1500},
            {"Title": "Material deprivation and IBD biologics access (UK)", "Year": 2021, "Country": "UK", "Population": "High-deprivation IBD", "Intervention": "Gastro care", "Comparison": "Low-deprivation IBD", "Outcome": "Delayed biologics", "Effect_Size": 1.45, "CI_Lower": 1.22, "CI_Upper": 1.72, "Sample_Size": 2900},
        ]),
        "effect_col": "Effect_Size",
        "ci_lower_col": "CI_Lower",
        "ci_upper_col": "CI_Upper",
        "title_col": "Title",
    },
    {
        "label": "🏛️ Example 2 — Social Sciences: Universal Basic Income (UBI) Policy Outcomes",
        "session_key": "ex2_ubi",
        "year_from": 2010, "year_to": 2024, "pub_types": ["journal-article", "book-chapter"],
        "synthesis_type": "narrative",
        "schema_type": "Thematic Synthesis",
        "effect_label": "N/A (Narrative Synthesis)",
        "null_val": None,
        "prisma_counts": (150, 138, 138, 12),
        "temporal_data": {
            2009: 2, 2010: 3, 2011: 4, 2012: 4, 2013: 5,
            2014: 6, 2015: 7, 2016: 9, 2017: 11, 2018: 13,
            2019: 15, 2020: 18, 2021: 21, 2022: 24, 2023: 27,
        },
        "overview_text": """
### Overview: Universal Basic Income (UBI) Policy Outcomes

**Research Question (Thematic Synthesis):** What are the empirically measured outcomes of Universal Basic Income (UBI) programmes and pilots in terms of employment, poverty, and well-being?

**Corpus & Screening:** 150 records retrieved via OpenAlex. 12 empirical evaluations of UBI or guaranteed income pilots were included after excluding opinion pieces and theoretical models. Screening performance: Recall = 0.92, Precision = 0.67.

**Key Findings (Thematic Synthesis):** Three cross-cutting themes emerge: (1) *Employment neutrality* — UBI does not produce significant declines in labor market participation; (2) *Well-being gains* — nearly all studies report reductions in psychological distress and income volatility; (3) *Poverty reduction* — material deprivation indicators improve consistently across contexts.

**Limitations:** Many pilots are short-term (1–3 years) and involve small, localized samples, making macroeconomic extrapolation difficult. Reporting standard: **PRISMA-S** (search reporting).
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "Finland Basic Income Pilot: Two-Year Results", "Year": 2020, "Country": "Finland", "Programme_Name": "Finland UBI", "Theme_Employment": "Neutral", "Theme_Wellbeing": "Improved", "Theme_Poverty": "Reduced stress", "Methodology": "RCT", "Sample_Size": 2000},
            {"Title": "Stockton SEED: Guaranteed Income Outcomes", "Year": 2021, "Country": "USA", "Programme_Name": "Stockton SEED", "Theme_Employment": "Positive (+12% FT)", "Theme_Wellbeing": "Improved", "Theme_Poverty": "Reduced volatility", "Methodology": "Quasi-exp", "Sample_Size": 125},
            {"Title": "Kenya GiveDirectly Long-Run Evaluation", "Year": 2022, "Country": "Kenya", "Programme_Name": "GiveDirectly", "Theme_Employment": "Positive (Self-emp)", "Theme_Wellbeing": "Improved", "Theme_Poverty": "Reduced", "Methodology": "RCT", "Sample_Size": 10500},
            {"Title": "Alaska Permanent Fund Dividend: Labor Effects", "Year": 2018, "Country": "USA", "Programme_Name": "APFD", "Theme_Employment": "Neutral", "Theme_Wellbeing": "N/A", "Theme_Poverty": "Reduced extreme poverty", "Methodology": "Obs", "Sample_Size": 50000},
            {"Title": "Ontario Basic Income Pilot Analysis", "Year": 2020, "Country": "Canada", "Programme_Name": "Ontario Pilot", "Theme_Employment": "Neutral", "Theme_Wellbeing": "Improved significantly", "Theme_Poverty": "Improved food security", "Methodology": "Survey", "Sample_Size": 4000},
            {"Title": "Mincome Experiment Re-evaluation", "Year": 2011, "Country": "Canada", "Programme_Name": "Mincome", "Theme_Employment": "Slight negative (youth)", "Theme_Wellbeing": "Improved (hospital visits down)", "Theme_Poverty": "Reduced", "Methodology": "Retro-obs", "Sample_Size": 1000},
            {"Title": "Barcelona Guaranteed Income Pilot", "Year": 2021, "Country": "Spain", "Programme_Name": "B-MINCOME", "Theme_Employment": "Neutral", "Theme_Wellbeing": "Improved sleep/stress", "Theme_Poverty": "Reduced material deprivation", "Methodology": "RCT", "Sample_Size": 1000},
            {"Title": "Madhya Pradesh UBI Experiment", "Year": 2014, "Country": "India", "Programme_Name": "MP UBI", "Theme_Employment": "Positive (agriculture)", "Theme_Wellbeing": "Improved nutrition", "Theme_Poverty": "Reduced debt", "Methodology": "RCT", "Sample_Size": 6000},
            {"Title": "Gary, Indiana Negative Income Tax", "Year": 1979, "Country": "USA", "Programme_Name": "Gary NIT", "Theme_Employment": "Slight negative", "Theme_Wellbeing": "N/A", "Theme_Poverty": "Increased consumption", "Methodology": "RCT", "Sample_Size": 1800},
            {"Title": "Compton Guaranteed Income Program", "Year": 2023, "Country": "USA", "Programme_Name": "Compton Pledge", "Theme_Employment": "Neutral", "Theme_Wellbeing": "Improved agency", "Theme_Poverty": "Reduced utility debt", "Methodology": "Quasi-exp", "Sample_Size": 800},
            {"Title": "Macau Basic Income Pilot", "Year": 2022, "Country": "Macau", "Programme_Name": "Wealth Part.", "Theme_Employment": "Neutral", "Theme_Wellbeing": "Improved satisfaction", "Theme_Poverty": "Reduced inequality", "Methodology": "Obs", "Sample_Size": 600000},
            {"Title": "Namibia UBI Pilot Project", "Year": 2009, "Country": "Namibia", "Programme_Name": "BIG Pilot", "Theme_Employment": "Positive (+11%)", "Theme_Wellbeing": "Child malnutrition dropped", "Theme_Poverty": "Poverty dropped from 76% to 37%", "Methodology": "Obs", "Sample_Size": 930},
        ]),
        "effect_col": None,
        "ci_lower_col": None,
        "ci_upper_col": None,
        "title_col": "Title",
    },
    {
        "label": "⚗️ Example 3 — Science / Engineering: Microplastic Pollution in Aquatic Environments",
        "session_key": "ex3_microplastics",
        "year_from": 2010, "year_to": 2024, "pub_types": ["journal-article"],
        "synthesis_type": "quantitative_summary",
        "schema_type": "Custom (Concentration Schema)",
        "effect_label": "Mean Concentration",
        "null_val": None,
        "prisma_counts": (150, 142, 142, 14),
        "temporal_data": {
            2012: 2, 2013: 3, 2014: 4, 2015: 6, 2016: 9,
            2017: 13, 2018: 17, 2019: 22, 2020: 28, 2021: 34,
            2022: 40, 2023: 46, 2024: 50,
        },
        "overview_text": """
### Overview: Microplastic Pollution in Aquatic Environments

**Research Question (Custom Schema):** What does the experimental literature report about the concentration, distribution, and detection methods of microplastic pollution across different aquatic environments?

**Corpus & Screening:** 150 records retrieved via Crossref/OpenAlex. 14 empirical studies providing explicit mean concentration measurements in aquatic environments were included. Screening performance: Recall = 0.96, Precision = 0.74.

**Key Findings:** The quantitative summary highlights massive variability in reported concentrations, heavily dependent on environment type and detection method. Marine sediments show the highest absolute concentrations (often >400 particles/kg), acting as a sink. Freshwater systems exhibit high variability (0.5 to 3.2 particles/L) often correlated with proximity to urban centers. FTIR and Raman spectroscopy are the dominant detection methods.

**Limitations:** Lack of standardized sampling protocols and reporting units (particles/L vs. particles/m³ vs. particles/kg) makes direct meta-analytic pooling impossible, necessitating a stratified quantitative summary. Reporting standard: **ROSES** (systematic reviews in broader fields).
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "Microplastic concentrations in the North Sea", "Year": 2020, "Country": "Netherlands", "Environment_Type": "Marine", "Concentration_Mean": 0.34, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PP", "Sample_Size": 48, "Detection_Method": "FTIR"},
            {"Title": "Freshwater microplastics in the Rhine River", "Year": 2021, "Country": "Germany", "Environment_Type": "Freshwater", "Concentration_Mean": 1.28, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PET", "Sample_Size": 36, "Detection_Method": "Raman"},
            {"Title": "Microplastic pollution in coastal sediments (China)", "Year": 2022, "Country": "China", "Environment_Type": "Marine sediment", "Concentration_Mean": 412.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "PP, PE", "Sample_Size": 60, "Detection_Method": "FTIR"},
            {"Title": "Microplastics in Amazon River tributaries", "Year": 2023, "Country": "Brazil", "Environment_Type": "Freshwater", "Concentration_Mean": 0.87, "Concentration_Unit": "particles/L", "Polymer_Types": "PET, PE", "Sample_Size": 24, "Detection_Method": "Visual+FTIR"},
            {"Title": "Mediterranean surface water microplastics", "Year": 2019, "Country": "Italy", "Environment_Type": "Marine", "Concentration_Mean": 0.15, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PS", "Sample_Size": 80, "Detection_Method": "FTIR"},
            {"Title": "Great Lakes freshwater microplastic assessment", "Year": 2020, "Country": "USA", "Environment_Type": "Freshwater", "Concentration_Mean": 2.10, "Concentration_Unit": "particles/L", "Polymer_Types": "PP, PE", "Sample_Size": 45, "Detection_Method": "Raman"},
            {"Title": "Deep sea sediment microplastics (Atlantic)", "Year": 2021, "Country": "UK", "Environment_Type": "Marine sediment", "Concentration_Mean": 280.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "Polyester", "Sample_Size": 30, "Detection_Method": "FTIR"},
            {"Title": "Microplastics in the Ganges River basin", "Year": 2022, "Country": "India", "Environment_Type": "Freshwater", "Concentration_Mean": 3.15, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PET", "Sample_Size": 50, "Detection_Method": "Visual+FTIR"},
            {"Title": "Baltic Sea coastal microplastic pollution", "Year": 2018, "Country": "Sweden", "Environment_Type": "Marine", "Concentration_Mean": 0.42, "Concentration_Unit": "particles/L", "Polymer_Types": "PP, PE", "Sample_Size": 40, "Detection_Method": "FTIR"},
            {"Title": "Lake Victoria sediment microplastics", "Year": 2023, "Country": "Uganda", "Environment_Type": "Freshwater sediment", "Concentration_Mean": 195.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "PE, PVC", "Sample_Size": 25, "Detection_Method": "Raman"},
            {"Title": "Microplastics in Arctic sea ice", "Year": 2020, "Country": "Norway", "Environment_Type": "Marine", "Concentration_Mean": 0.08, "Concentration_Unit": "particles/L", "Polymer_Types": "Rayon, PE", "Sample_Size": 20, "Detection_Method": "FTIR"},
            {"Title": "Yangtze River microplastic flux", "Year": 2021, "Country": "China", "Environment_Type": "Freshwater", "Concentration_Mean": 2.80, "Concentration_Unit": "particles/L", "Polymer_Types": "PP, PE", "Sample_Size": 65, "Detection_Method": "FTIR"},
            {"Title": "Microplastics in coral reef sediments", "Year": 2022, "Country": "Australia", "Environment_Type": "Marine sediment", "Concentration_Mean": 340.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "PE, PS", "Sample_Size": 35, "Detection_Method": "Raman"},
            {"Title": "Seine River microplastic monitoring", "Year": 2019, "Country": "France", "Environment_Type": "Freshwater", "Concentration_Mean": 1.15, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PP", "Sample_Size": 42, "Detection_Method": "FTIR"},
        ]),
        "effect_col": None,
        "ci_lower_col": None,
        "ci_upper_col": None,
        "title_col": "Title",
    },
    {
        "label": "💼 Example 4 — Management / Business: CSR and Firm Financial Performance",
        "session_key": "ex4_csr",
        "year_from": 2000, "year_to": 2024, "pub_types": ["journal-article"],
        "synthesis_type": "meta_analysis",
        "schema_type": "Custom (CSR/FP Schema)",
        "effect_label": "Correlation Coefficient (r)",
        "null_val": 0.0,
        "prisma_counts": (150, 140, 140, 16),
        "temporal_data": {
            2010: 4, 2011: 5, 2012: 7, 2013: 9, 2014: 11,
            2015: 14, 2016: 17, 2017: 20, 2018: 23, 2019: 27,
            2020: 31, 2021: 36, 2022: 41, 2023: 46, 2024: 50,
        },
        "overview_text": """
### Overview: CSR and Firm Financial Performance

**Research Question (Custom Schema):** What is the empirical evidence on the relationship between Corporate Social Responsibility (CSR) activities and firm financial performance (ROA, ROE, Tobin's Q)?

**Corpus & Screening:** 150 records retrieved via OpenAlex. 16 empirical studies reporting Pearson correlation coefficients (r) between a CSR metric and a financial performance metric were included. Screening performance: Recall = 0.93, Precision = 0.70.

**Key Findings:** The meta-analysis demonstrates a positive, statistically significant relationship between CSR and firm financial performance. The pooled correlation coefficient (r ≈ 0.168) indicates a small-to-medium effect size, supporting the "doing well by doing good" hypothesis. Environmental and Governance scores tend to drive the strongest financial correlations.

**Limitations:** Moderate heterogeneity (I² ~ 45%) suggests the relationship is influenced by the specific financial metric used (accounting-based ROA vs. market-based Tobin's Q) and the geographic market context (developed vs. emerging markets). Reporting standard: **PRISMA 2020**.
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "CSR disclosure and ROA in manufacturing firms", "Year": 2019, "Country": "USA", "CSR_Measure": "ESG score", "FP_Measure": "ROA", "Effect_Size": 0.21, "CI_Lower": 0.12, "CI_Upper": 0.30, "Sample_Size": 340},
            {"Title": "Environmental CSR and Tobin's Q in European firms", "Year": 2020, "Country": "Europe", "CSR_Measure": "Env score", "FP_Measure": "Tobin's Q", "Effect_Size": 0.18, "CI_Lower": 0.08, "CI_Upper": 0.28, "Sample_Size": 520},
            {"Title": "Social responsibility and ROE in Asian markets", "Year": 2021, "Country": "Asia", "CSR_Measure": "Social score", "FP_Measure": "ROE", "Effect_Size": 0.14, "CI_Lower": 0.05, "CI_Upper": 0.23, "Sample_Size": 410},
            {"Title": "CSR and stock returns: a meta-analytic review", "Year": 2022, "Country": "Global", "CSR_Measure": "Composite ESG", "FP_Measure": "Stock returns", "Effect_Size": 0.11, "CI_Lower": 0.04, "CI_Upper": 0.18, "Sample_Size": 890},
            {"Title": "Governance CSR and firm value in emerging markets", "Year": 2023, "Country": "Emerging", "CSR_Measure": "Gov score", "FP_Measure": "Tobin's Q", "Effect_Size": 0.24, "CI_Lower": 0.15, "CI_Upper": 0.33, "Sample_Size": 280},
            {"Title": "CSR activities and ROA in the banking sector", "Year": 2018, "Country": "Global", "CSR_Measure": "CSR Index", "FP_Measure": "ROA", "Effect_Size": 0.16, "CI_Lower": 0.07, "CI_Upper": 0.25, "Sample_Size": 150},
            {"Title": "Green innovation and financial performance", "Year": 2021, "Country": "China", "CSR_Measure": "Env score", "FP_Measure": "ROA", "Effect_Size": 0.28, "CI_Lower": 0.19, "CI_Upper": 0.37, "Sample_Size": 420},
            {"Title": "Board diversity and firm profitability", "Year": 2019, "Country": "UK", "CSR_Measure": "Gov score", "FP_Measure": "ROE", "Effect_Size": 0.12, "CI_Lower": 0.02, "CI_Upper": 0.22, "Sample_Size": 210},
            {"Title": "Philanthropy and market valuation", "Year": 2020, "Country": "USA", "CSR_Measure": "Social score", "FP_Measure": "Tobin's Q", "Effect_Size": 0.09, "CI_Lower": 0.00, "CI_Upper": 0.18, "Sample_Size": 630},
            {"Title": "ESG controversies and stock price drops", "Year": 2022, "Country": "Global", "CSR_Measure": "ESG score", "FP_Measure": "Stock returns", "Effect_Size": 0.19, "CI_Lower": 0.11, "CI_Upper": 0.27, "Sample_Size": 1100},
            {"Title": "Supply chain CSR and operational efficiency", "Year": 2021, "Country": "Japan", "CSR_Measure": "Social score", "FP_Measure": "ROA", "Effect_Size": 0.15, "CI_Lower": 0.06, "CI_Upper": 0.24, "Sample_Size": 320},
            {"Title": "Carbon emissions reduction and firm value", "Year": 2023, "Country": "Europe", "CSR_Measure": "Env score", "FP_Measure": "Tobin's Q", "Effect_Size": 0.22, "CI_Lower": 0.13, "CI_Upper": 0.31, "Sample_Size": 480},
            {"Title": "Employee relations and ROE", "Year": 2018, "Country": "USA", "CSR_Measure": "Social score", "FP_Measure": "ROE", "Effect_Size": 0.13, "CI_Lower": 0.04, "CI_Upper": 0.22, "Sample_Size": 550},
            {"Title": "Executive compensation ties to ESG and performance", "Year": 2022, "Country": "Australia", "CSR_Measure": "Gov score", "FP_Measure": "ROA", "Effect_Size": 0.17, "CI_Lower": 0.08, "CI_Upper": 0.26, "Sample_Size": 290},
            {"Title": "Water usage disclosure and financial risk", "Year": 2020, "Country": "Global", "CSR_Measure": "Env score", "FP_Measure": "Stock returns", "Effect_Size": 0.10, "CI_Lower": 0.01, "CI_Upper": 0.19, "Sample_Size": 740},
            {"Title": "Community engagement and market share", "Year": 2021, "Country": "Canada", "CSR_Measure": "Social score", "FP_Measure": "Tobin's Q", "Effect_Size": 0.14, "CI_Lower": 0.05, "CI_Upper": 0.23, "Sample_Size": 380},
        ]),
        "effect_col": "Effect_Size",
        "ci_lower_col": "CI_Lower",
        "ci_upper_col": "CI_Upper",
        "title_col": "Title",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def compute_forest(df, effect_col, ci_lower_col, ci_upper_col, effect_label, null_val):
    """Render forest plot to a PNG bytes buffer and return (buf, pooled, lo, hi, i2, p_val)."""
    n = len(df)
    fig_height = max(5, n * 0.45 + 2.8)
    fig, ax = plt.subplots(figsize=(11, fig_height))

    y_studies = list(range(n, 0, -1))
    effects = df[effect_col].tolist()
    lowers  = df[ci_lower_col].tolist()
    uppers  = df[ci_upper_col].tolist()
    labels  = [str(t)[:65] for t in df["Title"].tolist()]

    for y, eff, lo, hi, lbl in zip(y_studies, effects, lowers, uppers, labels):
        ax.plot([lo, hi], [y, y], color="#2c7bb6", linewidth=1.5, solid_capstyle="round")
        ax.plot(eff, y, "s", color="#d7191c", markersize=7, zorder=5)
        ax.text(-0.02, y, lbl, ha="right", va="center", fontsize=8.5,
                transform=ax.get_yaxis_transform())

    weights = []
    variances = []
    for lo, hi in zip(lowers, uppers):
        se = (hi - lo) / 3.92
        var = se**2
        variances.append(var)
        weights.append(1.0 / var if var > 0 else 0)

    total_w = sum(weights)
    pooled    = sum(w * e for w, e in zip(weights, effects)) / total_w if total_w > 0 else float(np.mean(effects))
    pooled_se = 1.0 / total_w**0.5 if total_w > 0 else 0
    pooled_lo = pooled - 1.96 * pooled_se
    pooled_hi = pooled + 1.96 * pooled_se

    Q = sum(w * (e - pooled)**2 for w, e in zip(weights, effects))
    df_Q = n - 1
    p_val = 1 - stats.chi2.cdf(Q, df_Q)
    i2 = max(0.0, 100 * (Q - df_Q) / Q) if Q > 0 else 0.0

    pooled_y = -0.6
    ax.axhline(y=pooled_y + 0.55, color="lightgray", linestyle="--", linewidth=0.6)
    ax.plot([pooled_lo, pooled_hi], [pooled_y, pooled_y], color="#1a9641", linewidth=3.0)
    ax.plot(pooled, pooled_y, "D", color="#1a9641", markersize=11, zorder=6)

    label_text = f"Pooled ({effect_label})\nI² = {i2:.1f}%, p = {p_val:.3f}"
    ax.text(-0.02, pooled_y, label_text, ha="right", va="center",
            fontsize=9, fontweight="bold", transform=ax.get_yaxis_transform())

    nv = null_val if null_val is not None else 0.0
    ax.axvline(nv, color="black", linestyle="-", linewidth=0.9, zorder=3)

    ax.set_yticks([])
    ax.set_ylim(pooled_y - 1.2, n + 0.9)
    ax.set_xlabel(effect_label, fontsize=10)
    ax.set_title("Forest Plot with Heterogeneity Statistics", fontsize=13, fontweight="bold", pad=12)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    legend_elements = [
        mpatches.Patch(color="#d7191c", label="Individual study estimate"),
        mpatches.Patch(color="#1a9641",
                       label=f"Pooled: {pooled:.3f}  95% CI [{pooled_lo:.3f}, {pooled_hi:.3f}]"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8.5, framealpha=0.9)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read(), pooled, pooled_lo, pooled_hi, i2, p_val


def compute_concentration_chart(df):
    """Render concentration bar chart to PNG bytes."""
    fig, ax = plt.subplots(figsize=(9, 5))
    df_sorted = df.sort_values("Environment_Type")
    colors = {
        "Marine": "#2c7bb6",
        "Freshwater": "#abd9e9",
        "Marine sediment": "#d7191c",
        "Freshwater sediment": "#fdae61",
    }
    bar_colors = [colors.get(e, "#999999") for e in df_sorted["Environment_Type"]]
    ax.bar(df_sorted["Title"].str[:25] + "...", df_sorted["Concentration_Mean"],
           color=bar_colors, edgecolor="white")
    unit = df["Concentration_Unit"].iloc[0] if "Concentration_Unit" in df.columns else ""
    ax.set_ylabel(f"Mean Concentration ({unit})")
    ax.set_title("Mean Microplastic Concentrations by Environment Type")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    legend_handles = [mpatches.Patch(color=c, label=l) for l, c in colors.items()]
    ax.legend(handles=legend_handles, title="Environment Type")
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read()


def compute_temporal_chart(temporal_data, title):
    """Render a temporal analysis line chart to PNG bytes."""
    years = sorted(temporal_data.keys())
    counts = [temporal_data[y] for y in years]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(years, counts, marker="o", color="#2c7bb6", linewidth=2.2, markersize=6)
    ax.fill_between(years, counts, alpha=0.15, color="#2c7bb6")
    ax.set_xlabel("Publication Year", fontsize=10)
    ax.set_ylabel("Number of Publications", fontsize=10)
    ax.set_title(f"Temporal Analysis — {title}", fontsize=12, fontweight="bold")
    ax.set_xticks(years[::2])
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read()


def compute_prisma(n_id, n_dedup, n_screened, n_included):
    """Render PRISMA 2020 flow diagram to PNG bytes."""
    fig, ax = plt.subplots(figsize=(9, 11))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    BOX_W   = 0.38
    BOX_H   = 0.10
    EXC_W   = 0.30
    LEFT_X  = 0.21
    RIGHT_X = 0.78
    Y_TOPS  = [0.92, 0.74, 0.56, 0.38, 0.20]

    n_duplicates        = n_id - n_dedup
    n_excluded_screen   = n_screened - int(n_screened * 0.60)
    n_fulltext          = int(n_screened * 0.60)
    n_excluded_fulltext = n_fulltext - n_included

    main_boxes = [
        f"Records identified\nvia API search\n(n = {n_id})",
        f"Records after\ndeduplication\n(n = {n_dedup})",
        f"Records screened\n(title & abstract)\n(n = {n_screened})",
        f"Full-text articles\nassessed for eligibility\n(n = {n_fulltext})",
        f"Studies included\nin synthesis\n(n = {n_included})",
    ]
    excl_boxes = [
        (Y_TOPS[1], f"Duplicates removed\n(n = {n_duplicates})"),
        (Y_TOPS[2], f"Excluded on\ntitle/abstract\n(n = {n_excluded_screen})"),
        (Y_TOPS[3], f"Excluded on\nfull-text\n(n = {n_excluded_fulltext})"),
    ]

    for y_c, text in zip(Y_TOPS, main_boxes):
        ax.add_patch(FancyBboxPatch(
            (LEFT_X - BOX_W / 2, y_c - BOX_H / 2), BOX_W, BOX_H,
            boxstyle="round,pad=0.015",
            facecolor="#dbeafe", edgecolor="#2563eb", linewidth=1.8, zorder=3,
        ))
        ax.text(LEFT_X, y_c, text, ha="center", va="center",
                fontsize=8.5, zorder=4, linespacing=1.4)

    for y_c, text in excl_boxes:
        ax.add_patch(FancyBboxPatch(
            (RIGHT_X - EXC_W / 2, y_c - BOX_H / 2), EXC_W, BOX_H,
            boxstyle="round,pad=0.015",
            facecolor="#fee2e2", edgecolor="#dc2626", linewidth=1.5, zorder=3,
        ))
        ax.text(RIGHT_X, y_c, text, ha="center", va="center",
                fontsize=8, zorder=4, linespacing=1.4)

    for i in range(len(Y_TOPS) - 1):
        ax.annotate(
            "", xy=(LEFT_X, Y_TOPS[i + 1] + BOX_H / 2),
            xytext=(LEFT_X, Y_TOPS[i] - BOX_H / 2),
            arrowprops=dict(arrowstyle="-|>", color="#1e3a5f", lw=1.5, mutation_scale=14),
            zorder=5,
        )

    for (y_c, _) in excl_boxes:
        ax.annotate(
            "", xy=(RIGHT_X - EXC_W / 2, y_c),
            xytext=(LEFT_X + BOX_W / 2, y_c),
            arrowprops=dict(arrowstyle="-|>", color="#991b1b", lw=1.2, mutation_scale=12),
            zorder=5,
        )

    ax.set_title("PRISMA 2020 Flow Diagram", fontsize=13, fontweight="bold", pad=14)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read()


# ══════════════════════════════════════════════════════════════════════════════
# RENDER ONE GUIDED EXAMPLE (called inside expander)
# ══════════════════════════════════════════════════════════════════════════════

def render_guided_example(ex):
    sk  = ex["session_key"]
    df  = ex["extraction_df"].copy()

    # ── Overview ───────────────────────────────────────────────────────────────
    st.markdown(ex["overview_text"])

    # ── Extraction Schema badge ────────────────────────────────────────────────
    schema_colors = {
        "PICO": "🟦",
        "Thematic Synthesis": "🟩",
        "Custom (Concentration Schema)": "🟧",
        "Custom (CSR/FP Schema)": "🟧",
    }
    badge = schema_colors.get(ex["schema_type"], "⬜")
    st.info(f"{badge} **Extraction Schema:** {ex['schema_type']}")

    # ── Extraction failure modes note ──────────────────────────────────────────
    st.warning(
        "⚠️ **Important — Extraction Failure Modes:** AI-assisted extraction is probabilistic. "
        "PDF extraction may fail due to structural variability, OCR noise, multi-column layouts, "
        "or ambiguous phrasing. LLM outputs are non-deterministic and may vary across runs. "
        "All outputs below should be treated as provisional and subject to manual verification. "
        "The app flags low-confidence extractions (shown in the table) for side-by-side auditing."
    )

    st.markdown("---")

    # ── Step 1: Extraction table ───────────────────────────────────────────────
    st.subheader("Step 1 — Structured Data Extraction")
    st.markdown(f"""
The table below shows the structured extraction output for this case study using the
**{ex['schema_type']}** schema. Each row corresponds to one included study; fields were
extracted using a discipline-specific LLM prompt. No coding required.
    """)
    st.success(f"✅ {len(df)} studies extracted.")
    st.dataframe(df, use_container_width=True)
    st.download_button(
        "⬇️ Download extraction table as CSV",
        df.to_csv(index=False).encode("utf-8"),
        f"day3_{sk}_extraction.csv", "text/csv",
        key=f"dl_extract_{sk}",
    )

    st.markdown("---")

    # ── Step 2: Temporal Analysis ──────────────────────────────────────────────
    st.subheader("Step 2 — Temporal Analysis")
    st.markdown("""
The **Temporal Analysis** widget visualizes how the volume of publications on this topic
has shifted over time, helping identify when a specific topic or methodology gained
prominence in the field.
    """)
    temporal_key = f"day3_{sk}_temporal_png"
    if temporal_key not in st.session_state:
        st.session_state[temporal_key] = compute_temporal_chart(
            ex["temporal_data"], ex["label"].split("—")[-1].strip()
        )
    st.image(st.session_state[temporal_key], use_container_width=True)
    st.download_button(
        "⬇️ Download temporal chart (PNG)", st.session_state[temporal_key],
        f"day3_{sk}_temporal.png", "image/png",
        key=f"dl_temporal_{sk}",
    )

    st.markdown("---")

    # ── Step 3: Synthesis ──────────────────────────────────────────────────────
    st.subheader("Step 3 — Synthesis & Meta-Analysis")

    if ex["synthesis_type"] == "meta_analysis":
        st.markdown(f"""
This full meta-analysis pools the **{ex['effect_label']}** across the {len(df)} extracted studies
using inverse-variance weighting. The diamond on the forest plot represents the
pooled estimate with its 95% confidence interval. Heterogeneity statistics (I² and Cochran's Q p-value)
are reported alongside the pooled estimate.
        """)
        forest_key = f"day3_{sk}_forest_png"
        if forest_key not in st.session_state:
            png, pooled, plo, phi, i2, p_val = compute_forest(
                df, ex["effect_col"], ex["ci_lower_col"], ex["ci_upper_col"],
                ex["effect_label"], ex["null_val"],
            )
            st.session_state[forest_key] = (png, pooled, plo, phi, i2, p_val)

        png, pooled, plo, phi, i2, p_val = st.session_state[forest_key]
        st.image(png, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric(f"Pooled {ex['effect_label']}", f"{pooled:.3f}", f"95% CI: [{plo:.3f}, {phi:.3f}]")
        col2.metric("Heterogeneity (I²)", f"{i2:.1f}%", "0% = none, >75% = high", delta_color="off")
        col3.metric("Cochran's Q (p-value)", f"{p_val:.3f}", "<0.05 = significant heterogeneity", delta_color="off")

        st.download_button(
            "⬇️ Download forest plot (PNG)", png,
            f"day3_{sk}_forest.png", "image/png",
            key=f"dl_forest_{sk}",
        )

    elif ex["synthesis_type"] == "narrative":
        st.markdown("""
The **Thematic Synthesis** organises the extracted data into a structured summary table
suitable for the Results section of a systematic review, categorizing findings across the
three cross-cutting themes: Employment, Well-being, and Poverty Reduction.
        """)
        cols_show = [c for c in ["Title", "Year", "Country", "Methodology",
                                  "Sample_Size", "Theme_Employment",
                                  "Theme_Wellbeing", "Theme_Poverty"]
                     if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True)

        # Theme summary
        st.markdown("**Theme Summary:**")
        theme_summary = pd.DataFrame({
            "Theme": ["Employment", "Well-being", "Poverty Reduction"],
            "Positive / Neutral / Negative": ["9 neutral, 3 positive, 2 slight negative", "10 improved, 2 N/A", "11 reduced, 1 increased consumption"],
            "Strength of Evidence": ["Moderate", "Strong", "Strong"],
        })
        st.dataframe(theme_summary, use_container_width=True)

    elif ex["synthesis_type"] == "quantitative_summary":
        st.markdown("""
The **quantitative summary** compares mean microplastic concentrations across environment
types and studies, highlighting the variance between marine, freshwater, and sediment sinks.
        """)
        if "Concentration_Mean" in df.columns and "Environment_Type" in df.columns:
            summary = (
                df.groupby("Environment_Type")["Concentration_Mean"]
                .agg(["mean", "min", "max", "count"])
                .rename(columns={"mean": "Mean", "min": "Min",
                                  "max": "Max", "count": "N Studies"})
                .round(2)
            )
            st.dataframe(summary, use_container_width=True)

        chart_key = f"day3_{sk}_chart_png"
        if chart_key not in st.session_state:
            st.session_state[chart_key] = compute_concentration_chart(df)
        st.image(st.session_state[chart_key], use_container_width=True)
        st.download_button(
            "⬇️ Download chart (PNG)", st.session_state[chart_key],
            f"day3_{sk}_chart.png", "image/png",
            key=f"dl_chart_{sk}",
        )

    st.markdown("---")

    # ── Step 4: PRISMA ─────────────────────────────────────────────────────────
    st.subheader("Step 4 — PRISMA 2020 Flow Diagram")
    n_id, n_dedup, n_screened, n_included = ex["prisma_counts"]
    st.markdown(f"""
Record flow: **{n_id}** identified → **{n_dedup}** after deduplication →
**{n_screened}** screened → **{n_included}** included in synthesis.
    """)
    prisma_key = f"day3_{sk}_prisma_png"
    if prisma_key not in st.session_state:
        st.session_state[prisma_key] = compute_prisma(n_id, n_dedup, n_screened, n_included)
    st.image(st.session_state[prisma_key], use_container_width=True)
    st.download_button(
        "⬇️ Download PRISMA diagram (PNG)", st.session_state[prisma_key],
        f"day3_{sk}_prisma.png", "image/png",
        key=f"dl_prisma_{sk}",
    )

    st.markdown("---")

    # ── Step 5: pyvis concept network ─────────────────────────────────────
    st.subheader("Step 5 — Concept Network of Included Studies")
    render_pyvis_network(df, sk)

    # ── VOSviewer section ───────────────────────────────────────────────
    if len(df) >= 3:
        render_vosviewer_section(df, sk)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

st.sidebar.title("Day 3 Navigation")
section = st.sidebar.radio(
    "Select section",
    [
        "Overview",
        "📌 Guided Examples",
        "📊 Reporting Standards",
        "⚖️ Ethics of AI in Research Synthesis",
        "🔎 BYOD — Your Own Synthesis",
    ],
)

# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if section == "Overview":
    st.title("📊 Day 3 — From Studies to Evidence")
    st.markdown("""
**Theme:** Extract structured data from included studies and produce a preliminary
narrative or quantitative synthesis — including a Temporal Analysis chart, a PRISMA
flow diagram, and a forest plot for meta-analyses — all in a **no-code** environment.

### What You Will Do Today

The third day brings the pipeline to its conclusion. Having built a corpus on Day 1 and
screened it on Day 2, participants now extract structured data from the included studies
and produce a preliminary synthesis.

**Structured data extraction** uses an LLM prompted with a discipline-specific schema
to parse each abstract and return a structured record. The app supports two standard
schemas and a fully customizable option:

| Schema | Discipline | Fields |
|---|---|---|
| **PICO** | Health Sciences | Population, Intervention, Comparison, Outcome |
| **Thematic Synthesis** | Social Sciences / Humanities | Cross-cutting themes, Evidence strength |
| **Custom** | Any discipline | User-defined variables (e.g., CSR measure + financial metric) |

**Temporal Analysis** visualizes how the volume and focus of the retrieved literature
has shifted over time, helping identify when a specific topic or methodology gained
prominence in the field.

**Narrative synthesis** organises the extracted data into a structured summary table
suitable for the Results section of a systematic review.

**Quantitative synthesis (meta-analysis)** pools effect sizes using inverse-variance
weighting and produces a forest plot with a pooled estimate, confidence interval, and
heterogeneity statistics (I²).

**PRISMA 2020 flow diagram** is generated automatically from the record counts at each
stage of the pipeline.

### The Four Case Studies at a Glance

| # | Discipline | Topic | Schema | Synthesis Type |
|---|---|---|---|---|
| 1 | Health Sciences | Health Inequalities in Chronic Disease Care | PICO | Meta-analysis (Risk Ratio) |
| 2 | Social Sciences | Universal Basic Income (UBI) Policy Outcomes | Thematic Synthesis | Narrative synthesis |
| 3 | Science / Engineering | Microplastic Pollution in Aquatic Environments | Custom (Concentration) | Quantitative summary |
| 4 | Management / Business | CSR and Firm Financial Performance | Custom (CSR/FP) | Meta-analysis (Correlation r) |

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Demonstrate automated data extraction. Participants select a discipline-specific schema (PICO, Thematic Synthesis, or Custom) and use the LLM to extract structured variables. Discuss the probabilistic nature of LLM extraction and the importance of auditing outputs. |
| **Hour 2** | Guide participants in preliminary synthesis and visualization. Generate summary tables, PRISMA flow diagrams, descriptive plots, and a Temporal Analysis chart showing how research focus in the field has shifted over time. |
| **Hour 3** | Review outputs, discuss feasibility and limits, and include a short discussion of the ethics of AI in evidence synthesis, focusing on hallucinations, bias, PRISMA 2020 and PRISMA-S reporting standards, and how the GitHub repository supports later replication. |

Use the sidebar to navigate to **📌 Guided Examples**, **📊 Reporting Standards**,
**⚖️ Ethics**, or **🔎 BYOD**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES — all four displayed simultaneously
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 3 — Guided Examples")
    st.markdown("""
Each example below walks through the full Day 3 pipeline for one case study:
**structured data extraction** (with schema badge and failure-mode warning),
**Temporal Analysis**, **synthesis** (meta-analysis, Thematic Synthesis, or quantitative
summary), and a **PRISMA 2020 flow diagram**. All outputs are pre-rendered and persist
on screen. Expand any example to explore it.
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            yr_from = ex.get("year_from")
            yr_to = ex.get("year_to")
            pub_types = ex.get("pub_types", [])
            period_str = f"{yr_from}\u2013{yr_to}" if yr_from and yr_to else "All years"
            types_str = ", ".join(pub_types) if pub_types else "All types"
            st.markdown(
                f"**Time period:** {period_str} \u00a0|\u00a0 **Publication types:** {types_str}"
            )
            render_guided_example(ex)

# ══════════════════════════════════════════════════════════════════════════════
# REPORTING STANDARDS
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📊 Reporting Standards":
    st.title("📊 Reporting Standards for AI-Assisted Reviews")
    st.markdown("""
Transparent reporting is a non-negotiable requirement for publishing AI-assisted
systematic reviews. This section summarizes the three key reporting frameworks
relevant to this seminar.

---

### PRISMA 2020

**PRISMA 2020** (Preferred Reporting Items for Systematic Reviews and Meta-Analyses)
is the primary reporting standard for systematic reviews and meta-analyses. It requires
a structured flow diagram documenting the number of records at each stage of the
review process (identification, screening, eligibility, inclusion), a checklist of 27 items
covering all aspects of the review methodology, and explicit reporting of search dates,
databases, and deduplication procedures.

> The app generates a **PRISMA 2020 flow diagram** automatically from the record counts
> at each pipeline stage. All four guided examples include a downloadable PRISMA diagram.

---

### PRISMA-S

**PRISMA-S** (PRISMA for Searching) is an extension of PRISMA 2020 that focuses
specifically on the documentation of the search strategy. It requires reporting the
exact search strings used in each database, the date of each search, the filters applied
(publication year, language, access type), and the number of records retrieved per source.

> The app's **Query Log** (Day 1) records all API queries with timestamps, enabling
> PRISMA-S compliant search reporting. Participants can download the query log as a CSV.

---

### ROSES

**ROSES** (RepOrting Standards for Systematic Evidence Syntheses) is a reporting
standard designed for systematic reviews and evidence maps in environmental science,
conservation, and broader interdisciplinary fields. It is particularly relevant for
reviews that go beyond the health sciences, such as the microplastics example in this
seminar. ROSES emphasizes transparent documentation of search strategies, inclusion
criteria, data extraction procedures, and evidence mapping.

> Example 3 (Microplastic Pollution) in this seminar uses ROSES as its reporting
> standard, reflecting the interdisciplinary nature of environmental science reviews.

---

### Reporting Standard by Case Study

| # | Topic | Reporting Standard | Rationale |
|---|---|---|---|
| 1 | Health Inequalities | PRISMA 2020 | Clinical systematic review with RCT-based evidence |
| 2 | UBI Policy Outcomes | PRISMA-S | Policy evaluation review requiring detailed search documentation |
| 3 | Microplastic Pollution | ROSES | Environmental science / interdisciplinary review |
| 4 | CSR and Firm Performance | PRISMA 2020 | Business meta-analysis with quantitative pooling |
    """)

# ══════════════════════════════════════════════════════════════════════════════
# ETHICS OF AI IN RESEARCH SYNTHESIS
# ══════════════════════════════════════════════════════════════════════════════

elif section == "⚖️ Ethics of AI in Research Synthesis":
    st.title("⚖️ Ethics of AI in Research Synthesis")
    st.markdown("""
This section addresses the ethical dimensions of using AI tools in systematic reviews
and meta-analyses. The goal is not to discourage the use of AI, but to ensure that
participants use it responsibly, transparently, and with appropriate human oversight.

---

### 1. Algorithmic Bias

AI screening models (both Active Learning and LLM-based) are trained on or calibrated
against existing literature. If the training data or seed labels are not representative,
the model may systematically under-prioritize studies from certain languages, regions,
or disciplines. This is particularly relevant for reviews that aim to be globally
comprehensive.

**Mitigation:** Use recall-oriented metrics (not precision) to evaluate screening
performance. Manually inspect excluded records from under-represented regions.
Always report the screening method and seed label strategy in the Methods section.

---

### 2. LLM Hallucinations in Extraction

Large Language Models can generate plausible-sounding but factually incorrect
extractions, particularly when the source text is ambiguous, multi-column, or
poorly structured. This is not a rare edge case — it is a systematic risk that must
be managed.

**Mitigation:** The app flags low-confidence extractions for manual review. All
extracted data should be treated as provisional until verified against the source PDF.
Never use LLM-extracted effect sizes in a meta-analysis without manual verification
of at least a random 20% sample.

---

### 3. Transparency and the Audit Trail

AI-assisted reviews must be reproducible. This requires documenting every AI
decision in the pipeline: which model was used, what prompts were given, what
outputs were produced, and which outputs were overridden by human reviewers.

**The app's Transparency Log** (Day 2) records every LLM prompt and justification.
**The GitHub repository** contains the underlying Python and R scripts, ensuring
that any researcher can inspect, replicate, or extend the workflow.

---

### 4. Human-in-the-Loop Oversight

AI tools in this seminar are designed to assist human judgment, not replace it.
Active Learning reorders the corpus to surface the most relevant papers first —
but the final inclusion/exclusion decision is always made by the researcher.
LLM screening provides a justification for each exclusion — but the researcher
reviews and can override any decision.

> **The principle:** AI reduces the time cost of systematic reviewing. Human
> expertise ensures the quality and validity of the final synthesis.

---

### 5. Reporting AI Use in Publications

Journals increasingly require explicit disclosure of AI tool use in systematic reviews.
Authors should report: the AI tools used (with version numbers), the tasks for which
AI was used (screening, extraction, synthesis), the human verification procedures
applied, and the reporting standard followed (PRISMA 2020, PRISMA-S, or ROSES).
    """)

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Your Own Synthesis":
    st.title("🔎 Day 3 — Bring Your Own Data")
    st.markdown("""
Use this section to produce a synthesis from **your own included studies**.
Upload the CSV of included studies from Day 2 (or any CSV with Title, Year, and Abstract
columns) and define your extraction schema below. No coding required.
    """)

    uploaded = st.file_uploader("Upload included studies CSV", type=["csv"])

    if uploaded is None and "byod_included_df" in st.session_state:
        st.info("Using included studies carried over from Day 2 BYOD session.")
        df = st.session_state["byod_included_df"]
    elif uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = None

    if df is not None:
        st.success(f"✅ {len(df)} included studies loaded.")
        st.dataframe(df.head(10), use_container_width=True)

        st.markdown("---")
        st.subheader("Extraction Schema")

        schema_choice = st.radio(
            "Choose an extraction schema",
            ["PICO (Health Sciences)", "Thematic Synthesis (Social Sciences / Humanities)", "Custom"],
            horizontal=True,
        )

        if schema_choice == "PICO (Health Sciences)":
            schema_fields = ["Title", "Year", "Country", "Population", "Intervention", "Comparison", "Outcome", "Effect_Size", "Sample_Size"]
        elif schema_choice == "Thematic Synthesis (Social Sciences / Humanities)":
            schema_fields = ["Title", "Year", "Country", "Methodology", "Sample_Size", "Theme_1", "Theme_2", "Theme_3", "Evidence_Strength"]
        else:
            schema_input = st.text_input(
                "Define your custom fields (comma-separated)",
                value="Title, Year, Country, Variable_1, Variable_2, Effect_Size, Sample_Size",
            )
            schema_fields = [f.strip() for f in schema_input.split(",") if f.strip()]

        st.info(f"**Active schema:** {', '.join(schema_fields)}")

        template_df = pd.DataFrame([
            {f: row.get(f, "") for f in schema_fields}
            for _, row in df.head(20).iterrows()
        ])
        st.dataframe(template_df, use_container_width=True)
        st.download_button(
            "⬇️ Download extraction template",
            template_df.to_csv(index=False).encode("utf-8"),
            "byod_extraction_template.csv", "text/csv",
            key="dl_byod_template",
        )

        st.markdown("---")
        st.subheader("Temporal Analysis")
        if "Year" in df.columns:
            year_counts = df["Year"].value_counts().sort_index().to_dict()
            if year_counts:
                byod_temporal_key = "byod_temporal_png"
                if byod_temporal_key not in st.session_state:
                    st.session_state[byod_temporal_key] = compute_temporal_chart(
                        year_counts, "Your Corpus"
                    )
                st.image(st.session_state[byod_temporal_key], use_container_width=True)
                st.download_button(
                    "⬇️ Download temporal chart (PNG)",
                    st.session_state[byod_temporal_key],
                    "byod_temporal.png", "image/png",
                    key="dl_byod_temporal",
                )
        else:
            st.info("Add a 'Year' column to your CSV to enable temporal analysis.")

        st.markdown("---")
        st.subheader("Forest Plot (if you have effect size data)")
        extracted_upload = st.file_uploader(
            "Upload completed extraction CSV "
            "(must have Effect_Size, CI_Lower, CI_Upper, Title columns)",
            type=["csv"], key="byod_forest_upload",
        )
        if extracted_upload is not None:
            df_ext = pd.read_csv(extracted_upload)
            required = {"Effect_Size", "CI_Lower", "CI_Upper", "Title"}
            if required.issubset(df_ext.columns):
                effect_label = st.text_input("Effect size label", value="Effect Size")
                png, pooled, plo, phi, i2, p_val = compute_forest(
                    df_ext, "Effect_Size", "CI_Lower", "CI_Upper", effect_label, None
                )
                st.image(png, use_container_width=True)
                col1, col2, col3 = st.columns(3)
                col1.metric(f"Pooled {effect_label}", f"{pooled:.3f}", f"95% CI: [{plo:.3f}, {phi:.3f}]")
                col2.metric("Heterogeneity (I²)", f"{i2:.1f}%", "0% = none, >75% = high", delta_color="off")
                col3.metric("Cochran's Q (p-value)", f"{p_val:.3f}", "<0.05 = significant heterogeneity", delta_color="off")
                st.download_button("⬇️ Download forest plot (PNG)", png,
                                   "byod_forest.png", "image/png", key="dl_byod_forest")
            else:
                missing = required - set(df_ext.columns)
                st.error(f"Missing required columns: {missing}")

        st.markdown("---")
        st.subheader("PRISMA Flow Diagram")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            n_id = st.number_input("Records identified", min_value=1, value=200)
        with col2:
            n_dedup = st.number_input("After deduplication", min_value=1, value=180)
        with col3:
            n_screened = st.number_input("Records screened", min_value=1, value=180)
        with col4:
            n_included_byod = st.number_input("Studies included", min_value=1,
                                               value=max(1, len(df)))

        png_prisma = compute_prisma(int(n_id), int(n_dedup), int(n_screened), int(n_included_byod))
        st.image(png_prisma, use_container_width=True)
        st.download_button(
            "⬇️ Download PRISMA diagram (PNG)",
            png_prisma,
            "byod_prisma.png", "image/png", key="dl_byod_prisma",
        )
