# Data Quality and Error Propagation in LLM-Assisted Evidence Synthesis

This branch contains the clean-slate rebuild of the empirical project for a prospective submission to the **ACM Journal of Data and Information Quality (JDIQ)**.

## Preservation guarantee

All content that existed at commit `0a74f80eb30113aad2ebad024541920d2f8558a4` is preserved under [`previous/`](previous/). The historical snapshot must not be edited, deleted, or used as if it were independently validated evidence. Reusable materials will be copied into the new project only after their provenance and behavior have been audited.

## Study purpose

The rebuilt project studies data quality across linked stages of an LLM-assisted evidence-synthesis pipeline. It separates corpus quality, screening validity, extraction accuracy, evaluator validity, technical reliability, provenance, and downstream analytical consequences.

The project does not treat model-generated labels or same-model evaluator verdicts as ground truth. Primary accuracy claims will rely on a documented human-adjudicated reference sample.

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

The rebuild follows a 16-step plan. **Steps 1, 3, 4, 6, 11–13, 15, and 16 are complete.** The data portion of Step 2 is complete, while historical non-data files remain outstanding. Steps 5, 7–10, and 14 have complete computational implementations but remain empirically pending human inputs. Step 11 found 95.0% exact three-call screening stability and 61.4% extraction stability. The Step 12 gate found no currently eligible synthesis case, so Steps 13 and 14 correctly produce no pooled or propagation estimates while retaining tested statistical code. The complete offline rebuild passes 67 tests. Step reports are under [`docs/`](docs/).

The consolidated interpretation is in [`docs/computational_status_report.md`](docs/computational_status_report.md). Exact local setup and rebuilding instructions are in [`docs/reproducibility.md`](docs/reproducibility.md).

## Reproduce the offline analyses

```bash
python3 -m pip install -e '.[dev]'
make pipeline
```

The offline pipeline does not issue new bibliographic queries or make new LLM calls. Those time-sensitive operations have separate scripts and explicit input requirements. Run `make verify` for tests, environment capture, checksums, and repository validation.

## Safety rules

- Never commit API keys, access tokens, or local environment files.
- Never overwrite transferred historical data.
- Never silently convert API or parsing failures into analytical values.
- Never generate placeholder analytical results or figures.
- Fail explicitly when required data, configuration, or provenance is missing.
