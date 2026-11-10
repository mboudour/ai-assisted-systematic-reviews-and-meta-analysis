"""Regression tests for the participant-facing Day 1 Streamlit workflow."""
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "1_Day1_Query_to_Corpus.py"
SECTION = "🔎 BYOD — Your Own Query"
SUBMIT = "FormSubmitter:openalex_private_credentials-▶ Run My Query"


def new_byod():
    app = AppTest.from_file(str(PAGE), default_timeout=90).run()
    app.sidebar.radio[0].set_value(SECTION).run()
    return app


class Day1UITests(unittest.TestCase):
    def test_example_opens_real_byod_controls(self):
        app = AppTest.from_file(str(PAGE), default_timeout=90).run()
        app.sidebar.radio[0].set_value("📌 Guided Examples").run()
        app.button(key="practice_ex3_microplastics").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.sidebar.radio[0].value, SECTION)
        self.assertEqual(app.text_input(key="byod_query_widget").value,
                         '(microplastic OR microplastics) AND (aquatic OR marine)')
        self.assertEqual(app.selectbox(key="byod_scope_widget").value,
                         "Title and abstract (no stemming)")
        self.assertTrue(app.checkbox(key="byod_use_year").value)
        self.assertEqual(app.slider(key="byod_yr_slider").value, (2010, 2024))
        self.assertEqual(app.multiselect(key="byod_type_widget").value, ["article"])

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
