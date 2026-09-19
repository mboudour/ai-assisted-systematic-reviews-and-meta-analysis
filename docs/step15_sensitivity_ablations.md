# Step 15 Sensitivity and Ablation Analyses

## Denominator choice changes the apparent evaluator result

Across all 90,554 requested fields, the archived evaluator assigned `CORRECT` to 58.39%. Excluding all 36,881 `UNVERIFIABLE` fields raises the reported value to 98.52%, an increase of 40.12 percentage points caused solely by denominator restriction. Neither value is human-referenced accuracy.

## Naive completeness gates overstate synthesis readiness

A numeric estimate-and-interval threshold of at least five rows admits 7 cases. A ten-row threshold admits 5. Independent case review leaves 4 cases pending source-level verification, and the full frozen gate admits zero cases. This ablation shows that row completeness cannot substitute for estimand compatibility, study independence, or value verification.

## Extraction coverage is not uniform

Five cases stop at 200 extracted records, leaving 7,776 historical INCLUDE decisions without archived extraction rows. Any all-case extraction summary must report this attrition rather than treating the retained extracted rows as a complete sample.

## Unavailable pooled-model sensitivity

Fixed-effect, DerSimonian–Laird, and REML Hartung–Knapp comparisons are not estimable because no case currently passes the synthesis gate. Reporting model-based robustness on provisional rows would obscure, rather than test, the dominant data-quality failures.[1]

## References

[1]: https://training.cochrane.org/handbook/current/chapter-10 "Cochrane Handbook Chapter 10: Analysing Data and Undertaking Meta-Analyses"
