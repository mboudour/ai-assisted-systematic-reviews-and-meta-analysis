"""Regression tests for the participant-facing Day 1 Streamlit workflow."""
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "1_Day1_Query_to_Corpus.py"
DAY2 = ROOT / "pages" / "2_Day2_Corpus_to_Included_Studies.py"
SECTION = "🔎 BYOD — Your Own Query"
SUBMIT = "FormSubmitter:openalex_private_credentials-▶ Run My Query"


def new_byod():
    app = AppTest.from_file(str(PAGE), default_timeout=90).run()
    app.sidebar.radio[0].set_value(SECTION).run()
    return app


class Day1UITests(unittest.TestCase):
    def test_guided_pages_leave_byod_state_untouched(self):
        corpus = pd.DataFrame([{"Title": "My own corpus", "Abstract": "My own abstract"}])
        for page in (PAGE, DAY2):
            with self.subTest(page=page.name):
                app = AppTest.from_file(str(page), default_timeout=90)
                app.session_state["byod_df"] = corpus.copy()
                app.session_state["byod_included_df"] = corpus.copy()
                app.session_state["byod_screening_run"] = {"sentinel": "my screening"}
                app.session_state["byod_api"] = "My provider"
                app.session_state["byod_query"] = "My query"
                app.session_state["byod_log"] = {"source": "my source"}
                app.session_state["byod_api_widget"] = "Crossref (DOI-centric, all disciplines)"
                app.session_state["byod_query_widget"] = "My unsubmitted search"
                app.run()
                with patch("requests.get") as direct_get, patch("requests.Session.get") as session_get:
                    app.sidebar.radio[0].set_value("📌 Guided Examples").run()
                    if app.selectbox and len(app.selectbox[0].options) > 1:
                        app.selectbox[0].set_value(app.selectbox[0].options[1]).run()
                direct_get.assert_not_called()
                session_get.assert_not_called()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.sidebar.radio[0].value, "📌 Guided Examples")
                pd.testing.assert_frame_equal(app.session_state["byod_df"], corpus)
                pd.testing.assert_frame_equal(app.session_state["byod_included_df"], corpus)
                self.assertEqual(app.session_state["byod_screening_run"], {"sentinel": "my screening"})
                self.assertEqual(app.session_state["byod_api"], "My provider")
                self.assertEqual(app.session_state["byod_query"], "My query")
                self.assertEqual(app.session_state["byod_log"], {"source": "my source"})
                self.assertEqual(app.session_state["byod_api_widget"], "Crossref (DOI-centric, all disciplines)")
                self.assertEqual(app.session_state["byod_query_widget"], "My unsubmitted search")
                self.assertFalse(any("BYOD" in button.label for button in app.button))

    def test_guided_pages_do_not_create_byod_results(self):
        for page in (PAGE, DAY2):
            with self.subTest(page=page.name):
                app = AppTest.from_file(str(page), default_timeout=90).run()
                app.sidebar.radio[0].set_value("📌 Guided Examples").run()
                self.assertEqual(len(app.exception), 0)
                for key in ("byod_df", "byod_log", "byod_screening_run", "byod_included_df",
                            "byod_api_widget", "byod_query_widget"):
                    self.assertNotIn(key, app.session_state)

    def test_byod_search_and_input_controls_remain_configurable(self):
        app = new_byod()
        self.assertEqual(len(app.exception), 0)
        api = app.selectbox(key="byod_api_widget")
        self.assertEqual(len(api.options), 4)
        self.assertTrue(any(option.startswith("OpenAlex") for option in api.options))
        self.assertTrue(any(option.startswith("Crossref") for option in api.options))
        self.assertTrue(any(option.startswith("Europe PMC") for option in api.options))
        self.assertTrue(any(option.startswith("OpenAIRE") for option in api.options))
        input_methods = next(item for item in app.radio if item.label == "How would you like to provide your literature?")
        self.assertEqual(input_methods.options, [
            "🔍 Search open APIs live", "📄 Upload RIS file", "📊 Upload corpus CSV", "🗂️ Zotero Integration",
        ])
        app.text_input(key="byod_query_widget").set_value('"my research"')
        app.selectbox(key="byod_scope_widget").set_value("Broad: title, abstract, full text and keywords")
        app.checkbox(key="byod_abstract_widget").set_value(False)
        app.checkbox(key="byod_use_year").set_value(True).run()
        app.slider(key="byod_yr_slider").set_value((2015, 2020))
        app.multiselect(key="byod_type_widget").set_value(["article", "preprint"]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.text_input(key="byod_query_widget").value, '"my research"')
        self.assertEqual(app.selectbox(key="byod_scope_widget").value, "Broad: title, abstract, full text and keywords")
        self.assertFalse(app.checkbox(key="byod_abstract_widget").value)
        self.assertEqual(app.slider(key="byod_yr_slider").value, (2015, 2020))
        self.assertEqual(app.multiselect(key="byod_type_widget").value, ["article", "preprint"])

    def test_credentials_and_results_are_session_scoped(self):
        app = new_byod()
        query = '"creativity" AND "artificial intelligence"'
        fake_key = "test-only-secret"
        fake_email = "tester@example.org"
        self.assertEqual(app.text_input(key="openalex_email_widget").proto.type, 1)
        self.assertEqual(app.text_input(key="openalex_key_widget").proto.type, 1)
        app.text_input(key="byod_query_widget").set_value(query)
        app.text_input(key="openalex_email_widget").set_value(fake_email)
        app.text_input(key="openalex_key_widget").set_value(fake_key)
        response = Mock(status_code=200)
        response.json.return_value = {
            "meta": {"count": 1, "next_cursor": None},
            "results": [{"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/x",
                         "title": "Creativity and artificial intelligence", "publication_year": 2021,
                         "authorships": [], "primary_location": {},
                         "abstract_inverted_index": {"Artificial": [0], "intelligence": [1], "creativity": [2]},
                         "cited_by_count": 1, "concepts": [], "type": "article"}],
        }
        with patch("requests.Session.get", return_value=response) as request:
            app.button(key=SUBMIT).click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(request.call_count, 1)
        call = request.call_args.kwargs
        self.assertEqual(call["headers"], {"Authorization": f"Bearer {fake_key}"})
        self.assertEqual(call["params"]["search.title_and_abstract.exact"], query)
        self.assertNotIn(fake_key, json.dumps(call["params"]))
        self.assertNotIn(fake_email, json.dumps(call["params"]))
        log = json.dumps(app.session_state["byod_log"])
        self.assertNotIn(fake_key, log)
        self.assertNotIn(fake_email, log)
        self.assertEqual(app.session_state["byod_log"]["records_retrieved"], 1)

        other = new_byod()
        self.assertEqual(other.text_input(key="openalex_email_widget").value, "")
        self.assertEqual(other.text_input(key="openalex_key_widget").value, "")
        self.assertNotIn("byod_log", other.session_state)
        app.button(key="forget_openalex").click().run()
        self.assertEqual(app.text_input(key="openalex_email_widget").value, "")
        self.assertEqual(app.text_input(key="openalex_key_widget").value, "")

    def test_empty_credentials_do_not_send_a_request(self):
        app = new_byod()
        app.text_input(key="byod_query_widget").set_value('"creativity"')
        with patch("requests.Session.get") as request:
            app.button(key=SUBMIT).click().run()
        request.assert_not_called()
        self.assertTrue(any("API key" in warning.value for warning in app.warning))


if __name__ == "__main__":
    unittest.main()
