import csv
from hashlib import sha256
import html
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.fetch_minyag_current import ITEM_URL
from pipeline.fetch_minyag_wolp import CATALOGUE_URL, TERMS_URL
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.minyag_wolp import NAMES, SELECTED, cards, catalogue_rows, load_snapshot
from pipeline.review_queue import export, minyag_inventory_rows


class MinyagCatalogueTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.snapshot = self.root / 'catalogue'
        self.snapshot.mkdir()
        self.current = self.root / 'current'
        self.current.mkdir()
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.out = self.root / 'review'
        self.absent = self.root / 'absent'
        terms = 'personal non-commercial use; internal non-commercial circulation; prior written permission; proprietary notices'
        (self.snapshot / 'terms.html').write_text(terms, encoding='utf-8')
        paragraphs = []
        for n in range(1, 63):
            identifier = 231150 if n == 19 else 100000 + n
            name = html.escape(NAMES.get(n, 'An unnamed person'))
            paragraphs.append(f'<p>{n}. <strong>Title {n}</strong><br>{name} speaks.'
                              f'<br><a href="http://www.dspace.cam.ac.uk/handle/1810/{identifier}">[Archive]</a></p>')
        catalogue = ('<html>77 audio files Bkra shis bzang po Bang smad Village Ri sne Village Sichuan Province '
                     'October and November of 2009 Khams Tibetan' + ''.join(paragraphs) + '</html>')
        (self.snapshot / 'catalogue.html').write_text(catalogue, encoding='utf-8')
        entries = []
        for name, url in [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)]:
            raw = (self.snapshot / name).read_bytes()
            entries.append({'path': name, 'url': url, 'sha256': sha256(raw).hexdigest(),
                            'bytes': len(raw), 'observed_at': '2026-11-23T00:00:00+00:00'})
        (self.snapshot / 'manifest.json').write_text(json.dumps({'version': 1, 'robots_status': '404', 'pages': entries}), encoding='utf-8')
        current = ('<html><head><title>A Story of Bu lung ma (Mgon po rnam rgyal)</title></head><body>'
                   '<a href="http://www.dspace.cam.ac.uk/handle/1810/231150">old handle</a>'
                   '<p>O rgyan dban phyugs tells a story.</p><a id="cc-name">All Rights Reserved</a></body></html>')
        (self.current / 'item.html').write_text(current, encoding='utf-8')
        raw = (self.current / 'item.html').read_bytes()
        data = {'version': 1, 'robots_status': '200', 'url': ITEM_URL, 'path': 'item.html',
                'sha256': sha256(raw).hexdigest(), 'bytes': len(raw), 'observed_at': '2026-11-23T00:00:00+00:00'}
        (self.current / 'manifest.json').write_text(json.dumps(data), encoding='utf-8')

    def stage(self):
        return stage_batch(self.vault, 'asia_cn_minyag_wolp', cards(self.snapshot, self.current), self.table, {})

    def review(self):
        return export(self.vault, self.out, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_review_preserves_units_and_conflicting_names(self):
        self.assertEqual(len(SELECTED), 34)
        result = self.stage()
        self.assertEqual(result['counts'], {'records': 35, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        self.assertEqual(summary['flags']['minyag_count_units'], 35)
        self.assertEqual(summary['flags']['minyag_name_variant'], 1)
        self.assertNotIn('minyag_fields_changed', summary['flags'])
        self.assertNotIn('minyag_current_invalid', summary['flags'])
        with (self.out / 'minyag_wolp_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            entries = {int(row['目录序号']): row for row in csv.DictReader(stream)}
        self.assertEqual(len(entries), 62)
        self.assertEqual(sum(row['筛查状态'] == '待审草稿' for row in entries.values()), 34)
        self.assertEqual(entries[21]['筛查状态'], '未选择')
        self.assertEqual(entries[19]['目录段落署名候选'], 'U gyan dbang phyung')
        self.assertEqual(entries[19]['现行单件姓名原写法'], 'O rgyan dban phyugs')
        self.assertEqual(entries[19]['现行单件链接'], ITEM_URL)
        self.assertTrue(all(not row['坐标'] and not row['标准码'] for row in entries.values()))
        with self.assertRaisesRegex(IntakeError, '已存在卡片'):
            stage_batch(self.vault, 'asia_cn_other', cards(self.snapshot, self.current), self.table, {})

    def test_snapshot_and_catalogue_tampering_fail_closed(self):
        _, rows = load_snapshot(self.snapshot)
        self.assertEqual(len(rows), 62)
        content = (self.snapshot / 'catalogue.html').read_text(encoding='utf-8')
        duplicate = content.replace('/1810/100002', '/1810/100001')
        with self.assertRaises(IntakeError):
            catalogue_rows(duplicate.encode('utf-8'))
        self.stage()
        (self.current / 'item.html').write_bytes((self.current / 'item.html').read_bytes() + b' ')
        summary = self.review()
        self.assertEqual(summary['flags']['source_hash_mismatch'], 1)
        self.assertEqual(summary['flags']['minyag_current_hash_invalid'], 1)

    def test_selected_missing_is_not_reported_as_unselected(self):
        _, rows = load_snapshot(self.snapshot)
        root = {'id': 'corpus_cn_minyag_wolp_2009', 'sources': [],
                'evidence': {'minyag_wolp_inventory': rows}}
        inventory = {row['目录序号']: row for row in minyag_inventory_rows([root])}
        self.assertEqual(inventory[19]['筛查状态'], '已选但不在待审队列')
        self.assertEqual(inventory[19]['人工复核'], '核对草稿状态')
        self.assertEqual(inventory[21]['筛查状态'], '未选择')


if __name__ == '__main__':
    unittest.main()
