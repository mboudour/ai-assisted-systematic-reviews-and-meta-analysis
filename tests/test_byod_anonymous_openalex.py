"""Participant-facing tests for the explicit no-key OpenAlex option."""
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'pages' / '1_Day1_Query_to_Corpus.py'
MODE = 'No API key or email (limited)'


def byod_app():
    app = AppTest.from_file(str(PAGE), default_timeout=90).run()
    app.sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
    app.radio(key='byod_openalex_credential_method').set_value(MODE).run()
    return app


class AnonymousOpenAlexUI(unittest.TestCase):
    def test_anonymous_mode_sends_one_page_without_any_credentials(self):
        app = byod_app()
        self.assertFalse(app.exception)
        self.assertEqual(app.radio(key='byod_openalex_credential_method').value, MODE)
        self.assertNotIn('openalex_key_widget', app.session_state)
        self.assertNotIn('openalex_email_widget', app.session_state)
        self.assertTrue(any('Only the first page' in item.value for item in app.info))
        app.text_input(key='byod_query_widget').set_value('diabetes')
        response = Mock(status_code=200)
        response.json.return_value = {
            'meta': {'count': 500, 'next_cursor': 'cursor-for-next-page'},
            'results': [{'id': 'https://openalex.org/W1', 'title': 'A diabetes study',
                         'doi': 'https://doi.org/10.1234/example', 'publication_year': 2023,
                         'authorships': [], 'primary_location': {},
                         'abstract_inverted_index': {'Diabetes': [0], 'study': [1]},
                         'concepts': [], 'referenced_works': []}],
        }
        with patch('requests.Session.get', return_value=response) as get:
            app.button(key='run_byod_openalex_anonymous').click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertFalse(app.error, [e.value for e in app.error])
        self.assertEqual(get.call_count, 1)
        kwargs = get.call_args.kwargs
        self.assertNotIn('Authorization', kwargs.get('headers', {}))
        self.assertNotIn('api_key', kwargs.get('params', {}))
        self.assertNotIn('mailto', kwargs.get('params', {}))
        self.assertEqual(app.session_state['byod_df'].iloc[0]['Title'], 'A diabetes study')
        self.assertEqual(app.session_state['byod_log']['max_pages'], 1)
        self.assertEqual(app.session_state['byod_log']['request']['pages_fetched'], 1)
        self.assertTrue(app.session_state['byod_log']['request']['possibly_truncated'])
        self.assertNotIn('api_key', json.dumps(app.session_state['byod_log']).lower())
        self.assertTrue(any('More records may be available' in item.value for item in app.warning))

    def test_rate_limit_is_explained_and_previous_data_not_presented_as_new(self):
        app = byod_app()
        app.text_input(key='byod_query_widget').set_value('different query')
        app.session_state['byod_query'] = 'old query'
        app.session_state['byod_df'] = 'old results'
        with patch('requests.Session.get', return_value=Mock(status_code=429)) as get:
            app.button(key='run_byod_openalex_anonymous').click().run()
        self.assertEqual(get.call_count, 1)
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue(any('rate limit' in item.value.lower() and 'no-key' in item.value.lower()
                            for item in app.error))
        self.assertNotIn('byod_df', app.session_state)

    def test_empty_query_does_not_send_a_request(self):
        app = byod_app()
        with patch('requests.Session.get') as get:
            app.button(key='run_byod_openalex_anonymous').click().run()
        get.assert_not_called()
        self.assertTrue(any('search query' in item.value for item in app.warning))


if __name__ == '__main__':
    unittest.main()
