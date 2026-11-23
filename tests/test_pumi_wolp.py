from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.fetch_minyag_wolp import TERMS_URL
from pipeline.fetch_pumi_current import ITEM_URL
from pipeline.fetch_pumi_wolp import CATALOGUE_URL
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.pumi_wolp import ROOT_ID, cards, catalogue_rows, load_snapshot
from pipeline.review_queue import export, pumi_inventory_rows


class PumiReviewTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.snapshot, self.current, self.vault = self.root / 'catalogue', self.root / 'current', self.root / 'vault'
        for path in (self.snapshot, self.current, self.vault): path.mkdir()
        self.table, self.output, self.absent = self.root / 'standards.json', self.root / 'review', self.root / 'absent'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        (self.snapshot / 'terms.html').write_text('personal non-commercial use internal non-commercial circulation prior written permission proprietary notices', encoding='utf-8')
        paragraphs = []
        for n in range(1, 46):
            kind = 'Interview' if 3 <= n <= 14 else 'Ritual' if 21 <= n <= 23 else 'Speech' if n == 39 else 'Story' if 40 <= n <= 43 else 'Song'
            title = f"{kind} {n}, 'Madami'" if n in (15, 27) else f"{kind} {n}, 'Example'"
            if n == 41: title = "Story 2, 'The Story of Two Hangui and A Witch'"
            protocol = 'https' if n == 11 else 'http'
            paragraphs.append(f'<p>{n}. <strong>{title}</strong><br>description '
                              f'<a href="http://www.dspace.cam.ac.uk/handle/1810/{240000+n}">[Archive]</a>'
                              f'<a href="{protocol}://sms.cam.ac.uk/media/{1000+n}">[Listen to audio]</a></p>')
        text = '<html>Hu Qianma Wangjiagou forty-five audio files Pumi Premi February 2008 February 2011' + ''.join(paragraphs) + '</html>'
        (self.snapshot / 'catalogue.html').write_text(text, encoding='utf-8')
        entries = []
        for name, url in [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)]:
            raw = (self.snapshot / name).read_bytes()
            entries.append({'path': name, 'url': url, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
                            'observed_at': '2026-11-23T00:00:00+00:00'})
        (self.snapshot / 'manifest.json').write_text(json.dumps({'version': 1, 'robots_status': '404', 'pages': entries}), encoding='utf-8')
        current = ("<html><head><title>Story 2, 'The Story of Two Hangui and A Witch'</title></head><body>"
                   '<a href="http://www.dspace.cam.ac.uk/handle/1810/240041">old</a><p>forty-six audio files</p>'
                   '<ds-metadata-field-wrapper><h2>Authors</h2><a href="/browse/author?startsWith=Hu%20Qianma">Hu Qianma</a>'
                   '</ds-metadata-field-wrapper><a id="cc-name" href="http://creativecommons.org/licenses/by-nc-nd/2.0/uk/">'
                   'Attribution-NonCommercial-NoDerivs 2.0 UK: England &amp; Wales</a></body></html>')
        (self.current / 'item.html').write_text(current, encoding='utf-8')
        raw = (self.current / 'item.html').read_bytes()
        (self.current / 'manifest.json').write_text(json.dumps({'version': 1, 'robots_status': '200', 'url': ITEM_URL,
            'path': 'item.html', 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
            'observed_at': '2026-11-23T00:00:00+00:00'}), encoding='utf-8')

    def stage(self):
        return stage_batch(self.vault, 'asia_cn_pumi_wolp', cards(self.snapshot, self.current), self.table, {})

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_review_separates_recording_categories_and_count_sources(self):
        result = self.stage()
        self.assertEqual(result['counts'], {'records': 46, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        self.assertEqual(summary['flags']['pumi_unit_not_story'], 46)
        self.assertEqual(summary['flags']['pumi_collection_count_difference'], 2)
        self.assertEqual(summary['flags']['pumi_comparison_unverified'], 1)
        self.assertNotIn('pumi_fields_changed', summary['flags'])
        self.assertNotIn('pumi_current_invalid', summary['flags'])
        with (self.output / 'pumi_wolp_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            inventory = {int(row['目录序号']): row for row in csv.DictReader(stream)}
        self.assertEqual(len(inventory), 45)
        self.assertEqual(Counter(row['题名标签'] for row in inventory.values()),
                         {'歌曲题名': 25, '访谈题名': 12, '仪式题名': 3, '演说题名': 1, '故事题名': 4})
        self.assertTrue(all(row['旧目录总述音频文件数'] == '45' and row['现行单件所载馆藏文件数'] == '46' for row in inventory.values()))
        self.assertEqual(inventory[41]['现行 Authors 原字段'], 'Hu Qianma')
        self.assertEqual(inventory[41]['现行单件链接'], ITEM_URL)
        self.assertIn('NonCommercial-NoDerivs', inventory[41]['现行单件许可原字段'])
        self.assertTrue(all(not row['坐标'] and not row['标准码'] for row in inventory.values()))
        with self.assertRaisesRegex(IntakeError, '已存在卡片'):
            stage_batch(self.vault, 'asia_cn_other', cards(self.snapshot, self.current), self.table, {})

    def test_missing_record_and_changed_current_are_flagged(self):
        _, rows = load_snapshot(self.snapshot)
        root = {'id': ROOT_ID, 'sources': [], 'evidence': {'pumi_wolp_inventory': rows, 'pumi_wolp_group': {}}}
        inventory = pumi_inventory_rows([root])
        self.assertTrue(all(row['筛查状态'] == '已登记但不在待审队列' for row in inventory))
        self.stage()
        (self.current / 'item.html').write_bytes((self.current / 'item.html').read_bytes() + b' ')
        summary = self.review()
        self.assertEqual(summary['flags']['source_hash_mismatch'], 2)
        self.assertEqual(summary['flags']['pumi_current_hash_invalid'], 2)
        with (self.output / 'pumi_wolp_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])

    def test_duplicate_archive_and_unrecognised_titles_are_rejected(self):
        content = (self.snapshot / 'catalogue.html').read_text(encoding='utf-8')
        duplicate = content.replace('/1810/240002', '/1810/240001')
        with self.assertRaises(IntakeError): catalogue_rows(duplicate.encode('utf-8'))
        unknown = content.replace('Interview 3,', 'Novel 3,')
        with self.assertRaises(IntakeError): catalogue_rows(unknown.encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
