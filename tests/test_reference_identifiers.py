"""Provider reference acquisition and namespace-safe normalization (no live APIs)."""
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from openalex_client import fetch_works


PAGE = Path(__file__).resolve().parents[1] / "pages" / "1_Day1_Query_to_Corpus.py"
STANDARD_COLUMNS = {
    "ID", "DOI", "Title", "Year", "Authors", "Venue", "Abstract",
    "Citations", "Concepts", "References",
}


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    return result


class ReferenceIdentifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("day1_reference_test", PAGE)
        cls.page = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.page)

    def crossref(self, items, *, per_page=50):
        payload = {"message": {"total-results": len(items), "items": items}}
        with patch.object(self.page.requests, "get", return_value=response(payload)) as get:
            df, log = self.page.query_crossref_live("example", per_page=per_page, include_log=True)
        return df, log, get

    def test_openalex_fetch_select_pagination_and_transformation(self):
        citing = {
            "id": "https://openalex.org/W999",
            "doi": "https://doi.org/10.9999/CITING",
            "title": " Study ", "publication_year": 2024,
            "authorships": [{"author": {"display_name": "Alice"}}],
            "primary_location": {"source": {"display_name": "Journal"}},
            "abstract_inverted_index": {"world": [1], "Hello": [0]},
            "cited_by_count": 7, "concepts": [{"display_name": "Science"}],
            "type": "article",
            "referenced_works": [
                " https://openalex.org/W123 ", "w123", "OPENALEX:w45",
                "https://api.openalex.org/works/W45", "https://OPENALEX.ORG/w67/",
                None, 123, {"id": "W7"}, "", "W", "A123",
                "https://example.org/W8", "W9?x=1", "10.9999/CITING",
            ],
        }
        pages = [
            response({"meta": {"count": 2, "next_cursor": "page-2"}, "results": [citing]}),
            response({"meta": {"count": 2, "next_cursor": None}, "results": [
                {"id": "https://openalex.org/W998", "doi": "10.9999/self", "cited_by_count": 9}
            ]}),
        ]
        with patch("requests.Session.get", side_effect=pages) as get:
            records, metadata = fetch_works("topic", "fake-key", per_page=1, max_pages=2)
        self.assertEqual(metadata["pages_fetched"], 2)
        self.assertEqual(len(records), 2)
        for call in get.call_args_list:
            fields = call.kwargs["params"]["select"].split(",")
            self.assertIn("referenced_works", fields)
            self.assertIn("abstract_inverted_index", fields)
            self.assertNotIn("fake-key", str(call.kwargs["params"]))
        df = self.page.openalex_to_df(records)
        self.assertTrue(STANDARD_COLUMNS.issubset(df.columns))
        self.assertEqual(json.loads(df.loc[0, "References"]),
                         ["openalex:W123", "openalex:W45", "openalex:W67"])
        self.assertEqual(df.loc[1, "References"], "")
        self.assertEqual(df.loc[0, "ID"], "https://openalex.org/W999")
        self.assertEqual(df.loc[0, "DOI"], "https://doi.org/10.9999/CITING")
        self.assertEqual(df.loc[0, "Title"], "Study")
        self.assertEqual(df.loc[0, "Authors"], "Alice")
        self.assertEqual(df.loc[0, "Abstract"], "Hello world")
        self.assertEqual(df.loc[0, "Venue"], "Journal")
        self.assertEqual(df.loc[0, "Concepts"], "Science")
        self.assertEqual(df.loc[0, "Citations"], 7)
        self.assertEqual(df.loc[0, "Publication Type"], "article")

    def test_author_lists_are_not_truncated_and_europepmc_is_structured(self):
        authors = [f"Researcher {i}" for i in range(8)]
        alex = self.page.openalex_to_df([{"title": "A", "authorships": [
            {"author": {"display_name": name}} for name in authors]}])
        self.assertEqual(alex.loc[0, "Authors"].split("; "), authors)
        crossref, _, _ = self.crossref([{"title": ["A"], "author": [
            {"family": name} for name in authors]}])
        self.assertEqual(crossref.loc[0, "Authors"].split("; "), authors)
        payload = {"resultList": {"result": [{"title": "A", "authorString": "A, B",
                   "authorList": {"author": [{"fullName": "Alice A"}, {"fullName": "Bob B"}]}}]}}
        with patch.object(self.page.requests, "get", return_value=response(payload)):
            europe = self.page.query_europepmc_live("topic")
        self.assertEqual(europe.loc[0, "Authors"], "Alice A; Bob B")

    def test_crossref_request_and_explicit_doi_references(self):
        item = {
            "DOI": "10.9999/citing", "title": ["Study"],
            "author": [{"family": "Doe", "given": "Jane"}],
            "published": {"date-parts": [[2021, 1, 1]]}, "container-title": ["Journal"],
            "abstract": "<jats:p>AI &amp; creativity</jats:p>",
            "reference": [
                {"DOI": " 10.1000/ABC.X "},
                {"DOI": "https://doi.org/10.1000/abc.x"},
                {"DOI": "DOI:10.2000/Second/Subpath"},
                {"doi": "http://dx.doi.org/10.2000/second/subpath"},
                {"DOI": "10.1002/(SICI)1097-0029(1999)47:4<369::AID-JEMT8>3.0.CO;2-7"},
                {"unstructured": "DOI: 10.3000/not-extracted"},
                {"DOI": "https://example.org/10.4000/not-doi"},
                {"DOI": "10.1234/contains space"}, {"DOI": None}, {},
                None, "10.5000/not-an-explicit-doi-field", 42,
            ],
        }
        df, log, get = self.crossref([item])
        fields = get.call_args.kwargs["params"]["select"].split(",")
        self.assertIn("reference", fields)
        self.assertIn("abstract", fields)
        self.assertTrue(STANDARD_COLUMNS.issubset(df.columns))
        self.assertEqual(
            json.loads(df.loc[0, "References"]),
            ["doi:10.1000/abc.x", "doi:10.2000/second/subpath",
             "doi:10.1002/(sici)1097-0029(1999)47:4<369::aid-jemt8>3.0.co;2-7"],
        )
        self.assertEqual(df.loc[0, "ID"], "10.9999/citing")
        self.assertEqual(df.loc[0, "Authors"], "Doe Jane")
        self.assertEqual(df.loc[0, "Year"], "2021")
        self.assertEqual(df.loc[0, "Abstract"], "AI & creativity")
        self.assertEqual(log["returned"], 1)
        self.assertFalse(log["possibly_truncated"])
        self.assertNotIn("headers", get.call_args.kwargs)

    def test_doi_suffix_is_preserved_and_does_not_merge_distinct_dois(self):
        doi = self.page._crossref_reference_doi
        self.assertEqual(doi("10.1234/A;B"), "doi:10.1234/a;b")
        self.assertEqual(doi("https://doi.org/10.1234/A%3BB"), "doi:10.1234/a;b")
        self.assertEqual(doi("10.1234/A%3BB"), "doi:10.1234/a%3bb")
        self.assertEqual(doi("https://doi.org/10.1234/A%253BB"), "doi:10.1234/a%3bb")
        self.assertNotEqual(doi("10.1234/A;B"), doi("10.1234/A%3BB"))
        self.assertEqual(doi("10.1234/a?b#c"), "doi:10.1234/a?b#c")
        self.assertEqual(doi("https://doi.org/10.1234/a%3Fb%23c"), "doi:10.1234/a?b#c")
        self.assertEqual(doi("10.1/name"), "doi:10.1/name")  # Syntax check, not registry validation.
        for bad in [None, 5, "", "10.1234/", "10.x/name", "not a doi",
                    "https://doi.org/10.1234/a?query=x", "https://doi.org/10.1234/a#frag",
                    "https://doi.org/10.1234/a%zz", "https://doi.org/10.1234/a%FF",
                    "https://doi.org/10.1234/a\nb"]:
            with self.subTest(bad=bad):
                self.assertEqual(doi(bad), "")

    def test_missing_empty_and_malformed_reference_lists_never_infer_references(self):
        values = [None, [], {}, "W123", 4, [None, {}, 1, "not-an-id"]]
        records = [{"id": "W1", "doi": "10.1000/self", "cited_by_count": 5,
                    "referenced_works": value} for value in values]
        records.append({"id": "W2", "doi": "10.1000/self"})
        alex = self.page.openalex_to_df(records)
        self.assertEqual(alex["References"].tolist(), [""] * len(records))
        items = [{"DOI": "10.1000/self", "reference": value,
                  "references-count": 200} for value in values]
        items.append({"DOI": "10.1000/self", "reference-count": 200})
        crossref, _, _ = self.crossref(items)
        self.assertEqual(crossref["References"].tolist(), [""] * len(items))

    def test_malformed_nonreference_metadata_does_not_prevent_reference_extraction(self):
        records = [None, "bad record", {
            "id": {}, "doi": 6, "title": [], "authorships": [None, {"author": 5}],
            "primary_location": {"source": "bad"}, "concepts": [None, {"display_name": 1}],
            "abstract_inverted_index": {"good": [0, True, "2"], "far": [10**12], None: [1], "bad": None},
            "referenced_works": ["W8", {"id": "W9"}],
        }]
        alex = self.page.openalex_to_df(records)
        self.assertEqual(len(alex), 1)
        self.assertEqual(json.loads(alex.loc[0, "References"]), ["openalex:W8"])
        self.assertEqual(alex.loc[0, "Abstract"], "good far")
        self.assertEqual(alex.loc[0, "Authors"], "")
        items = [None, "bad record", {"DOI": 8, "title": [None, "Safe title"],
                 "author": [None, {"family": 10, "given": "A"}],
                 "published": {"date-parts": [None]}, "container-title": 8,
                 "abstract": [], "reference": [{"DOI": "10.1234/Valid"}]}]
        crossref, _, _ = self.crossref(items)
        self.assertEqual(len(crossref), 1)
        self.assertEqual(json.loads(crossref.loc[0, "References"]), ["doi:10.1234/valid"])
        self.assertEqual(crossref.loc[0, "Title"], "Safe title")
        self.assertEqual(crossref.loc[0, "Authors"], "A")
        self.assertEqual(crossref.loc[0, "Year"], "")

    def test_empty_results_still_include_reference_schema(self):
        self.assertTrue(STANDARD_COLUMNS.issubset(self.page.openalex_to_df([]).columns))
        crossref, log, _ = self.crossref([])
        self.assertTrue(STANDARD_COLUMNS.issubset(crossref.columns))
        self.assertTrue(crossref.empty)
        self.assertEqual(log["returned"], 0)

    def test_bad_crossref_response_is_reported_safely(self):
        for payload in [None, [], {"message": None}, {"message": {"items": {}}}]:
            with self.subTest(payload=payload):
                with patch.object(self.page.requests, "get", return_value=response(payload)):
                    with self.assertRaises(self.page.CrossrefError) as raised:
                        self.page.query_crossref_live("secret query")
                self.assertNotIn("secret query", str(raised.exception))
        bad_json = response(None)
        bad_json.json.side_effect = ValueError("secret query")
        with patch.object(self.page.requests, "get", return_value=bad_json):
            with self.assertRaises(self.page.CrossrefError) as raised:
                self.page.query_crossref_live("secret query")
        self.assertNotIn("secret query", str(raised.exception))

    def test_shared_reference_matching_csv_round_trip_and_namespace_separation(self):
        alex = self.page.openalex_to_df([
            {"id": "W1", "title": "A", "referenced_works": ["W123", "W123"]},
            {"id": "W2", "title": "B", "referenced_works": ["https://openalex.org/w123"]},
        ])
        crossref, _, _ = self.crossref([
            {"DOI": "10.1000/a", "reference": [{"DOI": "10.1000/W123"}, {"DOI": "10.1000/X;Y"}]},
            {"DOI": "10.1000/b", "reference": [{"DOI": "https://doi.org/10.1000/w123"},
                                                 {"DOI": "https://doi.org/10.1000/x%3By"}]},
        ])
        combined = pd.concat([alex, crossref], ignore_index=True)
        restored = pd.read_csv(io.StringIO(combined.to_csv(index=False)), keep_default_na=False)
        refs = [set(json.loads(value)) if value else set() for value in restored["References"]]
        self.assertEqual(refs[0] & refs[1], {"openalex:W123"})
        self.assertEqual(refs[2] & refs[3], {"doi:10.1000/w123", "doi:10.1000/x;y"})
        self.assertEqual(refs[0] & refs[2], set())


if __name__ == "__main__":
    unittest.main()
