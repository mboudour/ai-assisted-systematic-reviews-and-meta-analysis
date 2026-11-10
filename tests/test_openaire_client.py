import os
import traceback
import unittest
from unittest.mock import patch

import requests

from openaire_client import COLUMNS, ENDPOINT, MAX_PAGES, OpenAIREError, fetch_openaire


class FakeResponse:
    def __init__(self, payload=None, status=200, error=None):
        self.payload = payload
        self.status_code = status
        self.error = error

    def json(self):
        if self.error:
            raise self.error
        return self.payload


def page(records, total=None, cursor=None):
    header = {"numFound": total}
    if cursor is not None:
        header["nextCursor"] = cursor
    return FakeResponse({"header": header, "results": records})


class OpenAIREClientTests(unittest.TestCase):
    def test_quoted_boolean_query_preserved_anonymously_and_cursor_paged(self):
        query = '  ("heart failure" AND "digital health") NOT "children"  '
        with patch("openaire_client.requests.get") as get:
            get.side_effect = [page([{"id": "one"}], 3, "cursor2"), page([{"id": "two"}], 3, "cursor3")]
            df, log = fetch_openaire(query, per_page=1, max_pages=2)
        self.assertEqual(list(df["ID"]), ["one", "two"])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[0].args, (ENDPOINT,))
        first = get.call_args_list[0].kwargs
        second = get.call_args_list[1].kwargs
        self.assertEqual(first["params"], {"search": query, "type": "publication", "pageSize": 1, "cursor": "*"})
        self.assertEqual(second["params"]["cursor"], "cursor2")
        self.assertEqual(second["params"]["search"], query)
        self.assertEqual(first["timeout"], 30)
        self.assertNotIn("headers", first)
        self.assertEqual(log["query"], query)
        self.assertEqual(log["endpoint"], ENDPOINT)
        self.assertEqual(log["numFound"], 3)
        self.assertEqual(log["pages_fetched"], 2)
        self.assertEqual(log["returned"], 2)
        self.assertTrue(log["possibly_truncated"])
        self.assertEqual(log["termination_reason"], "page_limit")
        self.assertIn("+00:00", log["fetched_at_utc"])
        self.assertIn("+00:00", log["started_at_utc"])
        self.assertIn("not title/abstract", log["scope"])
        self.assertEqual(log["filters"], ["type=publication"])

    def test_actual_v3_record_mapping_description_sources_and_jats(self):
        record = {
            "id": "doi_dedup___::123", "mainTitle": "<jats:italic>Some</jats:italic> &amp; more",
            "pids": [{"scheme": "pmc", "value": "P1"}, {"scheme": "doi", "value": "https://doi.org/10.1/example"}],
            "publicationDate": "2022-12-31",
            "authors": [{"fullName": "Alice A."}, {"name": "Bob", "surname": "B"}, {"fullName": "Carol C."}],
            "container": {"name": "Journal of Things"},
            "descriptions": ["", "<jats:p>First <jats:italic>careful</jats:italic> result, p&lt;0.05.</jats:p><jats:p>Second &amp; third.</jats:p><script>alert('x')</script>"],
            "indicators": {"citationImpact": {"citationCount": 0.0}},
            "subjects": [{"subject": {"scheme": "FOS", "value": "Life sciences"}}, {"subject": {"scheme": "keyword", "value": "Data"}}, {"subject": {"value": "data"}}],
            "instances": [{"type": "Article"}, {"type": "Article"}, {"type": "Preprint"}],
        }
        with patch("openaire_client.requests.get", return_value=page([record], 1, "c1")):
            df, log = fetch_openaire("test")
        row = df.iloc[0].to_dict()
        self.assertEqual(list(df.columns), COLUMNS)
        self.assertEqual(row["ID"], "doi_dedup___::123")
        self.assertEqual(row["DOI"], "10.1/example")
        self.assertEqual(row["Title"], "Some & more")
        self.assertEqual(row["Year"], "2022")
        self.assertEqual(row["Authors"], "Alice A.; Bob B; Carol C.")
        self.assertEqual(row["Venue"], "Journal of Things")
        self.assertEqual(row["Abstract"], "First careful result, p<0.05. Second & third.")
        self.assertEqual(row["Citations"], 0)
        self.assertEqual(row["Concepts"], "Life sciences; Data")
        self.assertEqual(row["Publication Type"], "Article; Preprint")
        self.assertIn("not necessarily", row["Abstract Source"])
        self.assertIn("may not be an abstract", log["abstract_note"])
        self.assertEqual(log["description_records"], 1)
        self.assertEqual(log["missing_description_records"], 0)
        self.assertFalse(log["possibly_truncated"])

    def test_missing_malformed_nested_fields_not_confused_with_zero_or_inferred(self):
        records = [
            {"id": "a", "mainTitle": None, "pids": None, "authors": {"fullName": "wrong"},
             "subjects": [None, {"subject": None}], "descriptions": [None, "  "],
             "container": "not a journal", "indicators": {"citationImpact": {"citationCount": None}},
             "instances": [None, {"pids": [{"scheme": "DOI", "value": "doi:10.999/example"}]}]},
            None,
        ]
        with patch("openaire_client.requests.get", return_value=page(records, 2)):
            df, log = fetch_openaire("test")
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["DOI"], "10.999/example")
        for field in ("Title", "Year", "Authors", "Venue", "Abstract", "Citations", "Concepts", "Publication Type"):
            self.assertEqual(row[field], "")
        self.assertEqual(row["Abstract Source"], "missing")
        self.assertEqual(log["missing_description_records"], 1)
        self.assertEqual(log["invalid_records_skipped"], 1)
        self.assertTrue(log["possibly_truncated"])

    def test_empty_result_schema_and_count(self):
        with patch("openaire_client.requests.get", return_value=page([], 0)):
            df, log = fetch_openaire("no match")
        self.assertEqual(list(df.columns), COLUMNS)
        self.assertTrue(df.empty)
        self.assertEqual(log["numFound"], 0)
        self.assertEqual(log["pages_fetched"], 1)
        self.assertFalse(log["possibly_truncated"])

    def test_size_is_capped_and_invalid_bounds_rejected_without_request(self):
        with patch("openaire_client.requests.get", return_value=page([], 0)) as get:
            _, log = fetch_openaire("x", per_page=1000)
        self.assertEqual(get.call_args.kwargs["params"]["pageSize"], 100)
        self.assertEqual(log["per_page"], 100)
        for kwargs in ({"per_page": 0}, {"per_page": True}, {"per_page": 1.5}, {"max_pages": 0}, {"max_pages": MAX_PAGES + 1}, {"max_pages": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                fetch_openaire("test", **kwargs)
        for query in (None, "", "  "):
            with self.subTest(query=query), self.assertRaises(ValueError):
                fetch_openaire(query)

    def test_no_cursor_and_repeated_cursor_stop_and_flag_incompleteness(self):
        for result, reason in [(page([{"id": "1"}], 9), "no_next_cursor"),
                               (page([{"id": "1"}], 9, "*"), "repeated_cursor")]:
            with self.subTest(reason=reason), patch("openaire_client.requests.get", return_value=result) as get:
                _, log = fetch_openaire("test", max_pages=3)
                self.assertEqual(get.call_count, 1)
                self.assertEqual(log["termination_reason"], reason)
                self.assertTrue(log["possibly_truncated"])

    def test_cycle_detection_and_missing_numfound(self):
        with patch("openaire_client.requests.get", side_effect=[
            page([{"id": "1"}], None, "a"),
            page([{"id": "2"}], None, "b"),
            page([{"id": "3"}], None, "a"),
        ]) as get:
            _, log = fetch_openaire("test", per_page=1, max_pages=8)
        self.assertEqual(get.call_count, 3)
        self.assertIsNone(log["total_matches"])
        self.assertEqual(log["termination_reason"], "repeated_cursor")
        self.assertTrue(log["possibly_truncated"])

    def test_unknown_or_changing_totals_do_not_claim_completeness(self):
        with patch("openaire_client.requests.get", return_value=page([{"id": "1"}], None)):
            _, log = fetch_openaire("test", per_page=50)
        self.assertIsNone(log["numFound"])
        self.assertTrue(log["possibly_truncated"])
        with patch("openaire_client.requests.get", side_effect=[
            page([{"id": "1"}], 2, "a"),
            page([{"id": "2"}], 3, "b"),
        ]):
            _, log = fetch_openaire("test", per_page=1, max_pages=2)
        self.assertEqual(log["numFound"], 2)
        self.assertEqual(log["last_page_numFound"], 3)
        self.assertTrue(log["possibly_truncated"])

    def test_http_and_network_errors_do_not_leak_query_url_or_provider_body(self):
        secret_query = '"private query"'
        for status in (429, 400, 503):
            with self.subTest(status=status), patch("openaire_client.requests.get", return_value=FakeResponse(status=status)):
                with self.assertRaises(OpenAIREError) as raised:
                    fetch_openaire(secret_query)
                message = str(raised.exception)
                self.assertIn(str(status), message)
                self.assertNotIn(secret_query, message)
                self.assertNotIn("https://", message)
                if status == 429:
                    self.assertIn("Wait", message)
        for error in (requests.Timeout(f"{ENDPOINT}?search={secret_query}"), requests.ConnectionError(secret_query)):
            with self.subTest(error=type(error)), patch("openaire_client.requests.get", side_effect=error):
                with self.assertRaises(OpenAIREError) as raised:
                    fetch_openaire(secret_query)
                formatted = "".join(traceback.format_exception(raised.exception))
                self.assertNotIn(secret_query, formatted)
                self.assertNotIn(ENDPOINT, formatted)
                self.assertIn("retry", str(raised.exception))

    def test_invalid_json_and_invalid_schema_are_not_empty_success(self):
        cases = [FakeResponse(error=ValueError("https://example/?search=private")),
                 FakeResponse(None), FakeResponse({"header": {}, "results": None}),
                 FakeResponse({"header": None, "results": []})]
        for response in cases:
            with self.subTest(payload=response.payload), patch("openaire_client.requests.get", return_value=response):
                with self.assertRaises(OpenAIREError) as raised:
                    fetch_openaire("private")
                formatted = "".join(traceback.format_exception(raised.exception))
                self.assertNotIn("https://", formatted)
                self.assertNotIn("private", formatted)
                self.assertIn("invalid response", str(raised.exception))


@unittest.skipUnless(os.environ.get("OPENAIRE_LIVE_TEST") == "1", "Set OPENAIRE_LIVE_TEST=1 for the network smoke test")
class OpenAIRELiveTests(unittest.TestCase):
    def test_tiny_unauthenticated_v3_request(self):
        df, log = fetch_openaire('"climate change"', per_page=1, max_pages=1)
        self.assertEqual(list(df.columns), COLUMNS)
        self.assertEqual(log["endpoint"], ENDPOINT)
        self.assertEqual(log["pages_fetched"], 1)
        self.assertIsInstance(log["numFound"], int)
        self.assertGreater(log["numFound"], 0)
        self.assertEqual(len(df), 1)
        self.assertTrue(df.iloc[0]["ID"])
        self.assertTrue(df.iloc[0]["Title"])
        self.assertTrue(log["possibly_truncated"])


if __name__ == "__main__":
    unittest.main()
