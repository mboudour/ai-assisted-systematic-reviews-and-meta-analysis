# Step 7 Human Reference Sample

## Completed computational work

A deterministic, stratified sample has been drawn from the frozen historical data using master seed `20260919`.

| Component | Population | Nonempty strata | Initial sample | Reviewers |
|---|---:|---:|---:|---:|
| Screening records | 94,522 | 40 | 1,192 | 2 |
| Extraction fields | 90,554 | 191 | 1,504 | 2 |

The screening design samples up to 30 historical INCLUDE and 30 historical EXCLUDE records per case. The extraction design samples up to 10 fields per nonempty combination of case, field audit class, null status, and historical evaluator verdict. Both manifests retain stratum populations and selection probabilities for later design-weighted estimation.

## Blinding

Two local screening packets and two local extraction packets were generated. Reviewer rows use different deterministic orders. Screening packets do not contain the historical LLM decision. Extraction packets do not contain the historical evaluator verdict. The tracked sample manifests contain no title, abstract, or extracted-value text.

The full reviewer packets are intentionally excluded from Git because they duplicate the underlying bibliographic text. They are retained locally under `data/interim/annotation_packets/`. Blank, schema-correct import templates are tracked under `annotations/forms/`.

## Required human work

Two humans must complete the packets independently under `annotations/protocols/human_reference_protocol.md`. No LLM or automated classifier may supply the human labels. After both files are locked, disagreements must be identified, pre-adjudication agreement calculated, and disagreements adjudicated by consensus or a third reviewer.

Until this human work is complete, screening accuracy, extraction accuracy, evaluator sensitivity, evaluator specificity, and human-referenced error rates remain **not estimable**. Subsequent scripts may create analysis specifications and pending-output schemas, but they must not insert model judgments as substitutes.

## Reproducibility controls

The sample identifiers are stable hashes derived from the master seed, case, stratum, and record or field identity. The tracked manifest SHA-256 values at generation were:

- Screening sample manifest: `b6a0b033d54c63d9dfed675b978891101adc818d278972d2ecee7fc3030321b7`
- Extraction sample manifest: `3cd14ff3e2c08b58278f87fdef537fa55473c8103a0faac2483247211a887d4b`

## References

[1]: https://training.cochrane.org/handbook/current/chapter-04 "Cochrane Handbook Chapter 4: Searching for and Selecting Studies"
[2]: https://doi.org/10.1177/001316446002000104 "A Coefficient of Agreement for Nominal Scales"
[3]: https://doi.org/10.1348/000711006X126600 "Computing Inter-Rater Reliability and Its Variance in the Presence of High Agreement"
