"""
Day 1 — From Query to Corpus
Five guided examples (Health, Social Science, Engineering, Business, Zotero) + BYOD extension.
Guided examples load exclusively from pre-cached CSVs — no live API calls required.
All outputs render immediately when the expander is opened — no button click needed.
No coding required.

APIs covered: OpenAlex, Crossref, Semantic Scholar, Europe PMC
BYOD inputs: Boolean query (4 APIs), RIS/BibTeX file upload, Zotero connection
Outputs: CSV download, RIS export, Query Log, VOSviewer bibliometric network link,
         pyvis interactive keyword co-occurrence network
"""

import io
import os
import re
import json
import time
import pathlib
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
CACHE_DIR = _repo_root / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Guided example definitions ─────────────────────────────────────────────────
GUIDED_EXAMPLES = [
    {
        "label": "🏥 Example 1 — Health Sciences: Health Inequalities in Chronic Disease Care",
        "cache_file": "day1_ex1_health_corpus.csv",
        "session_key": "ex1_health",
        "source": "OpenAlex",
        "query": "health inequalities diabetes care socioeconomic",
        "year_from": 2000,
        "year_to": 2024,
        "pub_types": ["journal-article"],
        "description": """
**Research question:** What does the empirical literature say about socioeconomic health
inequalities in the care and outcomes of patients with chronic diseases such as diabetes,
hypertension, and cardiovascular disease?

**Search strategy:** Boolean combination of *health inequalities*, *socioeconomic* factors,
and *diabetes care* — a standard PICO-informed search on OpenAlex.

**Why this topic?** One of the most active areas of systematic review in health sciences.
The corpus supports a full PICO extraction and meta-analysis on Day 3.
        """,
    },
    {
        "label": "🏛️ Example 2 — Social Sciences: Universal Basic Income (UBI) Policy Outcomes",
        "cache_file": "day1_ex2_ubi_corpus.csv",
        "session_key": "ex2_ubi",
        "source": "OpenAlex",
        "query": "universal basic income policy evaluation employment outcomes",
        "year_from": 2010,
        "year_to": 2024,
        "pub_types": ["journal-article", "book-chapter"],
        "description": """
**Research question:** What are the empirically measured outcomes of Universal Basic Income
(UBI) programmes and pilots in terms of employment, poverty, and well-being?

**Search strategy:** Targets empirical policy evaluations of UBI, excluding opinion pieces,
editorials, and grey literature.

**Why this topic?** UBI is one of the most actively debated policy interventions in the
social sciences, spanning economics, sociology, and political science.
        """,
    },
    {
        "label": "⚗️ Example 3 — Science / Engineering: Microplastic Pollution in Aquatic Environments",
        "cache_file": "day1_ex3_microplastics_corpus.csv",
        "session_key": "ex3_microplastics",
        "source": "OpenAlex",
        "query": "microplastics aquatic marine pollution concentration",
        "year_from": 2010,
        "year_to": 2024,
        "pub_types": ["journal-article"],
        "description": """
**Research question:** What does the experimental literature report about the concentration,
distribution, and ecological impact of microplastic pollution in aquatic environments?

**Search strategy:** Combines *microplastics* with *aquatic* or *marine* environments,
targeting experimental and observational studies.

**Why this topic?** One of the fastest-growing areas of environmental systematic review,
supporting a quantitative synthesis of concentration estimates on Day 3.
        """,
    },
    {
        "label": "💼 Example 4 — Management / Business: CSR and Firm Financial Performance",
        "cache_file": "day1_ex4_csr_corpus.csv",
        "session_key": "ex4_csr",
        "source": "OpenAlex",
        "query": "corporate social responsibility firm financial performance empirical",
        "year_from": 2000,
        "year_to": 2024,
        "pub_types": ["journal-article"],
        "description": """
**Research question:** What is the empirical evidence on the relationship between Corporate
Social Responsibility (CSR) activities and firm financial performance (ROA, ROE, Tobin's Q)?

**Search strategy:** Targets empirical studies measuring the CSR–financial performance link,
excluding purely theoretical or conceptual papers.

**Why this topic?** One of the most heavily meta-analysed topics in management research,
supporting a pooled effect size computation on Day 3.
        """,
    },
    {
        "label": "🗂️ Example 5 — Zotero Library: AI-Assisted Systematic Reviews (Mixed Sources)",
        "cache_file": "day1_ex5_zotero_corpus.csv",
        "session_key": "ex5_zotero",
        "source": "Zotero",
        "query": "AI-assisted systematic reviews (researcher's Zotero library)",
        "year_from": None,
        "year_to": None,
        "pub_types": ["All types (Zotero library)"],
        "description": """
**What this example demonstrates:** Instead of querying an open API, this example shows
what happens when a researcher connects their existing **Zotero library** to the pipeline.

**Scenario:** A researcher has been collecting papers on *AI-assisted systematic reviews*
in Zotero over several months — a mix of journal articles, conference papers, and preprints
from multiple sources (PubMed, Scopus, Web of Science, arXiv). They connect their Zotero
library here, and the app retrieves all items, deduplicates them, and feeds them into the
same pipeline as the API-based examples.

**Why Zotero?** Many researchers already maintain a reference manager. Zotero integration
means you do not need to re-search databases — you can start the systematic review pipeline
from your existing collection, regardless of which databases you used to build it.

**Input flexibility:** The BYOD section below also supports direct Zotero connection using
your personal User ID and API Key (available from your Zotero account settings).
        """,
    },
]

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
    """Return (html_string, error_message). error_message is None on success."""
    if not PYVIS_AVAILABLE:
        return None, "pyvis is not installed in this environment."

    freq, edges, top_keywords = _build_cooccurrence_network(df, top_n=top_n, min_cooccurrence=min_cooccurrence)

    if not edges:
        return None, (
            "Not enough co-occurring keywords to build a network with the current settings. "
            "Try lowering the minimum co-occurrence threshold or using a larger corpus."
        )

    # ── Louvain community detection ───────────────────────────────────────────
    # Build a networkx graph for Louvain
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

        # Distinct colour palette (up to 12 communities; cycles if more)
        PALETTE = [
            "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
            "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#00bcd4",
            "#8bc34a", "#ff5722",
        ]
        def community_color(node):
            cid = partition.get(node, 0)
            return PALETTE[cid % len(PALETTE)]

        louvain_ok = True
    except Exception:
        louvain_ok = False
        nodes_in_edges = set()
        for a, b, _ in edges:
            nodes_in_edges.add(a)
            nodes_in_edges.add(b)
        # Fallback: frequency-based colouring
        sorted_freqs = sorted([freq[kw] for kw in top_keywords]) if top_keywords else [1]
        q1 = sorted_freqs[max(0, len(sorted_freqs) // 4)]
        q2 = sorted_freqs[max(0, len(sorted_freqs) // 2)]
        q3 = sorted_freqs[max(0, 3 * len(sorted_freqs) // 4)]
        def community_color(node):
            f = freq.get(node, 1)
            if f >= q3: return "#e74c3c"
            if f >= q2: return "#e67e22"
            if f >= q1: return "#3498db"
            return "#95a5a6"
        num_communities = 4

    # ── Build pyvis network ───────────────────────────────────────────────────
    net = PyvisNetwork(height="560px", width="100%", bgcolor="#fafafa",
                       font_color="#222222", notebook=False)
    # ForceAtlas2 with stronger gravity so communities cluster tightly
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -120,
          "centralGravity": 0.015,
          "springLength": 100,
          "springConstant": 0.08,
          "damping": 0.9
        },
        "solver": "forceAtlas2Based",
        "stabilization": {"iterations": 200, "updateInterval": 25}
      },
      "nodes": {"font": {"size": 13, "color": "#222222"}, "borderWidth": 2,
                 "borderWidthSelected": 3},
      "edges": {"color": {"opacity": 0.4}, "smooth": {"type": "continuous"}},
      "interaction": {"hover": true, "tooltipDelay": 100}
    }
    """)

    for kw in nodes_in_edges:
        f = freq.get(kw, 1)
        size = max(10, min(45, 8 + f * 2))
        cid = partition.get(kw, 0) if louvain_ok else 0
        color = community_color(kw)
        if louvain_ok:
            tooltip = (
                f"<b>{kw}</b><br/>"
                f"Frequency: {f}<br/>"
                f"Community: {cid + 1}"
            )
        else:
            tooltip = f"<b>{kw}</b><br/>Frequency: {f}"
        net.add_node(kw, label=kw, title=tooltip, size=size,
                     color={"background": color, "border": "#333333",
                            "highlight": {"background": color, "border": "#000000"}})

    max_cooc = max(cnt for _, _, cnt in edges) if edges else 1
    for a, b, cnt in edges:
        width = max(1, min(8, 1 + (cnt / max_cooc) * 7))
        # Edges within the same community are slightly more opaque
        same_comm = louvain_ok and partition.get(a, -1) == partition.get(b, -2)
        opacity = 0.65 if same_comm else 0.3
        net.add_edge(a, b, value=cnt, title=f"Co-occurrences: {cnt}", width=width,
                     color={"opacity": opacity})

    legend_note = f" ({num_communities} Louvain communities detected)" if louvain_ok else ""
    # Inject a small legend note into the HTML
    html = net.generate_html()
    html = html.replace(
        "</body>",
        f'<div style="position:absolute;bottom:8px;left:12px;font-size:11px;'
        f'color:#555;font-family:sans-serif;">'
        f'Node colour = Louvain community{legend_note}. '
        f'Node size = keyword frequency.</div></body>'
    )
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

def load_cached_corpus(cache_file):
    """Load a pre-cached corpus CSV. Returns (DataFrame, error_message)."""
    path = CACHE_DIR / cache_file
    if path.exists():
        try:
            df = pd.read_csv(path)
            return df, None
        except Exception as e:
            return None, f"Could not read cached file: {e}"
    return None, f"Cache file not found: {cache_file}"


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
    Generates a valid VOSviewer JSON, uploads it to a public URL, and provides
    a one-click link to open the map directly in VOSviewer Online.
    """
    import subprocess, tempfile, os, json as _json

    st.markdown("#### 🔬 Bibliometric Network Map — VOSviewer")
    st.markdown("""
[VOSviewer](https://www.vosviewer.com) is the standard free tool for creating
**keyword co-occurrence networks**, **citation networks**, and **bibliographic coupling maps**
from a corpus of literature. It is free and available in two versions:
- **VOSviewer Online** (`app.vosviewer.com`) — browser-based, no installation needed.
- **VOSviewer Desktop** — full application (Windows / Mac / Linux), for larger corpora and offline use.
    """)

    # ── Generate VOSviewer JSON ────────────────────────────────────────────────
    vos_data = generate_vosviewer_json(df)
    vos_url = None

    if vos_data is not None:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, prefix=f"{session_key}_vos_"
            ) as tmp:
                _json.dump(vos_data, tmp, ensure_ascii=False)
                tmp_path = tmp.name

            result = subprocess.run(
                ["manus-upload-file", tmp_path],
                capture_output=True, text=True, timeout=30
            )
            os.unlink(tmp_path)

            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("http"):
                    vos_url = line
                    break
        except Exception:
            vos_url = None

    # ── Buttons row ───────────────────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])

    with col2:
        if vos_url:
            online_link = f"https://app.vosviewer.com/?json={vos_url}"
            st.link_button(
                "🌐 Open in VOSviewer Online",
                online_link,
                use_container_width=True,
            )
            st.caption("Click to open the keyword co-occurrence map directly in your browser — no installation needed.")
        else:
            st.link_button(
                "🌐 Open VOSviewer Online",
                "https://app.vosviewer.com",
                use_container_width=True,
            )
            st.caption("Load the downloaded JSON file via the folder icon on the site.")
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

    st.info("✅ This corpus is pre-loaded for Day 2 screening. Go to **Day 2 → From Corpus to Included Studies** when ready.")


# ── Live API helpers (BYOD only) ───────────────────────────────────────────────

def _sanitise_for_openalex(query: str) -> str:
    """Strip Boolean operators, parentheses, and quoted phrases from a query string
    so it is safe to pass to OpenAlex's `search` parameter, which only accepts
    plain keyword terms (no AND/OR/NOT/parentheses).
    """
    import re as _re
    # Remove parentheses
    q = query.replace('(', ' ').replace(')', ' ')
    # Remove quoted phrases — keep the words inside the quotes
    q = _re.sub(r'"([^"]+)"', r'\1', q)
    # Remove Boolean operators (case-insensitive, whole word)
    q = _re.sub(r'\b(AND|OR|NOT)\b', ' ', q, flags=_re.IGNORECASE)
    # Collapse whitespace
    q = ' '.join(q.split())
    return q


def query_openalex_live(search_query, per_page=50, max_pages=2):
    base = "https://api.openalex.org/works"
    clean_query = _sanitise_for_openalex(search_query)
    params = {
        "search": clean_query,
        "filter": "has_abstract:true",
        "per_page": per_page,
        "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index,cited_by_count,concepts",
        "cursor": "*",
    }
    records = []
    for _ in range(max_pages):
        r = requests.get(base, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("results", [])
        records.extend(batch)
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        params["cursor"] = cursor
        time.sleep(0.3)
    return records


def query_crossref_live(search_query, per_page=50):
    base = "https://api.crossref.org/works"
    params = {
        "query": search_query,
        "rows": per_page,
        "select": "DOI,title,author,published,container-title,abstract",
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])
    rows = []
    for item in items:
        title = item.get("title", [""])[0] if item.get("title") else ""
        authors_list = item.get("author", [])
        authors = "; ".join(
            f"{a.get('family', '')} {a.get('given', '')}".strip()
            for a in authors_list[:5]
        )
        pub = item.get("published", {})
        parts = pub.get("date-parts", [[""]])[0]
        year = str(parts[0]) if parts else ""
        venue = item.get("container-title", [""])[0] if item.get("container-title") else ""
        abstract = item.get("abstract", "") or ""
        rows.append({
            "ID": item.get("DOI", ""),
            "DOI": item.get("DOI", "") or "",
            "Title": title.strip(),
            "Year": year,
            "Authors": authors,
            "Venue": venue,
            "Abstract": abstract,
            "Citations": "",
            "Concepts": "",
        })
    return pd.DataFrame(rows)


def query_semantic_scholar_live(search_query, per_page=50):
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": search_query,
        "limit": per_page,
        "fields": "paperId,externalIds,title,year,authors,venue,abstract,citationCount",
    }
    # Retry with exponential backoff to handle 429 rate-limit responses
    for attempt in range(4):
        r = requests.get(base, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        break
    else:
        raise Exception("Semantic Scholar rate limit exceeded after 4 retries. Please wait a moment and try again.")
    items = r.json().get("data", [])
    rows = []
    for item in items:
        authors = "; ".join(a.get("name", "") for a in item.get("authors", [])[:5])
        doi = (item.get("externalIds") or {}).get("DOI", "") or ""
        rows.append({
            "ID": item.get("paperId", ""),
            "DOI": doi,
            "Title": (item.get("title", "") or "").strip(),
            "Year": item.get("year", ""),
            "Authors": authors,
            "Venue": item.get("venue", "") or "",
            "Abstract": item.get("abstract", "") or "",
            "Citations": item.get("citationCount", 0),
            "Concepts": "",
        })
    return pd.DataFrame(rows)


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
        authors = item.get("authorString", "") or ""
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
    for r in records:
        raw_aii = r.get("abstract_inverted_index") or {}
        if raw_aii:
            max_pos = max(pos for positions in raw_aii.values() for pos in positions)
            words = [""] * (max_pos + 1)
            for word, positions in raw_aii.items():
                for pos in positions:
                    words[pos] = word
            abstract = " ".join(words)
        else:
            abstract = ""
        authors = "; ".join(
            a.get("author", {}).get("display_name", "") or ""
            for a in (r.get("authorships") or [])[:5]
        )
        loc = r.get("primary_location") or {}
        source = loc.get("source") or {}
        venue = source.get("display_name", "") or ""
        concepts = "; ".join(
            c.get("display_name", "") for c in (r.get("concepts") or [])[:5]
        )
        rows.append({
            "ID": r.get("id", ""),
            "DOI": r.get("doi", "") or "",
            "Title": (r.get("title", "") or "").strip(),
            "Year": r.get("publication_year", ""),
            "Authors": authors,
            "Venue": venue,
            "Abstract": abstract,
            "Citations": r.get("cited_by_count", 0),
            "Concepts": concepts,
        })
    return pd.DataFrame(rows)


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
open APIs, including **OpenAlex**, **Crossref**, **Semantic Scholar**, and **Europe PMC**.

Participants are shown how API-based retrieval differs from manual database searching
and how it facilitates reproducibility. Because APIs evolve and results may change over
time, reproducibility requires logging queries and timestamps — a practice the app
supports automatically.

### Open APIs Covered

| API | Discipline Focus | Strengths |
|-----|-----------------|-----------|
| **OpenAlex** | All disciplines | 250M+ works, fully open, rich metadata including concepts and citations |
| **Crossref** | All disciplines | DOI-centric, strong for journal articles and conference papers |
| **Semantic Scholar** | STEM, CS, Biomedical | AI-extracted concepts, citation graphs, open access links |
| **Europe PMC** | Life sciences, health | Full-text access for many articles, strong for biomedical reviews |

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Introduce the logic of programmatic literature collection. Clarify the difference between manual database searches and open API retrieval. Present discipline-spanning examples and explain how query timestamps are logged for reproducibility. |
| **Hour 2** | Demonstrate query building and API access. Show how to translate research questions into Boolean queries and retrieve metadata from OpenAlex, Crossref, Semantic Scholar, and Europe PMC. |
| **Hour 3** | Use the Streamlit app to run automated deduplication. Participants inspect the output, compare field completeness, explore the corpus using the **interactive keyword co-occurrence network** (pyvis), export a clean CSV or RIS file, and create a **VOSviewer** bibliometric map. |

### Input Flexibility: Multiple Entry Points

Participants do not need to start from a Boolean query. The BYOD section accepts:

| Input Type | When to Use |
|------------|-------------|
| **Boolean Query** | Starting a review from scratch |
| **RIS / BibTeX File** | Already searched traditional databases (PubMed, Scopus, Web of Science) |
| **Zotero Integration** | Already using a reference manager — connect your cloud or self-hosted library |

### Two Visualisation Tools for Every Corpus

Every corpus produced by this app — whether from a guided example or your own BYOD query —
is visualised in **two complementary ways**:

1. **Interactive keyword co-occurrence network (pyvis)** — built directly in this app.
   Drag nodes, scroll to zoom, hover for details. Instantly shows which topics cluster together.

2. **VOSviewer bibliometric map** — export the corpus as a RIS file and open it in
   [VOSviewer Online](https://app.vosviewer.com) (free, browser-based). Provides
   publication-quality maps with colour-coded clusters, citation networks, and bibliographic
   coupling — the standard tool in systematic review methodology.

### Learning Outcome

By the end of Day 1, you should be able to formulate a search strategy, understand how
open APIs retrieve bibliographic metadata, follow the logic by which the app converts API
responses into a clean, deduplicated corpus ready for screening, and produce both an
interactive keyword network and a VOSviewer bibliometric map of your corpus.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Query**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES — all render immediately, no button required
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 1 — Guided Examples")
    st.markdown("""
Each example below loads a pre-built corpus from a cached dataset.
**Expand any example** to see the corpus preview, year distribution chart,
an **interactive keyword co-occurrence network** (pyvis), VOSviewer export
instructions, and download buttons (CSV and RIS).
No button click required — everything renders immediately.

**Five examples are provided:**
- 🏥 Health Sciences (OpenAlex)
- 🏛️ Social Sciences (OpenAlex)
- ⚗️ Science / Engineering (OpenAlex)
- 💼 Management / Business (OpenAlex)
- 🗂️ Zotero Library (researcher's existing reference collection)
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            st.markdown(ex["description"])
            if ex["source"] == "Zotero":
                st.markdown(f"**Source:** {ex['source']} &nbsp;|&nbsp; **Collection:** `{ex['query']}`")
            else:
                yr_from = ex.get("year_from")
                yr_to = ex.get("year_to")
                pub_types = ex.get("pub_types", [])
                period_str = f"{yr_from}–{yr_to}" if yr_from and yr_to else "All years"
                types_str = ", ".join(pub_types) if pub_types else "All types"
                st.markdown(
                    f"**API source:** {ex['source']} &nbsp;|&nbsp; **Query:** `{ex['query']}`  \n"
                    f"**Time period:** {period_str} &nbsp;|&nbsp; **Publication types:** {types_str}"
                )

            df, err = load_cached_corpus(ex["cache_file"])
            if err:
                st.error(f"❌ {err}")
            else:
                display_corpus(df, ex["label"], ex["session_key"])

# ══════════════════════════════════════════════════════════════════════════════
# BYOD — BRING YOUR OWN DATA
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Your Own Query":
    st.title("🔎 Day 1 — Bring Your Own Data")
    st.markdown("""
Use this section to build a corpus from **your own research question**.
Choose your preferred input method below. No coding required.

All three input methods produce the same outputs: a deduplicated corpus table,
a publication year chart, an **interactive keyword co-occurrence network** (pyvis),
a RIS export for Zotero, and a RIS file ready for **VOSviewer** bibliometric network analysis.
    """)

    input_method = st.radio(
        "How would you like to provide your literature?",
        [
            "🔍 Boolean Query (search open APIs live)",
            "📄 Upload RIS / BibTeX file",
            "🗂️ Zotero Integration",
        ],
        horizontal=True,
    )

    # ── Option 1: Boolean Query ────────────────────────────────────────────────
    if input_method == "🔍 Boolean Query (search open APIs live)":
        st.markdown("#### Search Open APIs")
        api_choice = st.selectbox(
            "Select API",
            [
                "OpenAlex (recommended for most disciplines)",
                "Crossref (DOI-centric, all disciplines)",
                "Europe PMC (Life sciences, health)",
            ],
        )
        st.caption("ℹ️ Semantic Scholar is not available for live queries due to strict rate limits on their public API. Use OpenAlex for STEM and biomedical topics — it covers the same literature without rate restrictions.")
        query_input = st.text_input(
            "Enter your search query (e.g. 'machine learning clinical diagnosis')",
            placeholder="e.g. telemedicine chronic disease management outcomes",
        )
        per_page = st.slider("Records per page", min_value=10, max_value=100, value=50, step=10)
        max_pages = st.slider("Number of pages to retrieve", min_value=1, max_value=5, value=2)

        use_year_filter = st.checkbox("Filter by publication year range", value=False, key="byod_use_year")
        if use_year_filter:
            yr_range = st.slider("Publication year range", min_value=1990, max_value=2026, value=(2010, 2026), step=1, key="byod_yr_slider")
            byod_year_from, byod_year_to = yr_range
        else:
            byod_year_from, byod_year_to = None, None
        byod_pub_types = st.multiselect(
            "Publication types (leave empty for all types)",
            ["journal-article", "book-chapter", "conference-paper", "preprint", "review", "report"],
            default=[],
        )
        if st.button("▶ Run My Query", key="run_byod"):
            if not query_input.strip():
                st.warning("Please enter a search query above.")
            else:
                with st.spinner(f"Querying {api_choice.split('(')[0].strip()}…"):
                    try:
                        api_name = api_choice.split("(")[0].strip()
                        if "OpenAlex" in api_choice:
                            records = query_openalex_live(query_input.strip(), per_page=per_page, max_pages=max_pages)
                            df = openalex_to_df(records)
                        elif "Crossref" in api_choice:
                            df = query_crossref_live(query_input.strip(), per_page=per_page)
                        elif "Semantic Scholar" in api_choice:
                            df = query_semantic_scholar_live(query_input.strip(), per_page=per_page)
                        elif "Europe PMC" in api_choice:
                            df = query_europepmc_live(query_input.strip(), per_page=per_page)
                        else:
                            df = pd.DataFrame()

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
                            "max_pages": max_pages if "OpenAlex" in api_choice else 1,
                            "records_retrieved": before,
                            "records_after_dedup": after,
                            "year_from": int(byod_year_from) if byod_year_from else "all",
                            "year_to": int(byod_year_to) if byod_year_to else "all",
                            "publication_types": byod_pub_types if byod_pub_types else "all",
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                        }
                        st.session_state["byod_log"] = log
                    except Exception as e:
                        st.error(f"Error retrieving data: {e}")

        if "byod_df" in st.session_state and st.session_state["byod_df"] is not None:
            df = st.session_state["byod_df"]
            _yr_from = st.session_state.get("byod_year_from")
            _yr_to = st.session_state.get("byod_year_to")
            _ptypes = st.session_state.get("byod_pub_types", [])
            _period = f"{_yr_from}–{_yr_to}" if _yr_from and _yr_to else ("from " + str(_yr_from) if _yr_from else ("up to " + str(_yr_to) if _yr_to else "All years"))
            _types_disp = ", ".join(_ptypes) if _ptypes else "All types"
            st.markdown(
                f"**API source:** {st.session_state.get('byod_api', '')} &nbsp;|&nbsp; "
                f"**Query:** `{st.session_state.get('byod_query', '')}`  \n"
                f"**Time period:** {_period} &nbsp;|&nbsp; **Publication types:** {_types_disp}"
            )
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

    # ── Option 2: RIS / BibTeX Upload ─────────────────────────────────────────
    elif input_method == "📄 Upload RIS / BibTeX file":
        st.markdown("""
#### Upload an Existing RIS or BibTeX File

If you have already searched traditional databases (PubMed, Scopus, Web of Science,
CINAHL, PsycINFO, etc.) and exported the results as a **RIS** or **BibTeX** file,
upload it here. The app will parse the file, deduplicate the records, and produce
the same corpus preview, year chart, interactive keyword co-occurrence network,
VOSviewer bibliometric network export, and download options as the guided examples.
        """)
        uploaded_file = st.file_uploader(
            "Upload your RIS or BibTeX file",
            type=["ris", "bib", "txt"],
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

    # ── Option 3: Zotero ──────────────────────────────────────────────────────
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
