"""Participant-facing OpenAIRE searches and downstream provenance."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
DAY1 = ROOT / 'pages' / '1_Day1_Query_to_Corpus.py'
DAY2 = ROOT / 'pages' / '2_Day2_Corpus_to_Included_Studies.py'
DAY3 = ROOT / 'pages' / '3_Day3_Studies_to_Evidence.py'
CHOICE = 'OpenAIRE (multidisciplinary; no participant key)'


def frame():
    return pd.DataFrame([{
        'ID': 'OA-1', 'DOI': '10.1234/example', 'Title': 'Creativity and artificial intelligence in teams',
        'Year': 2023, 'Authors': 'Alex One; Blake Two', 'Venue': 'Research Venue',
        'Abstract': 'An empirical study of artificial intelligence and creative teamwork outcomes.',
        'Citations': 1, 'Concepts': '',
    }])


def warning_text(app):
    return '\n'.join(item.value for item in app.warning)


class OpenAIREUITests(unittest.TestCase):
    def test_every_worked_example_offers_a_warned_openaire_preset(self):
        app = AppTest.from_file(str(DAY1), default_timeout=90).run()
        app.sidebar.radio[0].set_value('📌 Guided Examples').run()
        self.assertEqual(len(app.exception), 0)
        for example in ('ex1_health', 'ex2_ubi', 'ex3_microplastics', 'ex4_csr'):
            self.assertEqual(app.button(key=f'openaire_practice_{example}').label,
                             'Use OpenAIRE practice search in BYOD')
        self.assertEqual(warning_text(app).count('OpenAIRE limitations:'), 4)
        app.button(key='openaire_practice_ex4_csr').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox(key='byod_api_widget').value, CHOICE)
        self.assertEqual(app.text_input(key='byod_query_widget').value,
                         '("corporate social responsibility" OR "CSR") AND ("financial performance" OR "profitability")')
        self.assertIn('up to 60 per hour', warning_text(app))
        self.assertIn('non-peer-reviewed', warning_text(app))
        self.assertFalse(any('API key' in widget.label for widget in app.text_input))

    def test_live_selection_warns_and_success_records_source_and_limitations(self):
        app = AppTest.from_file(str(DAY1), default_timeout=90).run()
        app.sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
        app.selectbox(key='byod_api_widget').set_value(CHOICE).run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn('up to 60 per hour', warning_text(app))
        self.assertIn('not just titles and abstracts', warning_text(app))
        app.text_input(key='byod_query_widget').set_value('"creativity" AND "artificial intelligence"')
        metadata = {'endpoint': 'https://api.openaire.eu/graph/v3/research-products',
                    'pages_fetched': 1, 'total_matches': 10, 'possibly_truncated': True}
        with patch('openaire_client.fetch_openaire', return_value=(frame(), metadata)) as search:
            app.button(key='run_byod_other').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        search.assert_called_once_with('"creativity" AND "artificial intelligence"', per_page=50, max_pages=1)
        self.assertEqual(app.session_state['byod_api'], 'OpenAIRE')
        self.assertEqual(app.session_state['byod_df'].iloc[0]['Source'], 'OpenAIRE')
        log = app.session_state['byod_log']
        self.assertIn('provider_limitations', log)
        self.assertIn('OpenAIRE limitations', json.dumps(log))
        self.assertIsNone(log['year_from'])
        self.assertEqual(log['publication_types'], [])
        self.assertTrue(log['request']['possibly_truncated'])
        self.assertIn('OpenAIRE limitations:', warning_text(app))
        self.assertIn('complete result set', warning_text(app))
        app.selectbox(key='byod_api_widget').set_value('Crossref (DOI-centric, all disciplines)').run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn('OpenAIRE limitations:', warning_text(app))  # still shown with the last result

    def test_rate_limit_message_and_warning_remain_visible(self):
        from openaire_client import OpenAIREError
        app = AppTest.from_file(str(DAY1), default_timeout=90).run()
        app.sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
        app.selectbox(key='byod_api_widget').set_value(CHOICE).run()
        app.text_input(key='byod_query_widget').set_value('"creativity"')
        with patch('openaire_client.fetch_openaire', side_effect=OpenAIREError('OpenAIRE rate limit exceeded (HTTP 429). Please wait.')):
            app.button(key='run_byod_other').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn('OpenAIRE limitations:', warning_text(app))
        self.assertTrue(any('429' in message.value for message in app.error))

    def test_downstream_warning_only_for_marked_corpus(self):
        df = frame().assign(Source='OpenAIRE')
        app = AppTest.from_file(str(DAY2), default_timeout=90)
        app.session_state['byod_df'] = df
        app.session_state['byod_api'] = 'OpenAIRE'
        app.run().sidebar.radio[0].set_value('🔎 BYOD — Screen Your Own Corpus').run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn('OpenAIRE limitations:', warning_text(app))
        app.button(key='byod_screen').click().run()
        self.assertEqual(len(app.exception), 0)
        included = app.session_state['byod_included_df']
        self.assertGreater(len(included), 0)
        self.assertEqual(included.iloc[0]['Source'], 'OpenAIRE')

        app3 = AppTest.from_file(str(DAY3), default_timeout=90)
        app3.session_state['byod_included_df'] = included
        app3.run().sidebar.radio[0].set_value('🔎 BYOD — Your Own Synthesis').run()
        self.assertEqual(len(app3.exception), 0)
        self.assertIn('OpenAIRE limitations:', warning_text(app3))

        unrelated = AppTest.from_file(str(DAY2), default_timeout=90)
        unrelated.session_state['byod_df'] = frame()
        unrelated.session_state['byod_api'] = 'Crossref'
        unrelated.run().sidebar.radio[0].set_value('🔎 BYOD — Screen Your Own Corpus').run()
        self.assertNotIn('OpenAIRE limitations:', warning_text(unrelated))

    def test_openaire_records_are_generic_in_ris_exports(self):
        for index, path in enumerate((DAY1, DAY2)):
            spec = importlib.util.spec_from_file_location(f'ris_test_{index}', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = module.df_to_ris(frame().assign(Source='OpenAIRE'))
            self.assertIn('TY  - GEN', result)
            self.assertIn('DB  - OpenAIRE', result)
            self.assertNotIn('TY  - JOUR', result)


if __name__ == '__main__':
    unittest.main()
