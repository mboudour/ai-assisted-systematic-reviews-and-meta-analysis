# Repository Rebuild Log

## Rebuild initialization

**Date:** 19 September 2026

**Branch:** `jdiq-rebuild`

**Historical source commit:** `0a74f80eb30113aad2ebad024541920d2f8558a4`

The repository was clean at the historical source commit before the rebuild began. Nineteen existing top-level items were moved under `previous/`. The `.git/` directory remained at the repository root, preserving complete Git history.

A clean project skeleton was then created at the root. No historical file was intentionally deleted or overwritten. No raw, screened, or extracted case data were present in the cloned repository, so none could be transferred during this step.

The `previous/` tree is an immutable historical snapshot. Any reusable script, configuration, manuscript material, or derived output must be copied into the new tree and audited before use.

## Initial clean-root directories

- `config/`
- `data/manifests/`
- `data/raw_snapshot/`
- `data/interim/`
- `data/processed/`
- `annotations/protocols/`
- `annotations/forms/`
- `annotations/adjudicated/`
- `src/evidence_quality/`
- `scripts/`
- `tests/`
- `results/tables/`
- `results/figures/`
- `results/diagnostics/`
- `manuscript/`
- `docs/`

## Preservation policy

1. Do not edit files under `previous/`.
2. Do not commit secrets or private credentials.
3. Freeze transferred historical data before transformation and record SHA-256 hashes in `data/manifests/`.
4. Keep transformed data outside the historical snapshot.
5. Generate reported results only through tested code in the rebuilt project.

## Historical data import

**Date:** 19 September 2026

The supplied `data.zip` archive was inspected before extraction. It contained no unsafe paths, symbolic links, or credential-like filenames. Its SHA-256 hash is `619cb3d2d0d1f558454f77fd6b0aee98b476a648ec90e793d270c31005282f7c`.

The archive contains 20 raw/post-deduplication CSVs, 20 screened CSVs, and 20 extracted CSVs. These files were copied to the ignored `data/raw_snapshot/` zone and marked read-only. Tracked manifests and the Step 2 audit report record their hashes, schemas, row counts, completeness, cross-stage linkage, and remaining transfer gaps.

## Protocol freeze

**Date:** 19 September 2026

Protocol version `1.0.0` was frozen before new primary computations. It defines six primary estimands, eight separate data-quality dimensions, explicit failure and source-adequacy states, human-reference sampling rules, evaluator error-injection rules, meta-analysis eligibility gates, propagation models, random-number streams, and an append-only amendment policy.

Historical script declarations were extracted programmatically from source commit `0a74f80eb30113aad2ebad024541920d2f8558a4`. Unknown historical model snapshots, prompt versions, run dates, and call failures remain null rather than being inferred. A live model-catalog snapshot was retained for the prospective audit model choices.

## Retrieval and corpus-quality audit

**Date:** 19 September 2026

The audit confirmed 95,292 reported pre-deduplication records and 94,522 retained records. Six cases reached their historical configured retrieval limits. Current source-reported counts were obtained for 16 cases and retained strictly as temporal audit evidence, not as replacements for historical counts. Metadata completeness, conformance, truncation flags, request status, timestamps, and response hashes were written to tracked result tables.

## Deduplication structural audit

**Date:** 19 September 2026

The retained corpora were checked for exact normalized DOI groups, normalized-title groups, and deterministic high-similarity title candidates. A blinded 200-pair retained-record review form was generated. The historical false-merge estimate remains unavailable because the pre-deduplication rows and removed-pair decision log were not supplied; this limitation is preserved explicitly rather than imputed.

## Failure and missingness-state audit

**Date:** 19 September 2026

Historical screening failures were classified as not identifiable because no failure flags were retained. Extraction nulls and evaluator `UNVERIFIABLE` verdicts were audited without reclassifying them as known failures. The audit found 36,641 null extraction cells and 36,881 `UNVERIFIABLE` evaluator cells among 90,554 requested fields. A mandatory prospective event schema and empty table template now separate technical status, source status, and analytical labels.

## Human reference sample preparation

**Date:** 19 September 2026

Deterministic, stratified samples of 1,192 screening records and 1,504 extraction fields were created with recorded inclusion probabilities. Two differently ordered local reviewer packets were generated for each task. Historical screening decisions and evaluator verdicts are hidden from the corresponding reviewer packets. Human labels remain pending and will not be replaced by model-generated labels.

## Screening-validation implementation

**Date:** 19 September 2026

The archived decision profile was separated from accuracy reporting. It contains 19,276 historical INCLUDE decisions among 94,522 screened records. A design-weighted validation script and schema-correct result table are ready, but the accuracy table remains empty until adjudicated human labels are imported.

## Extraction and evaluator-validation implementation

**Date:** 19 September 2026

The historical evaluator profile now reports all 90,554 requested fields without dropping `UNVERIFIABLE`. Those verdicts comprise 20.66% of categorical fields, 72.89% of other numeric fields, and 64.66% of potentially synthesis-critical fields. These are dependent evaluator verdicts, not accuracy estimates. Human-referenced extraction and evaluator metrics remain empty until adjudication.

## Controlled evaluator experiment implementation

**Date:** 19 September 2026

An 11-type blocked error-injection design was frozen. It contains 30 injected items and 30 matched controls per type for each of two evaluator models, giving 1,320 planned calls. The strict-schema concurrent runner and analysis are tested. No calls were made because the experiment requires human-verified source-field pairs; call and metric tables therefore remain empty rather than using model-generated substitutes.

## Meta-analysis eligibility audit

**Date:** 19 September 2026

Twenty independent case reviews were consolidated with deterministic completeness checks. No case currently passes the frozen synthesis gate. Sixteen cases are structurally ineligible from the archived schema and records. Cases 2, 3, 6, and 15 remain pending human verification, but none is a primary synthesis candidate. Cases 3 and 15 may support narrowly specified sensitivity analyses after full-text verification, estimand harmonization, and report-to-study linkage.

## Gated meta-analysis engine

**Date:** 19 September 2026

Fixed-effect inverse-variance, DerSimonian–Laird, and REML Hartung–Knapp estimators were implemented and numerically tested. The production runner requires a verified common scale, human-verified values, and one selected estimate per independent study. Because no case passes the Step 12 gate, the final pooled-result and weight tables are intentionally empty.

## Error-propagation engine

**Date:** 19 September 2026

A deterministic PCG64DXSM Monte Carlo engine now implements screening omission, additive and multiplicative effect errors, variance errors, wrong-target shifts, technical failure, and joint pipeline error. Every replicate uses a SHA-256-derived independent stream. The empirical error model retains null probabilities until human validation and prospective event logs are available, so the final propagation table is intentionally empty.
