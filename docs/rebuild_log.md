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
