# Step 3 Frozen Study Protocol

**Protocol version:** 1.0.0

**Freeze date:** 2026-09-19

**Status:** `frozen_before_new_primary_computations`

## Study design

The study is a retrospective validation of archived pipeline outputs combined with a prospective audit, controlled error-injection experiment, and calibrated propagation simulation. The 20 cases are purposive test cases. They do not support population-level claims about disciplines. The target venue is ACM JDIQ, and manuscript preparation will follow its current author guidance.[1]

Archived model outputs are observations, not ground truth. Human adjudication is the primary reference standard. New model calls will be labeled as prospective 2026 audit runs and will not be attributed retroactively to the historical execution.

## Data-quality dimensions

| Dimension | Operational meaning |
|---|---|
| Completeness | presence of required metadata, source text, and synthesis fields |
| Accuracy | agreement with adjudicated human reference data |
| Validity And Conformance | type, range, unit, logical ordering, and schema checks |
| Consistency | agreement among linked values such as estimate and interval |
| Uniqueness | report deduplication and underlying-study linkage accuracy |
| Provenance | traceability to source record, text, prompt, model, call, and code version |
| Technical Reliability | successful completion without API, parsing, or schema failure |
| Source Adequacy | whether the supplied title/abstract supports field verification |

No arbitrary composite data-quality score will be calculated. Dimensions will be reported separately so that a high value in one dimension cannot mask a defect in another.

## Primary estimands

| ID | Unit | Target | Reference |
|---|---|---|---|
| P1_screening_sensitivity | record | design-weighted probability that an adjudicated relevant record was labeled INCLUDE | adjudicated human screening label |
| P2_extraction_error_rate | field | design-weighted probability that a source-assessable extracted field is incorrect | adjudicated same-source human field label |
| P3_evaluator_sensitivity | field | probability that the evaluator identifies a human-confirmed incorrect field | adjudicated same-source human field label |
| P4_evaluator_specificity | field | probability that the evaluator accepts a human-confirmed correct field | adjudicated same-source human field label |
| P5_observed_propagation_shift | eligible_meta_analysis | difference between pooled effects from matched LLM and human-adjudicated datasets | human-adjudicated synthesis dataset |
| P6_simulated_conclusion_change | monte_carlo_draw | probability that calibrated pipeline errors change a prespecified conclusion | human-adjudicated synthesis result |

Technical failure, evaluator unverifiability, and source inadequacy are required companion rates. None may be removed from reporting by conditional-denominator choices.

## Human reference sample

For screening, the initial stratified sample contains up to 30 historical INCLUDE and 30 historical EXCLUDE records per case. Case 1 contributes all 22 INCLUDE records, giving an expected initial total of 1,192 records. Sampling probabilities will be retained for design-weighted estimation.

For extraction, sampling occurs within case, field audit class, extracted-null status, and historical evaluator verdict. Up to 10 fields are drawn from every nonempty stratum. This gives an initial sample of 1,504 fields from 90,554 archived record-field pairs. Two reviewers independently label all sampled items before adjudication. Sample sizes may increase only under the frozen confidence-interval precision rule.

## Model roles for prospective audits

The primary prospective generator and same-lineage evaluator use `gpt-5-mini` with strict JSON schemas. An independent-evaluator robustness check uses `gemini-3.1-pro-preview`. Human adjudication remains primary. Every call must retain the requested and returned model IDs, prompt and schema hashes, request identifiers, attempts, timestamps, latency, usage, raw response, and explicit call status.

## Meta-analysis gate

A case requires a common estimand, at least five independent studies, human-verified synthesis-critical values, and documented handling of dependent estimates. A primary propagation analysis additionally requires at least ten independent studies. The primary model is REML with Hartung–Knapp inference; fixed-effect and DerSimonian–Laird analyses are comparators.

The number of eligible cases is an output of this gate. It is not fixed in advance, and no additional case will be forced into a meta-analysis merely to increase that number.

## Historical limitations frozen into the protocol

The archived files do not establish actual model snapshots, per-record prompt versions, call dates, retry events, API failures, pre-deduplication rows, or duplicate-pair decisions. These values remain explicitly unknown.

Cases 16, 17, 18, 19, 20 have partial extraction coverage because their retained extraction files contain 200 records despite larger INCLUDE sets.

The query, criterion, schema, and historical prompt registers preserve declarations from the tracked scripts at the historical source commit. They do not prove that every archived output was generated by those exact script versions.

## Amendment policy

Any change requires an append-only amendment that identifies the reason, affected fields, timing relative to outcome inspection, and a new semantic protocol version. Silent edits to frozen decisions are prohibited.

## Machine-readable files

- `config/study_protocol.json` contains the complete estimands and decision rules.
- `config/cases.json` contains the 20 case definitions, queries, criteria, and schemas.
- `config/historical_prompts.json` contains the prompt and model declarations found in the preserved scripts.
- `config/amendments.jsonl` is reserved for append-only protocol amendments.

## References

[1]: https://dl.acm.org/journal/jdiq/author-guidelines "ACM Journal of Data and Information Quality Author Guidelines"
