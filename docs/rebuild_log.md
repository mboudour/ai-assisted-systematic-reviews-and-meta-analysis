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
