"""Day 3 maps supplied metadata, not guessed bibliographic relationships."""
import io
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "3_Day3_Studies_to_Evidence.py"
BYOD = "🔎 BYOD — Your Own Synthesis"


def handoff_records():
    return pd.DataFrame([
        {"ID": "paper-A", "DOI": "10.9876/a", "Title": "Alpha", "Authors": "Alice; Bob; Bob",
         "References": "10.1111/x; 10.1111/y; 10.1111/x", "Source": "Provider X"},
        {"ID": "paper-B", "DOI": "10.9876/b", "Title": "Beta", "Authors": "Alice; Bob",
         "References": "https://doi.org/10.1111/X; 10.1111/y; W123", "Source": "Provider X"},
        {"ID": "paper-C", "Title": "Gamma", "Authors": "Alice; Carol",
         "References": "PMID:123; 10.1111/x", "Source": "Provider Y"},
        {"ID": "paper-D", "Title": "Delta", "Authors": None, "References": None, "Source": None},
    ])


def byod_app(df=None):
    app = AppTest.from_file(str(PAGE), default_timeout=90)
    if df is not None:
        app.session_state["byod_included_df"] = df
    app.run().sidebar.radio[0].set_value(BYOD).run()
    return app


def captions(app):
    return "\n".join(item.value for item in app.caption)


def infos(app):
    return "\n".join(item.value for item in app.info)


def links(app, weight_column):
    frames = [element.value for element in app.dataframe if weight_column in element.value.columns]
    if len(frames) != 1:
        raise AssertionError(f"Expected one links table containing {weight_column!r}; found {len(frames)}")
    return frames[0]


class Day3BibliometricUITests(unittest.TestCase):
    def assert_ok(self, app):
        self.assertEqual([item.message for item in app.exception], [])

    def test_handoff_coauthorship_uses_original_records_and_counts_sources(self):
        app = byod_app(handoff_records())
        self.assert_ok(app)
        self.assertIn("carried over from Day 2", infos(app))
        self.assertEqual(app.selectbox(key="d3_biblio_kind_byod").value, "Co-authorship")
        self.assertIn("Usable author data: 3 of 4 selected records. Displayed: 3 nodes and 2 links", captions(app))
        self.assertIn("does not disambiguate", captions(app))
        self.assertIn("original uploaded or Day 2 handed-off records", captions(app))
        sources = next(e.value for e in app.dataframe if list(e.value.columns) == ["Source", "Records"])
        self.assertEqual(dict(zip(sources["Source"], sources["Records"])),
                         {"Provider X": 2, "Provider Y": 1, "(not recorded)": 1})
        edge_table = links(app, "Shared studies")
        self.assertEqual(sorted(edge_table["Shared studies"].tolist()), [1, 2])
        self.assertEqual(len(app.get("iframe")), 1)
        self.assertTrue(any(e.key == "d3_biblio_edges_byod" for e in app.get("download_button")))

    def test_coupling_weights_caps_thresholds_and_empty_canvas(self):
        app = byod_app(handoff_records())
        app.selectbox(key="d3_biblio_kind_byod").set_value("Bibliographic coupling").run()
        self.assert_ok(app)
        self.assertIn("Usable reference data: 3 of 4 selected records. Displayed: 3 nodes and 3 links", captions(app))
        self.assertIn("different namespaces are not cross-linked", captions(app))
        self.assertIn("longest reference lists", captions(app))
        self.assertIn("1-based row", captions(app))
        table = links(app, "Shared references")
        self.assertEqual(sorted(table["Shared references"].tolist()), [1, 1, 2])
        pair = table.loc[table["Shared references"] == 2].iloc[0]
        self.assertEqual({pair["Source record ID"], pair["Target record ID"]}, {"paper-A", "paper-B"})
        self.assertEqual({pair["Source DOI"], pair["Target DOI"]}, {"10.9876/a", "10.9876/b"})
        html = app.get("iframe")[0].proto.srcdoc
        self.assertIn("Shared reference IDs", html)
        self.assertIn("Unique reference IDs for this study", html)
        self.assertNotIn("<script src=", html)
        self.assertTrue(any(e.key == "d3_biblio_edges_byod" for e in app.get("download_button")))

        app.slider(key="d3_biblio_min_byod_coupling").set_value(2).run()
        self.assert_ok(app)
        self.assertIn("3 nodes and 1 links", captions(app))
        self.assertEqual(links(app, "Shared references")["Shared references"].tolist(), [2])
        app.slider(key="d3_biblio_min_byod_coupling").set_value(3).run()
        self.assert_ok(app)
        self.assertIn("3 nodes and 0 links", captions(app))
        self.assertIn("No shared reference identifiers among shown studies", infos(app))
        self.assertEqual(len(app.get("iframe")), 0)
        self.assertFalse(any(e.key == "d3_biblio_edges_byod" for e in app.get("download_button")))

        app.slider(key="d3_biblio_min_byod_coupling").set_value(1)
        app.slider(key="d3_biblio_top_byod_coupling").set_value(1).run()
        self.assert_ok(app)
        self.assertIn("3 of 4 selected records. Displayed: 1 nodes and 0 links", captions(app))
        self.assertIn("node cap 1; minimum link weight 1", captions(app))
        self.assertEqual(len(app.get("iframe")), 0)
        self.assertEqual(len(app.session_state["byod_included_df"]), 4)

    def test_missing_invalid_and_nonoverlapping_references_never_infer_coupling(self):
        records = pd.DataFrame([
            {"Title": "AA", "Citations": 10, "Concepts": "shared", "Authors": "Solo"},
            {"Title": "BB", "Citations": 10, "Concepts": "shared", "Authors": "Another"},
        ])
        app = byod_app(records)
        app.selectbox(key="d3_biblio_kind_byod").set_value("Bibliographic coupling").run()
        self.assert_ok(app)
        self.assertIn("0 of 2 selected records. Displayed: 0 nodes and 0 links", captions(app))
        self.assertIn("No usable References data", infos(app))
        self.assertIn("Source column not supplied", captions(app))
        self.assertEqual(len(app.get("iframe")), 0)

        # A References column with unrecognized raw citations is not enough either.
        app.session_state["byod_included_df"] = records.assign(References=["A citation", "A citation"])
        app.run()
        self.assert_ok(app)
        self.assertIn("No usable References data", infos(app))
        self.assertEqual(len(app.get("iframe")), 0)

        # Valid IDs without overlap are distinct from missing usable reference data.
        app.session_state["byod_included_df"] = records.assign(References=["10.1111/first", "10.1111/second"])
        app.run()
        self.assert_ok(app)
        self.assertIn("2 of 2 selected records. Displayed: 2 nodes and 0 links", captions(app))
        self.assertIn("No shared reference identifiers among shown studies", infos(app))
        self.assertNotIn("No usable References data", infos(app))
        self.assertEqual(len(app.get("iframe")), 0)

    def test_empty_handoff_explains_that_no_records_are_available(self):
        app = byod_app(pd.DataFrame(columns=["Title", "Authors", "References", "Source"]))
        self.assert_ok(app)
        self.assertIn("0 of 0 selected records. Displayed: 0 nodes and 0 links", captions(app))
        self.assertIn("There are no selected records to map", infos(app))
        app.selectbox(key="d3_biblio_kind_byod").set_value("Bibliographic coupling").run()
        self.assert_ok(app)
        self.assertIn("There are no selected records to map", infos(app))
        self.assertEqual(len(app.get("iframe")), 0)

    def test_uploaded_csv_overrides_handoff_and_stale_extraction(self):
        app = byod_app(handoff_records())
        # An old extraction table must not supply or replace the input bibliography.
        app.session_state["byod_extracted_df_PICO (Health Sciences)"] = pd.DataFrame([
            {"Title": "Stale", "Authors": "Invented; Person", "References": "10.1111/stale"}
        ])
        upload = pd.DataFrame([
            {"ID": "upload-A", "Title": "One", "Authors": "New A; New B", "References": '["10.1111/new;part"]', "Source": "Upload"},
            {"ID": "upload-B", "Title": "Two", "Authors": "New A; New B", "References": '["https://doi.org/10.1111/new;part"]', "Source": "Upload"},
            {"ID": "upload-C", "Title": "Three", "Authors": "New C", "References": '["10.1111/new"]', "Source": "Upload"},
        ])
        app.file_uploader[0].set_value(("included.csv", upload.to_csv(index=False).encode(), "text/csv")).run()
        self.assert_ok(app)
        self.assertNotIn("Using included studies carried over", infos(app))
        self.assertIn("3 of 3 selected records. Displayed: 3 nodes and 1 links", captions(app))
        self.assertEqual(set(links(app, "Shared studies")["Source label"]) |
                         set(links(app, "Shared studies")["Target label"]), {"New A", "New B"})
        app.selectbox(key="d3_biblio_kind_byod").set_value("Bibliographic coupling").run()
        self.assert_ok(app)
        self.assertIn("JSON array", captions(app))
        self.assertIn("3 of 3 selected records. Displayed: 3 nodes and 1 links", captions(app))
        table = links(app, "Shared references")
        self.assertEqual(table["Shared references"].tolist(), [1])
        self.assertEqual({table.iloc[0]["Source record ID"], table.iloc[0]["Target record ID"]},
                         {"upload-A", "upload-B"})
        self.assertNotIn("Stale", " ".join(table.astype(str).to_numpy().flatten()))

    def test_guided_snapshots_and_fixtures_are_explicitly_separate(self):
        app = AppTest.from_file(str(PAGE), default_timeout=90).run()
        app.sidebar.radio[0].set_value("📌 Guided Examples").run()
        self.assert_ok(app)
        for name in ("ex1_health", "ex2_ubi", "ex3_microplastics", "ex4_csr"):
            self.assertEqual(app.selectbox(key=f"d3_biblio_kind_{name}").value, "Co-authorship")
            self.assertIn("cached include-labelled snapshot", app.radio(key=f"d3_biblio_source_{name}").value)
        self.assertIn("not the source of the Day 3 extraction fixture", captions(app))
        self.assertIn("neither its search provenance nor the screening labels are verified", captions(app))
        self.assertIn("No lineage to the fixture is inferred", captions(app))
        before = len(app.get("iframe"))
        app.selectbox(key="d3_biblio_kind_ex1_health").set_value("Bibliographic coupling").run()
        self.assert_ok(app)
        self.assertIn("No usable References data", infos(app))
        self.assertEqual(len(app.get("iframe")), before - 1)
        app.radio(key="d3_biblio_source_ex1_health").set_value("Day 3 extraction fixture").run()
        app.selectbox(key="d3_biblio_kind_ex1_health").set_value("Co-authorship").run()
        self.assert_ok(app)
        self.assertIn("Using the illustrative Day 3 extraction fixture", captions(app))
        self.assertIn("Usable author data: 0 of 15 selected records", captions(app))
        self.assertIn("No usable Authors data", infos(app))

    def test_renderer_failure_still_offers_link_download(self):
        with patch("day2_network_view.make_network_html", side_effect=ValueError("Local library unavailable")), \
             patch("streamlit.download_button", wraps=st.download_button) as downloads:
            app = byod_app(handoff_records())
        self.assert_ok(app)
        self.assertTrue(any("Local library unavailable" in item.value for item in app.warning))
        self.assertEqual(links(app, "Shared studies")["Shared studies"].max(), 2)
        self.assertTrue(any(e.key == "d3_biblio_edges_byod" for e in app.get("download_button")))
        call = next(call for call in downloads.call_args_list if call.args[0] == "Download bibliometric links (CSV)")
        downloaded = pd.read_csv(io.BytesIO(call.args[1]))
        self.assertEqual(sorted(downloaded["Shared studies"].tolist()), [1, 2])


if __name__ == "__main__":
    unittest.main()
