"""
Day 1 — From Query to Corpus
Four guided examples (Health, Social Science, Engineering, Business) + BYOD extension.
Guided examples load exclusively from pre-cached CSVs — no live API calls required.
BYOD section makes live API calls on demand.
No coding required.
"""

import os, json, time, pathlib
import requests
import pandas as pd
import streamlit as st

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
and *diabetes care* — a standard PICO-informed search.

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


def display_corpus(df, source_label, session_key):
    """Show stats, preview, year chart, download button, and Day 2 handoff."""
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

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download corpus as CSV",
        csv_bytes,
        f"{session_key}_corpus.csv",
        "text/csv",
        key=f"dl_{session_key}",
    )

    st.session_state[f"{session_key}_df"] = df
    st.info("✅ Corpus saved to session. Go to **Day 2 → From Corpus to Included Studies** when ready.")


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
open APIs, including **OpenAlex**, **Crossref**, and **Semantic Scholar**.

Participants are shown how API-based retrieval differs from manual database searching
and how it facilitates reproducibility. Because APIs evolve and results may change over
time, reproducibility requires logging queries and timestamps — a practice the app
supports automatically.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Introduce the logic of programmatic literature collection. Clarify the difference between manual database searches and open API retrieval. Present discipline-spanning examples and explain how query timestamps are logged for reproducibility. |
| **Hour 2** | Demonstrate query building and API access. Show how to translate research questions into Boolean queries and retrieve metadata from OpenAlex, Crossref, and Semantic Scholar. |
| **Hour 3** | Use the Streamlit app to run automated deduplication. Participants inspect the output, compare field completeness, and export a clean CSV. |

### Learning Outcome

By the end of Day 1, you should be able to formulate a search strategy, understand how
open APIs retrieve bibliographic metadata, follow the logic by which the app converts API
responses into a clean, deduplicated corpus ready for screening, and interpret a basic
bibliometric map of your corpus.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Query**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 1 — Guided Examples")
    st.markdown("""
Each example below uses a **pre-loaded corpus** retrieved from a real public API.
Click **▶ Load this example** to inspect the corpus, explore the year distribution,
and save it for Day 2. No API call is made — the data is already cached.
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            st.markdown(ex["description"])
            st.markdown(f"**API source:** {ex['source']} &nbsp;|&nbsp; **Query:** `{ex['query']}`")

            btn_key = f"load_{ex['session_key']}"
            if st.button(f"▶ Load Example — {ex['session_key']}", key=btn_key):
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
Enter your search terms below, choose an API, and the app will retrieve, flatten,
and deduplicate the records automatically. No coding required.
    """)

    api_choice = st.selectbox(
        "Select API",
        ["OpenAlex (recommended for most disciplines)"],
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
            with st.spinner("Querying OpenAlex…"):
                try:
                    records = query_openalex_live(query_input.strip(), per_page=per_page, max_pages=max_pages)
                    df = openalex_to_df(records)
                    before = len(df)
                    df = deduplicate_df(df)
                    after = len(df)
                    st.info(f"Deduplication removed {before - after} duplicate records ({before} → {after}).")
                    display_corpus(df, f"Custom query: '{query_input.strip()}'", "byod")

                    log = {
                        "query": query_input.strip(),
                        "api": "OpenAlex",
                        "per_page": per_page,
                        "max_pages": max_pages,
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
