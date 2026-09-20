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

## Sensitivity and ablation analyses

**Date:** 19 September 2026

The same-model evaluator's `CORRECT` share is 58.39% across all 90,554 requested fields but 98.52% after excluding `UNVERIFIABLE`, a denominator-driven increase of 40.12 percentage points. A naive five-row completeness gate admits seven cases, while the full gate admits none. Five capped extraction files omit 7,776 of 19,276 historical INCLUDE records.

## Repeatability and model provenance

**Date:** 19 September 2026

The frozen audit completed 600 screening calls and 1,500 extraction calls. Exact three-call stability was 95.0% for 200 screening records and 61.4% for 500 extraction fields. Categorical extraction stability was 35.62%, compared with 81.49% for numeric fields. The returned identifier was the unversioned `gpt-5-mini` alias and no nonempty system fingerprint was exposed. A separate preflight ledger preserves 1,500 extraction requests rejected because an unsupported union-type response schema produced `Invalid request format`; the corrected design uses scalar text plus an explicit null flag.

## Reproducibility package

**Date:** 19 September 2026

The deterministic offline runner rebuilt every result supported by the frozen snapshot without issuing new bibliographic queries or model calls. The environment and SHA-256 artifact manifests were regenerated, all repository whitespace checks passed, and the integrated suite completed with 67 passing tests. Continuous integration, exact run commands, protected-data rules, and separate human-review archives are available.

## No-human-validation scope amendment and repeatability correction

**Date:** 19 September 2026

The project scope was amended after inspecting the archived outputs and prospective repeatability results. Human-reference validation, controlled evaluator injection, empirical error calibration, and pooled meta-analysis are no longer planned for the current manuscript. Their code and forms remain archived; they are not presented as future requirements.

The historical and prospective model roles were also separated explicitly. Historical screening declared `gpt-4.1-mini`, and historical extraction and evaluation declared `gpt-4o-mini`. The later 600 screening and 1,500 corrected extraction calls used `gpt-5-mini` with different prompts and strict schemas. They are a separate prospective same-request experiment on frozen inputs, not a repeatability analysis of the historical models. The client requested `temperature=0`, but the retained responses do not verify the effective server-side decoding configuration.

A new offline sensitivity analysis separates 160 all-null, 304 all-non-null, and 36 mixed-null extraction items. Among all-non-null categorical fields, design-weighted raw exact agreement was 21.58%, normalized exact agreement was 46.13%, token-set agreement was 47.79%, and the share with minimum pairwise lexical similarity of at least 0.80 was 53.35%. Among all-non-null numeric fields, raw and normalized exact agreement were 88.40% and 88.55%. These values replace the earlier categorical-versus-numeric exact-match contrast as the primary interpretation. They measure output-form repeatability, not semantic correctness.

The evaluator nullness result, silent-failure bounds, and synthesis gate were correspondingly narrowed. Null–UNVERIFIABLE concordance is treated as structurally expected; attention shifts to the 218 null fields with a non-UNVERIFIABLE label and 458 non-null fields labelled UNVERIFIABLE. Failure bounds are used only to motivate event logging. The zero-case synthesis result is interpreted as evidence that the historical schemas did not collect sufficient analytical context, not as evidence that all extracted values are scientifically unusable.

## Second-round evidential corrections

**Date:** 19 September 2026

A comparison of the uploaded manuscript, preserved empirical README, committed screening script, archived CSV schema, file timestamps, and reachable Git history identified a three-way model-identity conflict. Manuscript Section 4.5.1 reports `gpt-4o`, the README reports `gpt-4o-mini`, and every reachable script revision declares `gpt-4.1-mini`. The 94,522 screening rows contain no model or request metadata and predate the first reachable screening-script commit by six days. The historical screening model is now recorded as unresolved. Amendment `A-2026-09-19-02` corrects the earlier amendment without altering it.

The repeatability report now treats 36 of 500 sampled extraction items as mixed null-status items rather than implying that nulls are uniformly stable. These items account for 44 adjacent state changes. Their unweighted sample prevalence is 7.20%; the inverse-probability-weighted estimate is 1.92%, with a case-cluster bootstrap interval of 0.60%–4.34%.

The failure workstream is relabelled as an identifiability audit. All 94,522 screening decisions and all 11,500 extraction rows lack call status. The 75,246 EXCLUDE labels, 23 all-null extraction rows, and 22 all-UNVERIFIABLE evaluator rows are collision sets that may contain valid outputs or failures; they are not reconstructed failures.

The extraction-cap statement now reports both valid denominators. The 7,776 omitted rows equal 88.61% of the 8,776 INCLUDE labels in Cases 16–20 and 40.34% of all 19,276 INCLUDE labels across the 20 cases.

A deterministic claim–consequence matrix now positions five controls against established provenance, MLOps, observability, data-contract, and LLM-evaluation literature. It quantifies the consequences observed in this archive rather than claiming the controls as novel. The historical schema audit records that ten case schemas yielded 927 complete estimate-and-interval rows. Report DOIs are retained when available, but none of the 20 schemas has a study-level linkage identifier, dedicated effect-measure label, variance or standard-error field, or dependence identifier. One schema names `hazard_ratio`; the other nine estimate-and-interval schemas use generic `effect_size`. Only two have an analysis time-point field.

The current JDIQ Call for Papers was checked directly. It explicitly requires the `Experience:` title prefix and sets a 10-page limit with an optional online-only supplement. The general Author Guidelines list Experience Papers and link to the call but do not repeat those two details.

## Third-round editorial corrections and review packaging

**Date:** 19 September 2026

The null-state interpretation now leads with the inverse-probability-weighted mixed-null estimate of 1.92% (case-cluster bootstrap interval 0.60%–4.34%) and describes null states as largely, but not perfectly, stable. The 36/500 realized-sample proportion is retained with its distinct estimand.

The consequence matrix now leads with the three measured effects: the 58.39% to 98.52% denominator contrast, the 21.58% to 46.13% categorical normalization contrast, and the 927-row schema audit. Failure logging is stated as historical non-identifiability rather than quantified by counting ordinary outputs that share fallback values. The reports explicitly explain that a later logged rerun would characterize a different model, prompt, schema, API, and execution period rather than recover the historical failure rate.

A single core-paper denominator-ledger figure was added in deterministic PNG and PDF formats. A 10-page JDIQ core and online-supplement allocation was documented. A dedicated minimal review artifact was built without Git history, raw bibliographic text, the `previous/` tree, old manuscripts, author-identifying strings, or unnecessary binaries. The artifact builds offline, requires no model or network calls, and passed its isolated test suite. Its public source uses anonymous commit metadata; the reviewer-facing Anonymous GitHub mirror requires completion of the service's read-only GitHub App authorization.

## Final pre-submission evidence corrections

**Date:** 19 September 2026

The prospective screening experiment is now reported rather than merely described: 190 of 200 records retained the same label across three calls, and 13 of 400 adjacent comparisons changed label. A disclosure-safe 240-row evaluator verdict cube was added at the case-by-field-type-by-null-status-by-verdict level; it reproduces all 90,554 field cells, the CORRECT/INCORRECT/UNVERIFIABLE totals, and the null cross-tabulation without bibliographic text.

The meta-analysis readiness discussion is now based only on schema coverage. Human-verification and expert-review gate rows were removed from the sensitivity output and anonymous artifact. The schema result is 0/20 cases jointly containing study linkage, effect-measure metadata, variance or standard error, and dependence identifiers.

The bibliography now records Anna Noel-Storr correctly from DOI 10.1002/cl2.70074. ACM CCS concepts are visible in the core paper. Every case that reached or exceeded a retrieval limit is listed in the supplement, including the 4,500-record Case 5 limit and the 4,600 records obtained because the OpenAlex loop appended a complete 200-record page before the next stopping-condition check.

The public SSRN prior report (DOI 10.2139/ssrn.7346302) is cited neutrally in the third person. An editor-only disclosure was prepared separately; it is not part of the reviewer-facing package. The final core paper remains exactly 10 pages, the online supplement is 7 pages, and the anonymous artifact rebuilds offline with 11 focused tests.

## Fourth-round pre-submission corrections

**Date:** 20 September 2026

The manuscript and supplement were audited after an external consistency review. The obsolete manual cross-reference to “Supplement Table S1” was removed; all LaTeX references were checked against local labels and both documents compiled without undefined-reference or overfull-box warnings. The paper now states that protocol amendments are summarized in the supplement and supplied verbatim in the anonymous artifact, which now includes `config/amendments.jsonl`.

The prior public report is cited through a double-anonymous placeholder in the reviewer-facing BibTeX database. A separate confidential cover-letter draft documents the public report, the overlap in archive, the present manuscript's revised contribution, and the unsupported historical screening-model attribution. A public correction draft was prepared but not posted because publication of an erratum is an external action requiring author approval.

The screening-repeatability methods now disclose the complete deterministic selection rule: a 1,192-record case-by-historical-label frame created by seeded hashing, followed by a second seeded hash rank selecting 200 records independent of file order. The realized subset covered all 20 cases and contained 96 historical INCLUDE and 104 historical EXCLUDE records.

The schema result now states that each of the four synthesis-critical fields is individually absent from all 20 schemas. Section 4.3 was retitled to cover both screening and extraction repeatability. The paper and supplement explicitly report the 11.45% complement of numeric normalized exact agreement, and the lessons add a versioned controlled-vocabulary recommendation for finite categorical outputs.

The anonymous artifact was rebuilt and tested. It contains `results/tables/evaluator_verdict_cube.csv` and both amendment records, while `expert_structural_review` and `cases_pending_verification` are absent from the sensitivity table. The reviewer-facing package passed an identity scan and contains a 10-page core paper, 7-page supplement, blinded LaTeX/BibTeX source, and the refreshed artifact.
