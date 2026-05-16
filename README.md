# AI-Assisted Systematic Reviews and Meta-Analysis

**instats Seminar — June 10, 11, and 12, 2026**
**Instructor:** Moses Boudourides, Data Science Graduate Program, School of Professional Studies, Northwestern University

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app)

---

## Overview

This repository is the companion resource for the three-day instats seminar
[AI-Assisted Systematic Reviews and Meta-Analysis](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta).

The seminar is a **no-code** research methods workshop: participants are not expected to write or
modify a single line of code. All operations are performed through a
[Streamlit application](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app)
that guides users through the complete evidence synthesis pipeline. This repository provides the
underlying Python and R scripts for transparency, reproducibility, and post-workshop extension.

---

## Seminar Structure

| Day | Date | Theme | Main Objective |
|-----|------|-------|----------------|
| **Day 1** | June 10, 2026 | From Query to Corpus | Collect bibliographic records via open APIs and deduplicate the corpus |
| **Day 2** | June 11, 2026 | From Corpus to Included Studies | Screen titles and abstracts using Active Learning and LLM zero-shot classification |
| **Day 3** | June 12, 2026 | From Studies to Evidence | Extract structured data from full-text PDFs and produce narrative or quantitative synthesis |

---

## Four Guided Case Studies

Each day works through four discipline-spanning examples:

| # | Discipline | Topic | API Source |
|---|---|---|---|
| 1 | Health Sciences | Health Inequalities in Chronic Disease Care | OpenAlex |
| 2 | Social Sciences | Universal Basic Income (UBI) Policy Outcomes | Semantic Scholar |
| 3 | Science / Engineering | Microplastic Pollution in Aquatic Environments | OpenAlex / Crossref |
| 4 | Management / Business | CSR and Firm Financial Performance | OpenAlex |

---

## Repository Structure

```
ai-assisted-systematic-reviews-and-meta-analysis/
├── app.py                          # Main Streamlit landing page
├── pages/
│   ├── 1_Day1_Query_to_Corpus.py
│   ├── 2_Day2_Corpus_to_Included_Studies.py
│   └── 3_Day3_Studies_to_Evidence.py
├── scripts/
│   ├── python/
│   │   ├── day1/                   # API query and deduplication scripts
│   │   ├── day2/                   # Active Learning and LLM screening scripts
│   │   └── day3/                   # PDF extraction and synthesis scripts
│   └── R/
│       ├── day1/                   # R equivalents of Day 1 scripts
│       ├── day2/                   # R equivalents of Day 2 scripts
│       └── day3/                   # R equivalents of Day 3 scripts
├── data/
│   └── cache/                      # Pre-cached API responses and processed datasets
├── slides/                         # Lecture slides (PDF)
├── requirements.txt                # Python dependencies for Streamlit Cloud
└── environment.yml                 # Conda environment definition
```

---

## No-Code Streamlit App

The live Streamlit app is available at:
**https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app**

No installation is required to use the app. Participants interact with menus, upload files,
and export results entirely through the browser interface.

---

## Local Installation (Optional — for post-workshop use)

To run the scripts locally, create the conda environment:

```bash
conda env create -f environment.yml
conda activate ai-sysreview-env
streamlit run app.py
```

The scripts in `scripts/python/` and `scripts/R/` can be run independently of the app
and are designed to work with [Ollama](https://ollama.com) for fully local, offline LLM
inference — no API key required.

---

## LLM Architecture

The Streamlit app uses the **Hugging Face Serverless Inference API** (via `st.secrets`) for
the BYOD (Bring Your Own Data) extension — participants do not need to provide any API key.
The Python and R scripts in this repository use **Ollama** for fully local inference,
ensuring complete data privacy for sensitive or unpublished material.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
