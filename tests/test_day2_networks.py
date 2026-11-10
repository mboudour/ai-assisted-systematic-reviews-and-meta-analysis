import unittest

import pandas as pd

from day2_networks import build_network


class Day2NetworksTests(unittest.TestCase):
    def test_authors_case_whitespace_duplicates_and_non_ascii(self):
        df = pd.DataFrame(
            [
                {"Authors": "José Álvarez; Jane Doe; jane   doe"},
                {"Authors": " josé álvarez ; 李小龙"},
            ]
        )
        result = build_network(df, "authors")
        self.assertEqual(
            [(node["id"], node["frequency"]) for node in result["nodes"]],
            [("josé álvarez", 2), ("jane doe", 1), ("李小龙", 1)],
        )
        self.assertEqual(
            result["edges"],
            [
                {"source": "jane doe", "target": "josé álvarez", "weight": 1},
                {"source": "josé álvarez", "target": "李小龙", "weight": 1},
            ],
        )

    def test_duplicate_authors_and_concepts_do_not_inflate_counts(self):
        df = pd.DataFrame(
            [
                {"Authors": "A;A;B", "Concepts": "Health; health ; Methods"},
                {"Authors": "A;B", "Concepts": "health;methods"},
            ]
        )
        self.assertEqual(build_network(df, "authors")["edges"], [{"source": "a", "target": "b", "weight": 2}])
        concepts = build_network(df, "concepts")
        self.assertEqual({n["id"]: n["frequency"] for n in concepts["nodes"]}, {"health": 2, "methods": 2})
        self.assertEqual(concepts["edges"][0]["weight"], 2)

    def test_terms_use_title_and_abstract_with_stopwords_and_bound(self):
        df = pd.DataFrame(
            [{"Title": "The Green Energy", "Abstract": "Energy policy and climate policy."}]
        )
        result = build_network(df, "terms")
        ids = {node["id"] for node in result["nodes"]}
        self.assertEqual(ids, {"green", "energy", "policy", "climate"})
        self.assertEqual(result["records_with_data"], 1)
        self.assertEqual(result["total_records"], 1)

    def test_sparse_missing_columns_and_no_concepts(self):
        df = pd.DataFrame([{"Title": None}, {"Authors": "A"}, {}])
        concepts = build_network(df, "concepts")
        self.assertEqual(concepts["nodes"], [])
        self.assertEqual(concepts["edges"], [])
        self.assertEqual(concepts["records_with_data"], 0)
        terms = build_network(df, "terms")
        self.assertEqual(terms["total_records"], 3)
        self.assertEqual(terms["records_with_data"], 0)

    def test_threshold_is_inclusive_and_top_n_filters_edges(self):
        df = pd.DataFrame(
            [
                {"Concepts": "A;B;C"},
                {"Concepts": "A;B"},
                {"Concepts": "A;C"},
            ]
        )
        result = build_network(df, "concepts", top_n=2, min_cooccurrence=2)
        self.assertEqual([node["id"] for node in result["nodes"]], ["a", "b"])
        self.assertEqual(result["edges"], [{"source": "a", "target": "b", "weight": 2}])

    def test_one_row_and_missing_values_are_safe(self):
        result = build_network(pd.DataFrame([{"Authors": "A; B", "Concepts": float("nan")}]), "authors")
        self.assertEqual(result["records_with_data"], 1)
        self.assertEqual(result["edges"][0]["weight"], 1)
        self.assertEqual(build_network(pd.DataFrame([{"Concepts": "A"}]), "concepts", min_cooccurrence=2)["edges"], [])

    def test_nullable_fields_and_large_author_list(self):
        rows = pd.DataFrame([{"Authors": pd.NA, "Concepts": pd.NA},
                             {"Authors": "; ".join(f"Author {i}" for i in range(1000)), "Concepts": "A; B"}])
        result = build_network(rows, "authors", top_n=10)
        self.assertEqual(result["records_with_data"], 1)
        self.assertEqual(len(result["nodes"]), 10)
        self.assertEqual(len(result["edges"]), 45)
        self.assertNotIn("<na>", {node["id"] for node in result["nodes"]})

    def test_validation(self):
        df = pd.DataFrame()
        with self.assertRaises(ValueError):
            build_network(df, "bad")
        with self.assertRaises(ValueError):
            build_network(df, "terms", top_n=-1)
        with self.assertRaises(ValueError):
            build_network(df, "terms", min_cooccurrence=-1)


if __name__ == "__main__":
    unittest.main()
