# Corrected Computational Status Report

## Auditing Data Quality in LLM-Assisted Evidence Synthesis Without Ground Truth

**Prepared:** 19 September 2026
**Repository branch:** `jdiq-rebuild`
**Current scope:** ground-truth-free data-quality audit

## Overall conclusion

The archived data can support a paper about **auditability**, but not a validation study. The current manuscript will not estimate screening accuracy, extraction accuracy, evaluator validity, calibrated error propagation, or pooled effects. Human-reference and source-verification branches are archived and explicitly outside the current scope.

The strongest generalizable lessons are operational:

1. never encode a technical failure as a valid analytical output;
2. report full stage-specific denominators before conditional percentages;
3. version prompts, schemas, models, and parsers, and retain per-call status;
4. separate surface-form repeatability, null-state stability, semantic validity, and factual accuracy; and
5. design extraction schemas for the intended downstream analysis before collecting values.

The append-only amendments in `config/amendments.jsonl` disclose that this is a **post-outcome methodological pivot** adopted after the archived and prospective results had been inspected. The original frozen protocol remains available, and the paper must state that the current research question was not preregistered.

These controls are familiar from provenance, MLOps, observability, data-contract, and LLM-evaluation literature.[3] [4] [5] [6] [7] [8] [9] The contribution must therefore be framed as a quantified account of their absence, not as the invention of new principles.

| Established lesson | Concrete consequence in this project |
|---|---|
| Denominators must remain explicit | Removing 36,881 UNVERIFIABLE cells changes the displayed CORRECT share from 58.39% to 98.52%, a 40.12 percentage-point change. |
| Repeatability must separate representation and null states | The design-weighted probability of changing null status was 1.92% (95% interval 0.60%–4.34%); 36 of 500 items in the realized stratified sample changed status. Among 154 all-non-null categorical items, normalization changes design-weighted exact agreement from 21.58% to 46.13%. |
| Schemas must encode downstream requirements | Ten case schemas yield 927 complete numeric estimate-and-interval rows, yet none records a study-level linkage identifier, dedicated effect-measure label, variance/standard error, or dependence identifier. Report DOIs are retained when available, but they cannot group multiple reports from one study. One schema names an effect-specific estimate (`hazard_ratio`); the other nine use generic `effect_size`. Only two schemas include an analysis time point. |
| Execution provenance must be relational and versioned | The script, README, and manuscript name three different screening aliases. Consequently, none of the 94,522 screening labels can be attributed defensibly to a specific model alias or snapshot. |
| Failure states must be typed separately | Historical failure incidence is not identifiable because the archive retains no call-status or retry history and the code maps terminal failures onto ordinary analytical states. A later logged rerun would characterize a different execution, not recover the historical run. |

## Historical and prospective model roles are different

| Component | Retained model evidence | Evidential role |
|---|---|---|
| Historical screening | Unresolved: script says `gpt-4.1-mini`; README says `gpt-4o-mini`; manuscript says `gpt-4o` | The generating alias for 94,522 archived labels cannot be established |
| Historical extraction | `gpt-4o-mini` is consistently declared but not verified per call | Produced the archived structured fields |
| Historical evaluation | `gpt-4o-mini` is consistently declared but not verified per call | Produced the archived CORRECT, INCORRECT, and UNVERIFIABLE labels |
| Prospective same-request experiment | `gpt-5-mini` | Produced a separate set of repeated outputs from frozen historical inputs |

The screened CSVs have no model or request metadata, and their timestamps predate the first reachable commit of the screening script by six days. The conflict cannot be resolved by preferring executable code over prose. It prevents model-specific interpretation of every historical screening label and is documented in `docs/historical_model_identity_audit.md`.

The prospective experiment therefore **does not estimate repeatability of the historical system**. It measures observed behavior of `gpt-5-mini` under a later prompt, schema, and runtime configuration. The client requested `temperature=0`, and the endpoint accepted every corrected call, but the retained responses do not expose the effective server-side decoding configuration. The result is described as observed same-request repeatability, not as nondeterminism under a verified deterministic configuration.

The current offline analyses make no external model calls. The 2,100 successful prospective calls and 1,500 rejected preflight requests had already occurred before the no-additional-calls scope was adopted.

## Corrected repeatability analysis

The original exact-match summary is retained as a strict descriptive statistic: 190 of 200 screening items and 307 of 500 extraction items produced byte-equivalent parsed values across all three prospective calls. For categorical fields, however, exact string equality confounds substantive change with capitalization, punctuation, word order, spelling, and paraphrase. Numeric stability was also inflated by repeated null outputs.

The corrected sensitivity analysis separates null states and applies deterministic normalization without human labels or new model calls. The **inverse-probability-weighted probability of changing null status was 1.92%**, with a case-cluster bootstrap interval of **0.60%–4.34%**. Null states were therefore **largely, but not perfectly, stable** in the target represented by the stratified sample. In the realized sample, **36 of 500 items (7.20%)** changed null status, while 160 were null in all three calls and 304 were non-null in all three calls. The 36 items comprise 23 categorical and 13 numeric fields and produce 44 adjacent state changes. The weighted estimate and unweighted sample proportion have different estimands and are both reported. All-null items are excluded from the primary non-null comparison.

| All-non-null prospective output | Items | Raw exact, design-weighted | Normalized exact, design-weighted | Token-set exact, design-weighted | Minimum pairwise lexical similarity ≥0.80 |
|---|---:|---:|---:|---:|---:|
| Categorical | 154 | 21.58% | 46.13% | 47.79% | 53.35% |
| Numeric | 150 | 88.40% | 88.55% | 88.55% | 90.22% |

The case-cluster bootstrap interval for normalized exact categorical agreement is **34.76%–56.34%**. The corresponding numeric interval is **81.18%–95.96%**. Normalization therefore changes the categorical conclusion materially and confirms that the earlier 35.62% all-item exact-match figure was not a defensible standalone headline. The residual categorical variation may contain both paraphrase and substantive differences. Lexical thresholds are sensitivity analyses rather than validated semantic-equivalence rules.

These results belong to the separate `gpt-5-mini` experiment. They neither validate the archived values nor describe the repeatability of the unresolved historical screening system or the historically declared extraction/evaluator alias.

## Evaluator labels and denominator policy

Across 90,554 requested historical extraction fields, 52,877 were labelled CORRECT, 796 INCORRECT, and 36,881 UNVERIFIABLE. The extractor and evaluator scripts declare the same `gpt-4o-mini` alias, but the calls retain no returned model identifier or version. The label distribution is not an accuracy estimate.

Nullness and UNVERIFIABLE are almost structurally equivalent in the archive. Of 36,641 null fields, 36,423 were UNVERIFIABLE. This is unsurprising because a null supplies no candidate value to confirm. The informative exceptions are:

- **198 null fields labelled CORRECT**;
- **20 null fields labelled INCORRECT**; and
- **458 non-null fields labelled UNVERIFIABLE**.

The first two groups expose inconsistency in how null values were judged. The last group identifies non-null extracted values that the evaluator could not confirm from the supplied title and abstract. It does not prove that those values are wrong.

Excluding every UNVERIFIABLE field changes the displayed CORRECT share from 58.39% of requested fields to 98.52% of evaluator-decidable fields. This contrast is retained as a transparent correction to the earlier analysis, which foregrounded the restricted percentage. It is not presented as a general accusation that conditional metrics are inherently invalid. The lesson is narrower: a conditional agreement percentage must never be displayed without the full denominator and excluded-state counts.

A comparison between archived evaluator labels and prospective `gpt-5-mini` repeatability is not used as a headline or validation analysis because the models, prompts, schemas, and constructs differ.

## Silent fallback states motivate logging but do not yield informative rate bounds

The historical code returned EXCLUDE after terminal screening failure, all-null values after terminal extraction failure, and all-UNVERIFIABLE labels after terminal evaluator failure. These fallbacks collide with legitimate analytical states. Because no event log was retained, the historical failure rates cannot be recovered.

The formal upper bounds—every EXCLUDE, every all-null record, or every all-UNVERIFIABLE record—are arithmetically valid but too wide to be substantively informative. They are retained only to demonstrate why failure logging is necessary. They are not empirical estimates or headline findings.

### Why a logged rerun would not recover the historical failure rate

A new run with event logging could estimate the operational failure rate of a **current** implementation. It could not recover the historical rate. The requested and returned model identities, provider infrastructure, rate limits, prompt and schema contracts, client code, retry behavior, corpus state, and execution period would differ. The historical execution is the object of this audit, so substituting a later run would answer a different question and could create false retrospective precision. A small logged rerun could be reported only as a separate prospective demonstration of the proposed event schema; it is not required for the present historical-identifiability claim.

## The synthesis gate diagnoses schema insufficiency

The earlier report said that no case passed the meta-analysis gate. That statement is true but misleading without its design context. The historical extraction schemas generally did not capture enough information to establish an outcome definition, time point, effect measure, compatible comparator, uncertainty, report-to-study identity, and independence. The gate therefore diagnoses **schema insufficiency for synthesis**, not failure of the LLM outputs to contain valid evidence.

A naive numeric-completeness rule admitted seven cases at a five-row threshold and five at a ten-row threshold. The stricter gate rejected them because the required analytical context was not collected or verified. No pooled estimate or calibrated propagation analysis will be reported. The general lesson is that downstream analytical requirements must be encoded in the data model before extraction begins.

Cases 16–20 also stopped at 200 extracted records each. Those five cases contain 8,776 records labelled INCLUDE, of which **7,776 (88.61%)** have no archived extraction row. The same omission is **40.34% of all 19,276 INCLUDE labels** across the 20 cases. These are documented coverage limits, not evidence about factual extraction quality.

## Corpus and provenance findings retained under the new scope

The archive contains 95,292 pre-deduplication records and 94,522 retained records. Six cases reached or exceeded their configured retrieval limit. Historical source totals were not retained, so corpus completeness cannot be reconstructed. Current source-count comparisons are temporal diagnostics only.

Titles, abstracts, DOIs, and valid years have measurable completeness. Language and source-native record identifiers were not collected. Exact normalized DOI matching found no residual duplicate rows, while title-based methods generated candidates rather than confirmed duplicates.

Across all 20 historical cases, the archive lacks a versioned model snapshot, prompt version, and failure log. The prospective responses return the alias `gpt-5-mini` but no system fingerprint. These are reportable provenance deficiencies. They prevent attribution to fixed deployed model snapshots.

A separate interface incident rejected all 1,500 preflight extraction requests because the strict response schema contained an unsupported union. After the schema was changed to scalar text plus an explicit null flag, all 1,500 corrected requests completed. This is evidence about client–service interface conformance, not model quality.

## Status under the current manuscript scope

| Workstream | Status | Use in current paper |
|---|---|---|
| Historical repository preservation and data inventory | Complete | Reproducibility and provenance |
| Retrieval, metadata, and configured-limit audit | Complete | Primary evidence |
| Deduplication candidate generation | Complete for ground-truth-free scope | Candidate counts only; no false-merge rate |
| Failure-state identifiability audit | Complete finding: historical rates non-identifiable | Code-level design evidence; no reconstructed rate |
| Human reference sampling and annotation | Archived; not planned | Not used |
| Screening and extraction validation | Archived; not estimable | Not used |
| Evaluator error-injection experiment | Archived; not run | Not used |
| Prospective `gpt-5-mini` same-request experiment | Complete | Separate, model-specific demonstration |
| Normalized and non-null repeatability sensitivity | Complete | Primary prospective analysis |
| Meta-analysis code | Tested but not used substantively | Supplementary software only |
| Calibrated error propagation | Not estimable and removed from paper | Not used |
| Offline reproducibility package | Complete | Primary artifact |

## Recommended manuscript direction

The current paper should lead with five established controls whose consequences are quantified in these data:

1. **Failure states must be orthogonal to analytical labels.** A failed screening call cannot be stored as EXCLUDE, and a failed extraction cannot be stored as an ordinary null.
2. **Quality percentages require denominator ledgers.** Every stage must retain attempted, completed, parseable, non-null, assessable, and excluded counts.
3. **Models, prompts, schemas, and parsers require versioned provenance.** A provider alias without a model snapshot is insufficient for longitudinal reproducibility.
4. **Repeatability requires explicit representation and missingness rules.** Raw exact, normalized exact, semantic, all-null, and mixed-null results answer different questions.
5. **Extraction schemas must be derived from downstream analytical requirements.** Numeric cells alone cannot establish a common estimand or independent-study set.

The prospective repeatability experiment illustrates the fourth control. It cannot characterize the historical models.

The paper should be submitted, if pursued, as a JDIQ Experience Paper. The current official **Call for Papers** explicitly states “Mandatory `Experience:` prefix in the title” and a 10-page limit with an optional online-only supplement.[1] The general Author Guidelines list Experience Papers and link to the call but do not repeat those two details.[2] The substantive title should avoid claiming validation or error propagation.

The 10-page core should prioritize the consequence matrix, the denominator-ledger figure, and the compact repeatability table. Case-level diagnostics, complete schema coverage, transition patterns, implementation details, protocols, amendments, and non-substantive software branches belong in the online supplement. The review artifact must be a dedicated identity-free snapshot rather than the full historical repository because JDIQ requires double anonymity and the `previous/` tree contains identifying text and binary manuscripts.[2]

## References

[1]: https://dl.acm.org/journal/jdiq/call-for-papers "JDIQ Call for Papers"

[2]: https://dl.acm.org/journal/jdiq/author-guidelines "JDIQ Author Guidelines"

[3]: https://www.w3.org/TR/prov-dm/ "PROV-DM: The PROV Data Model"

[4]: https://www.tensorflow.org/tfx/guide/mlmd "ML Metadata"

[5]: https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-spans.md "OpenTelemetry GenAI Semantic Conventions: Generative AI Client Spans"

[6]: https://doi.org/10.1080/07421222.1996.11518099 "Beyond Accuracy: What Data Quality Means to Data Consumers"

[7]: https://www.w3.org/TR/shacl/ "Shapes Constraint Language"

[8]: https://aclanthology.org/2023.acl-long.307/ "Evaluating Open-Domain Question Answering in the Era of Large Language Models"

[9]: https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00754/131566/Know-Your-Limits-A-Survey-of-Abstention-in-Large "Know Your Limits: A Survey of Abstention in Large Language Models"
