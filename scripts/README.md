# Streamlit application scripts

The production app starts from the repository root with `streamlit run app.py`. The `scripts/` directory contains synchronized copies of the app entry point and day pages. The shared helper modules and data directories remain at the repository root.

| File | Role |
|---|---|
| `app.py` | Workshop landing page and navigation overview |
| `1_Day1_Query_to_Corpus.py` | Searches, input uploads, corpus display and networks |
| `2_Day2_Corpus_to_Included_Studies.py` | Fixed guided examples and configurable, deterministic BYOD screening |
| `3_Day3_Studies_to_Evidence.py` | Fixed guided examples and configurable BYOD extraction and synthesis |
| `../guided_workflow.py` | Shared, self-contained guided workflow |
| `../data/guided_fixed/` | Saved Crossref examples, search logs and case settings |
| `../day2_networks.py` and `../day2_network_view.py` | Shared network calculation and rendering |

Guided examples and BYOD are separate. The guided workflow uses saved, recorded sample searches and fixed criteria; BYOD has configurable inputs. Day 2 BYOD screening is a keyword heuristic, not a GPT call. Day 3 offers an optional AI extraction path, for which a compatible provider key is required unless the deployment has one configured. Review outputs manually and consult the [main README](../README.md) for data and privacy limitations.

## Local installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

The hosted application is available at <https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app>.
