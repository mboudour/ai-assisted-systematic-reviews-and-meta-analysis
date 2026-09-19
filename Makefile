.PHONY: test pipeline manifest verify

test:
	python3 -m pytest -q

pipeline:
	python3 scripts/run_pipeline.py --root .

manifest:
	python3 scripts/build_environment_manifest.py --root . --output results/environment.json
	python3 scripts/build_artifact_manifest.py --root . --output results/artifact_manifest.json

verify: test manifest
	git diff --check
