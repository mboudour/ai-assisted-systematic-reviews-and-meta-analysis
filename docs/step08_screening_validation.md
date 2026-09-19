# Step 8 Screening Validation

## Current status

The historical decision profile is complete, but no adjudicated human screening labels have been imported. Screening sensitivity, specificity, precision, negative predictive value, balanced accuracy, and F1 are therefore **not estimable**.

`results/tables/screening_decision_profile.csv` reports the historical INCLUDE and EXCLUDE counts without calling them accuracy. `results/tables/screening_validation_metrics.csv` is schema-correct and empty until adjudicated labels are supplied.

## Frozen analysis

After import, primary estimates use inverse inclusion-probability weights. Pooled, case-level, domain-level, and prevalence-sensitive metrics will be reported. Uncertain human labels remain a separate count and are excluded only from the binary confusion matrix, not from sample accounting. Confidence intervals will follow the stratified cluster bootstrap specified in the frozen protocol; Wilson intervals are retained for unweighted descriptive proportions.[1]

## References

[1]: https://doi.org/10.1080/01621459.1927.10502953 "Probable Inference, the Law of Succession, and Statistical Inference"
