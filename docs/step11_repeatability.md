# Step 11 Prospective Same-Request and Model-Provenance Audit

## Results

The audit attempted 2,100 calls using the requested model alias `gpt-5-mini`. Every call preserves the returned model identifier, request identifier, system fingerprint when available, prompt and schema hashes, timing, token usage, retries, and explicit status.

This was a separate prospective experiment on frozen historical inputs. The historical screening model is unresolved: the committed script declares `gpt-4.1-mini`, the empirical README reports `gpt-4o-mini`, and manuscript Section 4.5.1 reports `gpt-4o`. Historical extraction and evaluator materials consistently declare `gpt-4o-mini` but lack per-call verification. The prospective prompts and schemas also differ from the historical requests. These results therefore describe `gpt-5-mini` under the prospective test configuration; they do not estimate repeatability of the historical models or validate the historical outputs.

The requested alias resolved to 1 distinct returned model identifier(s): `gpt-5-mini`. The responses exposed 0 distinct nonempty system fingerprint(s). The returned identifier therefore confirms the alias but does not identify a versioned model snapshot.

| Task | Items | Successful calls | Exact stability across three repeats |
|---|---:|---:|---:|
| Screening | 200 | 600 | 95.00% |
| Extraction | 500 | 1,500 | 61.40% |

### Extraction stability by declared field type

| Declared type | Items | Exact stability across three repeats |
|---|---:|---:|
| categorical | 219 | 35.62% |
| numeric | 281 | 81.49% |

Screening changed labels in 13 of 400 adjacent repeat transitions. Exactly 190 of 200 records were stable across all three calls. Extraction was stable for 307 of 500 fields. Historically null fields had 76.10% exact stability, compared with 51.19% for historically non-null fields.

The client requested `temperature=0`, and the endpoint accepted the parameter, but the retained responses do not expose the effective decoding configuration. The audit therefore reports observed same-request repeatability rather than making a claim about nominally deterministic decoding.

Exact stability requires all three successful outputs to match after JSON parsing. For free-text categorical fields, this rule treats wording variants as different and should not be used as a standalone instability estimate. All-null numeric outputs are trivially stable. The companion sensitivity analysis separates null states and reports conservative normalization and lexical-similarity thresholds. None of these measures establishes semantic correctness.

The preserved preflight ledger contains 1,500 rejected requests. All were extraction requests rejected as `Invalid request format` under an unsupported union-type schema. The corrected schema used scalar text plus an explicit null flag. The final planned-call ledger retains only the corrected attempts, while the preflight ledger remains available as a technical-reliability result. This was a client-schema failure, not evidence about extraction accuracy.

## References

[1]: https://platform.openai.com/docs/api-reference/chat "OpenAI Chat Completions API Reference"
