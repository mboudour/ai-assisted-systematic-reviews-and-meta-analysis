"""
AI-Assisted Systematic Reviews and Meta-Analysis — Workshop
Landing page: seminar overview, 5-module architecture, input flexibility, case studies.
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
— from the health and life sciences to the social sciences, humanities, and engineering.

Participants work through a guided workflow via this Streamlit application, through which
they upload, process, screen, extract, and synthesize literature through a guided, no-code
interface. A parallel code repository containing scripts in both **Python** and **R** is
provided for transparency and reproducibility, but interacting with it is entirely optional.

The seminar focuses on how the overwhelming volume of academic literature can be
navigated, screened, and synthesized using **Artificial Intelligence (AI)**. Participants
learn how to collect bibliographic data via open APIs, use **Active Learning** and
**Large Language Models (LLMs)** to screen abstracts, extract structured data from
full-text PDFs, and conduct an initial narrative or quantitative synthesis — all within this
no-code environment, with explicit validation and human verification at each stage.
""")

st.markdown("---")

# ── Navigation ─────────────────────────────────────────────────────────────────
st.markdown("### How to Navigate")
st.markdown("""
Use the **sidebar** to select a day. Each day covers one major stage of the systematic
review pipeline and includes four guided case studies plus a BYOD extension.

| Day | Date | Theme | Main Objective |
|-----|------|-------|----------------|
| **Day 1** | June 10 | From Query to Corpus | Programmatic literature collection via open APIs and automated deduplication |
| **Day 2** | June 11 | From Corpus to Included Studies | AI-assisted abstract screening with Active Learning and LLM zero-shot classification |
| **Day 3** | June 12 | From Studies to Evidence | LLM-assisted data extraction from PDFs and narrative or quantitative synthesis |
""")

st.info("👈 Select a day from the sidebar to begin.")

st.markdown("---")

# ── 5-Module Architecture ──────────────────────────────────────────────────────
st.markdown("### App Architecture: Five Workflow Modules")
st.markdown("""
The app is built around a **modular workflow** in which participants enter at different
points depending on what they already have. A participant beginning a new project starts
in **Search & Collect**. A participant who already has a deduplicated Zotero library
skips directly to **Screen**. A participant who has already screened their papers manually
enters only in **Extract**.

| Module | Function | What Participants Can Do |
|--------|----------|--------------------------|
| **1. Search & Collect** | Retrieve metadata via open APIs | Enter Boolean queries, ping OpenAlex / Crossref / Semantic Scholar / Europe PMC, and retrieve records |
| **2. Deduplicate** | Clean the corpus | Upload RIS/CSV files or process API results to remove duplicates |
| **3. Screen** | Active Learning & LLM screening | Connect to Zotero or upload data, iteratively label training sets, and apply exclusion prompts |
| **4. Extract** | Pull data from full texts | Upload PDFs, select a discipline-specific schema (PICO, Thematic Synthesis, or custom), and generate a structured table |
| **5. Synthesize & Map** | Visualise and export | Produce PRISMA flow diagrams, summary plots, a Temporal Analysis chart, an Interactive Bibliometric Map, and download final datasets |
""")

st.markdown("---")

# ── Input Flexibility ──────────────────────────────────────────────────────────
st.markdown("### Input Flexibility: Multiple Entry Points")
st.markdown("""
The app accepts multiple input types rather than forcing everyone into one narrow workflow.
This makes the seminar credible for participants from all fields whose research materials
and progress stages are likely to vary widely.

| Input Type | Use Case | App Behaviour |
|------------|----------|---------------|
| **Boolean Query** | Starting a review from scratch | The app queries open APIs and builds a new corpus |
| **RIS / BibTeX File** | Already searched traditional databases | The app parses the file and moves to deduplication or screening |
| **Zotero Integration** | Uses a reference manager | The app syncs directly with the user's cloud or self-hosted library |
| **PDF Documents** | Already completed screening | The app parses the PDFs and opens the data extraction module |
""")

st.markdown("---")

# ── Four Guided Case Studies ───────────────────────────────────────────────────
st.markdown("### Four Guided Case Studies")
st.markdown("""
Each day demonstrates the full pipeline across four discipline-spanning case studies.
Every case study is carried through all three days — from corpus construction on Day 1,
through screening on Day 2, to extraction and synthesis on Day 3.

| # | Discipline | Topic | Day 3 Synthesis |
|---|-----------|-------|-----------------|
| 1 | 🏥 **Health Sciences** | Health Inequalities in Chronic Disease Care | Meta-analysis: pooled Risk Ratio with I² heterogeneity |
| 2 | 🏛️ **Social Sciences** | Universal Basic Income (UBI) Policy Outcomes | Narrative synthesis table |
| 3 | ⚗️ **Science / Engineering** | Microplastic Pollution in Aquatic Environments | Quantitative concentration summary & chart |
| 4 | 💼 **Management / Business** | Corporate Social Responsibility & Firm Financial Performance | Meta-analysis: pooled correlation coefficient |
""")

st.markdown("---")

# ── BYOD Highlights ────────────────────────────────────────────────────────────
st.markdown("### Bring Your Own Data (BYOD)")
st.markdown("""
Each day includes a dedicated **BYOD extension** so participants can apply the workflow
to their own research question in real time.

**Day 1 BYOD:** Enter any Boolean query, select from OpenAlex, Crossref, Semantic Scholar,
or Europe PMC, retrieve and deduplicate your own corpus, and download a timestamped
query log for reproducibility. Alternatively, upload an existing **RIS/BibTeX file** from
your reference manager or connect your **Zotero** library directly.

**Day 2 BYOD:** Upload the CSV from Day 1 (or a RIS/BibTeX file), enter your own
inclusion and exclusion criteria, and screen your corpus using **Active Learning**,
**LLM-based zero-shot classification**, or a combination of both. The Transparency Log
records every AI decision for your audit trail.

**Day 3 BYOD:** Upload your included study **PDFs**, choose a discipline-specific
extraction schema (**PICO**, **Thematic Synthesis**, or define your own custom variables),
extract structured data, and generate a **PRISMA 2020 flow diagram**, a **Temporal
Analysis chart**, and synthesis visualisations for your own review.
""")

st.markdown("---")

# ── Adjustment Mechanisms ──────────────────────────────────────────────────────
st.markdown("### How Participants Adjust the App to Their Own Data")
st.markdown("""
Participants are not expected to alter code, but they can configure the workflow
meaningfully through the interface. The key principle is that the app lets them express,
in plain language or simple selections, what the underlying Python and R scripts should do.

| Adjustment Area | What the Participant Controls | Why It Matters |
|-----------------|-------------------------------|----------------|
| **API Filters** | Databases, years, open access status | Ensures the search is tailored to the research scope |
| **Screening Method** | Active Learning vs. LLM prompts (or both) | Allows control over the human-in-the-loop balance |
| **Extraction Schema** | Template (PICO, Thematic Synthesis) or custom variables | Supports heterogeneous research questions across disciplines |
| **Visualisations** | Which variables to plot or summarise | Lets participants tailor outputs to their specific findings |
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
