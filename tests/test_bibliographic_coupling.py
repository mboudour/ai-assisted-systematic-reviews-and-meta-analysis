"""Bibliographic coupling counts verified shared references, not co-occurring topics."""
import unittest
import pandas as pd
from day2_networks import build_network, canonical_reference
from day2_network_view import make_network_html


class BibliographicCouplingTests(unittest.TestCase):
    def test_identifier_normalization_does_not_merge_namespaces(self):
        examples = {
            'https://doi.org/10.1000/AbC': 'doi:10.1000/abc',
            'DOI: 10.1000/abc': 'doi:10.1000/abc',
            '10.1000/ABC': 'doi:10.1000/abc',
            'https://openalex.org/W123': 'openalex:w123',
            'openalex:W123': 'openalex:w123',
            'https://api.openalex.org/works/W123': 'openalex:w123',
            'W123': 'openalex:w123',
            'PMID: 123': 'pmid:123',
            'doi:10.1234/a%2Fb': 'doi:10.1234/a%2fb',
            'https://doi.org/10.1234/a%2Fb': 'doi:10.1234/a/b',
            'A title which is not an identifier': '',
            '': '',
        }
        for raw, expected in examples.items():
            with self.subTest(raw=raw):
                self.assertEqual(canonical_reference(raw), expected)
        self.assertNotEqual(canonical_reference('W123'), canonical_reference('PMID: 123'))
        self.assertNotEqual(canonical_reference('doi:10.1234/a%2Fb'), canonical_reference('doi:10.1234/a/b'))

    def test_counts_distinct_shared_refs_not_mentions_or_topic_overlap(self):
        df = pd.DataFrame([
            {'ID': 'paper-one', 'Title': 'First study',
             'References': '10.1000/ABC; https://doi.org/10.1000/abc; https://openalex.org/W123; W456'},
            {'ID': 'paper-two', 'Title': 'Second study',
             'References': 'doi:10.1000/abc; openalex:W123; W789'},
            {'ID': 'paper-three', 'Title': 'Third study',
             'References': '10.1000/abc; unidentifiable citation;  '},
            {'ID': 'paper-four', 'Title': 'No references', 'References': pd.NA},
        ])
        graph = build_network(df, 'coupling', top_n=10, min_cooccurrence=1)
        self.assertEqual(graph['records_with_data'], 3)
        self.assertEqual(graph['total_records'], 4)
        self.assertEqual({n['id']: n['frequency'] for n in graph['nodes']},
                         {'study:0': 3, 'study:1': 3, 'study:2': 1})
        self.assertEqual({(e['source'], e['target']): e['weight'] for e in graph['edges']},
                         {('study:0', 'study:1'): 2, ('study:0', 'study:2'): 1,
                          ('study:1', 'study:2'): 1})
        filtered = build_network(df, 'coupling', top_n=2, min_cooccurrence=2)
        self.assertEqual(filtered['records_omitted_by_node_limit'], 1)
        self.assertEqual(filtered['edges'], [{'source': 'study:0', 'target': 'study:1', 'weight': 2}])

    def test_no_reference_data_never_invents_links(self):
        df = pd.DataFrame([{'Title': 'Climate and health'}, {'Title': 'Climate and health'}])
        graph = build_network(df, 'coupling')
        self.assertEqual(graph['nodes'], [])
        self.assertEqual(graph['edges'], [])
        self.assertEqual(graph['records_with_data'], 0)
        self.assertEqual(build_network(df, 'coupling', top_n=0)['nodes'], [])

    def test_json_arrays_preserve_semicolons_inside_dois(self):
        df = pd.DataFrame([
            {'Title': 'Study A', 'References': '["doi:10.1111/abc;2020", "W1"]'},
            {'Title': 'Study B', 'References': '["https://doi.org/10.1111/abc;2020", "W2"]'},
            {'Title': 'Bad JSON', 'References': '["W1", invalid]'},
        ])
        graph = build_network(df, 'coupling')
        self.assertEqual(graph['records_with_data'], 2)
        self.assertEqual(graph['edges'], [{'source': 'study:0', 'target': 'study:1', 'weight': 1}])

    def test_tooltip_semantics_and_untrusted_labels(self):
        attack = '</script><script>window.attack=true</script>'
        df = pd.DataFrame([{'Title': attack, 'References': 'W1'},
                           {'Title': 'Another', 'References': 'W1'}])
        html = make_network_html(build_network(df, 'coupling'))
        self.assertNotIn(attack, html)
        self.assertIn('Shared reference IDs:', html)
        self.assertIn('Unique reference IDs for this study:', html)
        self.assertIn('tip.textContent', html)
        self.assertNotIn('<script src=', html)

    def test_long_study_labels_are_readable_and_keep_full_title(self):
        title = 'A real descriptive title that is long enough to overlap the entire network graph'
        graph = build_network(pd.DataFrame([{'Title': title, 'References': 'W1'}]), 'coupling')
        self.assertLess(len(graph['nodes'][0]['label']), len(title))
        self.assertIn(title, graph['nodes'][0]['full_label'])
        self.assertIn('Hover to see full study titles', make_network_html(graph))


if __name__ == '__main__':
    unittest.main()
