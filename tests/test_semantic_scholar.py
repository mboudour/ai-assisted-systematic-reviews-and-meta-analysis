"""Focused tests for the Day 1 Semantic Scholar best-effort provider."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "1_Day1_Query_to_Corpus.py"


def load_page_module():
    spec = importlib.util.spec_from_file_location("day1_semantic_test", PAGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SemanticScholarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.day1 = load_page_module()

    @staticmethod
    def response(status=200, payload=None):
        result = Mock(status_code=status)
        result.json.return_value = payload if payload is not None else {}
        return result

    def test_success_without_key_does_not_send_header_and_preserves_fields(self):
        payload = {
            "total": 1,
            "offset": 0,
            "data": [{
                "paperId": "S1", "externalIds": {"DOI": "10.1/example"},
                "title": "  Literal title: A/B  ", "year": 2022,
                "authors": [{"name": "Doe, Jane"}, {"name": "O'Neil"}],
                "venue": "Journal", "abstract": None, "citationCount": 4,
            }],
        }
        with patch.object(self.day1.requests, "get", return_value=self.response(payload=payload)) as get:
            frame, log = self.day1.query_semantic_scholar_live("A/B", per_page=10, include_log=True)
        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(frame.iloc[0]["Title"], "Literal title: A/B")
        self.assertEqual(frame.iloc[0]["Authors"], "Doe, Jane; O'Neil")
        self.assertEqual(get.call_args.kwargs["headers"], {})
        self.assertNotIn("A/B", json.dumps(log))
        self.assertEqual(log["total_matches"], 1)
        self.assertFalse(log["possibly_truncated"])

    def test_optional_key_is_header_only_and_not_logged(self):
        secret = "test-secret-not-real"
        payload = {"total": 2, "data": [{"paperId": "S1", "title": "Paper", "authors": []}]}
        with patch.object(self.day1.requests, "get", return_value=self.response(payload=payload)) as get:
            _, log = self.day1.query_semantic_scholar_live("paper", api_key=secret, include_log=True)
        call = get.call_args
        self.assertEqual(call.kwargs["headers"], {"x-api-key": secret})
        self.assertNotIn(secret, json.dumps(log))
        self.assertNotIn(secret, json.dumps(call.kwargs["params"]))

    def test_rate_limit_is_bounded_actionable_and_redacted(self):
        secret = "key-that-must-not-appear"
        responses = [self.response(status=429), self.response(status=429), self.response(status=429)]
        with patch.object(self.day1.requests, "get", side_effect=responses) as get, patch.object(self.day1.time, "sleep") as sleep:
            with self.assertRaises(self.day1.SemanticScholarError) as raised:
                self.day1.query_semantic_scholar_live("query", api_key=secret)
        message = str(raised.exception)
        self.assertIn("HTTP 429", message)
        self.assertIn("semanticscholar.org/product/api", message)
        self.assertIn("Crossref/OpenAlex", message)
        self.assertNotIn(secret, message)
        self.assertEqual(get.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_http_and_transport_errors_are_sanitized(self):
        secret = "private-key"
        with patch.object(self.day1.requests, "get", side_effect=self.day1.requests.RequestException("url?x=" + secret)):
            with self.assertRaises(self.day1.SemanticScholarError) as raised:
                self.day1.query_semantic_scholar_live("query", api_key=secret)
        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("could not be reached", str(raised.exception))

        with patch.object(self.day1.requests, "get", return_value=self.response(status=503)):
            with self.assertRaises(self.day1.SemanticScholarError) as raised:
                self.day1.query_semantic_scholar_live("query", api_key=secret)
        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("HTTP 503", str(raised.exception))

    def test_empty_response_and_total_count_report_truncation(self):
        with patch.object(self.day1.requests, "get", return_value=self.response(payload={"total": 0, "data": []})):
            frame, log = self.day1.query_semantic_scholar_live("nothing", per_page=10, include_log=True)
        self.assertTrue(frame.empty)
        self.assertEqual(log["returned"], 0)
        self.assertFalse(log["possibly_truncated"])

        payload = {"total": 50, "offset": 0, "data": [{"paperId": "S1", "title": "P", "authors": []}]}
        with patch.object(self.day1.requests, "get", return_value=self.response(payload=payload)):
            _, log = self.day1.query_semantic_scholar_live("many", per_page=1, include_log=True)
        self.assertTrue(log["possibly_truncated"])
        self.assertEqual(log["pagination"], "one page only")

    def test_ui_exposes_semantic_scholar_as_masked_optional_key(self):
        app = AppTest.from_file(str(PAGE), default_timeout=90).run()
        app.sidebar.radio[0].set_value("🔎 BYOD — Your Own Query").run()
        app.selectbox(key="byod_api_widget").set_value(
            "Semantic Scholar (best-effort relevance search; optional key)"
        ).run()
        self.assertEqual(len(app.exception), 0)
        key_widget = app.text_input(key="semantic_scholar_key_widget")
        self.assertEqual(key_widget.proto.type, 1)
        self.assertTrue(any("plain-text relevance search" in item.value for item in app.info))


if __name__ == "__main__":
    unittest.main()
