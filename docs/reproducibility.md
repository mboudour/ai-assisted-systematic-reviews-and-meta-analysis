# Reproducibility Guide

## Scope

The repository separates **deterministic offline reconstruction** from operations that require external services or human judgment. The offline runner rebuilds every audit and result that is supportable from the frozen archive. It does not rerun bibliographic searches, create human reference labels, or make language-model calls.

## Environment

Use Python 3.11 or later. Install the declared application and test dependencies from the repository root:

```bash
python3 -m pip install -e '.[dev]'
```

The environment used for the retained results is recorded in `results/environment.json`. The tracked `pyproject.toml` is the dependency contract.

## Frozen local data

The source archive is intentionally excluded from Git. Place the frozen snapshot at `data/raw_snapshot/legacy/`. Its filenames and SHA-256 hashes must match `data/manifests/files.csv` and `data/manifests/snapshot.json`. The historical repository is preserved under `previous/`.

The project does not embed API keys or credentials. Local configuration belongs in ignored environment files. Generated reviewer packets and raw model responses remain under ignored `data/interim/` paths because they may contain bibliographic text.

## Deterministic offline rebuild

Run:

```bash
make pipeline
```

The command executes `scripts/run_pipeline.py`, which rebuilds the data inventory, protocol, corpus audit, duplicate audit materials, missingness audit, archived validation stubs, repeatability summaries, normalized and non-null repeatability sensitivity analysis, schema-readiness audit, gated statistical outputs, test suite, environment snapshot, and artifact checksum manifest.

The runner intentionally consumes the retained `results/tables/current_source_count_audit.csv` rather than issuing new bibliographic API calls. Current source counts are time-sensitive and are not historical retrieval totals.

## External-call stages

Two scripts are excluded from the offline runner:

1. `scripts/run_error_injection_evaluators.py` makes controlled evaluator calls only after `annotations/forms/error_injection_item_template.csv` has been populated with human-verified source-field pairs.
2. `scripts/run_repeatability_audit.py` made the prospective `gpt-5-mini` calls. Its retained call table allows the downstream analyses to run offline. Those calls use a different model, prompt, and response schema from the historical `gpt-4.1-mini` screening and `gpt-4o-mini` extraction/evaluation runs.

Every prospective call records status, retries, requested and returned model identifiers, request identifiers when available, prompt and schema hashes, timing, and token usage. Technical failures are never converted to analytical labels.

## Archived stages outside the current manuscript scope

The repository retains code and forms for duplicate-removal validation, screening and extraction accuracy, evaluator error injection, meta-analysis, and calibrated error propagation. The current manuscript does not undertake these activities because it has no human-reference or source-verification component. The append-only entry in `config/amendments.jsonl` records that scope decision.

The corresponding output tables remain header-only. This is deliberate. They record estimands that are not identifiable under the current data and scope; they are not failed scripts or promised future work.

## Verification

Run:

```bash
make verify
```

This executes the full test suite, rebuilds the environment and artifact manifests, and checks repository whitespace. The continuous-integration workflow repeats the test suite on pushes and pull requests.

## References

[1]: https://docs.python.org/3/library/venv.html "Creation of Virtual Environments"
[2]: https://docs.github.com/en/actions "GitHub Actions Documentation"
[3]: https://json-schema.org/draft/2020-12/json-schema-core "JSON Schema Core Specification, Draft 2020-12"
