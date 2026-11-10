# AI-Assisted Systematic Reviews and Meta-Analysis

**instats seminar — June 10, 11 and 12, 2026**

**Instructor:** Moses Boudourides, Data Science Graduate Program, School of Professional Studies, Northwestern University

[Open the Streamlit app](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app) | [Seminar registration](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta)

## Two separate ways to use the app

The workshop is no-code: choose a day from the sidebar, then select one of two **independent** paths.

1. **Guided Examples:** Explore a complete, fixed teaching example, from a recorded search and saved corpus through screening, extraction, descriptive synthesis and networks. Search queries and criteria are displayed read-only; network display settings can be adjusted. Guided examples do not send data or settings to BYOD.
2. **BYOD — Bring Your Own Data:** Use your own research question or files and configure the available providers, search settings, screening criteria, extraction options and visualizations. Your Day 1 BYOD corpus can be carried to Day 2 BYOD, and included studies can be carried to Day 3 BYOD.

Both paths require critical appraisal. Automated screening and extraction are aids, not a substitute for independent review.

## Guided examples

Each of the four case studies appears in the guided section of every day. Expand a case to inspect **all of its stages** without leaving the guided path:

| Case | Topic |
|---|---|
| Health Sciences | Health inequalities in chronic disease care |
| Social Sciences | Universal basic income and policy outcomes |
| Science / Engineering | Microplastic pollution in aquatic environments |
| Management / Business | Corporate social responsibility and financial performance |

The examples use small saved Crossref samples with their actual query and retrieval metadata. Crossref's `query` is a relevance search, not guaranteed Boolean search; a bounded first-page sample is not an exhaustive literature search, and a later run may return different records. The displayed fixed screening decisions are a transparent, simplified keyword heuristic, not human-verified eligibility decisions, independent active-learning results or an LLM screening run. Extraction and descriptive synthesis use the included records from the same example; no clinical outcomes, effect sizes, validated recall, or meta-analysis results are invented. The record snapshots and logs are stored under `data/guided_fixed/`; the older historical teaching fixtures remain in the repository but are not the source of these new examples.

To reduce redistribution of copyrighted material, the saved samples retain abstracts only where Crossref metadata report a CC BY or CC0 license; other abstracts have been withheld. A missing abstract therefore does **not** necessarily mean the provider lacked one. The original response body is not published; its hash and the later license-check details are logged. Metadata about a license is not conclusive: verify its applicability, attribution requirements and the original source before further reuse.

Each example also shows a **precomputed AI extraction illustration for one included record**: its original source, exact fixed prompt, model and extracted quotations. No new AI call is made when a participant opens it. Exact quotation matching does not establish that a quotation is an appropriate interpretation; check the source and context. The AI illustration is not an extraction of every included record or a full evidence synthesis.

Each case can also display co-authorship and bibliographic-coupling networks when its metadata support them. Missing author or reference information is reported rather than fabricated.

## BYOD — your own configurable workflow

### Day 1: Build a corpus

Choose **OpenAlex, Crossref, Europe PMC, or OpenAIRE**, enter a search and choose the options supported by that provider. Alternatively, upload RIS or a corpus CSV or use Zotero. Provider coverage, query syntax, fields and filters differ. Save the query log and corpus; record caps and missing metadata can make a result incomplete.

- **OpenAlex:** Participants supply their own email-verified API key and email in masked, session-specific fields. The key is sent over HTTPS to OpenAlex in an authorization header. It is not put in query logs; the app/server operator may nevertheless have access to session data, so use a trusted deployment. Searches use bounded pagination.
- **Crossref:** No participant key is required. This app retrieves one page using Crossref relevance search; Boolean interpretation and complete abstracts are not guaranteed.
- **OpenAIRE:** No participant key or email is required. The app uses anonymous, bounded Graph API v3 searches. Anonymous requests can be rate-limited and participants on one hosted app may share the allowance. Its broad metadata search is not restricted to title/abstract, and the app does not apply year, specific publication-type or abstract filters for this source. Coverage varies; records may be non-peer-reviewed, and DOIs, author data and descriptions can be missing. Descriptions are not necessarily formal abstracts, and OpenAIRE subject labels are not OpenAlex concepts. Search expressions use quoted operands, e.g. `("creativity" OR "creative") AND "artificial intelligence"`. Check eligibility, retain the query log, and acknowledge OpenAIRE in accordance with [its terms](https://graph.openaire.eu/docs/apis/terms). OpenAIRE-derived records retain source notices in later stages when identifiable.

### Day 2: Screen a corpus

Upload a corpus CSV or use the Day 1 BYOD session handoff. Select the PICO or SPIDER framework, enter the descriptive fields and set inclusion and exclusion terms. The current screening method is a deterministic case-insensitive substring heuristic over title and abstract; it is **not** an LLM or an independently validated active-learning model. Inspect and verify its decisions manually. Keep the included-studies file and screening record for Day 3.

Day 2 also offers concept, title/abstract term, co-authorship and bibliographic-coupling networks where the required fields are available. Mapping all screened records is exploratory and does not mean they were included.

### Day 3: Extract and synthesize

Upload the included-studies CSV or use the Day 2 BYOD handoff. Choose PICO, thematic or custom extraction fields, edit the optional AI extraction instruction, and use the available NLP or optional AI extraction method. AI extraction sends each title, up to 1,200 abstract characters, the schema and instruction to OpenAI and may incur charges. Review all extracted values against the source studies; do not assume the outputs are accurate. Use charts or effect-size analyses only where the required, compatible data and documented counts are actually available. The generic forest plot pools supplied values on their given scale; ratios need appropriate transformation and all studies need compatible measures. The app no longer fabricates unknown full-text counts for a PRISMA-style diagram.

## Co-authorship and bibliographic coupling

All three days provide these network types in both paths:

- **Co-authorship:** nodes are author names; links count records listing both authors. Names in CSVs should be separated by semicolons. Names are not disambiguated and source author lists can be incomplete.
- **Bibliographic coupling:** nodes are studies; a link counts distinct shared cited-reference identifiers. This differs from direct citation and co-citation. OpenAlex may supply referenced-work IDs and Crossref may supply DOI reference IDs. Some records or providers do not supply these fields, so a missing link does not prove no common reference exists. DOI, OpenAlex and PMID identifiers are not resolved across namespaces.

For CSV uploads, `References` may contain a JSON array such as `["doi:10.1234/example", "openalex:W123"]`; a semicolon-separated list is also accepted when the identifiers themselves do not contain semicolons. The app's RIS export does not contain cited-reference links for VOSviewer coupling or citation analysis. Displayed node caps and link thresholds can affect the visualized network and downloaded tables.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app can also be used directly through the [hosted deployment](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app). It does not require participants to edit code.

## Workshop resources

- [Manuscript](./ai_systematic_review_paper.pdf)
- [Day 1 slides](./slides/day1_slides.pdf) and [additional slides](./slides/additional_slides_day1.pdf)
- [Day 2 slides](./slides/day2_slides.pdf) and [additional slides](./slides/additional_slides_day2.pdf)
- [Day 3 slides](./slides/day3_slides.pdf) and [additional slides](./slides/additional_slides_day3.pdf)

## License

MIT License. See [LICENSE](LICENSE). Provider metadata remain subject to their respective terms and data limitations.
