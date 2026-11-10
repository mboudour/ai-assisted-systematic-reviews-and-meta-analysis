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
Use the **sidebar** to select a day, then choose either **Guided Examples** or **BYOD**.
These are separate paths. Each guided example offers a choice of provider, contains all stages,
uses fixed, read-only searches and screening criteria, and shows how its results follow from
the selected provider's records. BYOD is for participants who want to enter their own searches
and criteria and use their own data.

| Day | Date | Theme | Main Objective |
|-----|------|-------|----------------|
| **Day 1** | June 10 | From Query to Corpus | Explore fixed worked searches and saved records or retrieve/upload your own corpus |
| **Day 2** | June 11 | From Corpus to Included Studies | Inspect fixed screening steps or configure screening on your own corpus |
| **Day 3** | June 12 | From Studies to Evidence | Examine the worked extraction and descriptive synthesis or use your own included records |
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
| **1. Search & Collect** | Retrieve or load metadata | Open a Day 1 guided example, use a bounded provider search, or upload RIS or CSV |
| **2. Deduplicate** | Clean the corpus | Inspect API results or uploaded records and download a corpus CSV/RIS; provider fields and coverage differ |
| **3. Screen** | Triage and verify records | Upload a Day 1 CSV, enter inclusion/exclusion terms, run the deterministic heuristic, inspect the full screening log, and verify decisions manually |
| **4. Extract** | Pull structured fields from study inputs | Upload included studies, choose a schema, and use the available NLP/AI extraction options; extracted values are drafts for verification |
| **5. Synthesize & Map** | Visualise and export | Produce teaching or BYOD charts, networks, tables, and downloadable outputs; interpret counts according to their provenance |
""")

st.markdown("---")

# ── Input Flexibility ──────────────────────────────────────────────────────────
st.markdown("### Input Flexibility: Multiple Entry Points")
st.markdown("""
The app accepts several input types rather than forcing everyone into one narrow workflow.

| Input Type | Use Case | App Behaviour |
|------------|----------|---------------|
| **API Search** | Starting a review from scratch | Day 1 presents provider-specific search menus. OpenAlex offers a limited first page without credentials or bounded retrieval with a per-user key; the query log records search metadata, not credentials |
| **RIS / CSV File** | Already searched databases or a previous app step | Upload and continue to deduplication, screening, or synthesis |
| **Zotero Integration** | Uses a reference manager | Use the Day 1 Zotero path or an exported library as an alternative starting corpus |
| **PDF Documents / Included CSV** | Already completed screening | Continue to Day 3 extraction and synthesis; outputs still require checking |
""")

st.markdown("---")

# ── Four Guided Case Studies ───────────────────────────────────────────────────
st.markdown("### Four Guided Case Studies")
st.markdown("""
Each guided example is self-contained: choose OpenAlex, Crossref, Europe PMC or OpenAIRE at the
top of the case. The provider's fixed search and records feed the screening criteria and decisions,
extraction, descriptive synthesis and networks. Each provider has its own recorded sample, available
immediately without a key. Where offered, a fixed live search is optional. Queries and criteria are
read-only; visualization controls let you explore a network without changing the example's inputs.
The examples are small, bounded search samples and their automatic screening is a teaching heuristic,
not a validated systematic review or a substitute for human judgment. Descriptive synthesis does
not create unverified clinical or financial effect sizes.

| # | Discipline | Topic | Worked teaching emphasis |
|---|-----------|-------|---------------------------|
| 1 | 🏥 **Health Sciences** | Health Inequalities in Chronic Disease Care | Fixed search, screening, extraction and descriptive synthesis |
| 2 | 🏛️ **Social Sciences** | Universal Basic Income (UBI) Policy Outcomes | Fixed search, screening, extraction and descriptive synthesis |
| 3 | ⚗️ **Science / Engineering** | Microplastic Pollution in Aquatic Environments | Fixed search, screening, extraction and descriptive synthesis |
| 4 | 💼 **Management / Business** | Corporate Social Responsibility & Firm Financial Performance | Fixed search, screening, extraction and descriptive synthesis |
""")

st.markdown("---")

# ── BYOD Highlights ────────────────────────────────────────────────────────────
st.markdown("### Bring Your Own Data (BYOD)")
st.markdown("""
Each day includes a BYOD extension so participants can apply the workflow to their own research
question. The live handoff is **Day 1 → Day 2 → Day 3**: download a Day 1 corpus, screen it on
Day 2, then upload the included-studies CSV to Day 3.

**Day 1 BYOD:** Choose a provider from the search menu (OpenAlex, Crossref, Europe PMC, or
OpenAIRE), enter a query, select any provider-specific filters, and retrieve a
bounded corpus. OpenAlex retrieval is capped by the configured page size and maximum pages, so a
large result set may be truncated; the query log reports retrieval metadata and should be saved.
Provider syntax, indexing, coverage, and available filters differ. Crossref needs no key and
retrieves one page with provider-specific relevance search; Boolean logic is not guaranteed.
You may instead upload RIS, upload a corpus CSV, or use Zotero.

**OpenAIRE limitations:** No participant key or email is needed, but anonymous requests are limited
to up to 60 per hour; users of one hosted app may share that limit. The app retrieves a bounded
number of pages and applies no year, specific publication-type or abstract filters. Coverage varies,
metadata and abstracts may be missing, and publication results can include non-peer-reviewed work.
The search covers broad metadata, not just titles and abstracts. Verify records and acknowledge
OpenAIRE as the data source. The app repeats these caveats when OpenAIRE is used.

**OpenAlex access:** participants can search without a key or email, limited to one page and
a shared server allowance that may be rate-limited. For more pages and an individual allowance,
participants can choose a credentials file kept on their own computer.
The browser reads the file and sends the key directly to OpenAlex over HTTPS; it sends the returned
records, not the key, to the app. This assumes the app's code and browser are trusted. The optional
masked manual-entry route sends the key to the app server. Search logs do not contain credentials.

**Day 2 BYOD:** Upload the Day 1 CSV (or another CSV with titles/abstracts), enter inclusion and
exclusion terms, and run the current deterministic, case-insensitive substring heuristic over
Title + Abstract. It is **not an actual LLM** and does not provide validated recall, precision,
F1, or WSS estimates. Reviewers must inspect the included file and full screening log and make
human eligibility decisions; the log is an audit aid, not proof of correctness.
The Day 2 interactive maps offer concept co-occurrence, title/abstract term co-occurrence,
co-authorship, and bibliographic coupling. Participants can map included studies or all screened
records (exploratory only). Co-occurrence links count records containing both items; author names
are not disambiguated.

**Day 3 BYOD:** Carry forward the Day 2 included-studies CSV, choose the extraction schema, and
use the available NLP or optional AI extraction route. Additional AI instructions are editable.
Generate tables, charts and networks as appropriate. These are analysis aids: confirm extracted fields, effect
sizes, denominators, and flow counts against the source studies. The guided route uses its own
fixed teaching samples; BYOD uses participant-supplied data and settings.

**Co-authorship and bibliographic coupling on all days:** Co-authorship uses the supplied author
names. Bibliographic coupling connects studies by the number of reference identifiers they share.
New OpenAlex and Crossref searches retain reference IDs when available. Some records and inputs
lack reference lists, and missing metadata can leave links absent;
the app explains this rather than drawing an empty coupling network. Identifier namespaces are
not automatically mapped, and the network node cap can bias which studies are displayed.

**Network appearance:** In-app networks use equally sized nodes; hover to see frequency and
the Louvain community. Node colors identify communities computed from the weighted, displayed
network. Worked cases also offer source-concept or text-derived keyword co-occurrence where
available; text-derived terms are not presented as provider-assigned concepts.
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
