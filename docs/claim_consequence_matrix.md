# Quantified Claim–Consequence Matrix

## Positioning rule

The five control principles are established in provenance, MLOps, observability, data-contract, and LLM-evaluation literature. The manuscript's contribution is not to invent those controls. It is to quantify what became unobservable, unreconstructable, or measurement-sensitive when the historical workflow did not retain them. W3C PROV and ML Metadata already formalize linked entities, activities, agents, artifacts, and executions.[1] [2] OpenTelemetry and site-reliability guidance already make errors and retries part of the execution trace.[3] [4] Fitness-for-use and declarative schema constraints are established data-quality concepts.[5] [6] [7] LLM evaluation work already distinguishes exact matching, semantic assessment, and abstention-aware coverage.[8] [9]

| Lesson | Concrete consequence in these data | Defensible claim | Not identifiable |
|---|---|---|---|
| Denominator-explicit reporting | CORRECT is 52,877/90,554 (58.39%) of requested fields but 52,877/53,673 (98.52%) after excluding 36,881 UNVERIFIABLE fields. 40.12 percentage-point increase. | The displayed percentage is highly sensitive to the declared denominator. | Extraction accuracy or evaluator validity |
| Typed operational failure states | All 94,522 screening decisions lack call status; 75,246 EXCLUDE labels collide with the terminal-failure fallback. All 11,500 extraction rows and 90,554 field cells lack call status; 23 all-null and 22 all-UNVERIFIABLE rows collide with fallback states. Historical screening, extraction, and evaluator failure rates are unrecoverable. | The archive cannot distinguish operational failure from specified analytical states. | Failure incidence, retry success, or mis-exclusion rate |
| Versioned relational provenance | The generating model for all 94,522 historical screening labels is unresolved: the script, README, and manuscript disagree, and the rows retain no model or request metadata. 94,522 labels cannot receive a model-specific attribution. | The historical screening execution identity is not reconstructable from retained artifacts. | Which model alias or snapshot generated any historical screening row |
| Representation- and null-aware repeatability | Among 500 prospective items, 36 (7.20%) changed null status; the design-weighted estimate is 1.92%. For 154 all-non-null categorical items, raw exact agreement is 21.58% and normalized exact agreement is 46.13%. 24.55 percentage-point normalization effect for categorical items. | Repeatability estimates depend materially on null-state treatment and representation. | Semantic equivalence or factual correctness |
| Downstream-requirements-first schema design | 10 of 20 schemas contain estimate and interval fields, yielding 927 complete numeric rows, and 7 cases pass a five-row numeric threshold. Yet 0 of 20 schemas contain a study-level linkage identifier, a dedicated effect-measure label, a variance/standard-error field, or a dependence identifier. Only 1 of 20 has an effect-specific estimate column, and only 2 of 20 contain an analysis time-point field. Zero cases establish an analysis-ready common estimand and independent-study set. | Numeric completeness does not establish downstream synthesis readiness. | A valid pooled effect or calibrated propagation result |

## Historical schema coverage

| Requirement | Cases with field | Consequence |
|---|---:|---|
| study-level linkage identifier | 0/20 | The retained DOI can identify a report when present, but multiple reports from one underlying study cannot be grouped. |
| explicit outcome construct | 8/20 | Most case schemas cannot distinguish estimates for different outcome constructs through a dedicated field. |
| analysis time point | 2/20 | Estimates measured at different follow-up times cannot generally be separated. |
| effect-measure label | 0/20 | No schema has a dedicated effect-measure metadata field; generic effect_size values therefore lack a recorded scale. |
| effect-specific estimate column | 1/20 | One schema names hazard_ratio explicitly; the other nine estimate-and-interval schemas use the generic field effect_size. |
| confidence interval | 10/20 | Ten schemas collect interval bounds; populated bounds alone do not establish a common estimand or independence. |
| variance or standard error | 0/20 | No schema directly records the within-study variance used for inverse-variance weighting. |
| dependence or clustering identifier | 0/20 | Multiple outcomes, time points, contrasts, and reports cannot be grouped for dependence handling. |

## Novelty boundary

The paper should claim a bounded empirical audit of consequences, not a new general-purpose provenance framework, observability standard, data contract, or agreement metric. The 20 cases are purposive and the prospective repeatability results are specific to `gpt-5-mini`, the frozen inputs, prompts, schemas, and execution period.

## References

[1]: https://www.w3.org/TR/prov-dm/ "PROV-DM: The PROV Data Model"

[2]: https://www.tensorflow.org/tfx/guide/mlmd "ML Metadata"

[3]: https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-spans.md "OpenTelemetry GenAI Semantic Conventions: Generative AI Client Spans"

[4]: https://sre.google/sre-book/monitoring-distributed-systems/ "Monitoring Distributed Systems"

[5]: https://doi.org/10.1080/07421222.1996.11518099 "Beyond Accuracy: What Data Quality Means to Data Consumers"

[6]: https://www.w3.org/TR/shacl/ "Shapes Constraint Language"

[7]: https://doi.org/10.1371/journal.pdig.0000527 "Systematic Data Quality Assessment of Electronic Health Record Data to Evaluate Study-Specific Fitness"

[8]: https://aclanthology.org/2023.acl-long.307/ "Evaluating Open-Domain Question Answering in the Era of Large Language Models"

[9]: https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00754/131566/Know-Your-Limits-A-Survey-of-Abstention-in-Large "Know Your Limits: A Survey of Abstention in Large Language Models"
