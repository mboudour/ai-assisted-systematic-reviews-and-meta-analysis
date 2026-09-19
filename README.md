# Auditing Data Quality in LLM-Assisted Evidence Synthesis Without Ground Truth

This branch contains the clean-slate rebuild of the empirical project for a prospective submission to the **ACM Journal of Data and Information Quality (JDIQ)**.

## Preservation guarantee

All content that existed at commit `0a74f80eb30113aad2ebad024541920d2f8558a4` is preserved under [`previous/`](previous/). The historical snapshot must not be edited, deleted, or used as if it were independently validated evidence. Reusable materials will be copied into the new project only after their provenance and behavior have been audited.

## Study purpose

The rebuilt project studies data quality across linked stages of an LLM-assisted evidence-synthesis workflow. The current manuscript scope is a ground-truth-free audit of corpus completeness, assessability, denominator sensitivity, failure-state observability, provenance, interface conformance, same-request repeatability, and analytical readiness.

The project does not treat model-generated labels or same-model evaluator verdicts as ground truth. It makes no screening-accuracy, extraction-accuracy, evaluator-validity, calibrated error-propagation, or pooled-effect claim. The append-only amendments in [`config/amendments.jsonl`](config/amendments.jsonl) record the post-outcome scope change and the later historical-model correction; the earlier human-validation materials remain archived but are not planned work.

## Project structure

| Path | Purpose |
|---|---|
| `previous/` | Immutable historical repository snapshot |
| `config/` | Frozen case, model, prompt, schema, and analysis configuration |
| `data/manifests/` | File inventory, checksums, licenses, and provenance |
| `data/raw_snapshot/` | Immutable transferred historical inputs; excluded from Git by default |
| `data/interim/` | Reconstructable intermediate data; excluded from Git |
| `data/processed/` | Analysis-ready data; excluded from Git until release review |
| `annotations/` | Human-review protocols, forms, and adjudicated references |
| `src/evidence_quality/` | Tested reusable analysis package |
| `scripts/` | Thin command-line entry points |
| `tests/` | Unit and integration tests |
| `results/` | Generated tables, figures, and diagnostics |
| `manuscript/` | Blinded ACM manuscript and supplementary material |
| `docs/` | Design decisions, audit reports, and reproducibility documentation |

## Execution sequence

The original rebuild followed a 16-step plan. The current no-human-validation scope retains the completed audits and retires the human-reference, error-injection, and calibrated-propagation branches rather than leaving them as promised future work. The frozen historical protocol remains intact, and the change is recorded as an amendment.

Step 11 is a separate prospective `gpt-5-mini` experiment on frozen historical inputs. It is not a repeatability test of the historical system. The historical screening model is unresolved because the committed script declares `gpt-4.1-mini`, the empirical README reports `gpt-4o-mini`, and manuscript Section 4.5.1 reports `gpt-4o`; the screening rows retain no model or request metadata. Historical extraction and evaluator materials consistently declare `gpt-4o-mini` but also lack per-call verification. The full conflict is documented in [`docs/historical_model_identity_audit.md`](docs/historical_model_identity_audit.md). The prospective client requested `temperature=0`, but the saved responses do not expose the effective server-side decoding configuration. Raw exact matching is retained as a strict measure, while the companion sensitivity analysis separates null states and applies deterministic normalization to all-non-null outputs. Step reports are under [`docs/`](docs/).

The consolidated interpretation is in [`docs/computational_status_report.md`](docs/computational_status_report.md). The five lessons, their observed consequences, and their literature boundaries are in [`docs/claim_consequence_matrix.md`](docs/claim_consequence_matrix.md). Exact local setup and rebuilding instructions are in [`docs/reproducibility.md`](docs/reproducibility.md).

## Reproduce the offline analyses

```bash
python3 -m pip install -e '.[dev]'
make pipeline
```

The offline pipeline does not issue new bibliographic queries or make new LLM calls. It reanalyzes already saved outputs, including the earlier 2,100 successful prospective calls and the separate ledger of 1,500 rejected preflight requests. Those requests were made before the present no-additional-calls scope. Run `make verify` for tests, environment capture, checksums, and repository validation.

## Safety rules

- Never commit API keys, access tokens, or local environment files.
- Never overwrite transferred historical data.
- Never silently convert API or parsing failures into analytical values.
- Never generate placeholder analytical results or figures.
- Fail explicitly when required data, configuration, or provenance is missing.
