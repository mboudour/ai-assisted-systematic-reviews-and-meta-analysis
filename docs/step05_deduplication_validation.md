# Step 5 Deduplication Validation

## Completed structural audit

Across 94,522 retained records, the audit found 0 extra rows in exact normalized-DOI groups and 407 extra rows in exact normalized-title groups. The candidate generator produced 713 retained exact-title or high-similarity pairs for potential human review.

String similarity is used only to prioritize candidates and is not treated as a duplicate label. The candidate generator uses normalized titles, deterministic SimHash blocking, token Jaccard similarity, and Python's `SequenceMatcher` ratio.[1]

## Human-review form

A deterministic sample of 200 retained candidate pairs was written to `annotations/forms/dedup_retained_pair_sample.csv`. Reviewers must label whether each pair is the same report and whether it represents the same underlying study. These are separate questions.

## Historical limitation

The historical archive contains neither the pre-deduplication rows nor a removed-pair log. Therefore the false-merge rate and positive predictive value of the historical removal rule cannot be estimated. An empty schema-correct form is provided at `annotations/forms/dedup_removed_pair_sample.csv` for use if those records are recovered.

Until human pair judgments and the removed-pair log are available, the deduplication-accuracy estimand remains pending. Exact residual counts and candidate counts are descriptive audit results, not accuracy estimates.

## References

[1]: https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher "Python SequenceMatcher Documentation"
