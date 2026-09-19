# Step 15 Sensitivity and Ablation Analyses

## Self-audit of the earlier conditional denominator

Across all 90,554 requested fields, the archived evaluator assigned `CORRECT` to 58.39%. Excluding all 36,881 `UNVERIFIABLE` fields raises the reported value to 98.52%, an increase of 40.12 percentage points caused solely by denominator restriction. Neither value is human-referenced accuracy. The contrast is retained to correct the earlier reporting choice and to demonstrate why the full denominator and excluded-state count must accompany a conditional percentage.

## Numeric completeness does not establish synthesis readiness

A numeric estimate-and-interval threshold of at least five rows admits 7 cases, and a ten-row threshold admits 5. However, 0 of 20 schemas contain all four required metadata groups: study linkage, effect-measure label, variance or standard error, and dependence identifier. This is a schema-only result; it does not depend on human verification and does not show that every extracted value is invalid.

## Extraction coverage is not uniform

Five cases stop at 200 extracted records. Those cases contain 8,776 historical INCLUDE decisions, of which 7,776 (88.61%) lack archived extraction rows. The same omitted rows are 40.34% of all 19,276 INCLUDE decisions across the 20 cases. Any all-case extraction summary must report both denominators rather than treating the retained rows as a complete sample.

## Unavailable pooled-model sensitivity

Fixed-effect, DerSimonian–Laird, and REML Hartung–Knapp comparisons are not estimable from the current archive because the historical schemas do not establish an analysis-ready common estimand. Reporting model-based robustness on provisional rows would obscure, rather than resolve, the missing analytical context.[1]

## References

[1]: https://training.cochrane.org/handbook/current/chapter-10 "Cochrane Handbook Chapter 10: Analysing Data and Undertaking Meta-Analyses"
