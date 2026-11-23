from contextlib import redirect_stdout
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline import fetch_bl_yi_project as index
from pipeline import fetch_bl_yi_project_details as details
from pipeline.bl_yi_project import cards, hints, old_id, reason, selected, viewer_url
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from tests.test_southeast_archives import definition

NOW = '2026-11-23T00:00:00+00:00'


def wrap(body, count=None):
    meta = f'<meta name="totalResults" content="{count}">' if count is not None else ''
    return ('<html><head><title>British Library Archives and Manuscripts Catalogue</title>' + meta
            + '</head><body><a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a>' + body + '</body></html>').encode()


def definitions(fields): return '<dl>' + ''.join(definition(k, v) for k, v in fields.items()) + '</dl>'


def source_rows():
    data = [('EAP081/1', '032-000000001', 'Fonds One', 'Archive'),
            ('EAP081/1/1', '040-000000001', 'First', 'Book of oral literature.'),
            ('EAP081/1/2', '040-000000002', 'First', 'Book of legends.'),
            ('EAP081/1/3', '040-000000003', 'Third', 'A medicinal text.'),
            ('EAP081/22', '032-000000022', 'Fonds Twenty-two', 'Archive')]
    data.extend((f'EAP081/22/{n}', f'040-{n+100:09}', f'Item {n}', 'A ritual document.') for n in range(1, 10))
    data.extend([('EAP081/25', '032-000000025', 'Prior Fonds', 'Archive'),
                 ('EAP081/25/1', '040-000000201', 'Prior Item', 'An oral recording.')])
    return data


def search_page(change=False):
    rows = source_rows(); docs = []
    for shelf, rid, title, description in rows:
        if change and shelf == 'EAP081/1/1': title = 'Changed'
        fields = {'Reference (shelfmark)': shelf, 'Title': title, 'Scope & Content': description,
                  'Languages': 'Nuosu', 'Extent': '32 TIFF images'}
        docs.append(f'<div class="document"><h2><a href="/catalog/{rid}">{shelf}</a></h2>{definitions(fields)}</div>')
    return wrap('<div id="documents">' + ''.join(docs) + '</div>', len(rows))


def receipt(raw):
    return {'url': index.page_url(1), 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw), 'observed_at': NOW}


def detail_page(row, bad_parent=False):
    parts = row['shelfmark'].split('/'); group = parts[1]
    root = f'032-{int(group):09}'
    f = {'Record Id': row['record_id'], 'Hierarchy Root Ancestor Record Id': '032-999999999' if bad_parent else root,
         'Hierarchy Record Ids': root, 'Reference (shelfmark)': row['shelfmark'], 'Title': row['fields']['Title'],
         'Scope & Content': row['fields']['Scope & Content'], 'Extent': row['fields']['Extent'],
         'Languages': 'Nuosu', 'Scripts': 'Yi', 'Record Type (Level)': 'Fonds' if len(parts) == 2 else 'File'}
    if row['shelfmark'] == 'EAP081/1/1':
        f['Digitised Content'] = 'https://eap.bl.uk/archive-file/EAP081-1-1 ⧉'
    return wrap(definitions(f))


class YiProjectDetailTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.idx = self.root / 'index'; self.snap = self.root / 'details'
        raw = search_page()
        with redirect_stdout(StringIO()), patch('pipeline.fetch_bl_yi_project.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_yi_project.request_page', return_value=(raw, receipt(raw))):
            index.fetch(self.idx)
        _, self.rows = index.load_snapshot(self.idx)

    def capture(self, changed=False):
        by_url = {row['url']: row for row in self.rows}
        def get(url, host, robots, delay): return detail_page(by_url[url]), NOW
        boundary = search_page(change=changed)
        with redirect_stdout(StringIO()), patch('pipeline.fetch_bl_yi_project_details.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_yi_project_details.request_html', side_effect=get), \
             patch('pipeline.fetch_bl_yi_project_details.request_page', return_value=(boundary, receipt(boundary))):
            return details.fetch(self.snap, self.idx)

    def test_full_context_and_prior_records_are_separate(self):
        chosen = selected(self.rows)
        self.assertEqual(len(chosen), 11)
        self.assertTrue(any('EAP081/22 完整馆藏上下文' in reason(r) for r in chosen if r['shelfmark'] == 'EAP081/22/4'))
        prior = next(r for r in self.rows if r['shelfmark'] == 'EAP081/25/1')
        self.assertEqual(old_id(prior), 'corpus_cn_bl_yi_eap081_25_01'); self.assertNotIn(prior, chosen)
        self.assertNotIn('故事', hints({'fields': {'Title': 'history', 'Scope & Content': 'Original creation unknown.'}}))
        result = self.capture()
        self.assertEqual((len(result['parents']), len(result['items'])), (2, 11))
        _, parents, items = details.load_snapshot(self.snap, self.idx)
        self.assertEqual((len(parents), len(items)), (2, 11))
        first = next(x for x in items if x[0]['shelfmark'] == 'EAP081/1/1')
        self.assertEqual(first[2]['Scope & Content'], 'Book of oral literature.')
        with patch('pipeline.fetch_bl_yi_project_details.robot_rules', side_effect=AssertionError('must not refetch')):
            details.fetch(self.snap, self.idx)

    def test_changed_index_and_tampering_fail_closed(self):
        with self.assertRaisesRegex(IntakeError, '详情采集期间项目首末检索变化'): self.capture(changed=True)
        self.assertFalse((self.snap / 'manifest.json').exists())
        self.capture()
        with (self.snap / 'item-001-001.html').open('ab') as stream: stream.write(b' ')
        with self.assertRaises(IntakeError): details.load_snapshot(self.snap, self.idx)

    def test_foreign_parent_is_not_accepted(self):
        row = next(r for r in self.rows if r['shelfmark'] == 'EAP081/1/1')
        with self.assertRaises(IntakeError): details.parse_detail(detail_page(row, bad_parent=True), row, {'EAP081/1': '032-000000001'})
        expected = 'https://eap.bl.uk/archive-file/EAP081-1-1'
        self.assertEqual(viewer_url(row, {'Digitised Content': expected + ' ⧉'}), expected)
        self.assertIsNone(viewer_url(row, {'Digitised Content': expected + '-wrong ⧉'}))

    def test_review_inventory_retains_full_scope_and_distinct_same_titles(self):
        self.capture()
        vault, output, absent = self.root / 'vault', self.root / 'review', self.root / 'absent'; vault.mkdir()
        table = self.root / 'standards.json'; table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        staged = stage_batch(vault, 'asia_cn_bl_yi_project_eap081', cards(self.idx, self.snap), table, {})
        self.assertEqual(staged['counts'], {'records': 14, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = export(vault, output, absent, absent, absent, absent, absent, table, absent)
        self.assertEqual(summary['flags']['yi_project_same_title'], 2)
        self.assertEqual(summary['flags']['yi_project_item_not_story'], 14)
        self.assertEqual(summary['flags']['yi_project_viewer_unchecked'], 1)
        self.assertNotIn('source_hash_missing', summary['flags'])
        for key in ('yi_project_source_changed', 'yi_project_fields_changed', 'yi_project_snapshot_invalid'):
            self.assertNotIn(key, summary['flags'])
        with (output / 'bl_yi_project_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            inventory = list(csv.DictReader(stream))
        self.assertEqual(len(inventory), 16)
        self.assertEqual(sum(r['筛查状态'] == '本批单件待审卡' for r in inventory), 11)
        self.assertEqual(sum(r['筛查状态'] == '本批父级待审卡' for r in inventory), 2)
        self.assertEqual(sum(r['筛查状态'] == '既有卡待确认' for r in inventory), 2)
        first = next(r for r in inventory if r['馆方档号'] == 'EAP081/1/1')
        self.assertIn('EAP081/1/2', first['同题目录档号（非去重依据）'])
        self.assertEqual(first['馆方影像入口（未取得）'], 'https://eap.bl.uk/archive-file/EAP081-1-1')
        self.assertTrue(all(not r['坐标'] and not r['标准码'] for r in inventory))
        with (self.snap / 'item-001-001.html').open('ab') as stream: stream.write(b' ')
        changed = export(vault, output, absent, absent, absent, absent, absent, table, absent)
        self.assertEqual(changed['flags']['yi_project_snapshot_invalid'], 14)


if __name__ == '__main__': unittest.main()
