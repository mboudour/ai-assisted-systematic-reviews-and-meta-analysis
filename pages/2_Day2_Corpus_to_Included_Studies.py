"""
Day 2 — From Corpus to Included Studies
Four self-contained guided cases and a separate BYOD workflow.
Guided cases use a selected provider's fixed search and records; BYOD can use the
Day 1 BYOD session or a user-supplied corpus.
No coding required.

Covers: PICO/SPIDER criteria, Active Learning (TF-IDF + Logistic Regression),
LLM zero-shot screening, Transparency Log, recall-oriented metrics,
inter-rater reliability, PRISMA-S, comparison with Rayyan/Covidence.
"""

import io
import re
import pathlib
import sys
import hashlib
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer

st.set_page_config(
    page_title="Day 2 — From Corpus to Included Studies",
    page_icon="🔍",
    layout="wide",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from day2_networks import build_network
from day2_network_view import make_network_html
from openaire_notice import OPENAIRE_LIMITATIONS, source_column_mentions_openaire
from guided_loader_v3 import load_guided_workflow

guided_workflow = load_guided_workflow()

def corpus_digest(df):
    """Detect changes to values, row indices, column names, ordering and types."""
    schema = {
        "columns": [(type(name).__name__, repr(name)) for name in df.columns],
        "dtypes": [str(dtype) for dtype in df.dtypes],
    }
    digest = hashlib.sha256(json.dumps(schema, ensure_ascii=True).encode("utf-8"))
    digest.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
    return digest.hexdigest()

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
            words = re.findall(r'\b[a-zA-Z]{4,}\b', t.lower())
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
            min_df=1, token_pattern=r'\b[a-zA-Z]{4,}\b',
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
    """Convert a DataFrame of included studies to RIS format with KW tags for VOSviewer."""
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
    """Render VOSviewer bibliometric network section for included studies."""
    st.markdown("#### 🔬 Bibliometric Network Map — VOSviewer (Included Studies)")
    st.markdown("""
[VOSviewer](https://www.vosviewer.com) provides a richer, publication-quality map of the
**included studies** with colour-coded clusters, zoom, and label filtering.
The interactive network above shows co-occurrence patterns computed in this app.
VOSviewer can support additional network types when its input contains the necessary
metadata. This RIS export does not include citation-reference lists, so it does not
by itself support citation networks or bibliographic coupling.

- **VOSviewer Desktop** — where you **create** maps from bibliographic data (free, Windows/Mac/Linux).
- **VOSviewer Online** (`app.vosviewer.com`) — browser viewer only; load a `.json` map saved from the desktop app.
    """)
    st.info("""
**How to create a VOSviewer map from the included studies — step by step (Desktop App):**

**Step 1 →** Click **"⬇️ Download RIS file for VOSviewer"** below.

**Step 2 →** Download and install **VOSviewer Desktop** (free) from the button on the right.

**Step 3 →** Open VOSviewer Desktop. Click **"Create"** (bottom-left panel).

**Step 4 →** Select **"Create a map based on bibliographic data"** → click **"Next"**.


**Step 5 →** Select **"Read data from reference manager files"** → click **"Next"**.


**Step 6 →** Click the **"RIS"** tab → **"Browse"** → select the RIS file → click **"Next"**.

**Step 7 →** Choose analysis type (Co-occurrence → All keywords recommended) → **"Next"**.

**Step 8 →** Set minimum occurrences to **2** (small corpus) or **3** → **"Next"** → **"Finish"**.

**To view in VOSviewer Online:** File → Save as `.json` in the desktop app, then load via the folder icon at `app.vosviewer.com`.
    """)
    col1, col2 = st.columns([3, 1])
    with col2:
        st.markdown("")
        st.link_button("🌐 Open VOSviewer Online", "https://app.vosviewer.com", use_container_width=True)
        st.caption("Free · browser-based · viewer only")
        st.markdown("")
        st.link_button("⬇️ VOSviewer Desktop", "https://www.vosviewer.com/download", use_container_width=True)
        st.caption("Create maps · free · Windows/Mac/Linux")
    with col1:
        ris_bytes = df_to_ris(df).encode("utf-8")
        st.download_button(
            "⬇️ Download RIS file for VOSviewer",
            ris_bytes,
            f"{session_key}_included_for_vosviewer.ris",
            "application/x-research-info-systems",
            key=f"dl_ris_vos_{session_key}",
        )
        st.caption("Contains titles, authors, years, DOIs, abstracts, and keywords for all included studies.")


def render_day2_networks(screened_df, included_df, session_key):
    """Let participants map actual included or all screened records."""
    st.markdown("#### Interactive networks")
    st.markdown(
        "Choose a set of records and a network. Co-occurrence and co-authorship links count "
        "records containing both items. Bibliographic-coupling nodes are studies and links "
        "count their shared references. These maps are descriptive, not causal."
    )
    source_labels = ["Included studies", "All screened records (exploratory)"]
    default_source = 0 if not included_df.empty else 1
    source = st.radio(
        "Records to map", source_labels, index=default_source, horizontal=True,
        key=f"d2_network_source_{session_key}",
    )
    selected_df = included_df if source == source_labels[0] else screened_df
    if source == source_labels[1]:
        st.caption("Exploratory only: this set includes records screened out or not included; it is not an included-studies map.")
    if selected_df.empty:
        st.warning("There are no records in this selection. Choose all screened records or revise the screening terms.")
        return

    has_concepts = bool("Concepts" in selected_df and selected_df["Concepts"].fillna("").astype(str).str.strip().ne("").any())
    choices = {
        "Concept co-occurrence": "concepts",
        "Title and abstract term co-occurrence": "terms",
        "Co-authorship": "authors",
        "Bibliographic coupling (shared references)": "coupling",
    }
    choice = st.selectbox(
        "Network type", list(choices), index=0 if has_concepts else 1,
        key=f"d2_network_kind_{session_key}",
    )
    kind = choices[choice]
    if kind == "concepts":
        st.caption("Concepts come from the corpus, separated by semicolons. No concepts are inferred when the field is empty.")
    elif kind == "terms":
        st.caption("Terms come from titles and abstracts, or titles alone when abstracts are missing. TF-IDF selects up to eight lowercase single words per record after English and generic research stopwords are removed. These are not OpenAlex concepts; no stemming or phrase extraction is applied, and changing the record set may change the selected terms.")
    elif kind == "authors":
        st.caption("Authors must be separated by semicolons. Names are matched by case and whitespace only; variants or different people with the same name are not disambiguated. Providers and older datasets may omit or truncate authors, and comma-separated names are treated as one label.")
    else:
        st.caption("Each node is a study; a link counts its distinct shared reference IDs with another study. Hover over a node for its full title. References may be JSON arrays of DOI, OpenAlex work IDs or prefixed PMIDs, or semicolon-separated IDs if no identifier itself contains a semicolon. Incomplete reference lists yield incomplete networks; DOI and OpenAlex identifiers are not matched across namespaces. With a node cap, studies with the most available references are shown first, which can bias the map.")

    c1, c2 = st.columns(2)
    with c1:
        top_n = st.slider("Maximum number of nodes", 10, 60, 25, 5, key=f"d2_network_top_{session_key}")
    with c2:
        threshold_label = "Minimum shared references per link" if kind == "coupling" else "Minimum records per link"
        minimum = st.slider(threshold_label, 1, 10, 1, 1, key=f"d2_network_min_{session_key}")
    graph = build_network(selected_df, kind, top_n=top_n, min_cooccurrence=minimum)
    if kind == "coupling":
        st.caption(f"Records with usable reference identifiers: {graph['records_with_data']} of {graph['total_records']}. "
                   f"Shown: {len(graph['nodes'])} studies and {len(graph['edges'])} links; {graph['records_omitted_by_node_limit']} reference-bearing studies omitted by the node cap.")
    else:
        st.caption(f"Usable {kind} data: {graph['records_with_data']} of {graph['total_records']} selected records. "
                   f"Shown: {len(graph['nodes'])} nodes and {len(graph['edges'])} links at the selected settings.")
    if not graph["edges"]:
        if not graph["records_with_data"]:
            if kind == "coupling":
                st.info("No usable reference identifiers are available in these records, so coupling cannot be calculated. Search OpenAlex or Crossref in Day 1 BYOD or upload a CSV containing a References column. No references are invented.")
            else:
                st.info("No usable data for this network type in the selected records. Try title/abstract terms or another network type.")
        elif kind == "coupling":
            st.info(f"No study pair shares at least {minimum} recognized reference ID(s) among the shown studies. Missing references, incompatible identifier namespaces, or the node cap may hide matches; lower the threshold or increase the node limit where possible.")
        else:
            st.info("No pairs meet these settings. Lower the link threshold, increase the node limit, choose all screened records, or use another network type. A lack of links can also reflect missing or incompatible reference identifiers.")
        return
    try:
        graph_html = make_network_html(graph)
    except ValueError as exc:
        st.warning(f"Unable to display the network: {exc}")
    else:
        components.html(graph_html, height=590, scrolling=False)

    node_lookup = {node["id"]: node for node in graph["nodes"]}
    metric = "Shared references" if kind == "coupling" else "Co-occurring records"
    edge_df = pd.DataFrame([
        {"Source": node_lookup[e["source"]].get("full_label", node_lookup[e["source"]]["label"]),
         "Target": node_lookup[e["target"]].get("full_label", node_lookup[e["target"]]["label"]),
         metric: e["weight"],
         **({"Source DOI": node_lookup[e["source"]].get("doi", ""),
             "Target DOI": node_lookup[e["target"]].get("doi", "")} if kind == "coupling" else {})}
        for e in graph["edges"]
    ]).sort_values([metric, "Source", "Target"], ascending=[False, True, True])
    node_df = pd.DataFrame([
        {"Node": node.get("full_label", node["label"]),
         ("Available unique reference IDs" if kind == "coupling" else "Records containing node"): node["frequency"],
         **({"Record ID": node.get("record_id", ""), "DOI": node.get("doi", "")} if kind == "coupling" else {})}
        for node in graph["nodes"]
    ])
    with st.expander("View and download network data"):
        st.caption("Each reference ID contributes at most once to a study pair. Files contain displayed nodes and links only." if kind == "coupling" else "Each record contributes at most once to a node or pair. Files contain the displayed top nodes and links only.")
        st.dataframe(edge_df, use_container_width=True)
        left, right = st.columns(2)
        with left:
            st.download_button("Download network links (CSV)", edge_df.to_csv(index=False).encode("utf-8"),
                               f"{session_key}_{kind}_network_links.csv", "text/csv", key=f"d2_edges_{session_key}")
        with right:
            st.download_button("Download network nodes (CSV)", node_df.to_csv(index=False).encode("utf-8"),
                               f"{session_key}_{kind}_network_nodes.csv", "text/csv", key=f"d2_nodes_{session_key}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def render_recall_chart(df, session_key):
    """Render a simulated recall curve showing how Active Learning surfaces relevant papers."""
    if "Relevance_Score" not in df.columns or "AL_Decision" not in df.columns:
        return
    df_sorted = df.sort_values("Relevance_Score", ascending=False).reset_index(drop=True)
    total_included = max((df_sorted["AL_Decision"] == "Include").sum(), 1)
    cumulative_included = (df_sorted["AL_Decision"] == "Include").cumsum().values
    recall_curve = cumulative_included / total_included
    random_curve = np.linspace(0, 1, len(df_sorted))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(np.linspace(0, 100, len(recall_curve)), recall_curve * 100,
            color="#4C72B0", linewidth=2, label="Cached include labels")
    ax.plot([0, 100], [0, 100], color="#aaaaaa", linewidth=1.5,
            linestyle="--", label="Diagonal reference")
    ax.set_xlabel("% of corpus screened")
    ax.set_ylabel("% of stored include labels encountered")
    ax.set_title("Illustrative cumulative included-label curve")
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    st.image(buf, use_container_width=True)
    st.download_button(
        "⬇️ Download Recall Curve (PNG)",
        buf.getvalue(),
        f"{session_key}_recall_curve.png",
        "image/png",
        key=f"dl_recall_{session_key}",
    )


def display_screening_results(df, session_key, ex):
    n_include = (df["AL_Decision"] == "Include").sum()
    n_exclude = (df["AL_Decision"] == "Exclude").sum()
    n_uncertain = (df["AL_Decision"] == "Uncertain").sum() if "Uncertain" in df["AL_Decision"].values else 0

    # ── Query constraints summary ──────────────────────────────────────────────
    yr_from = ex.get("year_from")
    yr_to = ex.get("year_to")
    pub_types = ex.get("pub_types", [])
    period_str = f"{yr_from}\u2013{yr_to}" if yr_from and yr_to else "All years"
    types_str = ", ".join(pub_types) if pub_types else "All types"
    if session_key != "byod":
        st.markdown(
            f"**Illustrative teaching criteria (not verified search filters):** {period_str} "
            f"\u00a0|\u00a0 **Publication types:** {types_str}"
        )
    # ── PICO / SPIDER criteria ─────────────────────────────────────────────────
    st.markdown("#### Screening Framework — " + ex["framework"])
    framework_data = {
        "PICO / SPIDER Element": ["Population", "Intervention / Exposure", "Comparison", "Outcome"],
        "Definition": [ex["population"], ex["intervention"], ex["comparison"], ex["outcome"]],
    }
    st.table(pd.DataFrame(framework_data))

    st.markdown(f"**Inclusion criteria:** {ex['inclusion_criteria']}")
    st.markdown("**Key inclusion terms:** " + ", ".join(f"`{t}`" for t in ex["include_terms"][:6]))
    st.markdown("**Key exclusion terms:** " + ", ".join(f"`{t}`" for t in ex["exclude_terms"][:4]))

    st.markdown("---")

    # ── Metrics ───────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total screened", len(df))
    col2.metric("✅ Include", int(n_include))
    col3.metric("❌ Exclude", int(n_exclude))
    col4.metric("⚠️ Uncertain", int(n_uncertain))

    if session_key != "byod":
        # Recall-oriented metrics
        st.markdown("#### Illustrative Diagnostics — Not Validated Performance")
        st.caption(
            "These values are descriptive diagnostics computed from the cached labels or the "
            "current BYOD heuristic output; they are not validated recall, precision, F1, or "
            "WSS estimates without an independently adjudicated reference set."
        )
        precision = n_include / max(n_include + n_exclude, 1)
        recall_est = min(1.0, n_include / max(n_include + n_uncertain, 1))
        f1 = 2 * precision * recall_est / max(precision + recall_est, 1e-9)
        wss = (n_exclude / len(df)) - (1 - recall_est)

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Precision", f"{precision:.3f}")
        m_col2.metric("Estimated Recall", f"{recall_est:.3f}")
        m_col3.metric("F1 Score", f"{f1:.3f}")
        m_col4.metric("WSS@95", f"{max(wss, 0):.3f}", help="Work Saved over Sampling at 95% recall")

        st.info("WSS@95 normally requires an independently verified reference set. "
                "The numbers shown here are illustrative ratios from cached teaching labels, "
                "not empirical estimates of recall or screening efficiency.")

        # ── Recall Curve ──────────────────────────────────────────────────────────
        st.markdown("#### Illustrative Cumulative Included-Label Curve")
        render_recall_chart(df, session_key)

    else:
        st.caption("No validated precision, recall, F1, WSS, or Active Learning curve is computed for this heuristic. An independent reference set would be needed.")

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Screening Results, Ranked by Score (top 30)")
    display_cols = ["Title", "Year", "Relevance_Score", "AL_Decision", "LLM_Decision", "LLM_Justification"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available].head(30), use_container_width=True)

    # ── Transparency Log ──────────────────────────────────────────────────────
    st.markdown("#### Screening Log — Decisions and Justifications")
    if session_key == "byod":
        st.caption("Both decision columns repeat the same keyword heuristic. They are not independent AI or human reviews.")
    else:
        st.caption("These are previously saved teaching labels; their model provenance is not verified.")
    log_cols = ["Title", "LLM_Decision", "LLM_Justification"]
    available_log = [c for c in log_cols if c in df.columns]
    st.dataframe(df[available_log].head(30), use_container_width=True)

    # ── Inter-rater reliability note ──────────────────────────────────────────
    agreement = (df["AL_Decision"] == df["LLM_Decision"]).mean() if "LLM_Decision" in df.columns else None
    if agreement is not None and session_key != "byod":
        st.markdown(f"""
#### Agreement Between Cached Teaching Labels
**Label agreement:** {agreement:.1%}

This is a descriptive overlap between stored columns, not independent inter-rater reliability.
        """)

    # ── Downloads ─────────────────────────────────────────────────────────────
    included_df = df[df["AL_Decision"] == "Include"].copy()
    col_a, col_b = st.columns(2)
    with col_a:
        csv_bytes = included_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download included studies as CSV",
            csv_bytes,
            f"{session_key}_included.csv",
            "text/csv",
            key=f"dl_inc_{session_key}",
        )
    with col_b:
        full_csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download full screening log as CSV",
            full_csv,
            f"{session_key}_screening_log.csv",
            "text/csv",
            key=f"dl_full_{session_key}",
        )

    # Unlike the old five-record gate, a network can be shown whenever real
    # co-occurring pairs exist. Participants can also explore all screened rows.
    render_day2_networks(df, included_df, session_key)

    # ── VOSviewer section ─────────────────────────────────────────────────────
    if len(included_df) >= 3:
        render_vosviewer_section(included_df, session_key)

    st.session_state[f"{session_key}_included_df"] = included_df
    st.info(f"✅ {len(included_df)} included studies saved. Go to **Day 3 → From Studies to Evidence** when ready.")


# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("Day 2 Navigation")
section = st.sidebar.radio(
    "Select section",
    ["Overview", "📌 Guided Examples", "🔎 BYOD — Screen Your Own Corpus"],
)

# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if section == "Overview":
    st.title("🔍 Day 2 — From Corpus to Included Studies")
    st.markdown("""
**Theme:** Learn about screening methods and explore a no-code, first-pass screening
workflow. The current BYOD implementation is a deterministic keyword heuristic, not
a live Active Learning or LLM model.

### What You Will Do Today

The second day focuses on the most time-consuming phase of a systematic review: screening
thousands of titles and abstracts against pre-specified inclusion and exclusion criteria.
You will learn about AI-assisted approaches, inspect four guided cases, and explore
networks built from the available study metadata.

### Where Day 2 Fits in the Pipeline

Each guided case offers OpenAlex, Crossref, Europe PMC and OpenAIRE at the top. It presents
the selected provider's bounded search and records, fixed keyword screening, direct
source-linked extraction, descriptive synthesis and bibliometric maps together. Each provider
has a ready-to-view saved capture; fixed live searches are optional. The screen is not LLM or
independent human review, and bounded searches are not exhaustive. The guided cases are
separate from BYOD. In **BYOD**, Day 1 supplies a
corpus, Day 2 screens it and offers an **included-studies CSV** plus a **full screening-log
CSV**, and Day 3 extracts fields and synthesizes evidence. Retain your query log and search
metadata separately for a reproducible review.

### Screening Frameworks: PICO and SPIDER

Before any screening can begin, the review question must be formalised using a structured
framework. The two most widely used are:

| Framework | Full Form | Best Suited For |
|-----------|-----------|-----------------|
| **PICO** | Population, Intervention, Comparison, Outcome | Clinical and health sciences, management research |
| **SPIDER** | Sample, Phenomenon of Interest, Design, Evaluation, Research type | Social sciences, qualitative and mixed-methods research |

Both frameworks are introduced in this seminar.

### Two Screening Approaches — Background

**Active Learning** is a human-in-the-loop machine learning technique that can prioritize
records for review after learning from labelled examples. Its performance must be evaluated
against independent reference labels; this app's current BYOD path does not train such a model.

**LLM zero-shot screening** prompts a language model with eligibility criteria. The current
BYOD path does not call an LLM: it matches inclusion and exclusion substrings. The two
decision columns in its log repeat the same heuristic and do not constitute independent
reviewers. Human verification remains essential.

### Comparison with Dedicated Screening Tools

Dedicated platforms such as **Rayyan** and **Covidence** support collaborative screening.
This teaching app connects its Day 1 corpus to Day 3 but does not replace independent reviewers
or a validated screening workflow.

### Recall-Oriented Evaluation Metrics

Recall matters because a false negative can omit an eligible paper. Metrics such as
precision, recall and **WSS@95** require independently adjudicated reference labels.
Illustrative examples are not a substitute for validated screening performance estimates.

### Inter-Rater Reliability

In any systematic review, at least two independent reviewers should screen a random
sample of abstracts to assess agreement. The **Cohen's κ** statistic is the standard
measure: κ ≥ 0.61 is considered substantial agreement. In BYOD, both decision columns
are produced by the same deterministic heuristic, not independent reviewers.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Present the bottleneck of abstract screening. Introduce PICO and SPIDER frameworks. Explain Active Learning and LLM zero-shot screening. Introduce recall-oriented metrics and inter-rater reliability. |
| **Hour 2** | Inspect the four guided cases and their screening decisions. |
| **Hour 3** | Discuss LLM screening, check the screening log, and explore the networks; verify eligibility manually. |

### Learning Outcome

By the end of Day 2, you should understand how to formalise a review question using
PICO or SPIDER, distinguish screening methods from the current heuristic, inspect a
screening log, and interpret exploratory co-occurrence and co-authorship networks.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Screen Your Own Corpus**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 2 — Guided Examples")
    guided_workflow.render_guided_examples("day2")

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Screen Your Own Corpus":
    st.title("🔎 Day 2 — Bring Your Own Data")
    st.markdown("""
Use this section to screen **your own corpus**. Upload a CSV from your Day 1 BYOD result
or another source, or use the corpus saved from Day 1 BYOD in the current session. Define
your PICO/SPIDER criteria as inclusion and exclusion terms, and the app will screen your
records automatically using a
deterministic case-insensitive substring heuristic over Title + Abstract (not a live LLM or
independent Active Learning model). The
resulting **included studies CSV** and **full screening log CSV** appear after screening;
download the included file and upload it in Day 3 → **BYOD — Your Own Synthesis**. No coding required.
    """)
    st.caption("Uploaded records and screening results are held by the app in your session, not published by the network visualization. The server operator may have access to session data; use a trusted deployment.")

    uploaded = st.file_uploader("Upload your Day 1 corpus CSV", type=["csv"])

    _legacy_snapshot = st.session_state.get("byod_log", {}).get("source") == "cached teaching snapshot"
    if uploaded is None and _legacy_snapshot:
        st.info("A teaching snapshot left by an older version is not used in BYOD. Upload your own corpus or run your own Day 1 search.")
        df = None
    elif uploaded is None and "byod_df" in st.session_state:
        st.info("Using corpus from Day 1 BYOD session.")
        df = st.session_state["byod_df"]
        _yr_from = st.session_state.get("byod_year_from")
        _yr_to = st.session_state.get("byod_year_to")
        _ptypes = st.session_state.get("byod_pub_types", [])
        _snapshot = st.session_state.get("byod_log", {}).get("source") == "cached teaching snapshot"
        _period = "Not recorded" if _snapshot else (f"{_yr_from}–{_yr_to}" if _yr_from and _yr_to else ("from " + str(_yr_from) if _yr_from else ("up to " + str(_yr_to) if _yr_to else "All years")))
        _types_disp = "Not recorded" if _snapshot else ("OpenAIRE publications (all subtypes)" if st.session_state.get("byod_api") == "OpenAIRE" else (", ".join(_ptypes) if _ptypes else "All types"))
        st.markdown(
            f"**Query:** `{st.session_state.get('byod_query', '')}` &nbsp;|&nbsp; "
            f"**API:** {st.session_state.get('byod_api', '')}  \n"
            f"**Time period:** {_period} &nbsp;|&nbsp; **Publication types:** {_types_disp}"
        )
    elif uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = None

    if df is not None:
        df = df.copy()
        if source_column_mentions_openaire(df):
            st.caption("The corpus identifies OpenAIRE as a source; retain the Day 1 query log to verify its provenance.")
            st.warning(OPENAIRE_LIMITATIONS)
        if df.empty:
            st.warning("The selected corpus has no records to screen.")
            df = None
        elif "Title" not in df.columns and "Abstract" not in df.columns:
            st.error("The CSV needs a Title or Abstract column for screening. Check the column names and upload it again.")
            df = None
        else:
            for column in ("Title", "Abstract"):
                if column not in df.columns:
                    df[column] = ""
                    st.info(f"No {column} column was supplied; screening will use the available text.")

    if df is not None:
        st.success(f"✅ {len(df)} records loaded.")
        st.dataframe(df.head(10), use_container_width=True)

        st.markdown("---")
        st.markdown("#### Define Your Screening Criteria")
        st.caption("PICO/SPIDER fields are descriptive context. Only the inclusion and exclusion term lists below affect this heuristic screening run.")
        framework = st.selectbox("Screening framework", ["PICO", "SPIDER"])

        if framework == "PICO":
            col1, col2 = st.columns(2)
            with col1:
                population = st.text_input("Population", placeholder="e.g. adults with type 2 diabetes")
                intervention = st.text_input("Intervention", placeholder="e.g. telemedicine")
            with col2:
                comparison = st.text_input("Comparison", placeholder="e.g. standard care")
                outcome = st.text_input("Outcome", placeholder="e.g. HbA1c levels, mortality")
        else:
            col1, col2 = st.columns(2)
            with col1:
                population = st.text_input("Sample", placeholder="e.g. adults in UBI pilots")
                intervention = st.text_input("Phenomenon of Interest", placeholder="e.g. cash transfers")
            with col2:
                comparison = st.text_input("Design", placeholder="e.g. RCT, quasi-experimental")
                outcome = st.text_input("Evaluation / Research type", placeholder="e.g. employment outcomes")

        include_input = st.text_area(
            "Inclusion terms (one per line)",
            value="empirical\nquantitative\noutcomes\nrandomized\npilot",
            height=120,
        )
        exclude_input = st.text_area(
            "Exclusion terms (one per line)",
            value="editorial\ncommentary\nbook review\nopinion",
            height=100,
        )

        if st.button("▶ Run Screening", key="byod_screen"):
            st.caption(
                "BYOD implementation note: this run uses deterministic substring counts and "
                "the same resulting heuristic decision in both displayed decision columns; "
                "it is not a validated AL-versus-LLM comparison."
            )
            include_terms = [t.strip() for t in include_input.splitlines() if t.strip()]
            exclude_terms = [t.strip() for t in exclude_input.splitlines() if t.strip()]

            texts = (df["Title"].fillna("").astype(str) + " " + df["Abstract"].fillna("").astype(str)).tolist()
            scores, al_decisions, llm_decisions, llm_justifications = [], [], [], []

            for text in texts:
                tl = text.lower()
                inc_hits = sum(1 for t in include_terms if t.lower() in tl)
                exc_hits = sum(1 for t in exclude_terms if t.lower() in tl)
                score = round(max(0.0, min(1.0, inc_hits / max(len(include_terms), 1) - 0.15 * exc_hits)), 3)
                scores.append(score)

                if len(tl.strip()) < 30:
                    al_decisions.append("Exclude")
                    llm_decisions.append("Exclude")
                    llm_justifications.append("Combined title and abstract text is too short.")
                elif exc_hits > 0 and inc_hits == 0:
                    al_decisions.append("Exclude")
                    llm_decisions.append("Exclude")
                    llm_justifications.append("Contains exclusion terms with no inclusion match.")
                elif inc_hits >= 1:
                    al_decisions.append("Include")
                    llm_decisions.append("Include")
                    llm_justifications.append(f"Matches {inc_hits} inclusion term(s).")
                else:
                    al_decisions.append("Exclude")
                    llm_decisions.append("Exclude")
                    llm_justifications.append("No inclusion terms matched.")

            result_df = df.copy()
            result_df["Relevance_Score"] = scores
            result_df["AL_Decision"] = al_decisions
            result_df["LLM_Decision"] = llm_decisions
            result_df["LLM_Justification"] = llm_justifications
            result_df = result_df.sort_values("Relevance_Score", ascending=False).reset_index(drop=True)

            byod_ex = {
                "framework": framework,
                "population": population,
                "intervention": intervention,
                "comparison": comparison,
                "outcome": outcome,
                "inclusion_criteria": include_input,
                "include_terms": include_terms,
                "exclude_terms": exclude_terms,
            }
            digest = corpus_digest(df)
            st.session_state["byod_screening_run"] = {"digest": digest, "results": result_df, "criteria": byod_ex}
            st.session_state["byod_included_df"] = result_df[result_df["AL_Decision"] == "Include"].copy()
            st.session_state["byod_included_origin"] = "uploaded" if uploaded is not None else "byod session"

        run = st.session_state.get("byod_screening_run")
        if run is not None:
            current_digest = corpus_digest(df)
            if current_digest != run["digest"]:
                st.warning("The corpus has changed since the last screening. Run screening again to update the results and networks.")
                st.session_state.pop("byod_included_df", None)
            else:
                if (run["criteria"]["inclusion_criteria"] != include_input or
                        run["criteria"]["exclude_terms"] != [t.strip() for t in exclude_input.splitlines() if t.strip()] or
                        run["criteria"]["framework"] != framework or
                        any(run["criteria"][k] != v for k, v in (("population", population), ("intervention", intervention), ("comparison", comparison), ("outcome", outcome)))):
                    st.info("Showing the last completed screening run. Changes to the criteria are not applied until you run screening again.")
                if not (run["results"]["AL_Decision"] == "Include").any():
                    st.warning("No records were included by these terms. Review the criteria and rerun, or explore all screened records in the network below; the latter is not an included-studies network.")
                display_screening_results(run["results"], "byod", run["criteria"])
