# Additional Case Studies: From Query to Corpus

This document provides **10 additional case studies** for the
*AI-Assisted Systematic Reviews and Meta-Analysis* seminar. Every example is completely
distinct from the five guided examples already built into the Streamlit app
(Health Inequalities, Universal Basic Income, Microplastics, CSR & Financial Performance,
and Zotero Library). Each case study can be run immediately in the **BYOD — Your Own Query**
section of the app by entering the parameters listed below.

These case studies are designed to work across all three days of the seminar. See
`Additional_Case_Studies_Suitability.md` in this folder for a full suitability mapping
of each case study against the Day 2 screening and Day 3 synthesis workflows.

---

## How to Use These Case Studies in the App

1. Open the Streamlit app and navigate to **From Query to Corpus**.
2. In the sidebar, select **🔎 BYOD — Your Own Query**.
3. Choose **🔍 Boolean Query (search open APIs live)**.
4. Select the **API** listed in the table for each case study.
5. Paste the **Boolean Query** into the search box.
6. Set **Records per page** and **Number of pages** as recommended.
7. Click **▶ Run My Query**.

---

## Parameter Reference

| Parameter | Where it appears in the app | Notes |
|---|---|---|
| **API** | "Select API" dropdown | OpenAlex, Crossref, Semantic Scholar, or Europe PMC |
| **Boolean Query** | "Enter your search query" text box | Paste exactly as written |
| **Records per page** | Slider (10–100) | Controls how many records are fetched per API page |
| **Number of pages** | Slider (1–5, OpenAlex only) | Multiplies total records retrieved |
| **Expected corpus size** | Informational | Approximate number of records after deduplication |
| **Recommended visualisation** | Informational | Suggested VOSviewer analysis type |

---

## The 10 Additional Case Studies

### Case Study 1 — Education Sciences: Technology-Enhanced Learning and Academic Achievement

| Parameter | Value |
|---|---|
| **Discipline** | Education Sciences |
| **API** | OpenAlex |
| **Boolean Query** | `technology enhanced learning academic achievement student outcomes` |
| **Records per page** | 50 |
| **Number of pages** | 3 |
| **Expected corpus size** | ~120–180 records |
| **Recommended VOSviewer analysis** | Co-occurrence → All keywords |

**Research question:** What does the empirical literature say about the effect of
technology-enhanced learning environments (e-learning, blended learning, gamification,
adaptive learning platforms) on student academic achievement?

**Why this topic?** One of the most active areas of educational meta-analysis since 2015,
spanning K-12 and higher education. The corpus supports a PICO-structured extraction
(Population = students; Intervention = technology-enhanced learning; Comparison = traditional
instruction; Outcome = academic achievement scores) and a pooled effect size in the
synthesis stage.

**What to look for in the keyword network:** Clusters around *blended learning*,
*e-learning*, *gamification*, and *higher education* should emerge as distinct communities.
A bridge node connecting *motivation* to *achievement* is a common finding in this literature.

---

### Case Study 2 — Psychology / Public Health: Mindfulness-Based Interventions and Anxiety

| Parameter | Value |
|---|---|
| **Discipline** | Psychology / Public Health |
| **API** | Europe PMC |
| **Boolean Query** | `mindfulness meditation anxiety reduction randomized controlled trial` |
| **Records per page** | 50 |
| **Number of pages** | 1 |
| **Expected corpus size** | ~40–70 records |
| **Recommended VOSviewer analysis** | Co-occurrence → Author keywords |

**Research question:** What is the evidence from randomised controlled trials on the
effectiveness of mindfulness-based interventions (MBSR, MBCT) in reducing anxiety
symptoms in adult populations?

**Why this topic?** A mature and heavily replicated literature with a large number of
RCTs, making it ideal for demonstrating the meta-analysis workflow. Europe PMC is
preferred here because it provides full-text access to many open-access trials and
indexes clinical trial registrations alongside journal articles.

**What to look for in the keyword network:** Strong co-occurrence between *mindfulness*,
*cognitive therapy*, and *generalised anxiety disorder*. The year distribution should
show exponential growth from 2010 to the present.

---

### Case Study 3 — Environmental Science / Policy: Carbon Pricing and Emissions Reduction

| Parameter | Value |
|---|---|
| **Discipline** | Environmental Science / Policy |
| **API** | OpenAlex |
| **Boolean Query** | `carbon pricing emissions trading scheme greenhouse gas reduction effectiveness` |
| **Records per page** | 50 |
| **Number of pages** | 2 |
| **Expected corpus size** | ~80–130 records |
| **Recommended VOSviewer analysis** | Co-occurrence → All keywords |

**Research question:** What does the empirical literature report about the effectiveness
of carbon pricing mechanisms (carbon taxes, emissions trading schemes) in reducing
greenhouse gas emissions?

**Why this topic?** A rapidly growing interdisciplinary literature spanning environmental
economics, climate policy, and political science. The corpus demonstrates how OpenAlex
handles cross-disciplinary topics and assigns multiple concept tags per paper.

**What to look for in the keyword network:** Expect two distinct clusters — one around
*emissions trading* and *EU ETS*, another around *carbon tax* and *fuel price*. Papers
bridging these clusters are typically comparative policy evaluations.

---

### Case Study 4 — Computer Science / AI: Large Language Models in Clinical Decision Support

| Parameter | Value |
|---|---|
| **Discipline** | Computer Science / Biomedical Informatics |
| **API** | Semantic Scholar |
| **Boolean Query** | `large language models clinical decision support healthcare GPT` |
| **Records per page** | 50 |
| **Number of pages** | 1 |
| **Expected corpus size** | ~40–60 records |
| **Recommended VOSviewer analysis** | Citation → Documents |

**Research question:** What is the current state of research on the application of large
language models (LLMs such as GPT-4, LLaMA, and Gemini) to clinical decision support
systems in healthcare settings?

**Why this topic?** An extremely fast-moving literature (most papers published after 2022),
making it an ideal demonstration of how the year distribution chart reveals an emerging
field. Semantic Scholar is preferred because it has strong coverage of arXiv preprints and
AI conference proceedings (NeurIPS, ICML, ACL) that are underrepresented in other APIs.

**What to look for in the keyword network:** A single large cluster dominated by *GPT*,
*ChatGPT*, *natural language processing*, and *electronic health records*. The near-absence
of papers before 2022 in the year distribution is itself a key finding.

---

### Case Study 5 — Economics / Development: Microfinance and Household Poverty Reduction

| Parameter | Value |
|---|---|
| **Discipline** | Development Economics |
| **API** | OpenAlex |
| **Boolean Query** | `microfinance microcredit household poverty income developing countries` |
| **Records per page** | 50 |
| **Number of pages** | 3 |
| **Expected corpus size** | ~130–200 records |
| **Recommended VOSviewer analysis** | Bibliographic coupling → Documents |

**Research question:** What is the empirical evidence on the impact of microfinance and
microcredit programmes on household income, poverty reduction, and women's empowerment
in developing countries?

**Why this topic?** One of the most contested topics in development economics, with a
large number of randomised evaluations and a well-documented debate between enthusiasts
and sceptics. Bibliographic coupling in VOSviewer will reveal whether the literature has
converged or remains divided into opposing camps.

**What to look for in the keyword network:** Clusters around *Bangladesh*, *Grameen Bank*,
*women empowerment*, and *randomised evaluation*. The year distribution should show a
peak around 2010–2015 following the Nobel Prize awarded to Muhammad Yunus in 2006.

---

### Case Study 6 — Nursing / Allied Health: Nurse-to-Patient Ratios and Patient Safety Outcomes

| Parameter | Value |
|---|---|
| **Discipline** | Nursing / Health Services Research |
| **API** | Europe PMC |
| **Boolean Query** | `nurse staffing patient ratio mortality hospital safety outcomes` |
| **Records per page** | 50 |
| **Number of pages** | 1 |
| **Expected corpus size** | ~40–70 records |
| **Recommended VOSviewer analysis** | Co-occurrence → Author keywords |

**Research question:** What is the evidence on the association between nurse-to-patient
staffing ratios and patient safety outcomes (mortality, adverse events, readmission rates)
in acute hospital settings?

**Why this topic?** A classic PICO-structured health services research question with a
large body of observational and quasi-experimental evidence. Europe PMC is preferred
because it indexes nursing journals and health policy reports alongside clinical trials.

**What to look for in the keyword network:** Strong co-occurrence between *nurse staffing*,
*patient mortality*, *hospital-acquired infections*, and *workload*. The corpus will
illustrate how the same outcome (patient safety) is measured using multiple different
indicators — a key challenge for meta-analysis.

---

### Case Study 7 — Political Science / Sociology: Social Media and Political Polarisation

| Parameter | Value |
|---|---|
| **Discipline** | Political Science / Computational Social Science |
| **API** | OpenAlex |
| **Boolean Query** | `social media political polarisation echo chamber filter bubble empirical` |
| **Records per page** | 50 |
| **Number of pages** | 2 |
| **Expected corpus size** | ~80–120 records |
| **Recommended VOSviewer analysis** | Co-occurrence → All keywords |

**Research question:** What does the empirical literature say about the relationship
between social media use and political polarisation, including the role of echo chambers
and algorithmic filter bubbles?

**Why this topic?** A highly active and contested interdisciplinary literature. The corpus
demonstrates how OpenAlex assigns concepts across disciplines (political science,
communication studies, computer science) and how a keyword network can reveal whether
the literature is converging on a consensus or remains fragmented.

**What to look for in the keyword network:** Expect distinct clusters around *Twitter/X*,
*Facebook*, *algorithmic curation*, and *affective polarisation*. Papers that bridge
the computational and social science clusters are typically the most-cited.

---

### Case Study 8 — Urban Planning / Civil Engineering: Green Infrastructure and Urban Heat Island Mitigation

| Parameter | Value |
|---|---|
| **Discipline** | Urban Planning / Environmental Engineering |
| **API** | Crossref |
| **Boolean Query** | `green infrastructure urban heat island mitigation cooling effect` |
| **Records per page** | 50 |
| **Number of pages** | 1 |
| **Expected corpus size** | ~40–60 records |
| **Recommended VOSviewer analysis** | Co-occurrence → All keywords |

**Research question:** What does the empirical literature report about the effectiveness
of urban green infrastructure (green roofs, urban forests, parks, green walls) in
mitigating the urban heat island effect?

**Why this topic?** An interdisciplinary literature spanning civil engineering,
environmental science, and urban planning. Crossref is used here to demonstrate its
strength in indexing engineering conference proceedings and grey literature reports
that OpenAlex may not fully cover.

**What to look for in the keyword network:** Clusters around *green roofs*, *urban
forests*, *surface temperature*, and *land surface temperature*. The year distribution
should show rapid growth after 2015, coinciding with increased policy attention to
urban climate adaptation.

---

### Case Study 9 — Pharmacology / Medicine: Statin Therapy and Cardiovascular Event Prevention

| Parameter | Value |
|---|---|
| **Discipline** | Pharmacology / Cardiology |
| **API** | Europe PMC |
| **Boolean Query** | `statin therapy cardiovascular events prevention primary secondary randomized trial` |
| **Records per page** | 100 |
| **Number of pages** | 1 |
| **Expected corpus size** | ~80–120 records |
| **Recommended VOSviewer analysis** | Citation → Documents |

**Research question:** What is the evidence from randomised controlled trials on the
effectiveness of statin therapy in preventing major cardiovascular events (myocardial
infarction, stroke) in primary and secondary prevention settings?

**Why this topic?** One of the most heavily meta-analysed topics in clinical medicine,
with landmark trials (4S, WOSCOPS, JUPITER) and multiple Cochrane reviews. The corpus
is ideal for demonstrating the meta-analysis workflow with a well-defined binary
outcome (cardiovascular event: yes/no) and a large number of high-quality RCTs.

**What to look for in the keyword network:** A dense, well-connected network dominated
by *LDL cholesterol*, *myocardial infarction*, *primary prevention*, and *secondary
prevention*. The citation network in VOSviewer will clearly show the landmark trials
as the most-cited nodes.

---

### Case Study 10 — Information Science / Library Science: Open Access Publishing and Citation Advantage

| Parameter | Value |
|---|---|
| **Discipline** | Information Science / Scientometrics |
| **API** | OpenAlex |
| **Boolean Query** | `open access publishing citation advantage impact bibliometric` |
| **Records per page** | 50 |
| **Number of pages** | 2 |
| **Expected corpus size** | ~80–120 records |
| **Recommended VOSviewer analysis** | Bibliographic coupling → Documents |

**Research question:** Does open access publishing confer a citation advantage — that is,
do open access articles receive more citations than equivalent subscription-access articles?

**Why this topic?** A self-referential and methodologically rich literature: it uses
the same bibliometric tools (citation counts, OpenAlex, Crossref) that are the subject
of the corpus-construction module. The corpus demonstrates how OpenAlex's `is_oa` filter
can be used to compare OA and non-OA papers within the same corpus.

**What to look for in the keyword network:** Clusters around *open access*, *citation
impact*, *gold open access*, *preprint*, and *bibliometrics*. The year distribution
will show a steady increase from 2001 (the Budapest Open Access Initiative) to the
present, with acceleration after 2012 (the Finch Report and RCUK mandate).

---

## Summary Table

| # | Discipline | Research Question (abbreviated) | API | Boolean Query | Records/page | Pages |
|---|---|---|---|---|---|---|
| 1 | Education Sciences | Technology-enhanced learning & academic achievement | OpenAlex | `technology enhanced learning academic achievement student outcomes` | 50 | 3 |
| 2 | Psychology / Public Health | Mindfulness-based interventions & anxiety (RCTs) | Europe PMC | `mindfulness meditation anxiety reduction randomized controlled trial` | 50 | 1 |
| 3 | Environmental Science | Carbon pricing & emissions reduction effectiveness | OpenAlex | `carbon pricing emissions trading scheme greenhouse gas reduction effectiveness` | 50 | 2 |
| 4 | Computer Science / AI | LLMs in clinical decision support | Semantic Scholar | `large language models clinical decision support healthcare GPT` | 50 | 1 |
| 5 | Development Economics | Microfinance & household poverty reduction | OpenAlex | `microfinance microcredit household poverty income developing countries` | 50 | 3 |
| 6 | Nursing / Allied Health | Nurse staffing ratios & patient safety | Europe PMC | `nurse staffing patient ratio mortality hospital safety outcomes` | 50 | 1 |
| 7 | Political Science | Social media & political polarisation | OpenAlex | `social media political polarisation echo chamber filter bubble empirical` | 50 | 2 |
| 8 | Urban Planning | Green infrastructure & urban heat island | Crossref | `green infrastructure urban heat island mitigation cooling effect` | 50 | 1 |
| 9 | Pharmacology / Medicine | Statin therapy & cardiovascular event prevention | Europe PMC | `statin therapy cardiovascular events prevention primary secondary randomized trial` | 100 | 1 |
| 10 | Information Science | Open access publishing & citation advantage | OpenAlex | `open access publishing citation advantage impact bibliometric` | 50 | 2 |

---

## Notes on API Selection

The four APIs available in the app each have different strengths. The case studies above
were assigned to APIs deliberately to showcase this diversity:

- **OpenAlex** is used for broad, cross-disciplinary topics where concept tagging and
  citation counts are important (Cases 1, 3, 5, 7, 10).
- **Europe PMC** is used for biomedical and clinical topics where full-text access and
  clinical trial indexing are valuable (Cases 2, 6, 9).
- **Semantic Scholar** is used for AI and computer science topics where arXiv preprint
  coverage is essential (Case 4).
- **Crossref** is used to demonstrate its strength in engineering and interdisciplinary
  conference proceedings (Case 8).

---

*Document prepared for the AI-Assisted Systematic Reviews and Meta-Analysis seminar
(instats, June 2026). All case studies are designed to run in the BYOD section of the
app without any coding. For suitability across all three seminar days, see
`Additional_Case_Studies_Suitability.md`.*
