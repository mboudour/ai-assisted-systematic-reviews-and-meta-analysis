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

The command executes `scripts/run_pipeline.py`, which rebuilds the data inventory, protocol, corpus audit, duplicate audit materials, missingness audit, human-reference samples, pending validation outputs, meta-analysis gate, gated statistical outputs, propagation gate, sensitivity analyses, test suite, environment snapshot, and artifact checksum manifest.

The runner intentionally consumes the retained `results/tables/current_source_count_audit.csv` rather than issuing new bibliographic API calls. Current source counts are time-sensitive and are not historical retrieval totals.

## External-call stages

Two scripts are excluded from the offline runner:

1. `scripts/run_error_injection_evaluators.py` makes controlled evaluator calls only after `annotations/forms/error_injection_item_template.csv` has been populated with human-verified source-field pairs.
2. `scripts/run_repeatability_audit.py` makes the frozen repeatability calls. Its retained call table allows the downstream analysis to run offline.

Every prospective call records status, retries, requested and returned model identifiers, request identifiers when available, prompt and schema hashes, timing, and token usage. Technical failures are never converted to analytical labels.

## Human-dependent stages

Duplicate-removal validation requires source pairs that were not preserved in the archive. Screening and extraction accuracy require two independent human reviewers and adjudication under `annotations/protocols/human_reference_protocol.md`. The controlled evaluator experiment requires verified source-field pairs. Meta-analysis and error propagation require a verified common estimand, report-to-study linkage, one prespecified estimate per independent study, and verified effect and uncertainty values.

Pending output tables remain header-only. This is deliberate. Empty tables record that an estimand is not currently identifiable; they are not failed scripts or missing files.

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
