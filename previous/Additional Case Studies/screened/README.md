# Day 2 Screened Corpora — 10 Additional Case Studies

This folder contains the **Day 2 BYOD screening outputs** for all 10 additional case studies.
Each CSV is the direct output of the Day 2 screening pipeline (keyword-based relevance scoring)
applied to the corresponding Day 1 corpus from the `corpora/` folder.

## How to use as Day 3 input

1. Open the Streamlit app and navigate to **Day 3 — From Studies to Evidence**.
2. In the sidebar, select **🔎 BYOD — Your Own Included Studies**.
3. Click **Upload a CSV file** and upload the relevant screened CSV from this folder.
4. The app will load the included studies and proceed with the synthesis workflow.

> **Tip:** Use the `*_screened.csv` files (not the raw `corpora/` files) as Day 3 input,
> because they contain the required `Relevance_Score`, `AL_Decision`, `LLM_Decision`,
> and `LLM_Justification` columns that Day 3 expects.

## CSV Schema

All files share the same 13-column schema:

| Column | Description |
|---|---|
| `ID` | Sequential record identifier |
| `DOI` | Digital Object Identifier (may be empty) |
| `Title` | Paper title |
| `Year` | Publication year |
| `Authors` | Author list (semicolon-separated) |
| `Venue` | Journal or conference name |
| `Abstract` | Full abstract text |
| `Citations` | Citation count at time of retrieval |
| `Concepts` | API-assigned concept/keyword tags |
| `Relevance_Score` | Keyword-based relevance score [0–1] |
| `AL_Decision` | Active Learning decision: Include / Exclude |
| `LLM_Decision` | LLM screening decision: Include / Exclude |
| `LLM_Justification` | One-sentence justification for the decision |

## Files

| File | Discipline | Total | Included | Excluded | Framework |
|---|---|---|---|---|---|
| `case01_technology_enhanced_learning_screened.csv` | Education Sciences | 150 | 145 | 5 | PICO |
| `case02_mindfulness_anxiety_screened.csv` | Psychology / Public Health | 50 | 50 | 0 | PICO |
| `case03_carbon_pricing_emissions_screened.csv` | Environmental Science | 99 | 99 | 0 | PICO |
| `case04_llms_clinical_decision_screened.csv` | Computer Science / AI | 50 | 50 | 0 | PICO |
| `case05_microfinance_poverty_screened.csv` | Development Economics | 150 | 150 | 0 | PICO |
| `case06_nurse_staffing_patient_safety_screened.csv` | Nursing / Health Services | 50 | 48 | 2 | PICO |
| `case07_social_media_polarisation_screened.csv` | Political Science | 98 | 94 | 4 | SPIDER |
| `case08_green_infrastructure_urban_heat_screened.csv` | Urban Planning | 48 | 47 | 1 | PICO |
| `case09_statin_cardiovascular_screened.csv` | Pharmacology / Medicine | 100 | 97 | 3 | PICO |
| `case10_open_access_citation_screened.csv` | Information Science | 100 | 99 | 1 | PICO |

## Screening Criteria

The inclusion/exclusion terms used for each case study are derived from the research
questions in `Additional_Case_Studies.md`. The screening algorithm is identical to the
one used in the Day 2 BYOD interface:

- **Relevance Score** = `inc_hits / len(include_terms) − 0.15 × exc_hits`, clipped to [0, 1]
- **Include** if ≥ 1 inclusion term matched and no exclusion terms matched
- **Exclude** if abstract is too short (< 30 chars), or exclusion terms matched with no inclusion match, or no inclusion terms matched

The high inclusion rates (96–100%) are expected: the corpora were retrieved using
topic-specific queries, so nearly all records are on-topic and match the inclusion terms.
