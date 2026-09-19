# Human Reference Annotation and Adjudication Protocol

**Protocol version:** 1.0.0
**Frozen:** 19 September 2026

## Purpose

This protocol creates the independent reference standard for screening and field-level extraction. It is designed to separate model error from source inadequacy and technical failure. Model decisions are not treated as truth, and annotators must not use an LLM or other automated classifier to make their judgments.

Two reviewers independently annotate every sampled item. They work from separate packets with different row orders. Screening packets hide the historical LLM decision. Extraction packets hide the historical evaluator verdict. Adjudication begins only after both independent files have been returned and locked.

## Sampling design

The screening sample contains **1,192 records** selected without replacement from 40 case-by-historical-decision strata. Up to 30 records were selected from each stratum. Case 1 contributes all 22 historical INCLUDE records because that stratum contains fewer than 30. Sampling probabilities are stored in `data/manifests/screening_sample_manifest.csv`.

The extraction sample contains **1,504 fields** selected without replacement from 191 nonempty strata defined by case, field audit class, extracted-null status, and historical evaluator verdict. Up to 10 fields were selected from each stratum. Sampling probabilities are stored in `data/manifests/extraction_sample_manifest.csv`.

The initial sample can be enlarged only under the confidence-interval precision rule in `config/study_protocol.json`. It must not be enlarged or stopped because the observed results look favorable.

## Screening annotation

Each reviewer receives a packet containing the case-specific inclusion criteria, title, and abstract. The reviewer records exactly one `human_screening_label`. The separation of independent screening from later reconciliation follows established systematic-review practice.[3]

| Label | Definition |
|---|---|
| `include` | The title and abstract meet the stated inclusion criteria. |
| `exclude` | The title and abstract provide sufficient evidence that at least one criterion is not met. |
| `uncertain` | The available title and abstract do not support a defensible include/exclude decision. |

When the label is `exclude`, the reviewer records one primary reason:

| Code | Meaning |
|---|---|
| `NOT_TOPIC` | The central topic does not match the case. |
| `NOT_POPULATION` | The population or setting does not match. |
| `NOT_INTERVENTION_EXPOSURE` | The intervention or exposure does not match. |
| `NOT_COMPARATOR` | A required comparator is absent or incompatible. |
| `NOT_OUTCOME` | The required outcome is absent or incompatible. |
| `NOT_DESIGN` | The study design does not meet the criterion. |
| `NOT_EMPIRICAL` | The record is editorial, commentary, protocol, or otherwise non-empirical when empirical evidence is required. |
| `DUPLICATE_REPORT` | The record is a duplicate report of another sampled record. |
| `OTHER` | None of the predefined reasons applies; explain in `review_notes`. |

`primary_exclusion_reason` must be blank for `include` and `uncertain`. Confidence is an integer from 1, meaning very uncertain, to 5, meaning very certain. Confidence does not change the categorical label.

## Extraction annotation

Each extraction item contains one requested field, its archived extracted value, and the same title and abstract available to the historical model. The reviewer first assigns one `source_status`:

| Source status | Definition |
|---|---|
| `reported_explicitly` | The title or abstract directly states the field value. |
| `derivable_from_source` | The value follows through a transparent, reproducible calculation from reported text. |
| `not_reported` | The source does not provide the information needed for the field. |
| `ambiguous_source` | The source contains relevant information but does not determine one defensible value. |
| `source_unavailable` | No usable title or abstract is available in the packet. |
| `not_applicable` | The requested field does not apply to the study described. |

The reviewer then assigns one `human_field_label`:

| Field label | Definition |
|---|---|
| `correct` | The archived extracted value matches the source, including meaning, sign, scale, unit, outcome, comparator, subgroup, and time point. A null is correct only when no value should have been extracted. |
| `incorrect` | The archived value conflicts with the source, omits an explicitly reported value, or supplies a value when the field should be null. |
| `not_assessable` | The available source cannot establish whether the extraction is correct. |

For `incorrect`, the reviewer enters a corrected value when the source supports one. Numeric corrections must preserve the reported unit in `corrected_unit`. The reviewer also provides the shortest source quotation that supports the decision. For `not_assessable`, the evidence quotation may identify why the source is inadequate.

## Null handling

A null is not automatically correct or unverifiable. Reviewers apply the following rules:

| Situation | Source status | Field label |
|---|---|---|
| Value is absent and the field is applicable | `not_reported` | `correct` if the archived value is null |
| Value is explicit but the archived value is null | `reported_explicitly` | `incorrect` |
| Source is ambiguous | `ambiguous_source` | `not_assessable` |
| Field does not apply | `not_applicable` | `correct` if the archived value is null |
| No usable source text | `source_unavailable` | `not_assessable` |

Technical failure is not an annotation label. If a packet is malformed, the reviewer stops and reports the packet problem outside the annotation fields.

## Independent review and adjudication

Reviewers must not compare notes until both independent files are locked. After lock, a reconciliation script will identify disagreements and invalid entries. Agreement will be reported before adjudication using raw agreement, Cohen’s kappa, and Gwet’s AC1 where appropriate. Agreement statistics describe annotation reliability; they do not replace adjudication.[1] [2]

For every disagreement, reviewers discuss the source and criteria. The adjudicated label is the consensus label. If consensus is not reached, a third reviewer decides. If no defensible resolution is possible, the final state is `human_unresolved`; it is retained and reported rather than forced into a binary label.

## Full-text synthesis reference

This protocol establishes a same-source reference because the historical model saw titles and abstracts. Any field used in a meta-analysis requires a second synthesis-reference check against the best available underlying source, normally the full text. Same-source correctness does not by itself establish synthesis correctness.

## Data-entry validation

The annotation import process will reject unknown sample identifiers, duplicate reviewer–sample combinations, missing reviewer identifiers, invalid labels, invalid confidence scores, exclusion reasons attached to non-excluded records, missing corrections for assessable incorrect fields, and evidence quotations for which the sample source cannot be located.

No model decision or evaluator verdict should be copied into the human label fields. The link to historical outputs is restored only after independent review is complete.

## References

[1]: https://doi.org/10.1177/001316446002000104 "A Coefficient of Agreement for Nominal Scales"
[2]: https://doi.org/10.1348/000711006X126600 "Computing Inter-Rater Reliability and Its Variance in the Presence of High Agreement"
[3]: https://training.cochrane.org/handbook/current/chapter-04 "Cochrane Handbook Chapter 4: Searching for and Selecting Studies"
