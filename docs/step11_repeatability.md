# Step 11 Repeatability and Model-Provenance Audit

## Results

The audit attempted 2,100 calls using the requested model alias `gpt-5-mini`. Every call preserves the returned model identifier, request identifier, system fingerprint when available, prompt and schema hashes, timing, token usage, retries, and explicit status.

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

Exact stability requires all three successful outputs to match after JSON normalization. It measures repeatability under this prospective configuration, not agreement with truth. Screening transitions and item-level extraction null/numeric variability are retained in separate result tables.

The preserved preflight ledger contains 1,500 rejected requests. All were extraction requests rejected as `Invalid request format` under an unsupported union-type schema. The corrected schema used scalar text plus an explicit null flag. The final planned-call ledger retains only the corrected attempts, while the preflight ledger remains available as a technical-reliability result. This was a client-schema failure, not evidence about extraction accuracy.

## References

[1]: https://platform.openai.com/docs/api-reference/chat "OpenAI Chat Completions API Reference"
