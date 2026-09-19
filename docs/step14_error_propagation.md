# Step 14 Monte Carlo Error Propagation

## No inferential simulation was run

The propagation engine is implemented and tested, but calibrated results were not generated because human validation has not calibrated the error model and no verified case passes the meta-analysis gate. The output table is intentionally empty.

Running arbitrary perturbation rates would create a sensitivity illustration rather than an empirically calibrated result. The frozen paper claims require observed human disagreement and prospective technical-failure rates, so no replacement values were invented.

Once both gates are satisfied, each scenario uses 10,000 or more deterministic PCG64DXSM draws with independent SHA-256-derived streams. The primary REML Hartung–Knapp model is refit in every valid draw. Outputs include pooled-estimate shifts, tau-squared shifts, 95% simulation intervals, invalid-draw counts, and conclusion-change probabilities.[1]

## References

[1]: https://numpy.org/doc/stable/reference/random/bit_generators/pcg64dxsm.html "NumPy PCG64DXSM Bit Generator"
