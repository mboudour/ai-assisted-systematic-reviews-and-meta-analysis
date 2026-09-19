# Step 6 Failure and Missingness-State Audit

## Historical identifiability

The archived screened files contain no call-status, retry, request, or error fields. The historical screening failure rate is therefore **not identifiable**. An `EXCLUDE` value cannot be distinguished from a valid model decision after the fact.

The archived extraction files contain null values but no source-status or call-status field. A null may mean that the source did not report the field, that the extractor omitted a reported value, or that the call failed. Those states cannot be separated retrospectively.

Evaluator `UNVERIFIABLE` values similarly conflate source insufficiency and evaluator-call failure under the historical implementation. They must be reported as archived verdicts, not reclassified as observed technical failures.

## Archived output profile

| Measure | Count | Rate |
|---|---:|---:|
| Requested extraction field cells | 90,554 | 100.00% |
| Null extraction cells | 36,641 | 40.46% |
| Evaluator CORRECT cells | 52,877 | 58.39% |
| Evaluator INCORRECT cells | 796 | 0.88% |
| Evaluator UNVERIFIABLE cells | 36,881 | 40.73% |
| Null fields judged CORRECT | 198 | 0.54% of null fields |
| Null fields judged INCORRECT | 20 | 0.05% of null fields |
| Null fields judged UNVERIFIABLE | 36,423 | 99.41% of null fields |
| Non-null fields judged UNVERIFIABLE | 458 | 0.85% of non-null fields |
| Conditional agreement after excluding UNVERIFIABLE | 52,877 / 53,673 | 98.52% |
| All-null extraction records | 23 | 0.20% of extracted records |
| All-UNVERIFIABLE evaluator records | 22 | 0.19% of extracted records |

Conditional agreement is shown only to reconcile the historical headline measure. It is not an accuracy estimate and must be presented beside the 40.73% UNVERIFIABLE rate.

## Prospective implementation

`config/pipeline_event.schema.json` defines a mandatory event record for every call attempt. The schema separates call status from source status and analytical labels. The empty `config/pipeline_events_template.csv` file provides the corresponding table header. Future screening, extraction, and evaluation scripts must write an event even when a call fails.

## Limitation

No historical failure rate, retry-success rate, or mis-exclusion rate is estimated here. Those quantities require prospective reruns on the frozen validation samples. Treating all-null or all-UNVERIFIABLE rows as known failures would overstate what the archive shows.

## References

[1]: https://json-schema.org/draft/2020-12/json-schema-core "JSON Schema Core Specification, Draft 2020-12"
