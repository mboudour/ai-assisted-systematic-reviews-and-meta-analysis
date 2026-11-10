"""Tests for the Crossref provider used by the Day 1 app."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PAGE = Path(__file__).resolve().parents[1] / 'pages' / '1_Day1_Query_to_Corpus.py'


class CrossrefProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('day1_crossref_test', PAGE)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_no_key_and_one_page_truncation(self):
        response = Mock()
        response.json.return_value = {'message': {'total-results': 200, 'items': [
            {'DOI':'10.1000/test', 'title':['Study'],
             'author':[{'family':'Doe','given':'Jane'}],
             'published':{'date-parts':[[2021]]}, 'container-title':['Journal']}
        ]}}
        with patch.object(self.module.requests, 'get', return_value=response) as get:
            df, log = self.module.query_crossref_live('study', per_page=10, include_log=True)
        self.assertEqual(log['total_matches'], 200)
        self.assertEqual(log['returned'], 1)
        self.assertTrue(log['possibly_truncated'])
        self.assertEqual(df.iloc[0]['Authors'], 'Doe Jane')
        self.assertEqual(df.iloc[0]['Abstract'], '')
        self.assertEqual(get.call_args.kwargs['params']['query'], 'study')
        self.assertNotIn('headers', get.call_args.kwargs)
        self.assertNotIn('mailto', get.call_args.kwargs['params'])

    def test_complete_small_result(self):
        response = Mock()
        response.json.return_value = {'message': {'total-results': 0, 'items': []}}
        with patch.object(self.module.requests, 'get', return_value=response):
            df, log = self.module.query_crossref_live('nothing', include_log=True)
        self.assertTrue(df.empty)
        self.assertFalse(log['possibly_truncated'])

    def test_jats_abstract_is_plain_text(self):
        response = Mock()
        response.json.return_value = {'message': {'total-results': 1, 'items': [{
            'DOI': '10.1000/example', 'title': ['P'],
            'abstract': '<jats:p>AI <jats:italic>teams</jats:italic> &amp; creativity</jats:p>'
        }]}}
        with patch.object(self.module.requests, 'get', return_value=response):
            df = self.module.query_crossref_live('query')
        self.assertEqual(df.iloc[0]['Abstract'], 'AI teams & creativity')

    def test_rate_limit_is_actionable_and_does_not_echo_request(self):
        response = Mock(status_code=429)
        error = self.module.requests.HTTPError('secret query', response=response)
        response.raise_for_status.side_effect = error
        with patch.object(self.module.requests, 'get', return_value=response):
            with self.assertRaises(self.module.CrossrefError) as raised:
                self.module.query_crossref_live('secret query')
        self.assertIn('HTTP 429', str(raised.exception))
        self.assertNotIn('secret query', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
