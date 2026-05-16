"""
Day 1 — From Query to Corpus
Four guided examples (Health, Social Science, Engineering, Business) + BYOD extension.
Guided examples load exclusively from pre-cached CSVs — no live API calls required.
All outputs render immediately when the expander is opened — no button click needed.
No coding required.

APIs covered: OpenAlex, Crossref, Semantic Scholar, Europe PMC
BYOD inputs: Boolean query (4 APIs), RIS/BibTeX file upload, Zotero connection
Outputs: CSV download, RIS export, Query Log, Interactive Bibliometric Map
"""

import io
import os
import json
import time
import pathlib
import requests
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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
        "description": """
**Research question:** What is the empirical evidence on the relationship between Corporate
Social Responsibility (CSR) activities and firm financial performance (ROA, ROE, Tobin's Q)?

**Search strategy:** Targets empirical studies measuring the CSR–financial performance link,
excluding purely theoretical or conceptual papers.

**Why this topic?** One of the most heavily meta-analysed topics in management research,
supporting a pooled effect size computation on Day 3.
        """,
    },
]

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


def render_bibliometric_map(df, session_key):
    """Render a simple keyword co-occurrence bar chart as a bibliometric map."""
    st.markdown("#### Interactive Bibliometric Map — Top Keywords / Concepts")
    if "Concepts" not in df.columns:
        st.info("No concept data available for this corpus.")
        return
    all_concepts = []
    for row in df["Concepts"].dropna():
        all_concepts.extend([c.strip() for c in str(row).split(";") if c.strip()])
    if not all_concepts:
        st.info("No concept data available for this corpus.")
        return
    from collections import Counter
    counts = Counter(all_concepts).most_common(20)
    labels = [c[0] for c in counts]
    values = [c[1] for c in counts]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels[::-1], values[::-1], color="#4C72B0")
    ax.set_xlabel("Frequency across corpus")
    ax.set_title("Top 20 Concepts / Keywords in Corpus")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    st.image(buf, use_container_width=True)
    st.download_button(
        "⬇️ Download Bibliometric Map (PNG)",
        buf.getvalue(),
        f"{session_key}_bibliometric_map.png",
        "image/png",
        key=f"dl_bib_{session_key}",
    )


def df_to_ris(df):
    """Convert a corpus DataFrame to RIS format string."""
    lines = []
    for _, row in df.iterrows():
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
        lines.append("ER  - ")
        lines.append("")
    return "\n".join(lines)


def display_corpus(df, source_label, session_key):
    """Show stats, preview, year chart, bibliometric map, and download buttons."""
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
            .astype(int)
            .value_counts()
            .sort_index()
        )
        st.markdown("#### Publication Year Distribution")
        st.bar_chart(year_counts)

    # Bibliometric map
    render_bibliometric_map(df, session_key)

    # Downloads: CSV and RIS
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

def query_openalex_live(search_query, per_page=50, max_pages=2):
    base = "https://api.openalex.org/works"
    params = {
        "search": search_query,
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
        title = " ".join(item.get("title", [])).strip()
        authors = "; ".join(
            f"{a.get('family', '')} {a.get('given', '')}".strip()
            for a in item.get("author", [])[:5]
        )
        year = ""
        pub = item.get("published", {})
        dp = pub.get("date-parts", [[]])
        if dp and dp[0]:
            year = str(dp[0][0])
        venue = " ".join(item.get("container-title", [])).strip()
        abstract = item.get("abstract", "") or ""
        rows.append({
            "ID": item.get("DOI", ""),
            "DOI": item.get("DOI", ""),
            "Title": title,
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
        "limit": min(per_page, 100),
        "fields": "paperId,externalIds,title,year,authors,venue,abstract,citationCount",
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    items = r.json().get("data", [])
    rows = []
    for item in items:
        doi = (item.get("externalIds") or {}).get("DOI", "")
        authors = "; ".join(
            a.get("name", "") for a in (item.get("authors") or [])[:5]
        )
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
        "format": "json",
        "pageSize": min(per_page, 100),
        "resultType": "core",
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    items = r.json().get("resultList", {}).get("result", [])
    rows = []
    for item in items:
        rows.append({
            "ID": item.get("id", ""),
            "DOI": item.get("doi", "") or "",
            "Title": (item.get("title", "") or "").strip(),
            "Year": item.get("pubYear", ""),
            "Authors": item.get("authorString", "") or "",
            "Venue": item.get("journalTitle", "") or "",
            "Abstract": item.get("abstractText", "") or "",
            "Citations": item.get("citedByCount", 0),
            "Concepts": "",
        })
    return pd.DataFrame(rows)


def openalex_to_df(records):
    rows = []
    for r in records:
        inv = r.get("abstract_inverted_index") or {}
        if inv:
            try:
                max_pos = max(p for positions in inv.values() for p in positions)
                words = [""] * (max_pos + 1)
                for word, positions in inv.items():
                    for p in positions:
                        if 0 <= p <= max_pos:
                            words[p] = word
                abstract = " ".join(words).strip()
            except Exception:
                abstract = ""
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
| **Hour 3** | Use the Streamlit app to run automated deduplication. Participants inspect the output, compare field completeness, export a clean CSV or RIS file for Zotero, and explore the Interactive Bibliometric Map of their corpus. |

### Input Flexibility: Multiple Entry Points

Participants do not need to start from a Boolean query. The BYOD section accepts:

| Input Type | When to Use |
|------------|-------------|
| **Boolean Query** | Starting a review from scratch |
| **RIS / BibTeX File** | Already searched traditional databases (PubMed, Scopus, Web of Science) |
| **Zotero Integration** | Already using a reference manager — connect your cloud or self-hosted library |

### Learning Outcome

By the end of Day 1, you should be able to formulate a search strategy, understand how
open APIs retrieve bibliographic metadata, follow the logic by which the app converts API
responses into a clean, deduplicated corpus ready for screening, and interpret a basic
bibliometric map of your corpus.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Query**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES — all render immediately, no button required
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 1 — Guided Examples")
    st.markdown("""
Each example below loads a pre-built corpus of 150 records from OpenAlex.
**Expand any example** to see the corpus preview, year distribution chart,
Interactive Bibliometric Map, and download buttons (CSV and RIS).
No button click required — everything renders immediately.
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            st.markdown(ex["description"])
            st.markdown(f"**API source:** {ex['source']} &nbsp;|&nbsp; **Query:** `{ex['query']}`")

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
                "Semantic Scholar (STEM, CS, Biomedical)",
                "Europe PMC (Life sciences, health)",
            ],
        )
        query_input = st.text_input(
            "Enter your search query (e.g. 'machine learning clinical diagnosis')",
            placeholder="e.g. telemedicine chronic disease management outcomes",
        )
        per_page = st.slider("Records per page", min_value=10, max_value=100, value=50, step=10)
        max_pages = st.slider("Number of pages to retrieve", min_value=1, max_value=5, value=2)

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
                        display_corpus(df, f"Custom query: '{query_input.strip()}'", "byod")

                        log = {
                            "query": query_input.strip(),
                            "api": api_name,
                            "per_page": per_page,
                            "max_pages": max_pages if "OpenAlex" in api_choice else 1,
                            "records_retrieved": before,
                            "records_after_dedup": after,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                        }
                        st.markdown("#### Query Log (for reproducibility)")
                        st.json(log)
                        log_bytes = json.dumps(log, indent=2).encode("utf-8")
                        st.download_button(
                            "⬇️ Download Query Log",
                            log_bytes, "query_log.json", "application/json",
                            key="dl_log",
                        )
                    except Exception as e:
                        st.error(f"Error retrieving data: {e}")

    # ── Option 2: RIS / BibTeX Upload ─────────────────────────────────────────
    elif input_method == "📄 Upload RIS / BibTeX file":
        st.markdown("""
#### Upload an Existing RIS or BibTeX File

If you have already searched traditional databases (PubMed, Scopus, Web of Science,
CINAHL, PsycINFO, etc.) and exported the results as a **RIS** or **BibTeX** file,
upload it here. The app will parse the file, deduplicate the records, and produce
the same corpus preview, year chart, bibliometric map, and export options as the
guided examples.
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

Your credentials are used only for this session and are never stored.
        """)
        zotero_user_id = st.text_input("Zotero User ID", placeholder="e.g. 1234567")
        zotero_api_key = st.text_input("Zotero API Key", type="password", placeholder="Your personal API key")
        zotero_collection = st.text_input(
            "Collection name or key (optional — leave blank to retrieve all items)",
            placeholder="e.g. MySystematicReview",
        )

        if st.button("▶ Connect to Zotero", key="run_zotero"):
            if not zotero_user_id.strip() or not zotero_api_key.strip():
                st.warning("Please enter both your Zotero User ID and API Key.")
            else:
                with st.spinner("Connecting to Zotero…"):
                    try:
                        headers = {"Zotero-API-Key": zotero_api_key.strip()}
                        url = f"https://api.zotero.org/users/{zotero_user_id.strip()}/items"
                        params = {"format": "json", "limit": 100, "itemType": "journalArticle"}
                        r = requests.get(url, headers=headers, params=params, timeout=30)
                        r.raise_for_status()
                        items = r.json()
                        rows = []
                        for item in items:
                            data = item.get("data", {})
                            creators = data.get("creators", [])
                            authors = "; ".join(
                                f"{c.get('lastName', '')} {c.get('firstName', '')}".strip()
                                for c in creators[:5]
                            )
                            rows.append({
                                "ID": item.get("key", ""),
                                "DOI": data.get("DOI", "") or "",
                                "Title": data.get("title", "").strip(),
                                "Year": str(data.get("date", ""))[:4],
                                "Authors": authors,
                                "Venue": data.get("publicationTitle", "") or "",
                                "Abstract": data.get("abstractNote", "") or "",
                                "Citations": "",
                                "Concepts": "",
                            })
                        df = pd.DataFrame(rows)
                        before = len(df)
                        df = deduplicate_df(df)
                        after = len(df)
                        st.info(f"Retrieved {before} records from Zotero. Deduplication removed {before - after} duplicates ({before} → {after}).")
                        display_corpus(df, "Zotero library", "byod_zotero")
                    except requests.HTTPError as e:
                        if e.response.status_code == 403:
                            st.error("Access denied. Please check your API key and User ID.")
                        else:
                            st.error(f"Zotero API error: {e}")
                    except Exception as e:
                        st.error(f"Error connecting to Zotero: {e}")
