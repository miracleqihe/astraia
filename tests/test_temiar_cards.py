import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.fetch_minyag_wolp import TERMS_URL
from pipeline.fetch_temiar_current import ITEM_URL
from pipeline.fetch_temiar_wolp import CATALOGUE_URL
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export, temiar_inventory_rows
from pipeline.temiar_wolp import ROOT_ID, SONGS, SELECTED, cards, load_snapshot


class TemiarReviewTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.snapshot, self.current, self.vault = self.root / 'catalogue', self.root / 'current', self.root / 'vault'
        for path in (self.snapshot, self.current, self.vault): path.mkdir()
        self.table, self.output, self.absent = self.root / 'standards.json', self.root / 'review', self.root / 'absent'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        (self.snapshot / 'terms.html').write_text('personal non-commercial use internal non-commercial circulation prior written permission proprietary notices', encoding='utf-8')
        descriptions = {1: 'Aileen Margaret Robertson', 23: 'Peggy Robertson', 29: 'H.D. Noone nine Dream Music tracks',
                        30: 'H.D. Noone', 32: 'nine Dream Music tracks December of 1941',
                        42: '8th December, 1941 Bersei, Upper Perak', 43: 'Carvill, recording engineer Sahwi, Sumatran driver'}
        paragraphs = []
        for n in range(1, 51):
            identifier = 100010 if n == 45 else 100000 + n
            title = 'Temiar Dream Music – Bah Motoh' if n == 33 else f'Title {n}'
            sound = f'<a href="http://sms.cam.ac.uk/media/{1000+n}">[Listen to audio]</a>' if n in SONGS | set(range(4, 9)) else ''
            paragraphs.append(f'<p>{n}. <strong>{title}</strong><br>{descriptions.get(n, "Sample description")} '
                              f'<a href="http://www.dspace.cam.ac.uk/handle/1810/{identifier}">[Archive]</a>{sound}</p>')
        text = '<html>Aileen Margaret Robertson ten audio tracks five tracks 1941 Temiar' + ''.join(paragraphs) + '</html>'
        (self.snapshot / 'catalogue.html').write_text(text, encoding='utf-8')
        entries = []
        for name, url in [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)]:
            raw = (self.snapshot / name).read_bytes()
            entries.append({'path': name, 'url': url, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
                            'observed_at': '2026-11-23T00:00:00+00:00'})
        (self.snapshot / 'manifest.json').write_text(json.dumps({'version': 1, 'robots_status': '404', 'pages': entries}), encoding='utf-8')
        current = ('<html><head><title>Temiar Dream Music – Bah Motoh</title></head><body>'
                   '<a href="http://www.dspace.cam.ac.uk/handle/1810/100033">old</a>'
                   '<ds-metadata-field-wrapper><h2>Authors</h2><a href="/browse/author?startsWith=Carvill">Carvill</a>'
                   '</ds-metadata-field-wrapper><a id="cc-name">All Rights Reserved</a></body></html>')
        (self.current / 'item.html').write_text(current, encoding='utf-8')
        raw = (self.current / 'item.html').read_bytes()
        (self.current / 'manifest.json').write_text(json.dumps({'version': 1, 'robots_status': '200', 'url': ITEM_URL,
            'path': 'item.html', 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
            'observed_at': '2026-11-23T00:00:00+00:00'}), encoding='utf-8')

    def stage(self):
        return stage_batch(self.vault, 'asia_my_temiar_wolp', cards(self.snapshot, self.current), self.table, {})

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_separates_song_context_and_unselected_duplicate_photos(self):
        self.assertEqual(len(SELECTED), 20)
        result = self.stage()
        self.assertEqual(result['counts'], {'records': 21, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        self.assertEqual(summary['flags']['temiar_unit_not_story'], 21)
        self.assertEqual(summary['flags']['temiar_credit_role'], 1)
        self.assertEqual(summary['flags']['temiar_duplicate_link'], 1)
        self.assertEqual(summary['flags']['temiar_comparison_unverified'], 2)
        self.assertNotIn('temiar_fields_changed', summary['flags'])
        self.assertNotIn('temiar_current_invalid', summary['flags'])
        self.assertNotIn('temiar_audio_link_changed', summary['flags'])
        with (self.output / 'temiar_wolp_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            inventory = {int(row['目录序号']): row for row in csv.DictReader(stream)}
        self.assertEqual(len(inventory), 50)
        self.assertEqual(sum(row['筛查状态'] == '待审草稿' for row in inventory.values()), 20)
        self.assertEqual(inventory[10]['旧档案链接（待核）'], inventory[45]['旧档案链接（待核）'])
        self.assertTrue(inventory[10]['共用链接疑点'] and inventory[45]['共用链接疑点'])
        self.assertEqual(inventory[4]['筛查类别'], '后期器乐录音')
        self.assertEqual(inventory[33]['现行 Authors 原字段'], 'Carvill')
        self.assertEqual(inventory[33]['现行单件链接'], ITEM_URL)
        self.assertTrue(all(not row['坐标'] and not row['标准码'] for row in inventory.values()))
        with self.assertRaisesRegex(IntakeError, '已存在卡片'):
            stage_batch(self.vault, 'asia_my_other', cards(self.snapshot, self.current), self.table, {})

    def test_tampering_and_missing_selected_record_are_flagged(self):
        _, rows = load_snapshot(self.snapshot)
        root = {'id': ROOT_ID, 'sources': [], 'evidence': {'temiar_wolp_inventory': rows}}
        inventory = {row['目录序号']: row for row in temiar_inventory_rows([root])}
        self.assertEqual(inventory[33]['筛查状态'], '已选但不在待审队列')
        self.assertEqual(inventory[4]['筛查状态'], '未选择')
        self.stage()
        (self.current / 'item.html').write_bytes((self.current / 'item.html').read_bytes() + b' ')
        summary = self.review()
        self.assertEqual(summary['flags']['source_hash_mismatch'], 1)
        self.assertEqual(summary['flags']['temiar_current_hash_invalid'], 1)

    def test_duplicate_archival_references_checked_even_with_rehashed_manifest(self):
        path = self.snapshot / 'catalogue.html'
        path.write_text(path.read_text(encoding='utf-8').replace('/1810/100010', '/1810/200010', 1), encoding='utf-8')
        manifest_path = self.snapshot / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        raw = path.read_bytes()
        manifest['pages'][1]['sha256'], manifest['pages'][1]['bytes'] = sha256(raw).hexdigest(), len(raw)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(IntakeError, '重复情况变化'):
            load_snapshot(self.snapshot)


if __name__ == '__main__':
    unittest.main()
