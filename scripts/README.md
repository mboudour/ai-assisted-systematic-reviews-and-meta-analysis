# Project Source Code Scripts

This folder contains all source code scripts for the **AI-Assisted Systematic Reviews and Meta-Analysis** Streamlit application. The application is structured as a multi-page Streamlit app covering three sequential workflow days.

## File Index

| File | Lines | Role | Description |
|---|---|---|---|
| `app.py` | 181 | App entry point | Main Streamlit application: landing page, navigation sidebar, project overview, and module descriptions. |
| `1_Day1_Query_to_Corpus.py` | 1,460 | Day 1 page | **Query to Corpus.** Guided and BYOD (Bring Your Own Data) workflows for building a literature corpus via OpenAlex, Crossref, and Europe PMC APIs. Includes keyword co-occurrence network visualisation (pyvis/vis-network), Louvain community detection, and CSV export. |
| `2_Day2_Corpus_to_Included_Studies.py` | 928 | Day 2 page | **Corpus to Included Studies.** AI-assisted abstract screening using OpenAI GPT models. Supports guided examples and BYOD CSV upload. Produces a screened CSV with inclusion/exclusion decisions and rationales. |
| `3_Day3_Studies_to_Evidence.py` | 1,351 | Day 3 page | **Studies to Evidence.** Full meta-analysis pipeline: data extraction, effect size computation (Cohen's d, OR, RR, HR), forest plots, funnel plots, heterogeneity statistics (I², τ², Cochran's Q), trim-and-fill, Egger's test, and network meta-analysis. |
| `requirements.txt` | — | Dependencies | Python package requirements for Streamlit Community Cloud deployment. |
| `environment.yml` | — | Dependencies | Conda environment specification for local development. |

## Application Architecture

```
app.py                          ← Streamlit entry point (landing page)
pages/
  1_Day1_Query_to_Corpus.py     ← Day 1: API fetch → keyword network → CSV
  2_Day2_Corpus_to_Included_Studies.py  ← Day 2: GPT screening → screened CSV
  3_Day3_Studies_to_Evidence.py ← Day 3: meta-analysis → forest/funnel plots
data/cache/                     ← Pre-built example corpora (CSV)
Additional Case Studies/        ← 10 additional case study corpora and docs
slides/                         ← Slide decks (PDF) for each day
```

## Key External Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web application framework |
| `openai` | GPT-based abstract screening (Day 2) |
| `pyvis` | Network graph generation (Day 1) |
| `python-louvain` | Louvain community detection (Day 1) |
| `networkx` | Graph construction and analysis |
| `pandas`, `numpy` | Data manipulation |
| `matplotlib`, `plotly` | Forest plots, funnel plots, visualisations |
| `scipy`, `statsmodels` | Statistical computations (effect sizes, heterogeneity) |
| `requests` | API calls to OpenAlex, Crossref, Europe PMC |

## Running Locally

```bash
# With conda
conda env create -f environment.yml
conda activate systematic-review-env
streamlit run app.py

# With pip
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

The application is deployed on **Streamlit Community Cloud** at:
[https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app)
