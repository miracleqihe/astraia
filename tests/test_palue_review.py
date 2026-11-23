import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.archive_fetch import json_bytes
from pipeline.fetch_palue_inventory import page_url, selected_item
from pipeline.fetch_palue_sample import COLLECTION_ID, COLLECTION_URL
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.palue_inventory import cards, load_inventory
from pipeline.review_queue import export


def item(number, sound=True, language='Sara Lu\'a', speaker=True, recorder=True):
    name = f'SD1-{number:03d}'
    def values(*v): return [{'value': s} for s in v]
    return selected_item({'type': 'item', 'uuid': f'00000000-0000-0000-0000-{number:012d}', 'name': name,
        'handle': f'10125/{number + 10000}', 'metadata': {'dc.title': values(name),
        'dc.type.dcmi': values('Sound' if sound else 'Text'), 'dc.subject.language': values(language),
        'dc.content.language': values('English', 'Indonesian'),
        'dc.contributor.speaker': values(*(['Speaker A'] if speaker else [])),
        'dc.contributor.recorder': values(*(['Recorder B'] if recorder else [])),
        'dc.description': values('Genre: Folk tale. Title: PRIVATE NARRATIVE MUST NOT BE COPIED.')}})


class PalueReviewTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.snapshot, self.vault = self.root / 'snapshot', self.root / 'vault'
        self.snapshot.mkdir(); self.vault.mkdir()
        self.table, self.output, self.absent = self.root / 'standards.json', self.root / 'review', self.root / 'absent'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.rows = [item(0, sound=False), item(45, speaker=False), item(282, language='Sara Lio', recorder=False)]
        self.write_snapshot()

    def write_snapshot(self):
        page = self.snapshot / 'page-000.json'
        page.write_bytes(json_bytes({'version': 1, 'page': 0, 'items': self.rows}))
        response = {'url': page_url(0), 'sha256': 'a' * 64, 'bytes': 20, 'observed_at': '2026-11-23T00:00:00+00:00'}
        manifest = {'version': 1, 'robots_status': '200', 'collection_url': COLLECTION_URL, 'scope_uuid': COLLECTION_ID,
            'total': len(self.rows), 'page_size': 50,
            'pages': [{'page': 0, 'path': page.name, 'sha256': sha256(page.read_bytes()).hexdigest(),
                       'count': len(self.rows), 'response': response}],
            'boundary_checks': [{'page': 0, 'response': response}]}
        (self.snapshot / 'manifest.json').write_bytes(json_bytes(manifest))

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_sound_filter_preserves_roles_and_uncertainties(self):
        result = stage_batch(self.vault, 'asia_sea_palue_inventory', cards(self.snapshot), self.table, {})
        self.assertEqual(result['counts'], {'records': 3, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        for key, count in [('palue_item_not_story', 3), ('palue_rights_unknown', 3),
                           ('palue_subject_language_variant', 1), ('palue_speaker_missing', 1), ('palue_recorder_missing', 1)]:
            self.assertEqual(summary['flags'][key], count)
        self.assertNotIn('palue_fields_changed', summary['flags'])
        self.assertNotIn('palue_source_invalid', summary['flags'])
        with (self.output / 'palue_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            inventory = {r['馆方编号']: r for r in csv.DictReader(stream)}
        self.assertEqual(len(inventory), 3)
        self.assertIn('未列 Sound', inventory['SD1-000']['筛查状态'])
        self.assertEqual(inventory['SD1-282']['主题语种原字段'], 'Sara Lio')
        self.assertEqual(inventory['SD1-282']['内容语言原字段'], 'English | Indonesian')
        self.assertTrue(all(not row['坐标'] and not row['标准码'] for row in inventory.values()))
        self.assertNotIn('PRIVATE NARRATIVE', (self.output / 'data.js').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(IntakeError, '已存在卡片'):
            stage_batch(self.vault, 'asia_other', cards(self.snapshot), self.table, {})

    def test_changed_or_duplicate_fields_fail_closed(self):
        self.rows[2]['handle'] = self.rows[1]['handle']
        self.write_snapshot()
        with self.assertRaises(IntakeError): load_inventory(self.snapshot)
        self.rows[2] = item(282)
        self.write_snapshot()
        with (self.snapshot / 'page-000.json').open('ab') as stream: stream.write(b' ')
        with self.assertRaises(IntakeError): load_inventory(self.snapshot)

    def test_changed_snapshot_is_flagged_in_review(self):
        stage_batch(self.vault, 'asia_sea_palue_inventory', cards(self.snapshot), self.table, {})
        with (self.snapshot / 'page-000.json').open('ab') as stream: stream.write(b' ')
        summary = self.review()
        self.assertEqual(summary['flags']['source_hash_mismatch'], 3)
        self.assertEqual(summary['flags']['palue_source_invalid'], 3)
        with (self.output / 'palue_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])


if __name__ == '__main__':
    unittest.main()
