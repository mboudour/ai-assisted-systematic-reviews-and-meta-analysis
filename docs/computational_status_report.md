# Computational Status Report

## Data Quality and Error Propagation in LLM-Assisted Evidence Synthesis

**Prepared:** 19 September 2026
**Repository branch:** `jdiq-rebuild`
**Target venue:** ACM Journal of Data and Information Quality (JDIQ)

## Overall conclusion

The rebuilt project now provides a substantially stronger data-quality audit than the original manuscript. It also shows that the proposed paper **cannot yet support human-referenced accuracy estimates, an evaluator-detection claim, or an empirical error-propagation result**. Those quantities depend on human annotation and source-level synthesis reconstruction that have not occurred.

The strongest completed findings concern denominator choice, repeatability, provenance, missingness, retrieval limits, and synthesis eligibility. The archived evaluator assigned `CORRECT` to 58.39% of all 90,554 requested fields. Excluding 36,881 `UNVERIFIABLE` fields raises the displayed value to 98.52%. This 40.12-percentage-point increase is caused solely by denominator restriction and is not independent evidence of accuracy. Prospective exact stability was 95.0% for screening but only 61.4% for extraction across three calls. The historical archive also lacks the call logs needed to distinguish technical failures from valid exclusions, null extractions, and unverifiable fields.

A separate review of all 20 cases found that **no case currently passes the frozen meta-analysis gate**. Sixteen cases are structurally ineligible from the archived schema and records. Cases 2, 3, 6, and 15 remain conditional candidates, but none is eligible until source-level human verification, common-estimand confirmation, report-to-study linkage, and dependence handling are complete. The rebuilt meta-analysis and propagation engines therefore produce intentionally empty inferential tables rather than reproducing unsupported pooled estimates.

The editor's written confirmation means that journal scope is no longer uncertain. The main risk is now evidential completeness, not fit with JDIQ.

## Status of the 16-step program

| Step | Status | Current outcome |
|---:|---|---|
| 1 | Complete | The historical repository is preserved under `previous/`; the clean project was created on `jdiq-rebuild`. |
| 2 | Partially complete | Sixty CSV files were frozen, hashed, inventoried, and lineage-audited. Sixteen historical non-data artifacts remain unavailable. |
| 3 | Complete | The case registry, prompts, estimands, thresholds, sample design, model roles, and master seed were frozen before new outcome analysis. |
| 4 | Complete | Retrieval and corpus quality were audited for all 20 cases. Historical completeness cannot be certified. |
| 5 | Computationally complete; human work pending | Residual duplicate candidates and a deterministic 200-pair review sample were created. False merges cannot be estimated without removed pairs. |
| 6 | Complete | Historical technical failures were found to be non-identifiable. A prospective event schema now separates failures from analytical labels. |
| 7 | Computationally complete; human work pending | Blinded packets contain 1,192 screening records and 1,504 extraction fields for two independent reviewers. |
| 8 | Computationally complete; human work pending | Design-weighted screening validation is implemented. Its result table remains empty until adjudication. |
| 9 | Computationally complete; human work pending | Extraction validity and evaluator sensitivity/specificity analyses are implemented. Their human-referenced result table remains empty. |
| 10 | Computationally complete; verified inputs pending | An 11-error-type, two-evaluator, 1,320-call experiment is frozen and executable. No calls were made without human-verified source-field pairs. |
| 11 | Complete | The 2,100-call audit found 95.0% exact screening stability and 61.4% exact extraction stability across three calls. |
| 12 | Complete | Twenty independent case reviews found zero currently eligible meta-analysis cases. |
| 13 | Complete | Fixed-effect, DerSimonian–Laird, and REML Hartung–Knapp estimators are tested. Final pooled tables are empty because the gate admitted no case. |
| 14 | Computationally complete; empirical calibration pending | The deterministic Monte Carlo engine is tested. No inferential simulation was run without calibrated errors and an eligible synthesis. |
| 15 | Complete | Denominator, eligibility-gate, and extraction-coverage ablations were completed from the archived data. |
| 16 | Complete | The full offline rebuild, environment capture, checksums, continuous integration, and 67-test validation suite completed successfully. |

## Completed empirical findings

### Retrieval and corpus construction

The archive contains 95,292 pre-deduplication records and 94,522 retained records. The reported 770 removals equal 0.81% of the original total. Cases 3, 5, 8, 11, 15, and 20 reached or exceeded their configured retrieval limit. They must be treated as configuration-truncated unless historical source totals show otherwise. Current source-count checks succeeded for 16 cases, but current counts do not reconstruct historical totals because indexes change over time.

Title, abstract, DOI, and valid-year completeness among retained records are 99.99%, 98.95%, 86.07%, and 98.98%, respectively. Language and source-native identifiers were not collected, so their completeness is not measurable from the archive.

### Deduplication

No residual duplicate rows were found through exact normalized DOI matching. Exact normalized-title groups contained 407 excess rows, and the broader candidate generator found 713 exact-title or high-similarity retained pairs. These are review candidates, not confirmed duplicates. A deterministic sample of 200 retained pairs awaits human classification. The archive contains neither pre-deduplication rows nor a removed-pair log, so false merges and historical positive predictive value remain non-identifiable.

### Failure states, nulls, and evaluator denominators

The screened files contain no request status, retry status, or error field. Historical screening failures are therefore not identifiable, and a technical failure cannot be distinguished retrospectively from a valid `EXCLUDE` label. Extraction nulls likewise conflate absent source information, extraction error, and call failure.

Among 90,554 requested extraction fields, 36,641 are null and 36,881 carry an `UNVERIFIABLE` evaluator verdict. The all-field evaluator profile is 52,877 `CORRECT`, 796 `INCORRECT`, and 36,881 `UNVERIFIABLE`. Almost every null field is unverifiable: 36,423 of 36,641, or 99.41%. The retained 98.52% headline is conditional on deleting every unverifiable field from its denominator.

The categorical-field profile is 78.73% `CORRECT`, 0.61% `INCORRECT`, and 20.66% `UNVERIFIABLE`. Other numeric fields are 25.03%, 2.08%, and 72.89%, respectively. Potentially synthesis-critical fields are 34.21%, 1.12%, and 64.66%. These are dependent same-model verdict shares, not accuracy estimates.

### Human-reference design

The screening reference sample contains 1,192 records across 40 nonempty strata. The extraction reference sample contains 1,504 fields across 191 nonempty strata. Two independently ordered reviewer packets were generated for each task, with historical model decisions hidden. Selection probabilities are retained for design-weighted estimates. No model output may substitute for either reviewer.

### Repeatability and model provenance

All 600 planned screening calls and 1,500 corrected extraction calls completed successfully under the requested `gpt-5-mini` alias. Screening outputs were exactly equal across all three calls for 190 of 200 sampled records, or 95.0%. Ten records changed at least once, and 13 of 400 adjacent repeat transitions changed label.

Extraction outputs were exactly equal across all three calls for 307 of 500 sampled fields, or 61.4%. Stability differed sharply by declared type: 78 of 219 categorical fields were stable (35.62%), compared with 229 of 281 numeric fields (81.49%). Historically null fields were more stable than historically non-null fields, at 76.10% versus 51.19%. These measures describe repeatability, not correctness.

The API returned only the same unversioned alias, `gpt-5-mini`, and provided no nonempty system fingerprint. The retained calls therefore do not identify a fixed model snapshot. A preflight ledger separately preserves 1,500 extraction requests rejected as `Invalid request format` because the initial strict schema used an unsupported union type. The corrected schema uses scalar text plus an explicit null flag. This incident is direct evidence that interface-level schema failures can affect an entire analytical stage unless request and failure provenance are retained.

### Synthesis eligibility

A naive requirement of five numeric estimate-and-interval rows admits seven cases. Raising the threshold to ten rows admits five cases. Independent structural review reduces this to four cases that merely remain pending verification, and the complete gate admits none. This ablation demonstrates that populated numeric columns do not establish a common estimand, independent studies, or valid measurements.

Cases 3 and 15 may support narrow sensitivity analyses after full source reconstruction. Case 3 would require a prespecified log hazard-ratio estimand for three-component major adverse cardiovascular events. Case 15 would require a prespecified adjusted odds-ratio estimand for childhood acute lower respiratory infection under a defined fuel contrast. Cases 2 and 6 remain descriptive candidates. The 921 provisional estimate-and-interval rows are retained only as an audit inventory and are explicitly marked unverified.

### Extraction coverage

Cases 16 through 20 stop at 200 extracted records. Across those capped cases, 7,776 of the 19,276 historical `INCLUDE` decisions have no archived extraction row. This attrition must appear in the manuscript because pooled field-level summaries otherwise imply coverage that did not occur.

## What can and cannot enter the manuscript now

The manuscript can report the corpus counts, configured truncation flags, metadata completeness, residual duplicate candidates, missingness profile, complete evaluator-verdict denominators, prospective repeatability, human-reference sampling design, 20-case synthesis gate, and deterministic sensitivity analyses. These results are supported by retained files and reproducible scripts.

The manuscript cannot yet report screening sensitivity, specificity, precision, negative predictive value, or F-scores. It also cannot report extraction accuracy, evaluator sensitivity, evaluator specificity, injection-test detection rates, calibrated propagation results, or validated pooled meta-analysis estimates. Those tables remain empty by design.

The earlier pooled hazard-ratio stability result should not be carried forward as substantive evidence. The current audit cannot establish that the archived rows represent compatible effects from independent studies. Repeating a statistical calculation would not resolve that data-quality failure.

## Human work required to unlock the remaining analyses

Two reviewers must independently label the 1,192 screening records and 1,504 extraction fields, after which disagreements must be adjudicated. The 200 retained duplicate-pair candidates also require human labels. Historical removed pairs are needed if false-merge performance is to be estimated.

For the evaluator experiment, human-verified source-field pairs must be selected and controlled candidate values constructed under the frozen 11-error taxonomy. The initial design requires 660 items evaluated by two model families, for 1,320 calls.

For any meta-analysis, full-text source verification must establish the effect measure, outcome, comparator, population, time point, and uncertainty for every included estimate. Reports must be linked to underlying studies. One estimate per independent study must be prespecified, or a justified dependence model must be used. At least five independent verified studies are required for any synthesis, and at least ten are required for a primary propagation case.

## Reproducibility state

The repository contains a deterministic offline runner, 67 passing unit and regression tests, a continuous-integration workflow, an environment manifest, and a SHA-256 artifact manifest. The end-to-end runner completed successfully. It excludes new bibliographic queries and new model calls because those operations are time-sensitive or input-dependent and must be invoked separately with their own provenance.

The historical dataset remains outside Git but is frozen locally with file hashes. Generated reviewer packets and raw model responses remain under ignored paths because they may contain bibliographic text. All tracked result tables use explicit empty outputs when an estimand is not currently identifiable.

## Recommended manuscript direction

The paper should emphasize a checkpoint-based audit of **retrieval limits, provenance loss, dependent evaluation, denominator sensitivity, extraction attrition, and synthesis eligibility**. The completed results already support the claim that aggregate agreement can be manufactured by denominator restriction and that downstream synthesis readiness cannot be inferred from populated numeric fields.

A stronger causal claim about evaluator performance or statistical error propagation should wait for the human-reference and source-verification work. If those activities cannot be completed, the manuscript should be reframed as a reproducible audit and methods paper rather than presenting human-referenced model accuracy or empirical propagation.

## References

[1]: https://dl.acm.org/journal/jdiq/author-guidelines "ACM Journal of Data and Information Quality Author Guidelines"
[2]: https://training.cochrane.org/handbook/current/chapter-04 "Cochrane Handbook Chapter 4: Searching for and Selecting Studies"
[3]: https://training.cochrane.org/handbook/current/chapter-10 "Cochrane Handbook Chapter 10: Analysing Data and Undertaking Meta-Analyses"
[4]: https://doi.org/10.18637/jss.v036.i03 "Conducting Meta-Analyses in R with the metafor Package"
[5]: https://json-schema.org/draft/2020-12/json-schema-core "JSON Schema Core Specification, Draft 2020-12"
[6]: https://numpy.org/doc/stable/reference/random/bit_generators/pcg64dxsm.html "NumPy PCG64DXSM Bit Generator"
