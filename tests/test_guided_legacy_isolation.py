"""Legacy cross-path state is never silently used in BYOD after separation."""
import unittest
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class LegacyGuidedStateTests(unittest.TestCase):
    def app(self, filename, section):
        app = AppTest.from_file(str(ROOT / 'pages' / filename), default_timeout=90)
        app.session_state['byod_log'] = {'source': 'cached teaching snapshot'}
        app.session_state['byod_df'] = pd.DataFrame([{'Title': 'Old guided snapshot', 'Abstract': 'old'}])
        app.session_state['byod_included_df'] = pd.DataFrame([{'Title': 'Old guided included'}])
        app.run().sidebar.radio[0].set_value(section).run()
        self.assertEqual([e.message for e in app.exception], [])
        return app

    def test_day1_and_day2_do_not_implicitly_use_an_old_snapshot(self):
        for filename, section in [
            ('1_Day1_Query_to_Corpus.py', '🔎 BYOD — Your Own Query'),
            ('2_Day2_Corpus_to_Included_Studies.py', '🔎 BYOD — Screen Your Own Corpus'),
        ]:
            with self.subTest(day=filename):
                app = self.app(filename, section)
                self.assertTrue(any('older version' in e.value for e in app.info))
                self.assertFalse(any('Old guided snapshot' in str(e.value) for e in app.dataframe))
                self.assertEqual(app.session_state['byod_df'].iloc[0]['Title'], 'Old guided snapshot')

    def test_day3_requires_fresh_user_data_instead_of_old_guided_handoff(self):
        app = self.app('3_Day3_Studies_to_Evidence.py', '🔎 BYOD — Your Own Synthesis')
        self.assertTrue(any('older version' in e.value for e in app.info))
        self.assertFalse(any('Old guided included' in str(e.value) for e in app.dataframe))
        uploaded = pd.DataFrame([{'Title': 'My own study', 'Year': 2024, 'Abstract': 'user record'}])
        app.file_uploader[0].set_value(('own.csv', uploaded.to_csv(index=False).encode(), 'text/csv')).run()
        self.assertEqual([e.message for e in app.exception], [])
        self.assertTrue(any('My own study' in str(e.value) for e in app.dataframe))


if __name__ == '__main__':
    unittest.main()
