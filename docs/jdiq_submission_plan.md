# JDIQ Submission Plan

## Core editorial decision

The submission should be a **10-page Experience Paper** whose empirical spine consists of three measured consequences: the denominator effect, representation-sensitive repeatability, and downstream schema insufficiency. Provenance conflict and historical failure non-identifiability remain important, but they should appear as design limitations and lessons rather than as pseudo-quantified headline effects.

The working title is:

> **Experience: Auditing LLM-Assisted Evidence Synthesis Without Ground Truth**

JDIQ requires double-anonymous review. The review manuscript must omit author names, affiliations, funding, acknowledgments, identity-bearing filenames and metadata, and first-person possessive self-citations.[1] The official Experience Paper call sets a 10-page limit and permits an online-only supplement.[2]

## Ten-page core allocation

| Core section | Target pages | Essential content |
|---|---:|---|
| Abstract and introduction | 1.0 | Ground-truth-free audit question, post-outcome scope disclosure, three measured consequences, and bounded contribution |
| Related work and novelty boundary | 1.0 | Provenance, MLOps observability, denominator policy, agreement measures, and fitness-for-use; state that the controls are established |
| Workflow, archive, and estimands | 1.5 | Twenty purposive cases, historical-versus-prospective model boundary, denominator definitions, sampling weights, and no-accuracy claim |
| Consequence matrix | 1.5 | Denominator: 58.39% to 98.52%; categorical normalization: 21.58% to 46.13%; schema: 927 complete rows but no study linkage or variance field |
| Denominator-ledger figure | 1.0 | One figure combining stage attrition and the denominator restriction; no additional corpus or flow figure |
| Repeatability results | 1.0 | Weighted mixed-null estimate 1.92% (0.60%–4.34%), realized sample 36/500, and the two-row all-non-null repeatability table |
| Provenance and failure identifiability | 0.75 | Three-way model-alias conflict and why a later logged rerun would audit a different execution |
| Schema implications | 0.75 | Study linkage, effect-measure, time-point, variance, and dependence omissions |
| Discussion and limitations | 1.0 | Post-outcome pivot, purposive cases, no semantic accuracy, model-specific prospective experiment, and generalizability boundary |
| Conclusion | 0.5 | Denominator ledger, representation-aware repeatability, and downstream-oriented schemas |
| **Total** | **10.0** | Includes the core figure and repeatability table |

## Core figures and tables

The core should contain exactly one figure and two compact tables.

| Item | Core role |
|---|---|
| **Figure 1: Denominator ledger** | Shows 95,292 retrieved records, 94,522 retained records, 19,276 INCLUDE labels, 11,500 extracted records, 90,554 requested fields, and the 58.39% to 98.52% denominator effect |
| **Table 1: Consequence matrix** | Leads with the denominator effect, normalization effect, and schema audit; provenance and failure non-identifiability appear last |
| **Table 2: All-non-null repeatability** | Reports categorical and numeric raw exact, normalized exact, token-set exact, and lexical sensitivity; the text leads with the weighted mixed-null estimate |

## Online supplement allocation

The supplement should contain the material needed for auditability but not for the core argument. It should include the case registry; full corpus-quality and configured-limit tables; duplicate-candidate methods; all case-level denominator rows; field-class and case-level evaluator profiles; null-transition patterns; normalization rules; bootstrap details; complete schema-requirement coverage; interface-conformance preflight details; software environment; artifact checksums; protocol and amendments; and the unused validation, meta-analysis, and propagation code with clear labels explaining why those branches are not part of the paper’s substantive results.

The old manuscripts and the complete `previous/` repository snapshot must not be included in the review artifact. They contain identity-bearing text and binary PDFs that a text-only anonymization proxy cannot safely sanitize.

## Why the workflow is not rerun merely to obtain failure rates

A logged rerun would be scientifically useful only as a **separate prospective reliability study**. It would not identify the historical failure rate because the model and provider infrastructure, prompts, response schemas, client and retry code, rate limits, corpus state, and execution period would differ. The paper should state this distinction before reviewers raise it. The absence of a new run is therefore not presented as a resource excuse; it follows from the estimand. The estimand is the auditability of the historical execution.

## Double-anonymous artifact

The review artifact should be a minimal, dedicated repository rather than an anonymized view of the full historical repository. It should contain only the analysis scripts, declared dependencies, compact generated tables, the core figure, neutral documentation, and tests needed to reproduce the reported results. It should exclude Git history, raw bibliographic records, annotation packets, old manuscripts, `previous/`, local logs, user names, affiliations, e-mail addresses, repository-owner URLs, and binary files that may contain author metadata.

Anonymous GitHub provides a stable identity-stripped mirror and downloadable ZIP for double-anonymous review. It automatically replaces the repository owner, organization, repository name, and custom text patterns in text files, but it does not anonymize binary content.[3] The dedicated artifact therefore removes identity-bearing binaries before the mirror is created.

The manuscript should refer to the artifact as:

> An anonymized review artifact containing the analysis code, compact derived tables, figure-generation scripts, and tests is available at **[ANONYMOUS-ARTIFACT-URL]**.

Earlier related work should be cited in neutral third-person form. For example, replace “In our previous work” with “In earlier work, Author(s) developed …” or, when the published citation itself would reveal identity and venue policy permits temporary masking, with “In earlier work [anonymized citation], …”. JDIQ’s current guidance requires relevant prior work to remain cited while avoiding possessive first-person phrasing.[1]

## References

[1]: https://dl.acm.org/journal/jdiq/author-guidelines "JDIQ Author Guidelines"

[2]: https://dl.acm.org/journal/jdiq/call-for-papers "JDIQ Call for Papers"

[3]: https://anonymous.4open.science/faq "Anonymous GitHub Frequently Asked Questions"
