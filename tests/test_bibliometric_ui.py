"""End-to-end controls for shared-reference and co-author networks in Days 1–2."""
import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
DAY1 = ROOT / 'pages' / '1_Day1_Query_to_Corpus.py'
DAY2 = ROOT / 'pages' / '2_Day2_Corpus_to_Included_Studies.py'


def corpus(reference_2='openalex:W1; doi:10.1234/shared'):
    return pd.DataFrame([
        {'ID': 'p1', 'DOI': '10.1234/p1', 'Title': 'An empirical study of creativity and collaboration',
         'Year': 2022, 'Authors': 'Alex One; Blake Two', 'Venue': 'Test Journal',
         'Abstract': 'An empirical investigation of creative collaboration among teams.', 'Citations': 0,
         'Concepts': '', 'References': 'W1; doi:10.1234/shared; W1'},
        {'ID': 'p2', 'DOI': '10.1234/p2', 'Title': 'An empirical study of creativity and software teams',
         'Year': 2023, 'Authors': 'Alex One; Blake Two', 'Venue': 'Test Journal',
         'Abstract': 'An empirical investigation of team collaboration using software.', 'Citations': 0,
         'Concepts': '', 'References': reference_2},
    ])


def setup_day1(df):
    app = AppTest.from_file(str(DAY1), default_timeout=90)
    app.session_state['byod_df'] = df
    app.session_state['byod_api'] = 'Test data'
    app.session_state['byod_query'] = 'Test query'
    app.run().sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
    return app


def setup_day2(df):
    app = AppTest.from_file(str(DAY2), default_timeout=90)
    app.session_state['byod_df'] = df
    app.run().sidebar.radio[0].set_value('🔎 BYOD — Screen Your Own Corpus').run()
    app.button(key='byod_screen').click().run()
    return app


class BibliometricUITests(unittest.TestCase):
    def test_day1_coauthorship_and_shared_references(self):
        app = setup_day1(corpus())
        app.selectbox(key='d1_bib_kind_byod').set_value('Co-authorship').run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('2 authors and 1 links' in c.value for c in app.caption))
        app.selectbox(key='d1_bib_kind_byod').set_value('Bibliographic coupling (shared references)').run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('2 studies and 1 links' in c.value for c in app.caption))
        self.assertTrue(any('Shared references' in str(frame.value.columns) for frame in app.dataframe))

    def test_day1_missing_and_nonoverlapping_references_are_reported(self):
        app = setup_day1(corpus().drop(columns=['References']))
        app.selectbox(key='d1_bib_kind_byod').set_value('Bibliographic coupling (shared references)').run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('No usable reference identifiers' in x.value for x in app.info))
        app2 = setup_day1(corpus('W999'))
        app2.selectbox(key='d1_bib_kind_byod').set_value('Bibliographic coupling (shared references)').run()
        self.assertEqual(len(app2.exception), 0)
        self.assertTrue(any('No study pair shares' in x.value for x in app2.info))

    def test_day1_csv_upload_with_json_reference_lists_and_handoff(self):
        df = corpus()
        df['References'] = ['["doi:10.1234/example;part", "W1"]',
                            '["https://doi.org/10.1234/example;part", "W2"]']
        df['Source'] = 'OpenAIRE'
        app = AppTest.from_file(str(DAY1), default_timeout=90).run()
        app.sidebar.radio[0].set_value('🔎 BYOD — Your Own Query').run()
        selector = next(item for item in app.radio if item.label == 'How would you like to provide your literature?')
        selector.set_value('📊 Upload corpus CSV').run()
        app.file_uploader[0].set_value(('papers.csv', df.to_csv(index=False).encode(), 'text/csv')).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('OpenAIRE' in item.value for item in app.warning))
        app.selectbox(key='d1_bib_kind_byod_csv').set_value('Bibliographic coupling (shared references)').run()
        self.assertTrue(any('2 studies and 1 links' in c.value for c in app.caption))
        app.button(key='send_csv_to_day2').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state['byod_df']['References'].tolist(), df['References'].tolist())
        self.assertEqual(app.session_state['byod_api'], 'User-supplied CSV')

    def test_day2_coauthorship_and_coupling(self):
        app = setup_day2(corpus())
        self.assertEqual(len(app.exception), 0)
        app.selectbox(key='d2_network_kind_byod').set_value('Co-authorship').run()
        self.assertTrue(any('2 nodes and 1 links' in x.value for x in app.caption))
        app.selectbox(key='d2_network_kind_byod').set_value('Bibliographic coupling (shared references)').run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('2 studies and 1 links' in x.value for x in app.caption))
        self.assertTrue(any('Shared references' in str(frame.value.columns) for frame in app.dataframe))

    def test_day2_missing_and_nonoverlapping_references_are_reported(self):
        for data, message in ((corpus().drop(columns=['References']), 'No usable reference identifiers'),
                              (corpus('W999'), 'No study pair shares')):
            with self.subTest(message=message):
                app = setup_day2(data)
                app.selectbox(key='d2_network_kind_byod').set_value('Bibliographic coupling (shared references)').run()
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any(message in item.value for item in app.info))


if __name__ == '__main__':
    unittest.main()
