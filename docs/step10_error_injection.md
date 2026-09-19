# Step 10 Controlled Evaluator Error-Injection Experiment

## Current status

The design, input schema, two-model evaluator runner, failure logging, and analysis code are complete. The experiment has not been executed because it requires human-verified source-field pairs and controlled candidate values. Detection rates and false-alarm rates are therefore **not estimable**.

The frozen design contains 11 error types, 30 injected items and 30 matched controls per type, and two evaluators. A full initial run therefore comprises 1,320 calls. Technical failures remain separate from `UNVERIFIABLE` verdicts and from incorrect-value detection.

## Primary analysis

For injected items, the target rate is the proportion of successful calls returning `INCORRECT`. For unchanged controls, the same calculation is the false-alarm rate. `UNVERIFIABLE` and failed calls retain separate denominators. Wilson intervals are reported for each model, error type, and arm.[1]

## References

[1]: https://doi.org/10.1080/01621459.1927.10502953 "Probable Inference, the Law of Succession, and Statistical Inference"
