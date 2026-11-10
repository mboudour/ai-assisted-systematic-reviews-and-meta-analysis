"""No credentials or external services are needed for these unit tests."""
import json
import traceback
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import requests

import guided_provider_search as guided


class Response:
    def __init__(self, payload=None, status_code=200, json_error=None):
        self.payload = payload
        self.status_code = status_code
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


def crossref_response(items, total=None):
    return Response({"message": {"items": items, "total-results": total}})


def europe_response(items, total=None):
    return Response({"hitCount": total, "resultList": {"result": items}})


class GuidedProviderSearchTests(unittest.TestCase):
    def test_public_fixed_queries_cover_each_case_and_provider(self):
        self.assertEqual(set(guided.GUIDED_QUERIES),
                         {"ex1_health", "ex2_ubi", "ex3_microplastics", "ex4_csr"})
        self.assertEqual(guided.PROVIDERS, ("OpenAlex", "Crossref", "Europe PMC", "OpenAIRE"))
        for case, words in {"ex1_health": ["health", "diabetes"],
                            "ex2_ubi": ["basic income", "employment"],
                            "ex3_microplastics": ["microplastics", "marine"],
                            "ex4_csr": ["corporate social responsibility", "financial performance"]}.items():
            for provider in guided.PROVIDERS:
                with self.subTest(case=case, provider=provider):
                    query = guided.guided_query(case, provider)
                    for word in words:
                        self.assertIn(word, query.lower())
                    if provider == "Crossref":
                        self.assertNotIn(" AND ", query)
                    if provider == "Europe PMC":
                        self.assertIn(" AND ", query)
                        self.assertNotIn(".search", query)  # not OpenAlex field syntax
                    if provider == "OpenAIRE":
                        # Every operand is quoted, including single words.
                        operands = query.replace("(", "").replace(")", "").split(" AND ")
                        operands = [part for group in operands for part in group.split(" OR ")]
                        self.assertTrue(all(part.startswith('"') and part.endswith('"') for part in operands))
        with self.assertRaises(TypeError):
            guided.GUIDED_QUERIES["ex1_health"]["Crossref"] = "edited"
        for case, provider in [("bad-secret", "Crossref"), ("ex1_health", "bad-secret"), (None, "Crossref")]:
            with self.subTest(case=case, provider=provider), self.assertRaises(ValueError) as raised:
                guided.guided_query(case, provider)
            self.assertNotIn("bad-secret", str(raised.exception))

    def test_all_case_provider_combinations_keep_fixed_query_provenance(self):
        for case in guided.GUIDED_QUERIES:
            for provider in guided.PROVIDERS:
                with self.subTest(case=case, provider=provider):
                    if provider == "OpenAlex":
                        patcher = patch.object(guided.openalex_client, "fetch_works",
                                               return_value=([{"id": "W1"}], {"total_matches": 1}))
                    elif provider == "OpenAIRE":
                        patcher = patch.object(guided.openaire_client, "fetch_openaire",
                                               return_value=(pd.DataFrame([{"ID": "id"}]), {"total_matches": 1}))
                    elif provider == "Crossref":
                        patcher = patch.object(guided.requests, "get", return_value=crossref_response([{"DOI": "10.1/id"}], 1))
                    else:
                        patcher = patch.object(guided.requests, "get", return_value=europe_response([{"id": "1"}], 1))
                    with patcher:
                        frame, meta = guided.fetch_guided(case, provider, "fake-key")
                    self.assertEqual(meta["case_key"], case)
                    self.assertEqual(meta["provider"], provider)
                    self.assertEqual(meta["source"], provider)
                    self.assertEqual(meta["query"], guided.guided_query(case, provider))
                    self.assertIn(meta["query"], meta["parameters"].values())
                    self.assertEqual(frame.loc[0, "Source"], provider)
                    self.assertEqual(meta["returned"], len(frame))
                    self.assertEqual(meta["total_matches"], 1)
                    self.assertFalse(meta["possibly_truncated"])
                    self.assertNotIn("fake-key", repr(meta))

    def test_openalex_real_client_one_page_header_exact_and_all_data(self):
        secret = "sensitive-openalex-credential"
        record = {"id": "https://openalex.org/W10", "doi": "https://doi.org/10.1234/abc",
                  "title": "  A study  ", "publication_year": 2022,
                  "authorships": [{"author": {"display_name": f"Author {i}"}} for i in range(8)],
                  "primary_location": {"source": {"display_name": "Journal"}},
                  "abstract_inverted_index": {"two": [1], "one": [0], "again": [2]},
                  "cited_by_count": 0, "concepts": [{"display_name": "Ecology"}],
                  "referenced_works": ["https://openalex.org/W23", "w23", "W44", "nonsense", {"id": "W1"}]}
        payload = {"meta": {"count": 125, "next_cursor": "next"}, "results": [record]}
        with patch("requests.Session.get", return_value=Response(payload)) as get:
            df, meta = guided.fetch_guided("ex3_microplastics", "OpenAlex", secret)
        self.assertEqual(get.call_count, 1)
        args = get.call_args
        self.assertEqual(args.args[0], guided.openalex_client.OpenAlexClient.BASE_URL)
        self.assertEqual(args.kwargs["headers"], {"Authorization": "Bearer " + secret})
        self.assertEqual(args.kwargs["params"], meta["parameters"])
        self.assertEqual(meta["query"], guided.guided_query("ex3_microplastics", "OpenAlex"))
        self.assertEqual(args.kwargs["params"]["search.title_and_abstract.exact"], meta["query"])
        self.assertEqual(args.kwargs["params"]["cursor"], "*")
        self.assertEqual(args.kwargs["params"]["per-page"], guided.PAGE_SIZE)
        self.assertNotIn("filter", args.kwargs["params"])
        self.assertEqual(df.loc[0, "Authors"], "; ".join(f"Author {i}" for i in range(8)))
        self.assertEqual(df.loc[0, "Abstract"], "one two again")
        self.assertEqual(df.loc[0, "Venue"], "Journal")
        self.assertEqual(df.loc[0, "Citations"], 0)
        self.assertEqual(json.loads(df.loc[0, "References"]), ["openalex:W23", "openalex:W44"])
        self.assertEqual(df.loc[0, "Source"], "OpenAlex")
        self.assertEqual(list(df.columns), guided.COLUMNS)
        self.assertEqual(meta["total_matches"], 125)
        self.assertEqual(meta["returned"], 1)
        self.assertTrue(meta["possibly_truncated"])
        self.assertEqual(meta["pages_fetched"], 1)
        self.assertNotIn(secret, repr(meta))
        self.assertNotIn(secret, repr(meta["parameters"]))
        self.assertNotIn(secret, args.args[0])
        timestamp = datetime.fromisoformat(meta["timestamp_utc"])
        self.assertEqual(timestamp.utcoffset(), timezone.utc.utcoffset(timestamp))

    def test_openalex_public_normalizer_handles_missing_sparse_and_invalid_values(self):
        df = guided.openalex_records_to_frame([None, "wrong", {
            "doi": "10.1/self", "cited_by_count": 100,
            "abstract_inverted_index": {"hello": [0, True, "1"], "last": [10**12], None: [2]},
            "authorships": [None, {"author": 12}, {"raw_author_name": "Author supplied"}],
            "referenced_works": ["W5", "bad", {"id": "W6"}],
        }, {"id": "W8", "cited_by_count": None, "referenced_works": None}])
        self.assertEqual(len(df), 2)
        self.assertEqual(df.loc[0, "Abstract"], "hello last")
        self.assertEqual(df.loc[0, "Authors"], "Author supplied")
        self.assertEqual(json.loads(df.loc[0, "References"]), ["openalex:W5"])
        self.assertEqual(df.loc[1, "References"], "")
        self.assertEqual(df.loc[1, "Citations"], "")
        self.assertEqual(df["Source"].tolist(), ["OpenAlex", "OpenAlex"])
        self.assertEqual(list(guided.openalex_records_to_frame([]).columns), guided.COLUMNS)

    def test_openalex_calls_client_with_unchanged_query_and_one_page(self):
        query = guided.guided_query("ex1_health", "OpenAlex")
        with patch.object(guided.openalex_client, "fetch_works", return_value=([], {"total_matches": 0, "possibly_truncated": False})) as fetch:
            frame, meta = guided.fetch_guided("ex1_health", "OpenAlex", "a-private-token")
        fetch.assert_called_once_with(query, "a-private-token", per_page=guided.PAGE_SIZE, max_pages=1,
                                      search_scope="title_abstract_exact", require_abstract=False)
        self.assertTrue(frame.empty)
        # Existing client substitutes zero if count is absent, so its zero is
        # conservatively unknown rather than claimed as a provider-reported zero.
        self.assertIsNone(meta["total_matches"])
        self.assertFalse(meta["possibly_truncated"])
        self.assertNotIn("a-private-token", str(meta))

    def test_crossref_explicit_references_json_and_request_metadata(self):
        item = {"DOI": "10.1111/citing", "title": ["A title"],
                "author": [{"given": "Alice", "family": "Smith"}, {"name": "Research Group"}],
                "published": {"date-parts": [[2023, 3, 4]]}, "container-title": ["Journal"],
                "abstract": "<jats:p>AI <jats:italic>teams</jats:italic> &amp; science</jats:p>",
                "is-referenced-by-count": 0, "subject": ["Science", "Ethics"],
                "reference": [{"DOI": "10.1000/FOO;BAR"}, {"doi": "https://doi.org/10.1000/foo%3Bbar"},
                              {"DOI": "10.2000/a"}, {"unstructured": "10.3000/NOT-EXTRACTED"},
                              "10.4/invalid", {"DOI": "not-a-doi"}, None]}
        with patch.object(guided.requests, "get", return_value=crossref_response([item], 90)) as get:
            df, meta = guided.fetch_guided("ex4_csr", "Crossref", "unused-secret")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args, (guided.CROSSREF_ENDPOINT,))
        self.assertEqual(get.call_args.kwargs["params"], meta["parameters"])
        self.assertNotIn("headers", get.call_args.kwargs)
        self.assertNotIn("unused-secret", repr(meta))
        self.assertEqual(meta["query"], meta["parameters"]["query"])
        self.assertEqual(meta["parameters"]["rows"], guided.PAGE_SIZE)
        self.assertIn("reference", meta["parameters"]["select"].split(","))
        self.assertEqual(meta["source"], "Crossref")
        self.assertEqual(meta["returned"], 1)
        self.assertEqual(meta["total_matches"], 90)
        self.assertTrue(meta["possibly_truncated"])
        self.assertIn("not guaranteed Boolean", meta["limitations"][0])
        self.assertEqual(df.loc[0, "ID"], "10.1111/citing")
        self.assertEqual(df.loc[0, "Authors"], "Alice Smith; Research Group")
        self.assertEqual(df.loc[0, "Year"], "2023")
        self.assertEqual(df.loc[0, "Abstract"], "AI teams & science")
        self.assertEqual(df.loc[0, "Citations"], 0)
        self.assertEqual(df.loc[0, "Concepts"], "Science; Ethics")
        self.assertEqual(json.loads(df.loc[0, "References"]), ["doi:10.1000/foo;bar", "doi:10.2000/a"])
        self.assertEqual(df.loc[0, "Source"], "Crossref")

    def test_europe_pmc_boolean_and_structured_metadata(self):
        item = {"id": "12345", "source": "MED", "doi": "10.1000/x", "title": "<i>Good</i> study",
                "pubYear": "2021", "authorString": "A, B",
                "authorList": {"author": [{"fullName": "Alice A"}, {"fullName": "Bob B"}]},
                "journalInfo": {"journal": {"title": "The journal"}},
                "abstractText": "<p>First &amp; second.</p>", "citedByCount": 3,
                "referenceCount": 8}
        with patch.object(guided.requests, "get", return_value=europe_response([item], 1)) as get:
            df, meta = guided.fetch_guided("ex2_ubi", "Europe PMC", "unused-secret")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args[0], guided.EUROPE_PMC_ENDPOINT)
        self.assertEqual(get.call_args.kwargs["params"], meta["parameters"])
        self.assertNotIn("headers", get.call_args.kwargs)
        self.assertEqual(meta["parameters"]["query"], guided.guided_query("ex2_ubi", "Europe PMC"))
        self.assertEqual(meta["parameters"]["resultType"], "core")
        self.assertEqual(meta["parameters"]["cursorMark"], "*")
        self.assertEqual(meta["parameters"]["pageSize"], guided.PAGE_SIZE)
        self.assertEqual(meta["source"], "Europe PMC")
        self.assertFalse(meta["possibly_truncated"])
        self.assertEqual(df.loc[0, "Title"], "Good study")
        self.assertEqual(df.loc[0, "Authors"], "Alice A; Bob B")
        self.assertEqual(df.loc[0, "Venue"], "The journal")
        self.assertEqual(df.loc[0, "Abstract"], "First & second.")
        self.assertEqual(df.loc[0, "Citations"], 3)
        self.assertEqual(df.loc[0, "References"], "")
        self.assertEqual(df.loc[0, "Source"], "Europe PMC")
        self.assertNotIn("unused-secret", repr(meta))

    def test_europe_pmc_missing_and_fallback_author_not_split(self):
        with patch.object(guided.requests, "get", return_value=europe_response([
            {"id": "345", "authorString": "Doe J, Smith A", "citedByCount": None, "referenceCount": 4}], 1)):
            df, _ = guided.fetch_guided("ex1_health", "Europe PMC")
        self.assertEqual(df.loc[0, "Authors"], "Doe J, Smith A")
        self.assertEqual(df.loc[0, "References"], "")
        self.assertEqual(df.loc[0, "Citations"], "")
        self.assertEqual(df.loc[0, "Abstract"], "")

    def test_openaire_client_normalization_is_preserved_and_log_allowlisted(self):
        existing = pd.DataFrame([{"ID": "rec-1", "Title": "A", "Authors": "Alice; Bob", "Abstract": "A description",
                                  "Publication Type": "Preprint", "Abstract Source": "description"}])
        log = {"total_matches": 1, "raw_records_received": 1, "possibly_truncated": False,
               "malicious": "https://private/?key=secret", "license_note": "unused", "endpoint": "bad"}
        query = guided.guided_query("ex1_health", "OpenAIRE")
        with patch.object(guided.openaire_client, "fetch_openaire", return_value=(existing, log)) as fetch:
            frame, meta = guided.fetch_guided("ex1_health", "OpenAIRE", "secret")
        fetch.assert_called_once_with(query, per_page=guided.PAGE_SIZE, max_pages=1)
        self.assertEqual(frame.loc[0, "ID"], "rec-1")
        self.assertEqual(frame.loc[0, "Authors"], "Alice; Bob")
        self.assertEqual(frame.loc[0, "Abstract Source"], "description")
        self.assertEqual(frame.loc[0, "References"], "")
        self.assertEqual(frame.loc[0, "Source"], "OpenAIRE")
        self.assertNotIn("Source", existing)  # no mutation
        self.assertEqual(meta["endpoint"], guided.openaire_client.ENDPOINT)
        self.assertEqual(meta["parameters"], {"search": query, "type": "publication", "pageSize": guided.PAGE_SIZE, "cursor": "*"})
        self.assertNotIn("secret", repr(meta))
        self.assertNotIn("license_note", meta)
        self.assertFalse(meta["possibly_truncated"])

    def test_actual_openaire_client_sends_one_anonymous_page(self):
        payload = {"header": {"numFound": 1}, "results": [{"id": "x", "mainTitle": "Study",
                   "authors": [{"fullName": "Alice"}], "descriptions": ["Text"]}]}
        with patch.object(guided.openaire_client.requests, "get", return_value=Response(payload)) as get:
            df, meta = guided.fetch_guided("ex3_microplastics", "OpenAIRE")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs["params"], meta["parameters"])
        self.assertNotIn("headers", get.call_args.kwargs)
        self.assertEqual(df.loc[0, "Authors"], "Alice")
        self.assertEqual(df.loc[0, "Abstract"], "Text")
        self.assertIn("not necessarily an abstract", df.loc[0, "Abstract Source"])

    def test_empty_and_possible_truncation(self):
        for provider, payload in [("Crossref", crossref_response([], 0)),
                                  ("Europe PMC", europe_response([], 0))]:
            with self.subTest(provider=provider), patch.object(guided.requests, "get", return_value=payload):
                df, meta = guided.fetch_guided("ex1_health", provider)
                self.assertEqual(list(df.columns), guided.COLUMNS)
                self.assertTrue(df.empty)
                self.assertEqual(meta["total_matches"], 0)
                self.assertEqual(meta["returned"], 0)
                self.assertFalse(meta["possibly_truncated"])
        # No count with results must not be presented as a complete corpus.
        with patch.object(guided.requests, "get", return_value=crossref_response([{"DOI": "10.1/a"}], None)):
            _, meta = guided.fetch_guided("ex1_health", "Crossref")
        self.assertIsNone(meta["total_matches"])
        self.assertTrue(meta["possibly_truncated"])
        # Count says all received but malformed records were skipped.
        with patch.object(guided.requests, "get", return_value=europe_response([None, {"id": "one"}], 2)):
            df, meta = guided.fetch_guided("ex1_health", "Europe PMC")
        self.assertEqual(len(df), 1)
        self.assertTrue(meta["possibly_truncated"])
        # OpenAlex may supply a cursor even when the authoritative count was reached.
        with patch.object(guided.openalex_client, "fetch_works", return_value=([{"id": "W1"}], {"total_matches": 1, "possibly_truncated": True})):
            _, meta = guided.fetch_guided("ex1_health", "OpenAlex", "key")
        self.assertFalse(meta["possibly_truncated"])

    def test_missing_key_invalid_schema_and_unsafe_errors_are_sanitized(self):
        secret = "credential-98765"
        with patch.object(guided.openalex_client, "fetch_works") as fetch:
            with self.assertRaises(guided.GuidedSearchError):
                guided.fetch_guided("ex1_health", "OpenAlex")
            fetch.assert_not_called()
        for provider in ("OpenAlex", "OpenAIRE"):
            module = guided.openalex_client if provider == "OpenAlex" else guided.openaire_client
            function = "fetch_works" if provider == "OpenAlex" else "fetch_openaire"
            with self.subTest(provider=provider), patch.object(module, function, side_effect=ValueError(f"https://example.com/?api_key={secret}")):
                with self.assertRaises(guided.GuidedSearchError) as caught:
                    guided.fetch_guided("ex1_health", provider, secret)
                text = "".join(traceback.format_exception(caught.exception))
                self.assertNotIn(secret, text)
                self.assertNotIn("https://example.com", text)
        for provider, bad in [("Crossref", Response({"message": {"items": None}})),
                              ("Europe PMC", Response({"resultList": {"result": None}})),
                              ("Crossref", Response(json_error=ValueError(secret))),
                              ("Europe PMC", Response(status_code=503))]:
            with self.subTest(provider=provider, status=bad.status_code), patch.object(guided.requests, "get", return_value=bad):
                with self.assertRaises(guided.GuidedSearchError) as caught:
                    guided.fetch_guided("ex2_ubi", provider, secret)
                self.assertNotIn(secret, "".join(traceback.format_exception(caught.exception)))
        for provider in ("Crossref", "Europe PMC"):
            with self.subTest(provider=provider), patch.object(guided.requests, "get", side_effect=requests.Timeout("url?key=" + secret)):
                with self.assertRaises(guided.GuidedSearchError) as caught:
                    guided.fetch_guided("ex1_health", provider, secret)
                text = "".join(traceback.format_exception(caught.exception))
                self.assertNotIn(secret, text)
                self.assertNotIn("url?key=", text)
        with patch.object(guided.requests, "get", side_effect=RuntimeError("unanticipated " + secret)):
            with self.assertRaises(guided.GuidedSearchError) as caught:
                guided.fetch_guided("ex1_health", "Crossref", secret)
            self.assertNotIn(secret, "".join(traceback.format_exception(caught.exception)))
        with patch.object(guided.requests, "get", return_value=Response(status_code=429)):
            with self.assertRaises(guided.GuidedSearchError) as caught:
                guided.fetch_guided("ex1_health", "Crossref", secret)
        self.assertIn("429", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
