# Step 13 Prespecified Meta-Analysis Models

## No pooled estimates were produced

Step 12 found zero cases that currently pass the frozen synthesis gate. The final meta-analysis summary and weight tables are therefore schema-correct and empty. The 921 provisional effect-and-interval rows were not pooled because none is human verified, linked to an independent study, or confirmed to share a common estimand.

The implemented engine supports fixed-effect inverse variance, DerSimonian–Laird random effects, and REML random effects with Hartung–Knapp inference. It reports normalized weights, confidence intervals, prediction intervals, Q, I-squared, and tau-squared. The runner enforces at least five verified independent studies and rejects mixed analysis scales.

This empty result is a substantive quality-control outcome. Reproducing the prior pooled values on unverified, heterogeneous report rows would violate the frozen protocol.[1]

## References

[1]: https://training.cochrane.org/handbook/current/chapter-10 "Cochrane Handbook Chapter 10: Analysing Data and Undertaking Meta-Analyses"
[2]: https://doi.org/10.18637/jss.v036.i03 "Conducting Meta-Analyses in R with the metafor Package"
