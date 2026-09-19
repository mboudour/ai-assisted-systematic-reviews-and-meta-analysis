# Empirical Evaluation Pipeline

This directory contains the four-script pipeline used to produce the empirical results reported in the manuscript.

## Pipeline

| Script | Role | Output |
|---|---|---|
| `scripts/01_retrieval.py` | Retrieves records for 20 case studies from OpenAlex, EuropePMC, and Semantic Scholar | `data/raw/` |
| `scripts/02_screening.py` | Screens titles and abstracts using GPT-4o-mini zero-shot classification | `data/screened/` |
| `scripts/03_extraction.py` | Extracts structured data fields and runs LLM-as-Judge verification | `data/extracted/` |
| `scripts/04_synthesis_and_figures.py` | Generates forest plots, PRISMA flow diagram, and summary figures | `figures/` |

## Requirements

```bash
pip install openai pandas numpy tqdm scikit-learn python-dotenv matplotlib seaborn networkx
```

Create `api_keys.env` in this directory with:
```
OPENAI_API_KEY=your_key_here
```

## Outputs

- `outputs/retrieval_summary.csv` — record counts per case study
- `outputs/screening_summary.csv` — inclusion/exclusion counts per case study
- `outputs/extraction_summary_corrected.csv` — extraction accuracy metrics (judge-verified) for all 20 cases
- `figures/` — all publication-ready figures (PDF)
