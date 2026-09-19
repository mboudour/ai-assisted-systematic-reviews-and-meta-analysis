# Step 2 Historical Data Inventory and Lineage Audit

**Generated:** 2026-09-19T13:51:35.348223+00:00

## Snapshot

The supplied archive has SHA-256 `619cb3d2d0d1f558454f77fd6b0aee98b476a648ec90e793d270c31005282f7c`. It contained 60 case CSV files: 20 raw, 20 screened, and 20 extracted files. No credential-like filenames, unsafe archive paths, or symbolic links were detected before extraction.

The archive and CSV files were copied into the ignored `data/raw_snapshot/` zone. Snapshot files were marked read-only. The original upload was not modified.

## Stage totals

| Stage | Files | Rows |
|---|---:|---:|
| Raw/post-deduplication corpus | 20 | 94,522 |
| Screened corpus | 20 | 94,522 |
| Extracted records | 20 | 11,500 |

The historical files called `raw` are post-deduplication corpus files. The archive does not contain the pre-deduplication records or a duplicate-pair decision table.

## Initial data-quality profile

| Measure | Count | Rate or denominator |
|---|---:|---:|
| Raw records without abstract text | 990 | 1.05% of raw rows |
| Raw records without DOI | 13,167 | 13.93% of raw rows |
| Historical LLM INCLUDE decisions | 19,276 | 20.39% of screened rows |
| Judge CORRECT cells | 52,877 | 58.39% of judge cells |
| Judge INCORRECT cells | 796 | 0.88% of judge cells |
| Judge UNVERIFIABLE cells | 36,881 | 40.73% of judge cells |
| Blank or invalid judge cells | 0 | 0.00% of judge cells |

These evaluator verdicts describe the historical same-model evaluation and are not human-validated accuracy estimates.

## Lineage classification

Cases with complete raw-to-screened linkage but partial extraction coverage: 16, 17, 18, 19, 20.

Cases with stage-linkage errors: none.

A case marked as having complete stage linkage is structurally linked only. It is not thereby human validated, and the archive alone does not identify prompts, model snapshots, run dates, retry events, or technical failures at record level.

## Anomaly summary

| Severity | Checks triggered |
|---|---:|
| Critical | 0 |
| Error | 18 |
| Warning | 12 |

Detailed counts and affected cases are recorded in `data/manifests/anomalies.csv`. Per-file hashes and schema information are in `data/manifests/files.csv`; cross-stage case summaries are in `data/manifests/cases.csv`.

## Reproducibility classification

The historical datasets are **partially traceable**. The files are now immutable and their stage linkage can be audited, but complete computational reproducibility is not yet established because record-level call logs, model snapshots, exact prompt versions, pre-deduplication inputs, and duplicate decisions are absent.

## Outstanding transfer gap

The uploaded archive contains the three data directories only. Files listed in the earlier local project tree but absent from both this archive and the Git snapshot remain recorded in `data/manifests/transfer_gaps.csv`. The most important are the Case 3 audit, Case 15 adjudication, meta-analysis sensitivity results and script, sequential screening summary, historical dependency file, and execution script.

Step 2 remains open until those files are transferred or explicitly declared unavailable. Missing provenance elements must be represented explicitly in the frozen protocol in Step 3 and must not be reconstructed as if they were observed historical facts.
