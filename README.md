# AI-Assisted Systematic Reviews and Meta-Analysis

**instats Seminar — June 10, 11, and 12, 2026**
**Instructor:** Moses Boudourides, Data Science Graduate Program, School of Professional Studies, Northwestern University

> ### 📋 Registration
> **[Register now at instats.org](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta)**

[![Streamlit App](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app)

---

## Overview

This repository is the companion resource for the three-day instats seminar
[AI-Assisted Systematic Reviews and Meta-Analysis](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta).

The seminar is a **no-code** research methods workshop: participants are not expected to write or
modify a single line of code. All operations are performed through a
[Streamlit application](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app)
that guides users through the complete evidence synthesis pipeline.

---

## Seminar Structure

| Day | Date | Theme | Main Objective |
|-----|------|-------|----------------|
| **Day 1** | June 10, 2026 | From Query to Corpus | Collect bibliographic records via open APIs and deduplicate the corpus |
| **Day 2** | June 11, 2026 | From Corpus to Included Studies | Screen titles and abstracts using Active Learning and LLM zero-shot classification |
| **Day 3** | June 12, 2026 | From Studies to Evidence | Extract structured data from full-text PDFs and produce narrative or quantitative synthesis |

---

## Four Guided Case Studies

Each day works through four discipline-spanning examples so you can follow the
full systematic review lifecycle in a domain close to your own:

| # | Discipline | Topic | API Source |
|---|---|---|---|
| 1 | Health Sciences | Health Inequalities in Chronic Disease Care | OpenAlex |
| 2 | Social Sciences | Universal Basic Income (UBI) Policy Outcomes | Semantic Scholar |
| 3 | Science / Engineering | Microplastic Pollution in Aquatic Environments | OpenAlex / Crossref |
| 4 | Management / Business | CSR and Firm Financial Performance | OpenAlex |

---

## BYOD — Bring Your Own Data

A central feature of the seminar is the **BYOD (Bring Your Own Data)** extension, which allows participants to apply the pipeline directly to their own research questions. The BYOD modules are integrated into every day of the workshop:

### Day 1: Build Your Own Corpus
Participants formulate their own search queries (using Boolean logic and PICO/SPIDER frameworks) and run them against the OpenAlex or Semantic Scholar APIs directly within the app. The module automatically fetches the records, flattens nested metadata, performs DOI and title-based deduplication, and exports a clean CSV corpus ready for screening. A detailed query log is also generated to ensure methodological reproducibility.

### Day 2: Screen Your Own Corpus
Participants upload their Day 1 corpus (or any existing CSV containing titles and abstracts) and define their own inclusion and exclusion criteria in plain language. They first use the Active Learning module to prioritise the most relevant papers by seeding the model with keywords. They then use the LLM zero-shot screening module (powered seamlessly by the Hugging Face Inference API) to automatically classify their abstracts. The app generates a full Transparency Log containing the AI's decision and justification for every record.

### Day 3: Synthesize Your Own Evidence
Participants upload their screened, included studies and define a custom extraction schema (e.g., PICO elements, methodology, sample size, or specific effect sizes). The LLM extracts the structured data into a tabular format. Depending on the data, participants can then generate a narrative synthesis table, or — if quantitative effect sizes and confidence intervals are extracted — a forest plot with a pooled inverse-variance estimate. The module also automatically generates a PRISMA 2020 flow diagram mapping the exact record counts from their personal pipeline.

---

## No-Code Streamlit App

The live Streamlit app is available at:
**https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app**

No installation is required to use the app. Participants interact with menus, upload files,
and export results entirely through the browser interface.

---

## LLM Architecture

The Streamlit app uses the **Hugging Face Serverless Inference API** (via `st.secrets`) for
the BYOD (Bring Your Own Data) extension — participants do not need to provide any API key
to use the live application during the seminar.

---

## Manuscript about the Workshop

A manuscript describing the workshope is available here:

[AI-Assisted Systematic Reviews and Meta-Analysis Manuscript](./ai_systematic_review_paper.pdf)

## Workshop Slides

- [Day 1: From Query to Corpus](./slides/day1_slides.pdf)
- [Day 2: From Corpus to Included Studies](./slides/day2_slides.pdf)
- [Day 3: From Studies to Evidence](./slides/day3_slides.pdf)

---

## License

MIT License. See [LICENSE](LICENSE) for details.
