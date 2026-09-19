# Data Zones

## `manifests/`

Tracked inventories, SHA-256 checksums, provenance records, schema reports, licensing notes, and retrieval instructions.

## `raw_snapshot/`

Immutable copies of transferred historical raw, screened, extracted, configuration, and log files. These files are ignored by Git by default. They must not be edited after hashing.

## `interim/`

Reconstructable outputs produced while cleaning, linking, annotating, or auditing the raw snapshot.

## `processed/`

Analysis-ready datasets created by the rebuilt pipeline. Publication of any processed dataset requires a separate review of source licenses, redistribution constraints, and de-identification needs.

No data file should be treated as validated merely because it exists in one of these directories. Validation state belongs in the manifest and record-level provenance fields.
