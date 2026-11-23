import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline import fetch_bl_burma as bl
from pipeline import fetch_dsal_burma as dsal
from pipeline.bl_burma import candidates, cards, selected_candidate
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from tests.test_southeast_archives import definition

NOW = '2026-11-23T00:00:00+00:00'


def html(body):
    return ('<html><head><title>British Library Archives and Manuscripts Catalogue</title></head><body>'
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a>' + body + '</body></html>').encode()


def fields(values): return '<dl>' + ''.join(definition(k, v) for k, v in values.items()) + '</dl>'


def root():
    return html(fields({'Record Id': '037-000091137', 'Reference (shelfmark)': 'IOR/S/2/3', 'Title': 'Burma',
                        'Extent': '35 gramophone records', 'Record Type (Level)': 'SubSeries'}))


def series():
    return html(fields({'Record Id': '036-000091073', 'Reference (shelfmark)': 'IOR/S/2',
        'Scope & Content': 'Burma; Parable of the Prodigal Son. S/2/2/1 records a separate incident.',
        'User Conditions': 'Records cannot be played in their present form.'}))


def search():
    docs = []
    for n in range(1, 36):
        shelf = f'IOR/S/2/3/{n}'
        docs.append(f'<div class="document"><h2><a href="/catalog/040-{n:09d}">{shelf}</a></h2>'
                    + fields({'Reference (shelfmark)': shelf, 'Title': f'Recording {n}'}) + '</div>')
    return html('<div id="documents">' + ''.join(docs) + '</div>')


def item(n):
    return html(fields({'Record Id': f'040-{n:09d}', 'Reference (shelfmark)': f'IOR/S/2/3/{n}',
        'Hierarchy Root Ancestor Record Id': '032-000090901', 'Hierarchy Record Ids': '032-000090901 037-000091137',
        'Record Type (Level)': 'File', 'Title': f'Recording {n}', 'Scope & Content': 'A and B are different components.',
        'Extent': '1 gramophone record', 'Languages': 'Language A', 'Date Range': '1918',
        'Former External References': f'{5496+n}-AK'}))


def dsal_item(n):
    data = {key: '' for key in dsal.FIELDS}
    data.update(recording_title=f'DSAL title {n}', language='Language A', recording_number=f'{5496+n}AK.mp3',
                gramophone_records_volume='Burma')
    return data


class BurmaReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.bl = self.root / 'bl'; self.dsal = self.root / 'dsal'
        def get(url, host, robots, delay):
            return (root() if url == bl.ROOT_URL else series() if url == bl.SERIES_URL
                    else item(int(url.rsplit('-', 1)[1]))), NOW
        with patch('pipeline.fetch_bl_burma.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_burma.request_html', side_effect=get), \
             patch('pipeline.fetch_bl_burma.request_search', return_value=(search(), NOW)):
            bl.fetch(self.bl)
        rows = [dsal_item(n) for n in range(1, 35)] + [dsal_item(2)]  # ambiguous second, absent 35th
        def page(volume, robots, delay):
            values = rows if volume == dsal.VOLUMES[0] else []
            return values, {'url': dsal.volume_url(volume), 'sha256': 'a' * 64, 'bytes': 100, 'observed_at': NOW}
        with patch('pipeline.fetch_dsal_burma.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_dsal_burma.request_volume', side_effect=page), \
             patch('pipeline.fetch_dsal_burma.request_html', return_value=(b'<html>terms</html>', NOW)):
            dsal.fetch(self.dsal)
        self.vault = self.root / 'vault'; self.vault.mkdir()
        self.table = self.root / 'standards.json'; self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.out, self.absent = self.root / 'review', self.root / 'absent'

    def review(self):
        return export(self.vault, self.out, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_catalogue_and_candidates_remain_pending_and_distinct(self):
        result = stage_batch(self.vault, 'asia_mm_bl_burma', cards(self.bl, self.dsal), self.table, {})
        self.assertEqual(result['counts'], {'records': 36, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        self.assertEqual(summary['flags']['bl_burma_candidate_unresolved'], 2)
        self.assertEqual(summary['flags']['bl_burma_speaker_missing'], 33)
        self.assertEqual(summary['flags']['bl_burma_colonial_context'], 36)
        for key in ('bl_burma_snapshot_invalid', 'bl_burma_fields_changed', 'bl_burma_source_changed'):
            self.assertNotIn(key, summary['flags'])
        with (self.out / 'bl_burma_recordings_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 35)
        self.assertEqual(rows[1]['DSAL严格编号候选数'], '2')
        self.assertFalse(rows[1]['DSAL候选链接（待核）'])
        self.assertEqual(rows[-1]['DSAL严格编号候选数'], '0')
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核'] == '待复核' for row in rows))
        self.assertIn('DSAL title 1', rows[0]['DSAL题名原字段'])

    def test_hash_tampering_blocks_reconstruction(self):
        stage_batch(self.vault, 'asia_mm_bl_burma', cards(self.bl, self.dsal), self.table, {})
        with (self.bl / 'item-01.html').open('ab') as stream: stream.write(b' ')
        summary = self.review()
        self.assertEqual(summary['flags']['bl_burma_snapshot_invalid'], 36)
        with (self.out / 'bl_burma_recordings_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])

    def test_exact_identifier_and_minimal_fields(self):
        document = dsal_item(1) | {'recording_file': 'media.mp3', 'transcript': 'DO NOT SAVE'}
        selected = dsal.selected_items([document])[0]
        self.assertNotIn('transcript', selected); self.assertNotIn('recording_file', selected)
        row = {'fields': selected, 'page': 0, 'volume': dsal.VOLUMES[0]}
        self.assertEqual(len(candidates({'Former External References': '5497-AK'}, [row])), 1)
        self.assertEqual(candidates({'Former External References': '5497-AK extra'}, [row]), [])
        self.assertEqual(candidates({'Former External References': '5497-AK'}, [row | {'fields': selected | {'gramophone_records_volume': 'Bengal'}}]), [])
        self.assertEqual(len(candidates({'Former External References': '5497-AK'}, [row, row])), 2)
        half_row = row | {'fields': selected | {'recording_number': '5513HALFAK.mp3'}}
        self.assertEqual(candidates({'Former External References': '5513 1/2-AK'}, [half_row]), [])
        self.assertEqual(selected_candidate({'Former External References': '5513 1/2-AK'}, [half_row])[1], '1/2 与 HALF 文字线索，待核')
        self.assertIsNone(selected_candidate({'Former External References': '5513 1/2-AK'}, [half_row, half_row])[0])

    def test_changed_title_or_search_fails_closed(self):
        children = bl.parse_search(search())
        with self.assertRaises(IntakeError): bl.parse_item(item(1).replace(b'Recording 1', b'Other title'), children[0])
        with self.assertRaises(IntakeError): bl.parse_search(search().replace(b'IOR/S/2/3/35', b'IOR/S/2/3/36'))
        with (self.dsal / 'page-00.json').open('ab') as stream: stream.write(b' ')
        with self.assertRaises(IntakeError): dsal.load_snapshot(self.dsal)

    def test_local_dsal_index_rejects_extra_fields_even_when_rehashed(self):
        path = self.dsal / 'page-00.json'; document = json.loads(path.read_text(encoding='utf-8'))
        document['items'][0]['transcript'] = 'not permitted in field index'
        path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        manifest_path = self.dsal / 'manifest.json'; manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['pages'][0]['sha256'] = sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(IntakeError): dsal.load_snapshot(self.dsal)


if __name__ == '__main__': unittest.main()
