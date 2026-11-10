"""Offline tests: no model calls, network, or real corpus mutations."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import build_guided_ai_demos as demos
import guided_workflow as guided


class FakeCompletion:
    def __init__(self, content, finish_reason="stop", model="gpt-6.1-sol-actual"):
        self.kwargs = None
        self.response = SimpleNamespace(
            id="response-123", created=1760000000, model=model,
            choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)],
        )

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def fake_client(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def fixture(directory: Path):
    case = {"key": "example", "inclusion_terms": ["climate change", "energy"],
            "exclusion_terms": ["exclude me"], "corpus_file": "corpus.csv",
            "log_file": "log.json"}
    rows = [
        {"ID": "wrong-a", "DOI": "10.1/a", "Title": "unrelated", "Abstract": "Green\nenergy"},
        {"ID": "wrong-b", "DOI": "10.1/b", "Title": "climate change", "Abstract": "Exclude   me."},
        {"ID": "no-abstract", "DOI": "10.1/c", "Title": "CLIMATE   CHANGE", "Abstract": ""},
        {"ID": "yes", "DOI": "10.1/yes", "Title": "Climate change study",
         "Abstract": "We investigate energy. We measured it. It fell by 2%."},
        {"ID": "later", "DOI": "10.1/later", "Title": "Energy study", "Abstract": "Later included abstract."},
    ]
    pd.DataFrame(rows).to_csv(directory / case["corpus_file"], index=False)
    (directory / case["log_file"]).write_text(json.dumps({"source": "Crossref"}), encoding="utf-8")
    return case, pd.DataFrame(rows)


class SelectionTests(unittest.TestCase):
    def test_selection_uses_same_shared_screen_and_corpus_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            case, frame = fixture(directory)
            screened = guided.screen_records(frame, case["inclusion_terms"], case["exclusion_terms"])
            # The first row is included by its abstract; ensure selection follows the renderer.
            self.assertEqual(guided.included_records(screened)["ID"].tolist(),
                             ["wrong-a", "no-abstract", "yes", "later"])
            source = demos.select_source(case, directory)
            self.assertEqual(source["record_id"], "wrong-a")
            self.assertEqual(source["doi"], "10.1/a")
            self.assertEqual(source["abstract"], "Green\nenergy")
            self.assertEqual(source["abstract_sha256"], demos.sha256_text("Green\nenergy"))
            self.assertEqual(source["citation_url"], "https://doi.org/10.1/a")

    def test_skips_excluded_and_blank_abstract(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            case, frame = fixture(directory)
            frame.loc[0, "Abstract"] = "unrelated"
            frame.to_csv(directory / case["corpus_file"], index=False)
            source = demos.select_source(case, directory)
            self.assertEqual(source["record_id"], "yes")
            self.assertEqual(source["abstract"], "We investigate energy. We measured it. It fell by 2%.")

    def test_no_eligible_abstract_means_no_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            case, frame = fixture(directory)
            frame["Abstract"] = ""
            frame.to_csv(directory / case["corpus_file"], index=False)
            with self.assertRaisesRegex(ValueError, "no heuristic-included record"):
                demos.select_source(case, directory)
            self.assertEqual(list(directory.glob("*.ai.json")), [])

    def test_bad_case_path_terms_or_capture_checksum_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            case, _ = fixture(directory)
            with self.assertRaises(ValueError):
                demos.select_source({**case, "key": "../escape"}, directory)
            with self.assertRaises(ValueError):
                demos.select_source({**case, "corpus_file": "../outside.csv"}, directory)
            with self.assertRaises(ValueError):
                demos.select_source({**case, "inclusion_terms": "climate"}, directory)
            (directory / case["log_file"]).write_text('{"corpus_sha256":"incorrect"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                demos.select_source(case, directory)


class ValidationTests(unittest.TestCase):
    abstract = "Objective: Reduce harm. Methods: Randomized trial. Results: Harm did not fall."

    def test_exact_substrings_and_not_reported(self):
        raw = json.dumps({"objective": "Reduce harm.", "methods": "Methods: Randomized trial.",
                          "results": "Not reported"})
        parsed, checks = demos.validate_response(raw, self.abstract)
        self.assertEqual(parsed["objective"], "Reduce harm.")
        self.assertEqual(parsed["results"], "Not reported")
        self.assertEqual(checks["objective"], {"valid": True, "status": "exact_substring"})
        self.assertEqual(checks["methods"], {"valid": True, "status": "exact_substring"})
        self.assertEqual(checks["results"], {"valid": None, "status": "not_reported"})

    def test_unsupported_or_edited_text_is_missing_even_when_almost_exact(self):
        raw = json.dumps({"objective": "reduce harm.", "methods": "Randomized trial.  ",
                          "results": "Harm fell."})
        parsed, checks = demos.validate_response(raw, self.abstract)
        self.assertEqual(parsed, {field: None for field in demos.FIELDS})
        self.assertTrue(all(not check["valid"] and check["status"] == "invalid_excerpt"
                            for check in checks.values()))

    def test_missing_not_reported_does_not_turn_into_an_asserted_excerpt(self):
        raw = json.dumps({"objective": "", "methods": None, "results": "Not reported"})
        parsed, checks = demos.validate_response(raw, self.abstract)
        self.assertIsNone(parsed["objective"])
        self.assertIsNone(parsed["methods"])
        self.assertEqual(parsed["results"], "Not reported")
        self.assertIsNone(checks["results"]["valid"])

    def test_malformed_incomplete_extra_and_duplicate_schema_fail_closed(self):
        cases = [('{broken', 'stop', 'invalid_json'),
                 ('{"objective":"Reduce harm.","methods":"x"}', 'stop', 'invalid_schema'),
                 ('{"objective":"a","objective":"b","methods":"x","results":"y"}', 'stop', 'invalid_json'),
                 (json.dumps({"objective": "Reduce harm.", "methods": "Randomized trial.",
                              "results": "Harm did not fall."}), 'length', 'incomplete_response')]
        for raw, finish_reason, status in cases:
            with self.subTest(status=status):
                parsed, checks = demos.validate_response(raw, self.abstract, finish_reason)
                self.assertEqual(parsed, {field: None for field in demos.FIELDS})
                self.assertTrue(all(check["status"] == status and check["valid"] is False
                                    for check in checks.values()))


class GenerationTests(unittest.TestCase):
    def test_real_request_shape_and_audit_record_with_fake_response(self):
        abstract = "We investigate energy. We measured it. It fell by 2%."
        source = {"record_id": "yes", "doi": "10.1/yes", "title": "Study", "abstract": abstract,
                  "abstract_sha256": demos.sha256_text(abstract), "citation_url": "https://doi.org/10.1/yes",
                  "corpus_file": "corpus.csv", "corpus_sha256": "hash"}
        raw = json.dumps({"objective": "We investigate energy.", "methods": "We measured it.",
                          "results": "It fell by 2%."})
        completion = FakeCompletion(raw)
        case = {"key": "example"}
        demo = demos.generate_demo(case, source, fake_client(completion))
        self.assertEqual(completion.kwargs["messages"], demo["prompt"]["messages"])
        self.assertEqual(completion.kwargs["model"], demos.MODEL)
        self.assertEqual(completion.kwargs["response_format"], demo["request"]["response_format"])
        self.assertEqual(completion.kwargs["extra_body"], {"reasoning": {"effort": demos.EFFORT}})
        self.assertIn(abstract, demo["prompt"]["messages"][1]["content"])
        self.assertEqual(demo["model"]["requested"], demos.MODEL)
        self.assertEqual(demo["model"]["returned"], "gpt-6.1-sol-actual")
        self.assertEqual(demo["response"]["raw_text"], raw)
        self.assertEqual(demo["response"]["id"], "response-123")
        self.assertEqual(demo["parsed_output"]["results"], "It fell by 2%.")
        self.assertTrue(all(item["valid"] is True for item in demo["validation"].values()))
        self.assertIn("not a full corpus synthesis", demo["label"])

    def test_no_content_or_exception_never_produces_generated_demo(self):
        completion = FakeCompletion(None)
        with self.assertRaisesRegex(RuntimeError, "no text"):
            demos.generate_demo({"key": "x"}, {"abstract": "Some abstract"}, fake_client(completion))
        completion.create = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("API failure"))
        with self.assertRaisesRegex(RuntimeError, "API failure"):
            demos.generate_demo({"key": "x"}, {"abstract": "Some abstract"}, fake_client(completion))

    def test_existing_output_is_only_reused_if_source_and_prompt_match(self):
        abstract = "We investigate energy. We measured it. It fell by 2%."
        source = {"abstract": abstract, "abstract_sha256": demos.sha256_text(abstract),
                  "corpus_sha256": "original-corpus-sha"}
        raw = json.dumps({"objective": "We investigate energy.", "methods": "We measured it.",
                          "results": "It fell by 2%."})
        case = {"key": "test"}
        demo = demos.generate_demo(case, source, fake_client(FakeCompletion(raw)))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.ai.json"
            demos.write_json_atomic(path, demo)
            self.assertTrue(demos.existing_matches(path, case, source))
            self.assertTrue(demos.existing_matches(path, case, {**source, "corpus_sha256": "new-corpus-sha"}))
            self.assertFalse(demos.existing_matches(path, case, {**source, "abstract": "Changed"}))
            demo["prompt"]["messages"][0]["content"] = "changed"
            demos.write_json_atomic(path, demo)
            self.assertFalse(demos.existing_matches(path, case, source))

    def test_error_messages_do_not_echo_sandbox_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sensitive-test-value"}):
            self.assertEqual(demos.redact_error(RuntimeError("key sensitive-test-value failed")),
                             "key [redacted] failed")


class BuilderIntegrationTests(unittest.TestCase):
    @staticmethod
    def four_cases(directory):
        case, _ = fixture(directory)
        cases = [{**case, "key": f"case{i}"} for i in range(4)]
        (directory / "cases.json").write_text(json.dumps(cases), encoding="utf-8")

    def test_nonfatal_api_failure_leaves_no_file_but_other_cases_continue(self):
        raw = json.dumps({"objective": "Green\nenergy", "methods": "Not reported", "results": "Not reported"})
        completion = FakeCompletion(raw)
        original = completion.create
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("transient model failure")
            return original(**kwargs)
        completion.create = create
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.four_cases(directory)
            stderr = io.StringIO()
            with patch("openai.OpenAI", return_value=fake_client(completion)), \
                    patch.object(demos, "verify_catalog"), redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                result = demos.main(["--data-dir", str(directory)])
            self.assertEqual(result, 1)
            self.assertEqual(len(calls), 4)
            self.assertFalse((directory / "case0.ai.json").exists())
            self.assertEqual(len(list(directory.glob("*.ai.json"))), 3)
            self.assertIn("transient model failure", stderr.getvalue())
            self.assertIn("no demonstration was written", stderr.getvalue())
            artifact = json.loads((directory / "case1.ai.json").read_text(encoding="utf-8"))
            self.assertEqual(artifact["response"]["raw_text"], raw)
            self.assertEqual(artifact["validation"]["objective"]["status"], "exact_substring")

    def test_fatal_api_failure_stops_without_fabricating_results(self):
        class FatalError(Exception):
            status_code = 401
        completion = FakeCompletion("unused")
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            raise FatalError("authentication failed")
        completion.create = create
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.four_cases(directory)
            stderr = io.StringIO()
            with patch("openai.OpenAI", return_value=fake_client(completion)), \
                    patch.object(demos, "verify_catalog"), redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                result = demos.main(["--data-dir", str(directory)])
            self.assertEqual(result, 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(list(directory.glob("*.ai.json")), [])
            self.assertIn("stopping the remaining cases", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
