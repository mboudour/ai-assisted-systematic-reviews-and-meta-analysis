"""
Day 2 — From Corpus to Included Studies
Four guided examples (Health, Social Science, Engineering, Business) + BYOD extension.
Guided examples load exclusively from pre-cached screening CSVs.
These are illustrative/cached teaching inputs, not evidence that a historical Day 1
query produced them. No live API calls are made by the guided examples; BYOD can use
the live Day 1 session or a user-supplied download.
No coding required.

Covers: PICO/SPIDER criteria, Active Learning (TF-IDF + Logistic Regression),
LLM zero-shot screening, Transparency Log, recall-oriented metrics,
inter-rater reliability, PRISMA-S, comparison with Rayyan/Covidence.
"""

import os
import io
import re
import pathlib
import sys
import hashlib
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
CACHE_DIR = _repo_root / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from day2_networks import build_network
from day2_network_view import make_network_html
from openaire_notice import OPENAIRE_LIMITATIONS, source_column_mentions_openaire

# ── Guided example definitions ─────────────────────────────────────────────────
GUIDED_EXAMPLES = [
    {
        "label": "🏥 Example 1 — Health Sciences: Health Inequalities in Chronic Disease Care",
        "screened_file": "day2_ex1_health_screened.csv",
        "session_key": "ex1_health",
        "year_from": 2000, "year_to": 2024, "pub_types": ["journal-article"],
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
        "year_from": 2010, "year_to": 2024, "pub_types": ["journal-article", "book-chapter"],
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
        "year_from": 2010, "year_to": 2024, "pub_types": ["journal-article"],
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
        "year_from": 2000, "year_to": 2024, "pub_types": ["journal-article"],
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
        "Choose a set of records and a network. A node is a term, concept or author; "
        "a link means both items occur in the same record. Node size reflects the "
        "number of records containing the item; link width reflects the number "
        "containing both. These are descriptive maps, not evidence of causal relationships."
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
    else:
        st.caption("Authors must be separated by semicolons. Names are matched by case and whitespace only; variants or different people with the same name are not disambiguated. Some Day 1 providers retain only the first five names, so the map can omit co-authors.")

    c1, c2 = st.columns(2)
    with c1:
        top_n = st.slider("Maximum number of nodes", 10, 60, 25, 5, key=f"d2_network_top_{session_key}")
    with c2:
        minimum = st.slider("Minimum records per link", 1, 10, 1, 1, key=f"d2_network_min_{session_key}")
    graph = build_network(selected_df, kind, top_n=top_n, min_cooccurrence=minimum)
    st.caption(f"Usable {kind} data: {graph['records_with_data']} of {graph['total_records']} selected records. "
               f"Shown: {len(graph['nodes'])} nodes and {len(graph['edges'])} links at the selected settings.")
    if not graph["edges"]:
        if not graph["records_with_data"]:
            st.info("No usable data for this network type in the selected records. Try title/abstract terms or another network type.")
        else:
            st.info("No pairs meet these settings. Lower the minimum records per link, increase the node limit, choose all screened records, or use another network type.")
        return
    try:
        graph_html = make_network_html(graph)
    except ValueError as exc:
        st.warning(f"Unable to display the network: {exc}")
    else:
        components.html(graph_html, height=590, scrolling=False)

    labels = {node["id"]: node["label"] for node in graph["nodes"]}
    edge_df = pd.DataFrame([
        {"Source": labels[e["source"]], "Target": labels[e["target"]], "Co-occurring records": e["weight"]}
        for e in graph["edges"]
    ]).sort_values(["Co-occurring records", "Source", "Target"], ascending=[False, True, True])
    node_df = pd.DataFrame([
        {"Node": node["label"], "Records containing node": node["frequency"]}
        for node in graph["nodes"]
    ])
    with st.expander("View and download network data"):
        st.caption("Each record contributes at most once to a node or pair. Files contain the displayed top nodes and links only.")
        st.dataframe(edge_df, use_container_width=True)
        left, right = st.columns(2)
        with left:
            st.download_button("Download network links (CSV)", edge_df.to_csv(index=False).encode("utf-8"),
                               f"{session_key}_{kind}_network_links.csv", "text/csv", key=f"d2_edges_{session_key}")
        with right:
            st.download_button("Download network nodes (CSV)", node_df.to_csv(index=False).encode("utf-8"),
                               f"{session_key}_{kind}_network_nodes.csv", "text/csv", key=f"d2_nodes_{session_key}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_screened(screened_file):
    path = CACHE_DIR / screened_file
    if path.exists():
        try:
            return pd.read_csv(path), None
        except Exception as e:
            return None, str(e)
    return None, f"Screened file not found: {screened_file}"


def render_guided_provenance(ex, df):
    """Explain the checked-in handoff without implying a reproducible historical search."""
    day1_file = ex["screened_file"].replace("day2_", "day1_").replace("_screened", "_corpus")
    day1_path = CACHE_DIR / day1_file
    id_check = "not available"
    day1_count = "not available"
    if day1_path.exists():
        try:
            day1_df = pd.read_csv(day1_path)
            day1_count = len(day1_df)
            if "ID" in day1_df.columns and "ID" in df.columns:
                day1_ids = set(day1_df["ID"].dropna().astype(str))
                day2_ids = set(df["ID"].dropna().astype(str))
                id_check = "match" if day1_ids == day2_ids else (
                    f"do not match ({len(day1_ids - day2_ids)} only in Day 1; "
                    f"{len(day2_ids - day1_ids)} only in Day 2)"
                )
        except Exception as e:
            id_check = f"unavailable ({e})"
    st.info(
        f"**Teaching-input provenance:** this screen is loaded from the checked-in "
        f"`data/cache/{ex['screened_file']}` ({len(df)} rows). The corresponding Day 1 "
        f"corpus file is `data/cache/{day1_file}` "
        f"({'present' if day1_path.exists() else 'not present'}). These files are "
        f"visible as **Day 1 rows = {day1_count}; Day 2 rows = {len(df)}; ID-set check = {id_check}** "
        "(row order may differ). Both are cached teaching snapshots; the repository "
        "does not establish the historical Day 1 search parameters, date, or API response "
        "that produced them. Day 2 displays existing screening labels and criteria and "
        "offers the included-study CSV and full "
        "screening-log downloads below."
    )


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
You will learn about AI-assisted approaches, inspect cached teaching labels for the four
case studies, and explore networks built from the available study metadata.

### Where Day 2 Fits in the Pipeline

**Day 1 → Day 2 → Day 3:** Day 1 supplies a corpus CSV; Day 2 screens that corpus and
offers an **included-studies CSV** plus a **full screening-log CSV**; Day 3 extracts fields
and synthesizes evidence. The guided path uses checked-in teaching snapshots so it can
render without a live search. It is not a reconstruction of the historical Day 1 search:
the checked-in CSVs do not prove the original query string, search date, filters, or API
response. Use **Day 1 → Guided Examples** to inspect/download the example corpus, or
**Day 1 → BYOD** to run or upload your own corpus and download its CSV before using it
here. In a reproducible review, retain the Day 1 query log and search metadata separately.

### Screening Frameworks: PICO and SPIDER

Before any screening can begin, the review question must be formalised using a structured
framework. The two most widely used are:

| Framework | Full Form | Best Suited For |
|-----------|-----------|-----------------|
| **PICO** | Population, Intervention, Comparison, Outcome | Clinical and health sciences, management research |
| **SPIDER** | Sample, Phenomenon of Interest, Design, Evaluation, Research type | Social sciences, qualitative and mixed-methods research |

Both frameworks are used in this seminar. Examples 1 and 4 use PICO; Example 2 uses SPIDER.

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
The teaching snapshot diagnostics are not validated estimates of screening performance.

### Inter-Rater Reliability

In any systematic review, at least two independent reviewers should screen a random
sample of abstracts to assess agreement. The **Cohen's κ** statistic is the standard
measure: κ ≥ 0.61 is considered substantial agreement. In the guided teaching snapshots,
the AL/LLM decision columns are displayed for audit practice; their agreement is
descriptive and does not establish two independently run validated screeners. In BYOD,
both columns are produced by the deterministic heuristic described above.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Present the bottleneck of abstract screening. Introduce PICO and SPIDER frameworks. Explain Active Learning and LLM zero-shot screening. Introduce recall-oriented metrics and inter-rater reliability. |
| **Hour 2** | Inspect the four cached screening examples and their descriptive diagnostics. |
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
    st.markdown("""
Each example below loads **cached screening-result labels** from checked-in teaching CSVs.
The matching Day 1 corpus CSV is shown as a reference input, but these files do not prove
that a particular historical query created the snapshot. **Expand any example** to see the PICO/SPIDER criteria, Active Learning
rankings, recall curve, recall-oriented metrics, LLM decisions, and Transparency Log.
No button click required — results render immediately. Download the included-study CSV or
full screening log at the bottom of each example, then open Day 3 and upload the included
CSV if session carry-over is unavailable.
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            df, err = load_screened(ex["screened_file"])
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Screening results loaded: {len(df)} records.")
                render_guided_provenance(ex, df)
                display_screening_results(df, ex["session_key"], ex)

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Screen Your Own Corpus":
    st.title("🔎 Day 2 — Bring Your Own Data")
    st.markdown("""
Use this section to screen **your own corpus** from Day 1. In Day 1, use the **Download
corpus as CSV** control in a guided example or BYOD result, then upload that file here (or
use the corpus saved in the current session). Define your PICO/SPIDER criteria as inclusion
and exclusion terms, and the app will rank and screen your records automatically using a
deterministic case-insensitive substring heuristic over Title + Abstract (not a live LLM or
independent Active Learning model). The
resulting **included studies CSV** and **full screening log CSV** appear after screening;
download the included file and upload it in Day 3 → **BYOD — Your Own Synthesis**. No coding required.
    """)
    st.caption("Uploaded records and screening results are held by the app in your session, not published by the network visualization. The server operator may have access to session data; use a trusted deployment.")

    uploaded = st.file_uploader("Upload your Day 1 corpus CSV", type=["csv"])

    if uploaded is None and "byod_df" in st.session_state:
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
            digest = hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()
            st.session_state["byod_screening_run"] = {"digest": digest, "results": result_df, "criteria": byod_ex}
            st.session_state["byod_included_df"] = result_df[result_df["AL_Decision"] == "Include"].copy()

        run = st.session_state.get("byod_screening_run")
        if run is not None:
            current_digest = hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()
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
