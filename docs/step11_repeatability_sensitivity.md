# Step 11 Repeatability Sensitivity Analysis

## Scope and model boundary

This analysis uses the already completed `gpt-5-mini` calls. The historical screening model is unresolved: the committed script declares `gpt-4.1-mini`, the empirical README reports `gpt-4o-mini`, and manuscript Section 4.5.1 reports `gpt-4o`. Historical extraction and evaluator materials consistently declare `gpt-4o-mini` but lack per-call verification. The results therefore describe a separate prospective experiment on frozen historical inputs; they do not estimate repeatability of the historical models or validate their outputs.

The client requested `temperature=0`, and the endpoint accepted every corrected call, but the retained responses do not expose the effective decoding configuration. The results are reported as observed same-request repeatability, not as evidence about nominally deterministic decoding.

## Null-state decomposition

Of 500 extraction items, 160 were null in all three calls, 304 were non-null in all three calls, and 36 (7.20%) changed null status at least once. The mixed-null group contained 23 categorical and 13 numeric items and accounted for 44 adjacent state changes. Its inverse-probability-weighted estimate was 1.92% (case-cluster bootstrap 95% interval 0.60%–4.34%). All-null items are trivially stable and are excluded from the primary non-null comparison.

## All-non-null outputs

| Declared type | Items | Raw exact, weighted | Normalized exact, weighted | Token-set exact, weighted | Minimum pairwise lexical similarity ≥0.80, weighted |
|---|---:|---:|---:|---:|---:|
| Categorical | 154 | 21.58% | 46.13% | 47.79% | 53.35% |
| Numeric | 150 | 88.40% | 88.55% | 88.55% | 90.22% |

Normalization uses Unicode NFKC, case folding, punctuation and separator normalization, whitespace normalization, and a small declared British-to-American spelling map. Token-set equality additionally ignores token order and duplicate tokens. Lexical thresholds are reported only as sensitivity analyses; they are not validated semantic-equivalence cutoffs.

The categorical raw exact rate is therefore not a defensible standalone measure of instability. Normalization approximately doubles its design-weighted estimate, while the remaining gap includes both wording variation and potentially substantive output changes. Numeric non-null outputs remain more stable, but this is a result for the prospective `gpt-5-mini` experiment only.
