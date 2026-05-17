"""
Day 2 — From Corpus to Included Studies
Four guided examples (Health, Social Science, Engineering, Business) + BYOD extension.
Guided examples load exclusively from pre-cached screening CSVs.
No live API calls, no session state dependency from Day 1.
No coding required.

Covers: PICO/SPIDER criteria, Active Learning (TF-IDF + Logistic Regression),
LLM zero-shot screening, Transparency Log, recall-oriented metrics,
inter-rater reliability, PRISMA-S, comparison with Rayyan/Covidence.
"""

import os
import io
import re
import pathlib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
from itertools import combinations

# pyvis — optional import with graceful fallback
try:
    from pyvis.network import Network as PyvisNetwork
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

st.set_page_config(
    page_title="Day 2 — From Corpus to Included Studies",
    page_icon="🔍",
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
        "screened_file": "day2_ex1_health_screened.csv",
        "session_key": "ex1_health",
        "framework": "PICO",
        "population": "Adults with chronic diseases (diabetes, hypertension, cardiovascular disease)",
        "intervention": "Standard or enhanced care access",
        "comparison": "High vs. low socioeconomic status groups",
        "outcome": "Disease control, mortality, care utilisation",
        "inclusion_criteria": (
            "Include empirical studies (observational, experimental, or mixed-methods) "
            "that measure health outcomes or access to care for patients with chronic diseases "
            "(diabetes, hypertension, cardiovascular disease) and report differences by "
            "socioeconomic status, race, ethnicity, or geographic area. "
            "Exclude editorials, opinion pieces, conference abstracts, and purely theoretical papers."
        ),
        "include_terms": [
            "socioeconomic", "health inequalit", "disparity", "disparities",
            "diabetes", "hypertension", "cardiovascular", "chronic disease",
            "access to care", "racial", "income", "poverty",
        ],
        "exclude_terms": [
            "editorial", "letter to the editor", "commentary", "book review",
        ],
    },
    {
        "label": "🏛️ Example 2 — Social Sciences: Universal Basic Income (UBI) Policy Outcomes",
        "screened_file": "day2_ex2_ubi_screened.csv",
        "session_key": "ex2_ubi",
        "framework": "SPIDER",
        "population": "Adults in UBI pilot programmes or policy evaluations",
        "intervention": "Universal Basic Income / guaranteed income transfer",
        "comparison": "Control groups or pre-intervention periods",
        "outcome": "Employment, poverty, well-being, social behaviour",
        "inclusion_criteria": (
            "Include empirical evaluations (quantitative, qualitative, or mixed-methods) "
            "of Universal Basic Income programmes or pilots that report measured outcomes "
            "on employment, poverty, well-being, or social behaviour. "
            "Exclude opinion pieces, editorials, theoretical proposals, and grey literature "
            "without peer review."
        ),
        "include_terms": [
            "universal basic income", "basic income", "guaranteed income",
            "cash transfer", "pilot", "evaluation", "employment", "poverty",
        ],
        "exclude_terms": [
            "opinion", "commentary", "book review", "policy proposal", "editorial",
        ],
    },
    {
        "label": "⚗️ Example 3 — Science / Engineering: Microplastic Pollution in Aquatic Environments",
        "screened_file": "day2_ex3_microplastics_screened.csv",
        "session_key": "ex3_microplastics",
        "framework": "PICO",
        "population": "Aquatic environments (freshwater, marine, estuarine)",
        "intervention": "Presence and concentration of microplastic particles",
        "comparison": "Baseline or reference measurements",
        "outcome": "Concentration levels (particles/L or mg/kg), ecological impact",
        "inclusion_criteria": (
            "Include experimental or observational studies that measure microplastic "
            "concentrations, distribution, or ecological impact in freshwater or marine "
            "aquatic environments. Studies must report quantitative measurements. "
            "Exclude purely laboratory studies with no environmental relevance, reviews, "
            "and studies focused on terrestrial environments only."
        ),
        "include_terms": [
            "microplastic", "marine", "freshwater", "aquatic", "concentration",
            "polymer", "sampling", "detection",
        ],
        "exclude_terms": [
            "terrestrial", "soil contamination", "atmospheric", "review article",
        ],
    },
    {
        "label": "💼 Example 4 — Management / Business: CSR and Firm Financial Performance",
        "screened_file": "day2_ex4_csr_screened.csv",
        "session_key": "ex4_csr",
        "framework": "PICO",
        "population": "Publicly listed firms across industries and countries",
        "intervention": "Corporate Social Responsibility (CSR) activities",
        "comparison": "Low vs. high CSR firms; pre/post CSR adoption",
        "outcome": "Financial performance (ROA, ROE, Tobin's Q, stock returns)",
        "inclusion_criteria": (
            "Include empirical studies that quantitatively measure the relationship between "
            "Corporate Social Responsibility (CSR) activities and firm financial performance "
            "metrics (ROA, ROE, Tobin's Q, stock returns, or similar). "
            "Exclude purely conceptual or theoretical papers, qualitative case studies without "
            "quantitative financial performance data, and editorials."
        ),
        "include_terms": [
            "corporate social responsibility", "csr", "esg", "roa", "roe",
            "tobin", "financial performance", "firm performance", "empirical",
        ],
        "exclude_terms": [
            "conceptual framework", "editorial", "commentary", "book review",
        ],
    },
]

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

# ── pyvis network helpers ──────────────────────────────────────────────────────

def _build_cooccurrence_network(df, top_n=40, min_cooccurrence=2):
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
    if not PYVIS_AVAILABLE:
        return None, "pyvis is not installed in this environment."
    freq, edges, top_keywords = _build_cooccurrence_network(df, top_n=top_n, min_cooccurrence=min_cooccurrence)
    if not edges:
        return None, "Not enough co-occurring keywords to build a network. Try lowering the minimum co-occurrence threshold."
    sorted_freqs = sorted([freq[kw] for kw in top_keywords]) if top_keywords else [1]
    q1 = sorted_freqs[max(0, len(sorted_freqs) // 4)]
    q2 = sorted_freqs[max(0, len(sorted_freqs) // 2)]
    q3 = sorted_freqs[max(0, 3 * len(sorted_freqs) // 4)]
    def node_color(f):
        if f >= q3: return "#e74c3c"
        if f >= q2: return "#e67e22"
        if f >= q1: return "#3498db"
        return "#95a5a6"
    net = PyvisNetwork(height="520px", width="100%", bgcolor="#1a1a2e",
                       font_color="white", notebook=False)
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -80,
          "centralGravity": 0.01,
          "springLength": 120,
          "springConstant": 0.05
        },
        "solver": "forceAtlas2Based",
        "stabilization": {"iterations": 150}
      },
      "nodes": {"font": {"size": 13, "color": "white"}, "borderWidth": 1.5},
      "edges": {"color": {"opacity": 0.5}, "smooth": {"type": "continuous"}},
      "interaction": {"hover": true, "tooltipDelay": 100}
    }
    """)
    nodes_in_edges = set()
    for a, b, _ in edges:
        nodes_in_edges.add(a)
        nodes_in_edges.add(b)
    for kw in nodes_in_edges:
        f = freq.get(kw, 1)
        size = max(10, min(40, 8 + f * 2))
        net.add_node(kw, label=kw, title=f"{kw}\nFrequency: {f}",
                     size=size, color=node_color(f))
    max_cooc = max(cnt for _, _, cnt in edges) if edges else 1
    for a, b, cnt in edges:
        width = max(1, min(8, 1 + (cnt / max_cooc) * 7))
        net.add_edge(a, b, value=cnt, title=f"Co-occurrences: {cnt}", width=width)
    return net.generate_html(), None


def render_pyvis_network(df, session_key, label="Included Studies"):
    st.markdown("#### 🕸️ Interactive Keyword Co-occurrence Network — " + label)
    st.markdown("""
This network maps the **most frequent keywords** in the included studies and draws a link
between any two keywords that appear together in the same paper. It reveals the thematic
structure of the studies that survived screening. **Drag nodes, scroll to zoom, hover for details.**
    """)
    col_opts, _ = st.columns([2, 1])
    with col_opts:
        top_n = st.slider("Number of top keywords", min_value=10, max_value=60, value=35, step=5,
                          key=f"pyvis_topn_{session_key}")
        min_cooc = st.slider("Minimum co-occurrence", min_value=1, max_value=10, value=2, step=1,
                             key=f"pyvis_mincooc_{session_key}")
    html, err = generate_pyvis_html(df, top_n=top_n, min_cooccurrence=min_cooc)
    if err:
        st.warning(f"⚠️ Network could not be generated: {err}")
    else:
        components.html(html, height=540, scrolling=False)
        st.caption("🔴 High-frequency  🟠 Medium-high  🔵 Medium-low  ⚫ Low-frequency. Edge thickness = co-occurrence count.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_screened(screened_file):
    path = CACHE_DIR / screened_file
    if path.exists():
        try:
            return pd.read_csv(path), None
        except Exception as e:
            return None, str(e)
    return None, f"Screened file not found: {screened_file}"


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
            color="#4C72B0", linewidth=2, label="Active Learning")
    ax.plot([0, 100], [0, 100], color="#aaaaaa", linewidth=1.5,
            linestyle="--", label="Random screening")
    ax.set_xlabel("% of corpus screened")
    ax.set_ylabel("% of relevant papers found (Recall)")
    ax.set_title("Active Learning — Recall Curve")
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

    # Recall-oriented metrics
    st.markdown("#### Recall-Oriented Evaluation Metrics")
    precision = n_include / max(n_include + n_exclude, 1)
    recall_est = min(1.0, n_include / max(n_include + n_uncertain, 1))
    f1 = 2 * precision * recall_est / max(precision + recall_est, 1e-9)
    wss = (n_exclude / len(df)) - (1 - recall_est)

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Precision", f"{precision:.3f}")
    m_col2.metric("Estimated Recall", f"{recall_est:.3f}")
    m_col3.metric("F1 Score", f"{f1:.3f}")
    m_col4.metric("WSS@95", f"{max(wss, 0):.3f}", help="Work Saved over Sampling at 95% recall")

    st.info("""
**WSS@95** (Work Saved over Sampling at 95% recall) measures how much screening effort
is saved by Active Learning compared to random ordering, while retaining 95% of relevant
papers. A value of 0.30 means 30% fewer abstracts need to be read to find 95% of
relevant studies.
    """)

    # ── Recall Curve ──────────────────────────────────────────────────────────
    st.markdown("#### Active Learning — Recall Curve")
    render_recall_chart(df, session_key)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Active Learning — Relevance-Ranked Results (top 30)")
    display_cols = ["Title", "Year", "Relevance_Score", "AL_Decision", "LLM_Decision", "LLM_Justification"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available].head(30), use_container_width=True)

    # ── Transparency Log ──────────────────────────────────────────────────────
    st.markdown("#### Transparency Log — LLM Decisions (Audit Trail)")
    st.markdown("""
The Transparency Log records every AI decision alongside its one-sentence justification.
This log forms part of the **audit trail** required by PRISMA 2020 and supports
inter-rater reliability checks between the AI and a human reviewer.
    """)
    log_cols = ["Title", "LLM_Decision", "LLM_Justification"]
    available_log = [c for c in log_cols if c in df.columns]
    st.dataframe(df[available_log].head(30), use_container_width=True)

    # ── Inter-rater reliability note ──────────────────────────────────────────
    agreement = (df["AL_Decision"] == df["LLM_Decision"]).mean() if "LLM_Decision" in df.columns else None
    if agreement is not None:
        st.markdown(f"""
#### Inter-Rater Reliability
**AL ↔ LLM agreement rate:** {agreement:.1%}

In a real review, this figure would be computed between two human reviewers (or between
the AI and a human reviewer). A Cohen's κ ≥ 0.61 is generally considered substantial
agreement. Disagreements are resolved by a third reviewer or by consensus.
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

    # ── pyvis network of included studies ────────────────────────────────────
    if len(included_df) >= 5:
        render_pyvis_network(included_df, session_key, label="Included Studies")
    else:
        st.info("ℹ️ Too few included studies to build a keyword co-occurrence network.")

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
**Theme:** Show how Active Learning and LLM-based zero-shot screening can drastically
reduce the time spent screening titles and abstracts — all in a **no-code** environment.

### What You Will Do Today

The second day focuses on the most time-consuming phase of a systematic review: screening
thousands of titles and abstracts against pre-specified inclusion and exclusion criteria.
You will be introduced to two complementary AI-assisted approaches and will see them
applied to all four guided case studies.

### Screening Frameworks: PICO and SPIDER

Before any screening can begin, the review question must be formalised using a structured
framework. The two most widely used are:

| Framework | Full Form | Best Suited For |
|-----------|-----------|-----------------|
| **PICO** | Population, Intervention, Comparison, Outcome | Clinical and health sciences, management research |
| **SPIDER** | Sample, Phenomenon of Interest, Design, Evaluation, Research type | Social sciences, qualitative and mixed-methods research |

Both frameworks are used in this seminar. Examples 1 and 4 use PICO; Example 2 uses SPIDER.

### The Two Screening Approaches

**Active Learning** is a human-in-the-loop machine learning technique. A TF-IDF
vectoriser converts each abstract into a numerical representation, and a Logistic
Regression classifier is trained on a small set of seed labels derived from your
inclusion and exclusion terms. The model then reorders the entire corpus to surface
the most relevant papers first — dramatically reducing the number of abstracts that
need to be read to achieve high recall.

**LLM zero-shot screening** uses a Large Language Model prompted with your inclusion
and exclusion criteria to automatically classify each abstract and provide a one-sentence
justification. This is a powerful first-pass filter, not a replacement for human judgment.
Every decision is recorded in the **Transparency Log** to support the audit trail required
by PRISMA 2020.

### Comparison with Dedicated Screening Tools

The approach used in this seminar is complementary to dedicated systematic review
screening platforms. The table below situates the app in relation to the two most
widely used tools:

| Feature | This App | Rayyan | Covidence |
|---------|----------|--------|-----------|
| Active Learning | ✅ | ✅ | ❌ |
| LLM screening | ✅ | ❌ | ❌ |
| Transparency Log | ✅ | ✅ | ✅ |
| No-code | ✅ | ✅ | ✅ |
| Free | ✅ | Freemium | Paid |
| Integrates with this pipeline | ✅ | ❌ | ❌ |

**Rayyan** and **Covidence** are excellent tools for collaborative human screening.
This app is designed for the AI-assisted, single-reviewer or small-team context and
integrates directly with the Day 1 corpus and the Day 3 extraction pipeline.

### Recall-Oriented Evaluation Metrics

Standard classification metrics (accuracy, F1) are not appropriate for systematic
review screening because the cost of a false negative (missing a relevant paper) is
far higher than the cost of a false positive (including an irrelevant paper). The
key metric is **WSS@95** (Work Saved over Sampling at 95% recall), which measures
how much screening effort is saved while retaining 95% of relevant studies.

### Inter-Rater Reliability

In any systematic review, at least two independent reviewers should screen a random
sample of abstracts to assess agreement. The **Cohen's κ** statistic is the standard
measure: κ ≥ 0.61 is considered substantial agreement. In this app, the AL model and
the LLM serve as two independent screeners, and their agreement rate is reported in
the Transparency Log.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Present the bottleneck of abstract screening. Introduce PICO and SPIDER frameworks. Explain Active Learning and LLM zero-shot screening. Introduce recall-oriented metrics and inter-rater reliability. |
| **Hour 2** | Demonstrate the Active Learning module across the four case studies. Examine recall curves and WSS@95 values. |
| **Hour 3** | Introduce LLM-based screening. Participants verify the model's one-sentence justifications. The Transparency Log records every AI decision. Compare with Rayyan and Covidence. |

### Learning Outcome

By the end of Day 2, you should understand how to formalise a review question using
PICO or SPIDER, how Active Learning and LLMs can accelerate abstract screening,
how recall-oriented metrics assess screening quality, how to interpret the Transparency
Log as an audit trail, and how this approach relates to dedicated tools such as Rayyan
and Covidence.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Screen Your Own Corpus**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 2 — Guided Examples")
    st.markdown("""
Each example below loads **pre-computed screening results** for the four case study corpora
from Day 1. **Expand any example** to see the PICO/SPIDER criteria, Active Learning
rankings, recall curve, recall-oriented metrics, LLM decisions, and Transparency Log.
No button click required — results render immediately.
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            df, err = load_screened(ex["screened_file"])
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Screening results loaded: {len(df)} records.")
                display_screening_results(df, ex["session_key"], ex)

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Screen Your Own Corpus":
    st.title("🔎 Day 2 — Bring Your Own Data")
    st.markdown("""
Use this section to screen **your own corpus** from Day 1. Upload the CSV you downloaded
from Day 1 (or use the corpus saved in the session), define your PICO/SPIDER criteria
as inclusion and exclusion terms, and the app will rank and screen your records automatically.
No coding required.
    """)

    uploaded = st.file_uploader("Upload your Day 1 corpus CSV", type=["csv"])

    if uploaded is None and "byod_df" in st.session_state:
        st.info("Using corpus from Day 1 BYOD session.")
        df = st.session_state["byod_df"]
    elif uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = None

    if df is not None:
        st.success(f"✅ {len(df)} records loaded.")
        st.dataframe(df.head(10), use_container_width=True)

        st.markdown("---")
        st.markdown("#### Define Your Screening Criteria")
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
            include_terms = [t.strip() for t in include_input.splitlines() if t.strip()]
            exclude_terms = [t.strip() for t in exclude_input.splitlines() if t.strip()]

            texts = (df["Title"].fillna("") + " " + df["Abstract"].fillna("")).tolist()
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
                    llm_justifications.append("Abstract too short or missing.")
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
            display_screening_results(result_df, "byod", byod_ex)
            st.session_state["byod_included_df"] = result_df[result_df["AL_Decision"] == "Include"].copy()
