"""Day 2 networks must work for included and zero-include BYOD runs."""
import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest
from day2_network_view import make_network_html
from day2_networks import build_network

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'pages' / '2_Day2_Corpus_to_Included_Studies.py'


class Day2UITests(unittest.TestCase):
    def test_network_html_escapes_script_and_stays_offline(self):
        attack = '</script><script>window.example_attack=true</script>__EDGES__'
        result = build_network(pd.DataFrame([{'Authors': f'{attack}; Scientist B'}]), 'authors')
        html = make_network_html(result)
        self.assertNotIn(attack, html)
        self.assertIn('\\u003c/script\\u003e', html)
        self.assertIn('__EDGES__', html)  # placeholder-looking data remains intact
        self.assertIn('tip.textContent', html)
        self.assertNotIn('<script src=', html)

    def test_missing_concepts_and_zero_included_still_allow_networks(self):
        df = pd.DataFrame([
            {'Title': 'Artificial intelligence and creativity in software teams',
             'Abstract': 'A case describing creative collaboration in small groups.',
             'Authors': 'Alex One; Blake Two'},
            {'Title': 'Artificial intelligence and creativity in product teams',
             'Abstract': 'Creative collaboration in a group of product designers.',
             'Authors': 'Alex One; Cameron Three'},
        ])
        app = AppTest.from_file(str(PAGE), default_timeout=90)
        app.session_state['byod_df'] = df
        app.run().sidebar.radio[0].set_value('🔎 BYOD — Screen Your Own Corpus').run()
        self.assertEqual(len(app.exception), 0)
        app.button(key='byod_screen').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.session_state['byod_included_df']), 0)
        self.assertTrue(any('No records were included' in w.value for w in app.warning))
        self.assertEqual(app.radio(key='d2_network_source_byod').value, 'All screened records (exploratory)')
        self.assertEqual(app.selectbox(key='d2_network_kind_byod').value, 'Title and abstract term co-occurrence')
        self.assertTrue(any('2 of 2' in c.value for c in app.caption))

        # Changing network widgets reruns Streamlit but must not erase the screened data.
        app.selectbox(key='d2_network_kind_byod').set_value('Co-authorship').run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn('byod_screening_run', app.session_state)
        self.assertEqual(app.selectbox(key='d2_network_kind_byod').value, 'Co-authorship')
        self.assertTrue(any('2 of 2' in c.value for c in app.caption))
        app.slider(key='d2_network_min_byod').set_value(2).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('No pairs meet' in i.value for i in app.info))

    def test_missing_abstract_column_is_handled(self):
        app = AppTest.from_file(str(PAGE), default_timeout=90)
        app.session_state['byod_df'] = pd.DataFrame([
            {'Title': 'A sufficiently long empirical study about creativity', 'Authors': 'A; B'}
        ])
        app.run().sidebar.radio[0].set_value('🔎 BYOD — Screen Your Own Corpus').run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('No Abstract column' in i.value for i in app.info))
        app.button(key='byod_screen').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.session_state['byod_included_df']), 1)
        self.assertIn('d2_network_kind_byod', app.session_state)

    def test_renamed_concepts_column_invalidates_old_results(self):
        original = pd.DataFrame([{
            'Title': 'An empirical study of creativity and artificial intelligence',
            'Abstract': 'This empirical study describes creative collaboration and teamwork.',
            'Authors': 'Alex One; Blake Two', 'Concepts': 'creativity; collaboration',
        }])
        app = AppTest.from_file(str(PAGE), default_timeout=90)
        app.session_state['byod_df'] = original
        app.run().sidebar.radio[0].set_value('🔎 BYOD — Screen Your Own Corpus').run()
        app.button(key='byod_screen').click().run()
        self.assertEqual(app.selectbox(key='d2_network_kind_byod').value, 'Concept co-occurrence')
        self.assertIn('byod_included_df', app.session_state)

        # The record values are unchanged; only the schema changes.
        app.session_state['byod_df'] = original.rename(columns={'Concepts': 'Subject'})
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('corpus has changed' in item.value for item in app.warning))
        self.assertNotIn('byod_included_df', app.session_state)
        self.assertNotIn('d2_network_kind_byod', app.session_state)

        app.button(key='byod_screen').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox(key='d2_network_kind_byod').value,
                         'Title and abstract term co-occurrence')
        self.assertTrue(any('1 of 1' in item.value for item in app.caption))


if __name__ == '__main__':
    unittest.main()
