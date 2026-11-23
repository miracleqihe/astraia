from contextlib import redirect_stdout
import csv
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline import fetch_bl_dongjing as fetch
from pipeline.bl_dongjing import cards, date_range_years, extent_file_count, title_year_range
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from tests.test_southeast_archives import definition

NOW = '2026-11-23T00:00:00+00:00'
EXTENT = '62 files in VOB (DVD video), DAT (Video CD), WAV and MP3 format arranged into 27 electronic folders'


def html(body):
    return ('<html><head><title>British Library Archives and Manuscripts Catalogue</title></head><body>'
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a>' + body + '</body></html>').encode()


def fields(values): return '<dl>' + ''.join(definition(k, v) for k, v in values.items()) + '</dl>'


def root():
    return html(fields({'Record Id': '036-001577227', 'Reference (shelfmark)': 'EAP012/6/2',
        'Title': 'Dongjing Performances and Interviews', 'Extent': EXTENT, 'Record Type (Level)': 'Series',
        'Scope & Content': 'Collected during surveys between 1989 and 2006.', 'Languages': 'Chinese',
        'Start Date': '1900', 'End Date': '1999', 'Date Range': '20th century'}))


def fonds():
    return html(fields({'Record Id': '032-001577217', 'Reference (shelfmark)': 'EAP012/6',
        'Record Type (Level)': 'Fonds', 'Scope & Content': 'Music, performances and oral interviews.',
        'User Conditions': 'Access is for research purposes only'}))


def title(n): return f'Recording {n} [{1989 if n == 1 else 2006}]'


def search():
    docs = []
    for n in range(1, 28):
        shelf = f'EAP012/6/2/{n}'
        docs.append(f'<div class="document"><h2><a href="/catalog/040-{n:09d}">{shelf}</a></h2>'
                    + fields({'Reference (shelfmark)': shelf, 'Title': title(n)}) + '</div>')
    return html('<div id="documents">' + ''.join(docs) + '</div>')


def item(n):
    f = {'Record Id': f'040-{n:09d}', 'Reference (shelfmark)': f'EAP012/6/2/{n}',
         'Hierarchy Root Ancestor Record Id': '032-001577217', 'Hierarchy Record Ids': '032-001577217 036-001577227',
         'Record Type (Level)': 'File', 'Title': title(n),
         'Scope & Content': 'An oral history interview with Speaker A. Interview conducted and recorded by Recorder B.',
         'Extent': '2 WAV files, 1 hour in duration', 'Languages': 'Chinese', 'Material Type': 'Sound recordings',
         'Start Date': '2005' if n == 1 else '2006', 'End Date': '2007' if n == 1 else '2006',
         'Date Range': '2005-2007' if n == 1 else 'Dec 2006', 'Former Internal References': 'CX_20061009_Example' if n == 12 else 'ID'}
    if n == 2: f['User Conditions'] = 'Access is for research purposes only'
    if n == 20: f['Start Date'] = f['End Date'] = '2005'
    return html(fields(f))


class DongjingReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.snap = self.root / 'snapshot'; self.vault = self.root / 'vault'; self.vault.mkdir()
        def get(url, host, robots, delay):
            return (root() if url == fetch.ROOT_URL else fonds() if url == fetch.SERIES_URL
                    else item(int(url.rsplit('-', 1)[1]))), NOW
        with redirect_stdout(StringIO()), patch('pipeline.fetch_bl_dongjing.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_dongjing.request_html', side_effect=get), \
             patch('pipeline.fetch_bl_dongjing.request_search', return_value=(search(), NOW)):
            fetch.fetch(self.snap)
        self.table = self.root / 'standards.json'; self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.output, self.absent = self.root / 'review', self.root / 'absent'

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_pending_folder_inventory_retains_source_and_date_differences(self):
        staged = stage_batch(self.vault, 'asia_cn_bl_dongjing_eap012', cards(self.snap), self.table, {})
        self.assertEqual(staged['counts'], {'records': 28, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        for flag, count in [('bl_dongjing_folder_not_story', 28), ('bl_dongjing_title_year_range', 2),
                            ('bl_dongjing_date_fields_disagree', 1),
                            ('bl_dongjing_extent_disagreement', 1), ('bl_dongjing_series_year_range', 1),
                            ('bl_dongjing_item_conditions_absent', 26), ('bl_dongjing_identifier_digits', 1)]:
            self.assertEqual(summary['flags'][flag], count)
        for flag in ('bl_dongjing_source_changed', 'bl_dongjing_fields_changed', 'bl_dongjing_snapshot_invalid'):
            self.assertNotIn(flag, summary['flags'])
        with (self.output / 'bl_dongjing_recordings_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 27)
        self.assertEqual(rows[0]['题名年份落在起止字段范围'], '否')
        self.assertEqual(rows[0]['单件范围字段首项文件数相加'], '54')
        self.assertIn('Speaker A', rows[0]['馆方内容说明']); self.assertIn('Recorder B', rows[0]['馆方内容说明'])
        self.assertIn('CX_20061009', rows[11]['馆方内部项目标识原字段'])
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核'] == '待复核' for row in rows))

    def test_changed_snapshot_stops_reconstruction(self):
        stage_batch(self.vault, 'asia_cn_bl_dongjing_eap012', cards(self.snap), self.table, {})
        with (self.snap / 'item-01.html').open('ab') as stream: stream.write(b' ')
        summary = self.review()
        self.assertEqual(summary['flags']['bl_dongjing_snapshot_invalid'], 28)
        with (self.output / 'bl_dongjing_recordings_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])

    def test_parser_distinguishes_explicit_counts_and_uncomparable_dates(self):
        self.assertEqual(extent_file_count('2 MP3 files, 90 minutes'), 2)
        self.assertEqual(extent_file_count('1 MP3, 24 minutes'), 1)
        self.assertIsNone(extent_file_count('2 MP3 and 1 WAV file, 90 minutes'))
        self.assertIsNone(extent_file_count('one file, 90 minutes'))
        self.assertEqual(title_year_range({'Title': 'Example [1989]', 'Start Date': '2005', 'End Date': '2007'}), (1989, False))
        self.assertEqual(title_year_range({'Title': 'Example [2006]', 'Start Date': '', 'End Date': '2007'}), (2006, None))
        self.assertEqual(date_range_years({'Date Range': 'Oct 2006', 'Start Date': '2005', 'End Date': '2005'}), ([2006], False))
        children = fetch.parse_search(search())
        with self.assertRaises(IntakeError): fetch.parse_item(item(1).replace(b'Recording 1', b'Other title'), children[0])
        with self.assertRaises(IntakeError): fetch.parse_search(search().replace(b'EAP012/6/2/27', b'EAP012/6/2/28'))

    def test_search_change_during_capture_blocks_manifest_and_resume_is_safe(self):
        with patch('pipeline.fetch_bl_dongjing.robot_rules', side_effect=AssertionError('completed snapshot must not refetch')):
            self.assertEqual(len(fetch.fetch(self.snap)['records']), 27)
        def get(url, host, robots, delay):
            return (root() if url == fetch.ROOT_URL else fonds() if url == fetch.SERIES_URL
                    else item(int(url.rsplit('-', 1)[1]))), NOW
        changed = search().replace(b'Recording 27 [2006]', b'Changed 27 [2006]')
        target = self.root / 'changed'
        with redirect_stdout(StringIO()), patch('pipeline.fetch_bl_dongjing.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_dongjing.request_html', side_effect=get), \
             patch('pipeline.fetch_bl_dongjing.request_search', side_effect=[(search(), NOW), (changed, NOW)]):
            with self.assertRaisesRegex(IntakeError, '采集期间检索结果变化'): fetch.fetch(target)
        self.assertFalse((target / 'manifest.json').exists())
        self.assertTrue((target / 'item-27.html').exists())


if __name__ == '__main__': unittest.main()
