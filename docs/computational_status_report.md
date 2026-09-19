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

The append-only amendment in `config/amendments.jsonl` records this post-outcome scope change without rewriting the original frozen protocol.

## Historical and prospective model roles are different

| Component | Declared model | Evidential role |
|---|---|---|
| Historical screening | `gpt-4.1-mini` | Produced the archived INCLUDE and EXCLUDE labels |
| Historical extraction | `gpt-4o-mini` | Produced the archived structured fields |
| Historical evaluation | `gpt-4o-mini` | Produced the archived CORRECT, INCORRECT, and UNVERIFIABLE labels |
| Prospective same-request experiment | `gpt-5-mini` | Produced a separate set of repeated outputs from frozen historical inputs |

The prospective experiment therefore **does not estimate repeatability of the historical system**. It measures observed behavior of `gpt-5-mini` under a later prompt, schema, and runtime configuration. The client requested `temperature=0`, and the endpoint accepted every corrected call, but the retained responses do not expose the effective server-side decoding configuration. The result is described as observed same-request repeatability, not as nondeterminism under a verified deterministic configuration.

The current offline analyses make no external model calls. The 2,100 successful prospective calls and 1,500 rejected preflight requests had already occurred before the no-additional-calls scope was adopted.

## Corrected repeatability analysis

The original exact-match summary is retained as a strict descriptive statistic: 190 of 200 screening items and 307 of 500 extraction items produced byte-equivalent parsed values across all three prospective calls. For categorical fields, however, exact string equality confounds substantive change with capitalization, punctuation, word order, spelling, and paraphrase. Numeric stability was also inflated by repeated null outputs.

The corrected sensitivity analysis separates null states and applies deterministic normalization without human labels or new model calls. Among the 500 extraction items, **160 were null in all three calls, 304 were non-null in all three calls, and 36 changed null status**. All-null items are excluded from the primary non-null comparison.

| All-non-null prospective output | Items | Raw exact, design-weighted | Normalized exact, design-weighted | Token-set exact, design-weighted | Minimum pairwise lexical similarity ≥0.80 |
|---|---:|---:|---:|---:|---:|
| Categorical | 154 | 21.58% | 46.13% | 47.79% | 53.35% |
| Numeric | 150 | 88.40% | 88.55% | 88.55% | 90.22% |

The case-cluster bootstrap interval for normalized exact categorical agreement is **34.76%–56.34%**. The corresponding numeric interval is **81.18%–95.96%**. Normalization therefore changes the categorical conclusion materially and confirms that the earlier 35.62% all-item exact-match figure was not a defensible standalone headline. The residual categorical variation may contain both paraphrase and substantive differences. Lexical thresholds are sensitivity analyses rather than validated semantic-equivalence rules.

These results belong to the separate `gpt-5-mini` experiment. They neither validate the archived values nor describe the repeatability of `gpt-4.1-mini` or `gpt-4o-mini`.

## Evaluator labels and denominator policy

Across 90,554 requested historical extraction fields, 52,877 were labelled CORRECT, 796 INCORRECT, and 36,881 UNVERIFIABLE by the same `gpt-4o-mini` model family used for extraction. The label distribution is not an accuracy estimate.

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

## The synthesis gate diagnoses schema insufficiency

The earlier report said that no case passed the meta-analysis gate. That statement is true but misleading without its design context. The historical extraction schemas generally did not capture enough information to establish an outcome definition, time point, effect measure, compatible comparator, uncertainty, report-to-study identity, and independence. The gate therefore diagnoses **schema insufficiency for synthesis**, not failure of the LLM outputs to contain valid evidence.

A naive numeric-completeness rule admitted seven cases at a five-row threshold and five at a ten-row threshold. The stricter gate rejected them because the required analytical context was not collected or verified. No pooled estimate or calibrated propagation analysis will be reported. The general lesson is that downstream analytical requirements must be encoded in the data model before extraction begins.

Cases 16–20 also stopped at 200 extracted records. Across those cases, 7,776 of 19,276 records labelled INCLUDE have no archived extraction row. This is a documented coverage limit, not evidence about factual extraction quality.

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
| Failure-state reconstruction | Complete | Primary methodological evidence |
| Human reference sampling and annotation | Archived; not planned | Not used |
| Screening and extraction validation | Archived; not estimable | Not used |
| Evaluator error-injection experiment | Archived; not run | Not used |
| Prospective `gpt-5-mini` same-request experiment | Complete | Separate, model-specific demonstration |
| Normalized and non-null repeatability sensitivity | Complete | Primary prospective analysis |
| Meta-analysis code | Tested but not used substantively | Supplementary software only |
| Calibrated error propagation | Not estimable and removed from paper | Not used |
| Offline reproducibility package | Complete | Primary artifact |

## Recommended manuscript direction

The current paper should lead with the three generalizable controls supported by the evidence:

1. **Failure states must be orthogonal to analytical labels.** A failed screening call cannot be stored as EXCLUDE, and a failed extraction cannot be stored as an ordinary null.
2. **Quality percentages require denominator ledgers.** Every stage must retain attempted, completed, parseable, non-null, assessable, and excluded counts.
3. **Models, prompts, schemas, and parsers require versioned provenance.** A provider alias without a model snapshot is insufficient for longitudinal reproducibility.

The prospective repeatability experiment can illustrate the additional need to distinguish exact string agreement, normalized agreement, null-state stability, and semantic equivalence. It cannot characterize the historical models.

The paper should be submitted, if pursued, as a JDIQ Experience Paper. The required title prefix is `Experience:`. The substantive title should avoid claiming validation or error propagation.

## References

[1]: https://dl.acm.org/journal/jdiq/call-for-papers "JDIQ Call for Papers"

[2]: https://dl.acm.org/journal/jdiq/author-guidelines "JDIQ Author Guidelines"
