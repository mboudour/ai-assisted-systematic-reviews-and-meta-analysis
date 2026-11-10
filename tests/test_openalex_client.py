import unittest
from unittest.mock import Mock, patch

import requests

from openalex_client import OpenAlexClient, OpenAlexError, fetch_works


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {}
        self.status_code = status_code

    def json(self):
        return self.payload


class OpenAlexClientTests(unittest.TestCase):
    def test_fetches_two_cursor_pages_with_header_only_key(self):
        secret = "private-key-123"
        session = Mock()
        session.get.side_effect = [
            FakeResponse({"meta": {"count": 2, "next_cursor": "next"}, "results": [{"id": "a"}]}),
            FakeResponse({"meta": {"count": 2, "next_cursor": None}, "results": [{"id": "b"}]}),
        ]
        # Direct client use verifies header-only credentials independently.
        client = OpenAlexClient(secret, session=session)
        result = client._request({"search": "a AND b", "per-page": 1, "cursor": "*"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(session.get.call_args.kwargs["headers"], {"Authorization": f"Bearer {secret}"})
        self.assertNotIn(secret, str(session.get.call_args.kwargs["params"]))

    def test_fetch_works_paginates_and_preserves_boolean_query(self):
        secret = "do-not-leak"
        query = '("heart failure" AND digital) NOT pediatric'
        with patch("requests.Session.get") as request:
            request.side_effect = [
                FakeResponse({"meta": {"count": 2, "next_cursor": "c2"}, "results": [{"id": "1"}]}),
                FakeResponse({"meta": {"count": 2, "next_cursor": None}, "results": [{"id": "2"}]}),
            ]
            records, metadata = fetch_works(
                query, secret, per_page=150, max_pages=2, year_from=2020, year_to=2022,
                publication_types=("article", "review"), search_scope="broad", require_abstract=True,
            )
        self.assertEqual([r["id"] for r in records], ["1", "2"])
        self.assertEqual(metadata["query"], query)
        self.assertEqual(metadata["search_param"], "search")
        self.assertEqual(metadata["scope"], "broad")
        self.assertEqual(metadata["returned_total"], 2)
        self.assertEqual(metadata["pages"], 2)
        first = request.call_args_list[0].kwargs["params"]
        second = request.call_args_list[1].kwargs["params"]
        for call in request.call_args_list:
            self.assertEqual(call.kwargs["headers"], {"Authorization": f"Bearer {secret}"})
            self.assertNotIn(secret, str(call.kwargs["params"]))
        self.assertEqual(first["search"], query)
        self.assertEqual(first["per-page"], 100)
        self.assertEqual(first["cursor"], "*")
        self.assertEqual(second["cursor"], "c2")
        self.assertIn("from_publication_date:2020-01-01", first["filter"])
        self.assertIn("to_publication_date:2022-12-31", first["filter"])
        self.assertIn("type:article|review", first["filter"])
        self.assertIn("has_abstract:true", first["filter"])
        self.assertNotIn(secret, metadata)

    def test_empty_results_are_valid(self):
        with patch("openalex_client.OpenAlexClient._request", return_value=FakeResponse({"meta": {"count": 0}, "results": []})):
            records, metadata = fetch_works("nothing", "secret", max_pages=3)
        self.assertEqual(records, [])
        self.assertEqual(metadata["returned_total"], 0)
        self.assertEqual(metadata["pages"], 1)

    def test_exact_scope_and_no_abstract_restriction(self):
        query = '"creativity working" AND "artificial intelligence"'
        with patch("requests.Session.get", return_value=FakeResponse({"meta": {"count": 0}, "results": []})) as request:
            _, metadata = fetch_works(query, "secret", search_scope="title_abstract_exact", require_abstract=False)
        params = request.call_args.kwargs["params"]
        self.assertEqual(params["search.title_and_abstract.exact"], query)
        self.assertNotIn("search", params)
        self.assertNotIn("filter", params)
        self.assertEqual(metadata["search_param"], "search.title_and_abstract.exact")

    def test_secret_not_in_params_or_errors_and_rate_limit(self):
        secret = "super-secret"
        client = OpenAlexClient(secret, session=Mock())
        with patch.object(client.session, "get", side_effect=requests.Timeout("x")):
            with self.assertRaises(OpenAlexError) as raised:
                client._request({"search": "query"})
        self.assertNotIn(secret, str(raised.exception))
        client.session.get = Mock(return_value=FakeResponse(status_code=429))
        with self.assertRaises(OpenAlexError) as raised:
            client._request({"search": "query"})
        self.assertIn("429", str(raised.exception))
        self.assertNotIn(secret, str(raised.exception))

    def test_key_required_and_scope_and_types_validated(self):
        with self.assertRaises(ValueError):
            OpenAlexClient("")
        with self.assertRaises(ValueError):
            fetch_works("q", "key", search_scope="bad")
        with self.assertRaises(ValueError):
            fetch_works("q", "key", publication_types=("not-a-type",))


if __name__ == "__main__":
    unittest.main()
