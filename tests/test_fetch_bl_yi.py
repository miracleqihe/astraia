from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import json
import unittest
from unittest.mock import patch

from pipeline.bl_yi import cards, duration_minutes
from pipeline import fetch_bl_yi as yi
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from tests.test_southeast_archives import definition


def page(number=None):
    content = '<html><head><title>British Library Archives and Manuscripts Catalogue</title></head><body>'
    content += '<a href="https://creativecommons.org/licenses/by/4.0/">CC-BY</a><dl>'
    if number is None:
        fields = {'Record Id': '032-001617335', 'Reference (shelfmark)': 'EAP081/25', 'Languages': 'Nuosu', 'Title': 'Yi recordings',
                  'Extent': '6 electronic folders containing 81 mpa files, approximately 22 hours in duration',
                  'Scope & Content': 'The recordings are the outcome of a project conducted between 2004 and 2009.',
                  'Start Date': '1560', 'End Date': '1940'}
        for key, value in fields.items():
            content += definition(key, value)
        links = ''.join(f'<a href="/catalog/040-{number:09d}"><b>EAP081/25/{number}</b> : Title</a>' for number in range(1, 7))
        links += '<a href="/?f%5Bparent_reference_ssi%5D%5B%5D=EAP081%2F25"><b>EAP081/25</b></a>'
        content += definition('Contains', links)
    else:
        fields = {'Record Id': f'040-{number:09d}', 'Hierarchy Root Ancestor Record Id': '032-001617335',
                  'Reference (shelfmark)': f'EAP081/25/{number}', 'Languages': 'Nuosu', 'Record Type (Level)': 'File',
                  'Title': 'Recordings of Pu Rongxiang' if number == 4 else f'Recordings {number}',
                  'Scope & Content': 'Pu Rongziang; digital recordings made in 2006.' if number == 4 else 'Digital recordings made in 2006.',
                  'Extent': '2 mpa files, 1 hour 17minutes in duration', 'User Conditions': 'Access is for research purposes only. Additional access conditions.',
                  'Start Date': '1560', 'End Date': '1940'}
        for key, value in fields.items():
            content += definition(key, value)
    return (content + '</dl></body></html>').encode('utf-8')


class BritishLibraryYiFetchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / 'snapshot'

    def test_sources_are_bounded_and_tampering_fails(self):
        requests = []
        def get(url, host, robots, delay):
            requests.append(url)
            return (page() if url == yi.ROOT_URL else page(int(url.rsplit('-', 1)[1]))), '2026-11-23T00:00:00+00:00'
        with patch('pipeline.fetch_bl_yi.robot_rules', return_value=(None, '404')), patch('pipeline.fetch_bl_yi.request_html', side_effect=get):
            result = yi.fetch(self.folder)
            self.assertEqual(len(result['records']), 6)
            self.assertEqual(len(requests), 7)
            yi.fetch(self.folder)
            self.assertEqual(len(requests), 7)
        _, root, children = yi.load_snapshot(self.folder)
        self.assertEqual(root['Languages'], 'Nuosu')
        self.assertEqual(children[0][3]['Start Date'], '1560')
        self.assertEqual(children[0][3]['Scope & Content'], 'Digital recordings made in 2006.')
        target = self.folder / 'record-01.html'
        target.write_bytes(target.read_bytes() + b'changed')
        with self.assertRaises(IntakeError):
            yi.load_snapshot(self.folder)

    def test_rejects_foreign_link_and_changed_access(self):
        with self.assertRaises(IntakeError):
            yi.parse_root(page().replace(b'/catalog/040-000000001', b'https://other.example/040-000000001'))
        child = yi.parse_root(page())[1][0]
        with self.assertRaises(IntakeError):
            yi.parse_child(page(1).replace(b'Access is for research purposes only', b'unknown'), child)

    def test_review_retains_disagreement_and_keeps_groups_unclassified(self):
        def get(url, host, robots, delay):
            return (page() if url == yi.ROOT_URL else page(int(url.rsplit('-', 1)[1]))), '2026-11-23T00:00:00+00:00'
        with patch('pipeline.fetch_bl_yi.robot_rules', return_value=(None, '404')), patch('pipeline.fetch_bl_yi.request_html', side_effect=get):
            yi.fetch(self.folder)
        vault, table, output, absent = (Path(self.temporary.name) / name for name in ('vault', 'table.json', 'review', 'absent'))
        vault.mkdir()
        table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        result = stage_batch(vault, 'asia_cn_bl_yi_eap081', cards(self.folder), table, {})
        self.assertEqual(result['counts'], {'records': 7, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = export(vault, output, absent, absent, absent, absent, absent, table, absent)
        self.assertEqual(summary['flags']['bl_yi_group_not_story'], 7)
        self.assertEqual(summary['flags']['bl_yi_dates_disagree'], 7)
        self.assertEqual(summary['flags']['bl_yi_name_variant'], 1)
        self.assertEqual(summary['flags']['bl_yi_duration_difference'], 1)
        self.assertNotIn('bl_yi_snapshot_invalid', summary['flags'])
        self.assertNotIn('bl_yi_fields_changed', summary['flags'])
        self.assertEqual(duration_minutes('2 mpa files, 1 hour 17minutes in duration'), 77)
        with (output / 'bl_yi_recordings_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核'] == '待复核' for row in rows))
        fourth = next(row for row in rows if row['馆方档号'] == 'EAP081/25/4')
        self.assertIn('Pu Rongxiang', fourth['馆方题名'])
        self.assertIn('Pu Rongziang', fourth['馆方内容说明'])
        self.assertIn('1560', fourth['馆方日期起始原字段'])
        self.assertIn('2006', fourth['馆方内容说明'])


if __name__ == '__main__':
    unittest.main()
