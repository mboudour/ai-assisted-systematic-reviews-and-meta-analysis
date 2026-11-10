import traceback
import unittest
from unittest.mock import Mock, patch

import requests

from openalex_client import OPENALEX_CLIENT_RELEASE, OpenAlexClient, OpenAlexError, fetch_works


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


class OpenAlexAnonymousTests(unittest.TestCase):
    def test_release_marker(self):
        self.assertEqual(OPENALEX_CLIENT_RELEASE, 2)

    def test_anonymous_one_page_and_metadata_even_when_more_requested(self):
        payload = {"meta": {"count": 3, "next_cursor": "page-2"},
                   "results": [{"id": "W1"}, {"id": "W2"}]}
        query = '("heart failure" AND digital) NOT pediatric'
        with patch("requests.Session.get", return_value=FakeResponse(payload)) as get:
            records, metadata = fetch_works(
                query, None, anonymous=True, per_page=500, max_pages=99,
                year_from=2020, year_to=2022, publication_types=("article",),
                search_scope="broad", require_abstract=False,
            )
        self.assertEqual(records, payload["results"])
        self.assertEqual(get.call_count, 1)
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs["params"]["search"], query)
        self.assertEqual(kwargs["params"]["cursor"], "*")
        self.assertEqual(kwargs["params"]["per-page"], 100)
        self.assertIn("from_publication_date:2020-01-01", kwargs["params"]["filter"])
        self.assertIn("to_publication_date:2022-12-31", kwargs["params"]["filter"])
        self.assertIn("type:article", kwargs["params"]["filter"])
        self.assertNotIn("has_abstract:true", kwargs["params"]["filter"])
        self.assertNotIn("api_key", kwargs["params"])
        self.assertNotIn("mailto", kwargs["params"])
        self.assertNotIn("email", kwargs["params"])
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(metadata["per_page"], 100)
        self.assertEqual(metadata["max_pages"], 1)
        self.assertEqual(metadata["pages"], 1)
        self.assertEqual(metadata["pages_fetched"], 1)
        self.assertEqual(metadata["records_retrieved"], 2)
        self.assertEqual(metadata["total_matches"], 3)
        self.assertTrue(metadata["possibly_truncated"])
        self.assertTrue(metadata["anonymous"])

    def test_blank_or_missing_key_never_silently_downgrades(self):
        with patch("requests.Session.get") as get:
            for key in (None, "", " \t\n"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    fetch_works("topic", key)
                with self.subTest(client_key=key), self.assertRaises(ValueError):
                    OpenAlexClient(key)
            with self.assertRaises(ValueError):
                fetch_works("topic")
            with self.assertRaises(ValueError):
                fetch_works("topic", None, anonymous=1)
            with self.assertRaises(ValueError):
                fetch_works("topic", 1, anonymous=True)
            with self.assertRaises(ValueError):
                fetch_works("topic", "valid-looking-key", anonymous=True)
            with self.assertRaises(ValueError):
                OpenAlexClient("valid-looking-key", anonymous=True)
        get.assert_not_called()

    def test_anonymous_accepts_absent_and_empty_keys(self):
        for key in (None, "", "   "):
            with self.subTest(key=key):
                with patch("requests.Session.get", return_value=FakeResponse(
                    {"meta": {"count": 0}, "results": []}
                )) as get:
                    records, metadata = fetch_works("topic", key, anonymous=True)
                get.assert_called_once()
                self.assertEqual(records, [])
                self.assertEqual(metadata["max_pages"], 1)
                self.assertNotIn("Authorization", get.call_args.kwargs["headers"])
        with patch("requests.Session.get", return_value=FakeResponse(
            {"meta": {"count": 0}, "results": []}
        )):
            self.assertEqual(fetch_works("topic", anonymous=True)[0], [])

    def test_prepared_request_has_no_implicit_netrc_session_auth_or_email(self):
        # Inspect a real prepared Requests request, not just the get() kwargs.
        for session_auth in (None, ("session-user", "session-password")):
            with self.subTest(session_auth=session_auth):
                session = requests.Session()
                session.headers["Authorization"] = "Bearer session-secret"
                session.auth = session_auth
                session.send = Mock(return_value=FakeResponse({"results": []}))
                client = OpenAlexClient(None, "private@example.com",
                                        anonymous=True, session=session)
                with patch("requests.sessions.get_netrc_auth",
                           return_value=("netrc-user", "netrc-secret")) as netrc:
                    client._request({"search": "topic", "cursor": "*"})
                netrc.assert_not_called()
                prepared = session.send.call_args.args[0]
                self.assertNotIn("Authorization", prepared.headers)
                self.assertNotIn("private@example.com", str(prepared.headers))
                self.assertNotIn("private@example.com", prepared.url)
                self.assertNotIn("session-secret", str(prepared.headers))
                self.assertFalse(session.send.call_args.kwargs["allow_redirects"])

    def test_truncation_uses_count_or_cursor_and_handles_zero(self):
        scenarios = [
            # payload, expected truncation
            ({"meta": {"count": 0, "next_cursor": None}, "results": []}, False),
            ({"meta": {"count": 0, "next_cursor": "unused"}, "results": []}, False),
            ({"meta": {"count": 1, "next_cursor": None}, "results": [{"id": "W1"}]}, False),
            ({"meta": {"count": 10, "next_cursor": None}, "results": [{"id": "W1"}]}, True),
            ({"meta": {"count": 10, "next_cursor": None}, "results": []}, True),
            ({"meta": {"next_cursor": "next"}, "results": [{"id": "W1"}]}, True),
            # A cursor is conservative evidence even if count is already met.
            ({"meta": {"count": 1, "next_cursor": "next"}, "results": [{"id": "W1"}]}, True),
        ]
        for payload, expected in scenarios:
            with self.subTest(payload=payload):
                with patch("requests.Session.get", return_value=FakeResponse(payload)) as get:
                    records, metadata = fetch_works("topic", anonymous=True, max_pages=8)
                get.assert_called_once()
                self.assertEqual(records, payload["results"])
                self.assertEqual(metadata["possibly_truncated"], expected)
                self.assertEqual(metadata["max_pages"], 1)
                if payload["meta"].get("count") == 0:
                    self.assertEqual(metadata["total_matches"], 0)

    def test_anonymous_status_errors_are_helpful_sanitized_and_not_retried(self):
        secret = "private-secret-from-upstream"
        for status in (301, 401, 403, 429, 500):
            with self.subTest(status=status):
                response = FakeResponse({"message": secret}, status_code=status)
                with patch("requests.Session.get", return_value=response) as get:
                    with self.assertRaises(OpenAlexError) as raised:
                        fetch_works("topic", anonymous=True, max_pages=3)
                get.assert_called_once()
                message = str(raised.exception)
                self.assertIn(str(status), message)
                self.assertNotIn(secret, message)
                self.assertNotIn(secret, "".join(traceback.format_exception(raised.exception)))
                if status in (401, 403):
                    self.assertIn("anonymous", message.lower())
                    self.assertIn("key", message.lower())
                if status == 429:
                    self.assertIn("IP", message)
                    self.assertIn("wait", message.lower())
                    self.assertIn("budget", message.lower())

    def test_network_and_json_error_tracebacks_do_not_reveal_secrets(self):
        secret = "secret-in-underlying-exception"
        for anonymous in (False, True):
            with self.subTest(anonymous=anonymous):
                with patch("requests.Session.get", side_effect=requests.Timeout(secret)):
                    with self.assertRaises(OpenAlexError) as raised:
                        fetch_works("topic", None if anonymous else secret, anonymous=anonymous)
                self.assertNotIn(secret, str(raised.exception))
                self.assertNotIn(secret, "".join(traceback.format_exception(raised.exception)))
                response = Mock(status_code=200)
                response.json.side_effect = ValueError(secret)
                with patch("requests.Session.get", return_value=response):
                    with self.assertRaises(OpenAlexError) as raised:
                        fetch_works("topic", None if anonymous else secret, anonymous=anonymous)
                self.assertNotIn(secret, str(raised.exception))
                self.assertNotIn(secret, "".join(traceback.format_exception(raised.exception)))

    def test_keyed_pagination_retains_bearer_and_requested_page_cap(self):
        secret = "keyed-secret"
        responses = [
            FakeResponse({"meta": {"count": 3, "next_cursor": "second"},
                          "results": [{"id": "W1"}]}),
            FakeResponse({"meta": {"count": 3, "next_cursor": "third"},
                          "results": [{"id": "W2"}]}),
        ]
        with patch("requests.Session.get", side_effect=responses) as get:
            records, metadata = fetch_works("topic", secret, max_pages=2)
        self.assertEqual(len(records), 2)
        self.assertEqual(get.call_count, 2)
        self.assertEqual([call.kwargs["params"]["cursor"] for call in get.call_args_list],
                         ["*", "second"])
        for call in get.call_args_list:
            self.assertEqual(call.kwargs["headers"], {"Authorization": f"Bearer {secret}"})
            self.assertNotIn(secret, str(call.kwargs["params"]))
        self.assertNotIn(secret, str(metadata))
        self.assertEqual(metadata["max_pages"], 2)
        self.assertEqual(metadata["pages_fetched"], 2)
        self.assertTrue(metadata["possibly_truncated"])
        self.assertFalse(metadata["anonymous"])


if __name__ == "__main__":
    unittest.main()
