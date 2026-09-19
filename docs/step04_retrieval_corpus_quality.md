# Step 4 Retrieval and Corpus-Quality Audit

## Main findings

The archived summaries report 95,292 records before within-case deduplication and 94,522 retained records. The reported 770 removals correspond to 0.81% of the pre-deduplication total.

Cases 3, 5, 8, 11, 15, 20 reached or exceeded their configured retrieval limit. They must be described as truncated by the project configuration unless historical source-total evidence proves otherwise. No case can currently be certified complete because the original source-reported hit totals were not archived.

A current source-count check is a temporal reproducibility audit, not a reconstruction of the historical count. It succeeded for 16 cases. Cases 7, 10, 12, 19 could not be checked automatically and retain explicit failure statuses.[1] [2] [3] [4] [5]

For successful current checks, Cases 3, 4, 5, 6, 8, 9, 11, 13, 14, 15, 17, 18, 20 now return more hits than the historical configured maximum. This supports a risk-of-truncation flag but does not prove the source total at the historical run date.

## Pooled metadata completeness

| Field | Complete or valid among retained rows |
|---|---:|
| Title | 99.99% |
| Abstract | 98.95% |
| DOI | 86.07% |
| Year | 98.99% |
| Valid year | 98.98% |

Language and source-native record identifiers were not collected in the archived corpus. Their completeness is therefore **not measurable from these files** and is not zero.

## Deduplication limitation

The archive contains only post-deduplication records. It does not contain the removed pairs or pre-deduplication rows required to estimate false merges. Exact duplicate DOI and title checks can detect residual duplicates, but they cannot validate the historical deduplication algorithm. Step 5 will therefore produce an executable audit protocol and mark the empirical false-merge estimate as pending source-pair recovery.

## Interpretation rule

Current source counts must not replace historical counts. Bibliographic indexes change over time, and the audit uses the historical query strings through current source interfaces. Differences may reflect index growth, metadata change, query-semantics change, or historical retrieval truncation.

## Outputs

- `results/tables/retrieval_corpus_quality.csv` contains case-level historical and current audit measures.
- `results/tables/current_source_count_audit.csv` contains request status, query hashes, timestamps, and response hashes.
- Raw current count responses are retained in ignored `data/interim/retrieval_count_audit/` files.

## References

[1]: https://docs.openalex.org/api-entities/works "OpenAlex Works API"
[2]: https://www.ncbi.nlm.nih.gov/books/NBK25501/ "NCBI Entrez Programming Utilities Help"
[3]: https://europepmc.org/RestfulWebService "Europe PMC RESTful Web Service"
[4]: https://api.semanticscholar.org/api-docs/graph "Semantic Scholar Academic Graph API"
[5]: https://api.core.ac.uk/docs/v3 "CORE API Documentation"
