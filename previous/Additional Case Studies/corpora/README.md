# Additional Case Studies — Pre-Built Corpora (Day 1 Output CSVs)

This folder contains **10 pre-built corpus CSV files**, one for each additional case
study defined in `../Additional_Case_Studies.md`. Each CSV was produced by running the
Day 1 workflow (*From Query to Corpus*) with the exact query parameters specified in
that document.

These files are ready to use as **BYOD inputs for Day 2** (*From Corpus to Included
Studies*) without re-running the Day 1 API queries.

---

## How to Use in Day 2

1. Open the Streamlit app and navigate to **Day 2 — From Corpus to Included Studies**.
2. In the sidebar, select **🔎 BYOD — Your Own Corpus**.
3. Choose **📂 Upload a CSV file**.
4. Upload the CSV file for the case study you want to screen.
5. The app will load the corpus and proceed with AI-assisted screening.

---

## File Index

| File | Case | Topic | API used | Records | With abstracts |
|---|---|---|---|---|---|
| `case01_technology_enhanced_learning.csv` | 1 | Technology-Enhanced Learning & Academic Achievement | OpenAlex | 150 | 150 |
| `case02_mindfulness_anxiety.csv` | 2 | Mindfulness-Based Interventions & Anxiety | Europe PMC | 50 | 43 |
| `case03_carbon_pricing_emissions.csv` | 3 | Carbon Pricing & Emissions Reduction | OpenAlex | 99 | 99 |
| `case04_llms_clinical_decision.csv` | 4 | LLMs in Clinical Decision Support | OpenAlex* | 50 | 50 |
| `case05_microfinance_poverty.csv` | 5 | Microfinance & Household Poverty Reduction | OpenAlex | 150 | 150 |
| `case06_nurse_staffing_patient_safety.csv` | 6 | Nurse Staffing Ratios & Patient Safety | Europe PMC | 50 | 42 |
| `case07_social_media_polarisation.csv` | 7 | Social Media & Political Polarisation | OpenAlex | 98 | 98 |
| `case08_green_infrastructure_urban_heat.csv` | 8 | Green Infrastructure & Urban Heat Island | Crossref | 48 | 17 |
| `case09_statin_cardiovascular.csv` | 9 | Statin Therapy & Cardiovascular Event Prevention | Europe PMC | 100 | 86 |
| `case10_open_access_citation.csv` | 10 | Open Access Publishing & Citation Advantage | OpenAlex | 100 | 100 |

\* Case 4 originally specified Semantic Scholar, which was removed from the app due to
rate-limit constraints. OpenAlex was substituted using the identical query; it provides
strong coverage of CS/AI conference papers and preprints.

---

## CSV Schema

All files share the same column schema produced by the Day 1 pipeline:

| Column | Description |
|---|---|
| `ID` | API-internal identifier (OpenAlex ID, Europe PMC ID, or Crossref DOI) |
| `DOI` | Digital Object Identifier (where available) |
| `Title` | Paper title |
| `Year` | Publication year |
| `Authors` | Semicolon-separated author names (up to 5) |
| `Venue` | Journal or conference name |
| `Abstract` | Full abstract text |
| `Citations` | Citation count (where available from the API) |
| `Concepts` | Semicolon-separated concept/keyword tags (OpenAlex only; empty for Crossref/Europe PMC) |

---

## Notes on Abstract Coverage

- **OpenAlex** returns abstracts for all records (filtered with `has_abstract:true`).
- **Europe PMC** returns abstracts for most records; a small fraction lack them.
- **Crossref** returns abstracts only when deposited by the publisher; Case 8 therefore
  has lower abstract coverage (~35%). This is normal for Crossref and does not affect
  the screening workflow — the title alone is sufficient for many inclusion/exclusion
  decisions.

---

*Generated June 2026 for the AI-Assisted Systematic Reviews and Meta-Analysis seminar
(instats). Queries match exactly those in `../Additional_Case_Studies.md`.*
