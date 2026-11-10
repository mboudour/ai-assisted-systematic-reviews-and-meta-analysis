# AI-Assisted Systematic Reviews and Meta-Analysis

**instats Seminar — June 10, 11, and 12, 2026**
**Instructor:** Moses Boudourides, Data Science Graduate Program, School of Professional Studies, Northwestern University

> ### 📋 Registration
> **[Register now at instats.org](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta)**

[![Streamlit App](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app) [Streamlit App](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app)

---

## Overview

This repository is the companion resource for the three-day instats seminar
[AI-Assisted Systematic Reviews and Meta-Analysis](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta).

The seminar is a **no-code** research methods workshop: participants are not expected to write or
modify a single line of code. Operations are performed through a
[Streamlit application](https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app)
that exposes menus for cached teaching examples, live or uploaded Day 1 inputs, screening, and
Day 3 extraction/synthesis.

The repaired workflow is deliberately explicit about provenance. The checked-in Day 1 and Day 2
files are cached teaching snapshots. They do not establish the historical query string, search
date, filters, or API response that produced them. Day 1's clickable practice searches are new
suggestions that load proposed query/menu settings into the BYOD form; they are useful exercises,
not claims about the original cached retrieval. Guided Day 3 pages use illustrative/synthetic
teaching fixtures rather than a live empirical end-to-end run.

---

## Seminar Structure

| Day | Date | Theme | Main Objective |
|-----|------|-------|----------------|
| **Day 1** | June 10, 2026 | From Query to Corpus | Inspect cached examples, try suggested searches, or collect/upload a corpus via the available menus |
| **Day 2** | June 11, 2026 | From Corpus to Included Studies | Review cached labels or run deterministic keyword screening on a supplied corpus, followed by human verification |
| **Day 3** | June 12, 2026 | From Studies to Evidence | Explore illustrative teaching outputs or continue a Day 2 BYOD included-studies CSV into extraction and synthesis |

The intended live handoff is **Day 1 BYOD → Day 2 BYOD → Day 3 BYOD**. Save the files and logs
from each step; the guided path is for teaching and does not reconstruct historical provenance.

---

## Four Guided Case Studies

The Day 1 **Guided Examples** menu contains four discipline-spanning worked examples. Opening an
example loads its cached corpus and provides a clickable **practice search** suggestion tied to the
search menus (query text, years, publication types, and related settings). These practice searches
are suggestions, not verified historical searches for the cached files.

| # | Discipline | Topic | API Source |
|---|-----------|-------|---|
| 1 | Health Sciences | Health Inequalities in Chronic Disease Care | OpenAlex teaching snapshot |
| 2 | Social Sciences | Universal Basic Income (UBI) Policy Outcomes | OpenAlex teaching snapshot |
| 3 | Science / Engineering | Microplastic Pollution in Aquatic Environments | OpenAlex teaching snapshot |
| 4 | Management / Business | CSR and Firm Financial Performance | OpenAlex teaching snapshot |

The Day 2 guided pages similarly load checked-in screening snapshots and expose screening-log
downloads. They do not prove the original Day 1 query, date, filters, or API response. The Day 3
guided pages display illustrative extraction tables, narratives, charts, and PRISMA-style teaching
outputs; their counts and performance values are not a live retrieval or screening run.

---

## BYOD — Bring Your Own Data

A central feature of the seminar is the **BYOD (Bring Your Own Data)** extension, which lets
participants apply the pipeline to their own research questions. The intended path is a real file
handoff from Day 1 to Day 2 to Day 3.

### Day 1: Build Your Own Corpus

Use the search menus to choose OpenAlex, Crossref, Europe PMC, or OpenAIRE, enter a query,
and set the available scope, year, publication-type, and abstract filters. OpenAlex is retrieved
with bounded pagination: page size and maximum pages impose a retrieval cap, so a large result set
may be truncated. The query log records the actual query, filters, provider, retrieval metadata,
and timestamp; download and retain it for reproducibility. Provider syntax, indexing, coverage,
metadata, and filters differ. Crossref is a one-page relevance search and needs no account or key;
it does not guarantee Boolean interpretation or complete abstracts. Alternatively, upload RIS or
use the Zotero path.

**OpenAlex participant credentials:** each participant uses their own email-verified OpenAlex key.
The app collects the key and email in masked, session-specific inputs. The key is sent to OpenAlex
only over HTTPS in an `Authorization: Bearer` header; the email is not sent with searches. The key
and email are not written to query logs or error metadata. This is not a promise of complete
privacy from the operator or hosting environment: participants must assess operator/hosting trust
and use credentials they are comfortable entering.

**OpenAIRE:** participants need no key or email. The app uses anonymous Graph API v3 search with
bounded paging (default one page; at most three), not authenticated service access. OpenAIRE's
published anonymous limit is up to 60 requests/hour and participants on one hosted app may share
that allowance; rate limiting can occur. A page is an API request. OpenAIRE aggregates metadata
across disciplines but has uneven coverage; its publication results can include non-peer-reviewed
outputs. Abstract-like descriptions, DOIs and other fields may be missing, and descriptions are not
necessarily formal abstracts. The Concepts column contains OpenAIRE subject labels, not OpenAlex
concepts. Search is across broad metadata; the app applies no OpenAIRE year,
specific publication-type or abstract filters. Boolean search values must be double-quoted, e.g.
`("creativity" OR "creative") AND "artificial intelligence"`. Live results may be truncated.
Check eligibility, save the query log, and acknowledge OpenAIRE as the data source in accordance
with [its terms](https://graph.openaire.eu/docs/apis/terms). RIS exports label OpenAIRE records
as generic rather than verified journal articles and record OpenAIRE in the database field. The guided examples' OpenAIRE practice
queries are new suggestions, not the verified searches behind the saved teaching snapshots.

### Day 2: Screen Your Own Corpus

Upload the Day 1 corpus CSV (or another CSV containing titles and abstracts), enter inclusion and
exclusion terms, and run the current BYOD screening path. The implementation is a deterministic,
case-insensitive substring heuristic over Title + Abstract. It does **not** require or use an
actual LLM for this BYOD run. The output includes an included-studies CSV and a full screening log,
but the decisions are first-pass triage and need human eligibility verification. Any displayed
recall, precision, F1, or WSS-style values are descriptive diagnostics, not validated metrics
without an independently adjudicated reference set.

Day 2 offers concept co-occurrence, title/abstract term co-occurrence, and co-authorship networks.
Choose included studies or all screened records (the latter is exploratory). Node counts indicate
records containing an item; link weights indicate records containing both. Terms are lexical, not
OpenAlex concepts, and author names are not disambiguated. Only the displayed top nodes and links
are exported. Title/abstract terms are selected with TF-IDF (up to eight per record) and depend on
the selected record set. No concepts are invented when the source field is empty.

### Day 3: Synthesize Your Own Evidence

Upload or carry forward the Day 2 included-studies CSV, choose a PICO, Thematic Synthesis, or
custom schema, and use the available NLP route or optional AI extraction route. Generate structured
tables, temporal/network views, and narrative or quantitative charts when the data support them.
Check extracted values, effect sizes, denominators, and flow counts against the source studies.
The guided Day 3 route is illustrative/synthetic; the BYOD route is the route for participant-
supplied inputs and outputs.

---

## No-Code Streamlit App

The live Streamlit app is available at:
**https://ai-assisted-systematic-reviews-and-meta-analysis.streamlit.app**

No installation is required to use the app. Participants interact with menus, upload files,
run bounded searches or local heuristics, and export results through the browser interface.

---

## LLM Architecture

The current repaired BYOD Day 2 screening implementation is **not an actual LLM call**: it uses a
simple deterministic keyword heuristic and requires human verification. Day 3 offers an optional
AI extraction route when configured, alongside a no-key NLP route; the guided examples remain
illustrative teaching fixtures. Do not infer that every workflow stage uses an LLM or that any
output is validated without review.

---

## Manuscript about the Workshop

A manuscript describing the workshop is available here:

[AI-Assisted Systematic Reviews and Meta-Analysis Manuscript](./ai_systematic_review_paper.pdf)

## Workshop Slides

- [Day 1: From Query to Corpus](./slides/day1_slides.pdf)
- [Day 1 additional slides](./slides/additional_slides_day1.pdf)
- [Day 2: From Corpus to Included Studies](./slides/day2_slides.pdf)
- [Day 2 additional slides](./slides/additional_slides_day2.pdf)
- [Day 3: From Studies to Evidence](./slides/day3_slides.pdf)
- [Day 3 additional slides](./slides/additional_slides_day3.pdf)

---

## License

MIT License. See [LICENSE](LICENSE) for details.
