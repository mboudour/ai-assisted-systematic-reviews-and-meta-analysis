"""BYOD receives results from the local browser, never the credential file."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'pages' / '1_Day1_Query_to_Corpus.py'


class BrowserCredentialUITests(unittest.TestCase):
    def test_local_file_search_uses_returned_records_once_without_server_api_call(self):
        app = AppTest.from_file(str(PAGE), default_timeout=90).run()
        app.sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
        self.assertEqual(app.radio(key='byod_openalex_credential_method').value,
                         'Local JSON file (browser only)')
        self.assertNotIn('openalex_key_widget', app.session_state)
        query = '"creativity" AND "artificial intelligence"'
        app.text_input(key='byod_query_widget').set_value(query)
        records = [{'id': 'https://openalex.org/W1', 'title': 'A study of creativity',
                    'doi': 'https://doi.org/10.1234/example', 'publication_year': 2023,
                    'authorships': [], 'primary_location': {},
                    'abstract_inverted_index': {'Useful': [0], 'result.': [1]},
                    'concepts': [], 'referenced_works': ['https://openalex.org/W2']}]
        metadata = {'query': query, 'request_id': 'a' * 32, 'records_retrieved': 1,
                    'total_matches': 1, 'pages_fetched': 1, 'possibly_truncated': False}
        with patch('browser_openalex.render_browser_openalex', return_value=(records, metadata)) as browser, \
             patch('requests.Session.get') as server_request:
            app.run()
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.session_state['byod_query'], query)
            self.assertEqual(app.session_state['byod_api'], 'OpenAlex')
            self.assertEqual(app.session_state['byod_df'].iloc[0]['Title'], 'A study of creativity')
            self.assertEqual(app.session_state['byod_browser_last_request_id'], 'a' * 32)
            browser.assert_called()
            self.assertEqual(browser.call_args.args, (query,))
            self.assertTrue(browser.call_args.kwargs['require_abstract'])
            server_request.assert_not_called()
            log_before = json.dumps(app.session_state['byod_log'], sort_keys=True)
            app.run()
            self.assertEqual(json.dumps(app.session_state['byod_log'], sort_keys=True), log_before)
            self.assertEqual([e.message for e in app.exception], [])
            server_request.assert_not_called()
        self.assertNotIn('api_key', log_before.lower())
        self.assertNotIn('email', log_before.lower())
        other = AppTest.from_file(str(PAGE), default_timeout=90).run()
        other.sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
        self.assertNotIn('byod_df', other.session_state)
        self.assertNotIn('byod_browser_last_request_id', other.session_state)

    def test_blank_query_does_not_open_browser_or_send_request(self):
        app = AppTest.from_file(str(PAGE), default_timeout=90).run()
        with patch('browser_openalex.render_browser_openalex') as browser, patch('requests.Session.get') as server:
            app.sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
        self.assertEqual([e.message for e in app.exception], [])
        browser.assert_not_called()
        server.assert_not_called()
        self.assertTrue(any('Enter your search query' in info.value for info in app.info))


if __name__ == '__main__':
    unittest.main()
