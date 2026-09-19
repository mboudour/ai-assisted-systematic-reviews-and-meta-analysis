# Step 9 Extraction and Evaluator Validation

## Current status

No adjudicated human extraction labels have been imported. Human-referenced extraction error, evaluator sensitivity, evaluator specificity, and evaluator abstention among source-assessable fields are therefore **not estimable**.

The historical same-model evaluator profile is retained as a descriptive output. It is not described as accuracy because the evaluator shares the generator's model lineage and source text, and the archived verdicts have not been independently validated.

## Historical evaluator verdict profile

| Field class | Fields | CORRECT | INCORRECT | UNVERIFIABLE |
|---|---:|---:|---:|---:|
| categorical | 49,935 | 78.73% | 0.61% | 20.66% |
| other_numeric | 3,652 | 25.03% | 2.08% | 72.89% |
| potentially_synthesis_critical | 36,967 | 34.21% | 1.12% | 64.66% |

`results/tables/extraction_evaluator_profile.csv` contains case-by-field counts and full denominators. `results/tables/extraction_validation_metrics.csv` remains schema-correct and empty until human adjudication is complete.

## Frozen analysis

The primary extraction estimand is the design-weighted error rate among source-assessable fields. The primary evaluator estimands are sensitivity to human-confirmed errors and specificity for human-confirmed correct fields. Source inadequacy and evaluator abstention are separate reported rates. Estimates will be stratified by case, field name, field class, and extracted-null status, with record-clustered uncertainty.

## References

[1]: https://doi.org/10.1177/001316446002000104 "A Coefficient of Agreement for Nominal Scales"
