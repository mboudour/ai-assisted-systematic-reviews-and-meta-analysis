"""
AI-Assisted Systematic Reviews and Meta-Analysis — Workshop
Landing page: seminar overview, workflow architecture, worked examples, and BYOD limits.
"""

import streamlit as st

st.set_page_config(
    page_title="AI-Assisted Systematic Reviews and Meta-Analysis",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔬 AI-Assisted Systematic Reviews and Meta-Analysis")
st.subheader("A Three-Day Academic Workshop — June 10, 11 & 12, 2026")

st.markdown("""
**Instructor:** Moses Boudourides, Data Science Graduate Program,
School of Professional Studies, Northwestern University

> **📋 Registration**
> **[Register now at instats.org](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta)**
""")

st.markdown("---")

# ── No-Code Identity ───────────────────────────────────────────────────────────
st.markdown("""
### A No-Code Seminar for Researchers

This seminar is conceived as a **no-code** research methods workshop: participants are not
expected to write or modify a single line of code. It is designed for early-career academic
professionals, advanced doctoral students, and researchers across a wide range of disciplines
—from the health and life sciences to the social sciences, humanities, and engineering.

Participants work through a guided workflow via this Streamlit application. The app provides
menus for cached teaching examples, live or uploaded Day 1 inputs, deterministic Day 2 practice
screening, and Day 3 extraction/synthesis options. A parallel code repository containing scripts
in **Python** and **R** is provided for transparency; interacting with it is optional.

The seminar focuses on how academic literature can be navigated, screened, and synthesized with
explicit validation and human verification. Some workshop material demonstrates AI-assisted
methods, but the current BYOD Day 2 screening path is a simple deterministic keyword heuristic,
not a live LLM: its decisions require human review. Provider coverage, metadata quality, and
retrieval caps also affect every result.
""")

st.markdown("---")

# ── Navigation ─────────────────────────────────────────────────────────────────
st.markdown("### How to Navigate")
st.markdown("""
Use the **sidebar** to select a day. Each day has guided examples plus a BYOD extension. The
worked examples are connected by menus, but their checked-in inputs are teaching snapshots—not
a verified historical end-to-end search.

| Day | Date | Theme | Main Objective |
|-----|------|-------|----------------|
| **Day 1** | June 10 | From Query to Corpus | Use search menus to inspect cached examples, try suggested searches, or retrieve/upload a corpus |
| **Day 2** | June 11 | From Corpus to Included Studies | Review cached screening examples or run deterministic keyword screening on a supplied corpus |
| **Day 3** | June 12 | From Studies to Evidence | Use illustrative teaching fixtures or carry a Day 2 BYOD included-studies CSV into extraction and synthesis |
""")

st.info("👈 Select a day from the sidebar to begin.")

st.markdown("---")

# ── 5-Module Architecture ──────────────────────────────────────────────────────
st.markdown("### App Architecture: Five Workflow Modules")
st.markdown("""
The app is modular: participants can start with a search, upload an existing corpus, or enter
with already included studies. The menus make those entry points visible without requiring code.

| Module | Function | What Participants Can Do |
|--------|----------|--------------------------|
| **1. Search & Collect** | Retrieve or load metadata | Open a Day 1 guided example, use a bounded provider search, or upload RIS |
| **2. Deduplicate** | Clean the corpus | Inspect API results or uploaded records and download a corpus CSV/RIS; provider fields and coverage differ |
| **3. Screen** | Triage and verify records | Upload a Day 1 CSV, enter inclusion/exclusion terms, run the deterministic heuristic, inspect the full screening log, and verify decisions manually |
| **4. Extract** | Pull structured fields from study inputs | Upload included studies, choose a schema, and use the available NLP/AI extraction options; extracted values are drafts for verification |
| **5. Synthesize & Map** | Visualise and export | Produce teaching or BYOD charts, PRISMA-style diagrams, networks, tables, and downloadable outputs; interpret counts according to their provenance |
""")

st.markdown("---")

# ── Input Flexibility ──────────────────────────────────────────────────────────
st.markdown("### Input Flexibility: Multiple Entry Points")
st.markdown("""
The app accepts several input types rather than forcing everyone into one narrow workflow.

| Input Type | Use Case | App Behaviour |
|------------|----------|---------------|
| **API Search** | Starting a review from scratch | Day 1 presents provider-specific search menus. OpenAlex accepts a per-user key and bounded retrieval; the query log records search metadata, not credentials |
| **RIS / CSV File** | Already searched databases or a previous app step | Upload and continue to deduplication, screening, or synthesis |
| **Zotero Integration** | Uses a reference manager | Use the Day 1 Zotero path or an exported library as an alternative starting corpus |
| **PDF Documents / Included CSV** | Already completed screening | Continue to Day 3 extraction and synthesis; outputs still require checking |
""")

st.markdown("---")

# ── Four Guided Case Studies ───────────────────────────────────────────────────
st.markdown("### Four Guided Case Studies")
st.markdown("""
The Day 1 guided menu shows four discipline-spanning examples. Opening an example loads its
cached teaching corpus and offers a **clickable practice search** that suggests query text,
years, publication types, and other menu settings in the BYOD search form. These suggestions are
new practice inputs, not the original provenance of the cached file.

The cached Day 1/Day 2 snapshots do **not** establish a verified historical query string, search
date, filters, or API response. Day 3 guided pages likewise use illustrative/synthetic teaching
fixtures and narratives; they are not a live retrieval, screening, or empirical synthesis run.
For a reproducible review, run your own search, retain its log, and carry the resulting files
through the BYOD path.

| # | Discipline | Topic | Worked teaching emphasis |
|---|-----------|-------|---------------------------|
| 1 | 🏥 **Health Sciences** | Health Inequalities in Chronic Disease Care | PICO framing and Risk Ratio illustration |
| 2 | 🏛️ **Social Sciences** | Universal Basic Income (UBI) Policy Outcomes | SPIDER framing and narrative synthesis illustration |
| 3 | ⚗️ **Science / Engineering** | Microplastic Pollution in Aquatic Environments | Concentration summary and chart illustration |
| 4 | 💼 **Management / Business** | Corporate Social Responsibility & Firm Financial Performance | Correlation/meta-analysis illustration |
""")

st.markdown("---")

# ── BYOD Highlights ────────────────────────────────────────────────────────────
st.markdown("### Bring Your Own Data (BYOD)")
st.markdown("""
Each day includes a BYOD extension so participants can apply the workflow to their own research
question. The live handoff is **Day 1 → Day 2 → Day 3**: download a Day 1 corpus, screen it on
Day 2, then upload the included-studies CSV to Day 3.

**Day 1 BYOD:** Choose a provider from the search menu (OpenAlex, Crossref, Europe PMC, or
best-effort Semantic Scholar), enter a query, select any provider-specific filters, and retrieve a
bounded corpus. OpenAlex retrieval is capped by the configured page size and maximum pages, so a
large result set may be truncated; the query log reports retrieval metadata and should be saved.
Provider syntax, indexing, coverage, and available filters differ. Crossref needs no key, while
Semantic Scholar has an optional masked key and can rate-limit requests. Both retrieve one page
and use provider-specific relevance search, not guaranteed Boolean logic. Abstracts may be missing.
You may instead upload RIS or use Zotero.

**OpenAlex credentials:** each participant supplies their own email-verified OpenAlex key and
email in masked, session-specific inputs. The app sends the key to OpenAlex only as an HTTPS
`Authorization: Bearer` header; the email is not sent with searches. Credentials are not placed
in query logs or error metadata, and the app does not promise complete privacy from the operator
or hosting environment. Participants should use a key they control and consider operator/hosting
trust before entering it.

**Day 2 BYOD:** Upload the Day 1 CSV (or another CSV with titles/abstracts), enter inclusion and
exclusion terms, and run the current deterministic, case-insensitive substring heuristic over
Title + Abstract. It is **not an actual LLM** and does not provide validated recall, precision,
F1, or WSS estimates. Reviewers must inspect the included file and full screening log and make
human eligibility decisions; the log is an audit aid, not proof of correctness.
The Day 2 interactive maps offer concept co-occurrence, title/abstract term co-occurrence, and
co-authorship. Participants can map included studies or all screened records (exploratory only).
Links count records containing both items; author names are not disambiguated.

**Day 3 BYOD:** Carry forward the Day 2 included-studies CSV, choose the extraction schema, and
use the available NLP or optional AI extraction route. Generate tables, charts, networks, and
PRISMA-style outputs as appropriate. These are analysis aids: confirm extracted fields, effect
sizes, denominators, and flow counts against the source studies. The guided Day 3 route is
illustrative/synthetic; only the BYOD route represents a participant-supplied pipeline.
""")

st.markdown("---")

# ── Adjustment Mechanisms ──────────────────────────────────────────────────────
st.markdown("### How Participants Adjust the App to Their Own Data")
st.markdown("""
Participants configure the workflow through menus and uploads rather than editing code. The
settings below affect the live or uploaded run, but do not retroactively describe cached examples.

| Adjustment Area | What the Participant Controls | Why It Matters |
|-----------------|-------------------------------|----------------|
| **Search menu** | Provider, query, search scope, years, publication types, abstract requirement | Records the actual live request and exposes provider differences and retrieval caps |
| **Search log** | Download the query/filter/retrieval metadata produced by a BYOD run | Preserves provenance for that run; it contains no OpenAlex key or email |
| **Screening method** | Inclusion/exclusion terms and human verification of heuristic output | Makes the current Day 2 implementation transparent and prevents treating it as a validated LLM screener |
| **Extraction schema** | PICO, Thematic Synthesis, custom variables, and NLP/optional AI route | Supports heterogeneous questions while requiring source-level checking |
| **Visualisations** | Variables and included records used for plots or maps | Helps tailor outputs without implying that illustrative counts are empirical |
""")

st.markdown("---")

# ── Resources ──────────────────────────────────────────────────────────────────
st.markdown("### Resources")
col1, col2 = st.columns(2)
with col1:
    st.markdown("""
**📋 InStats Seminar Page**
[Register and view full details](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta)
    """)
with col2:
    st.markdown("""
**💻 GitHub Repository**
[View the code and scripts](https://github.com/mboudour/ai-assisted-systematic-reviews-and-meta-analysis)
    """)

st.markdown("---")
st.caption("© 2026 Moses Boudourides · Northwestern University · Built with Streamlit")
