"""
Day 1 — From Query to Corpus
Four guided examples (Health, Social Science, Engineering, Business) + BYOD extension.
No coding required: all operations are available through the menus on the left.
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

# ── Robust cache directory ─────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent
if _repo_root.name == "pages":
    _repo_root = _repo_root.parent
CACHE_DIR = str(_repo_root / "data" / "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── helpers ────────────────────────────────────────────────────────────────────

def load_or_fetch_json(cache_path, fetch_fn):
    """Load from cache if available, otherwise fetch and save."""
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    data = fetch_fn()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def query_openalex(search_query, per_page=50, max_pages=2):
    """Query the OpenAlex Works API and return a list of record dicts."""
    base = "https://api.openalex.org/works"
    params = {
        "search": search_query,
        "filter": "has_abstract:true,type:article",
        "per_page": per_page,
        "select": "id,doi,title,publication_year,authorships,host_venue,abstract_inverted_index,cited_by_count,concepts",
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
    """Flatten a list of OpenAlex work records into a tidy DataFrame."""
    rows = []
    for r in records:
        # Reconstruct abstract from inverted index
        inv = r.get("abstract_inverted_index") or {}
        if inv:
            max_pos = max(p for positions in inv.values() for p in positions)
            words = [""] * (max_pos + 1)
            for word, positions in inv.items():
                for p in positions:
                    words[p] = word
            abstract = " ".join(words).strip()
        else:
            abstract = ""

        authors = "; ".join(
            a.get("author", {}).get("display_name", "") or ""
            for a in (r.get("authorships") or [])[:5]
        )
        venue = (r.get("host_venue") or {}).get("display_name", "")
        concepts = "; ".join(
            c.get("display_name", "") for c in (r.get("concepts") or [])[:5]
        )
        rows.append({
            "ID": r.get("id", ""),
            "DOI": r.get("doi", ""),
            "Title": r.get("title", ""),
            "Year": r.get("publication_year", ""),
            "Authors": authors,
            "Venue": venue,
            "Abstract": abstract,
            "Citations": r.get("cited_by_count", 0),
            "Concepts": concepts,
        })
    return pd.DataFrame(rows)


def query_semantic_scholar(search_query, limit=50):
    """Query the Semantic Scholar Graph API."""
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": search_query,
        "limit": limit,
        "fields": "paperId,externalIds,title,year,authors,venue,abstract,citationCount,fieldsOfStudy",
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def semantic_scholar_to_df(records):
    """Flatten Semantic Scholar records into a tidy DataFrame."""
    rows = []
    for r in records:
        authors = "; ".join(a.get("name", "") for a in (r.get("authors") or [])[:5])
        fields = "; ".join(r.get("fieldsOfStudy") or [])
        doi = (r.get("externalIds") or {}).get("DOI", "")
        rows.append({
            "ID": r.get("paperId", ""),
            "DOI": doi,
            "Title": r.get("title", ""),
            "Year": r.get("year", ""),
            "Authors": authors,
            "Venue": r.get("venue", ""),
            "Abstract": r.get("abstract", "") or "",
            "Citations": r.get("citationCount", 0),
            "Fields": fields,
        })
    return pd.DataFrame(rows)


def deduplicate_df(df):
    """Remove duplicate records based on DOI (when available) then title similarity."""
    # DOI-based deduplication
    has_doi = df[df["DOI"].str.strip().str.len() > 0].copy()
    no_doi = df[df["DOI"].str.strip().str.len() == 0].copy()
    has_doi_deduped = has_doi.drop_duplicates(subset=["DOI"], keep="first")
    # Title-based deduplication for records without DOI
    no_doi["_title_norm"] = no_doi["Title"].str.lower().str.strip()
    no_doi_deduped = no_doi.drop_duplicates(subset=["_title_norm"], keep="first").drop(columns=["_title_norm"])
    result = pd.concat([has_doi_deduped, no_doi_deduped], ignore_index=True)
    return result


def save_and_display_result(df, source_label, day2_key):
    """Show preview, download button, and Day 2 handoff."""
    st.success(f"✅ Loaded {len(df)} records from {source_label}.")
    st.markdown("#### Preview (first 20 rows)")
    st.dataframe(df.head(20), use_container_width=True)

    # Year distribution chart
    if "Year" in df.columns and df["Year"].notna().any():
        year_counts = df["Year"].value_counts().sort_index()
        st.markdown("#### Publication Year Distribution")
        st.bar_chart(year_counts)

    # Download
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download corpus as CSV",
        csv_bytes,
        f"{day2_key}_corpus.csv",
        "text/csv",
        key=f"dl_{day2_key}",
    )

    # Session state handoff to Day 2
    st.session_state[f"{day2_key}_df"] = df
    st.info("✅ Corpus saved. Go to **Day 2 → From Corpus to Included Studies** when you are ready.")


# ── sidebar ────────────────────────────────────────────────────────────────────

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
**Theme:** Help participants understand how to use open APIs for programmatic literature
collection and how to automatically deduplicate records in a no-code setting.

### What You Will Do Today

The first day introduces the logic of programmatic literature collection. The session begins
with the formulation of search strategies — such as the **PICO framework** for health sciences
or **SPIDER** for social sciences — and the identification of suitable open APIs, including
**OpenAlex**, **Crossref**, and **Semantic Scholar**.

Participants are shown how API-based retrieval differs from manual database searching and
how it facilitates reproducibility. Because APIs evolve and results may change over time,
reproducibility requires logging queries and timestamps — a practice the app supports
automatically.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Introduce the logic of programmatic literature collection. Clarify the difference between manual database searches and open API retrieval. Present discipline-spanning examples and explain how query timestamps are logged for reproducibility. |
| **Hour 2** | Demonstrate query building and API access. Show how to translate research questions into Boolean queries and retrieve metadata from OpenAlex, Crossref, and Semantic Scholar. |
| **Hour 3** | Use the Streamlit app to run automated deduplication. Participants inspect the output, compare field completeness, and export a clean CSV. An Interactive Bibliometric Map module visualizes co-author networks and recurring keywords from the retrieved metadata. |

### Learning Outcome

By the end of Day 1, you should be able to formulate a search strategy, understand how open
APIs retrieve bibliographic metadata, follow the logic by which the app converts API responses
into a clean, deduplicated corpus ready for screening, and interpret a basic bibliometric map
of your corpus.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Query**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 1 — Guided Examples")
    st.markdown("""
Each example below uses a real public API with a pre-configured research question drawn from
a different academic discipline. Click **▶ Run this example** to fetch the data, inspect the
corpus, and save it for Day 2.
    """)

    # ── Example 1: Health Sciences ────────────────────────────────────────────
    st.markdown("---")
    with st.expander("🏥 Example 1 — Health Sciences: Health Inequalities in Chronic Disease Care", expanded=False):
        st.markdown("""
**Source:** [OpenAlex API](https://openalex.org)

**Research question:** What does the empirical literature say about socioeconomic health
inequalities in the care and outcomes of patients with chronic diseases such as diabetes,
hypertension, and cardiovascular disease?

**Search strategy:** The query uses a Boolean combination of terms covering *health inequalities*,
*socioeconomic* factors, and *diabetes care* — a standard PICO-informed search for this topic.

**Why this topic?** Health inequalities in chronic disease care is one of the most active areas
of systematic review in health sciences. The corpus is large (>37,000 articles), well-structured,
and supports a full PICO extraction and meta-analysis on Day 3.
        """)
        if st.button("▶ Run Example 1 — Health Inequalities", key="run_ex1"):
            cache_path = os.path.join(CACHE_DIR, "day1_ex1_health_raw.json")
            def fetch_health():
                return query_openalex("health inequalities diabetes care socioeconomic", per_page=50, max_pages=2)
            with st.spinner("Querying OpenAlex for health inequalities in chronic disease care…"):
                try:
                    records = load_or_fetch_json(cache_path, fetch_health)
                    df = openalex_to_df(records)
                    df = deduplicate_df(df)
                    save_and_display_result(df, "OpenAlex — Health Inequalities in Chronic Disease Care", "ex1_health")
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Example 2: Social Sciences ────────────────────────────────────────────
    st.markdown("---")
    with st.expander("🏛️ Example 2 — Social Sciences: Universal Basic Income (UBI) Policy Outcomes", expanded=False):
        st.markdown("""
**Source:** [Semantic Scholar API](https://www.semanticscholar.org)

**Research question:** What are the empirically measured outcomes of Universal Basic Income
(UBI) programmes and pilots in terms of employment, poverty, and well-being?

**Search strategy:** The query targets empirical policy evaluations of UBI, excluding
opinion pieces, editorials, and grey literature.

**Why this topic?** UBI is one of the most actively debated policy interventions in the
social sciences. The corpus is well-populated and spans economics, sociology, and political
science — making it ideal for a cross-disciplinary narrative synthesis on Day 3.
        """)
        if st.button("▶ Run Example 2 — UBI Policy Outcomes", key="run_ex2"):
            cache_path = os.path.join(CACHE_DIR, "day1_ex2_ubi_raw.json")
            def fetch_ubi():
                return query_semantic_scholar("universal basic income policy evaluation outcomes", limit=50)
            with st.spinner("Querying Semantic Scholar for UBI policy outcomes…"):
                try:
                    records = load_or_fetch_json(cache_path, fetch_ubi)
                    df = semantic_scholar_to_df(records)
                    df = deduplicate_df(df)
                    save_and_display_result(df, "Semantic Scholar — UBI Policy Outcomes", "ex2_ubi")
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Example 3: Science / Engineering ─────────────────────────────────────
    st.markdown("---")
    with st.expander("⚗️ Example 3 — Science / Engineering: Microplastic Pollution in Aquatic Environments", expanded=False):
        st.markdown("""
**Source:** [OpenAlex API](https://openalex.org)

**Research question:** What does the experimental literature report about the concentration,
distribution, and ecological impact of microplastic pollution in aquatic environments?

**Search strategy:** The query combines *microplastics* with *aquatic* or *marine* environments,
targeting experimental and observational studies.

**Why this topic?** Microplastic pollution is one of the fastest-growing areas of environmental
systematic review. The corpus is large, methodologically diverse, and supports a quantitative
synthesis of concentration estimates on Day 3.
        """)
        if st.button("▶ Run Example 3 — Microplastics", key="run_ex3"):
            cache_path = os.path.join(CACHE_DIR, "day1_ex3_microplastics_raw.json")
            def fetch_micro():
                return query_openalex("microplastics aquatic marine pollution concentration", per_page=50, max_pages=2)
            with st.spinner("Querying OpenAlex for microplastic pollution in aquatic environments…"):
                try:
                    records = load_or_fetch_json(cache_path, fetch_micro)
                    df = openalex_to_df(records)
                    df = deduplicate_df(df)
                    save_and_display_result(df, "OpenAlex — Microplastic Pollution in Aquatic Environments", "ex3_microplastics")
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Example 4: Management / Business ─────────────────────────────────────
    st.markdown("---")
    with st.expander("💼 Example 4 — Management / Business: CSR and Firm Financial Performance", expanded=False):
        st.markdown("""
**Source:** [OpenAlex API](https://openalex.org)

**Research question:** What is the empirical evidence on the relationship between Corporate
Social Responsibility (CSR) activities and firm financial performance (e.g., ROA, ROE,
Tobin's Q)?

**Search strategy:** The query targets empirical studies measuring the CSR–financial
performance link, excluding purely theoretical or conceptual papers.

**Why this topic?** CSR and firm performance is one of the most heavily meta-analysed topics
in management research (>42,000 articles). It supports a pooled effect size computation
(correlation coefficient meta-analysis) on Day 3, making it an ideal business school example.
        """)
        if st.button("▶ Run Example 4 — CSR and Firm Performance", key="run_ex4"):
            cache_path = os.path.join(CACHE_DIR, "day1_ex4_csr_raw.json")
            def fetch_csr():
                return query_openalex("corporate social responsibility firm financial performance empirical", per_page=50, max_pages=2)
            with st.spinner("Querying OpenAlex for CSR and firm financial performance…"):
                try:
                    records = load_or_fetch_json(cache_path, fetch_csr)
                    df = openalex_to_df(records)
                    df = deduplicate_df(df)
                    save_and_display_result(df, "OpenAlex — CSR and Firm Financial Performance", "ex4_csr")
                except Exception as e:
                    st.error(f"Error: {e}")

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
        ["OpenAlex (recommended for most disciplines)", "Semantic Scholar (strong for CS, Biomedicine)"],
    )
    query_input = st.text_input(
        "Enter your search query (Boolean terms, e.g. 'machine learning clinical diagnosis')",
        placeholder="e.g. telemedicine chronic disease management outcomes",
    )
    per_page = st.slider("Records per page", min_value=10, max_value=100, value=50, step=10)
    max_pages = st.slider("Number of pages to retrieve", min_value=1, max_value=5, value=2)

    if st.button("▶ Run My Query", key="run_byod") and query_input.strip():
        with st.spinner(f"Querying {'OpenAlex' if 'OpenAlex' in api_choice else 'Semantic Scholar'}…"):
            try:
                if "OpenAlex" in api_choice:
                    records = query_openalex(query_input.strip(), per_page=per_page, max_pages=max_pages)
                    df = openalex_to_df(records)
                else:
                    records = query_semantic_scholar(query_input.strip(), limit=per_page)
                    df = semantic_scholar_to_df(records)

                before = len(df)
                df = deduplicate_df(df)
                after = len(df)
                st.info(f"Deduplication removed {before - after} duplicate records ({before} → {after}).")
                save_and_display_result(df, f"Custom query: '{query_input.strip()}'", "byod")

                # Save query log
                log = {
                    "query": query_input.strip(),
                    "api": api_choice,
                    "per_page": per_page,
                    "max_pages": max_pages,
                    "records_retrieved": before,
                    "records_after_dedup": after,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                }
                st.markdown("#### Query Log (for reproducibility)")
                st.json(log)
                log_bytes = json.dumps(log, indent=2).encode("utf-8")
                st.download_button("⬇️ Download Query Log", log_bytes, "query_log.json", "application/json", key="dl_log")

            except Exception as e:
                st.error(f"Error retrieving data: {e}")
    elif st.button("▶ Run My Query", key="run_byod_empty"):
        st.warning("Please enter a search query above.")
