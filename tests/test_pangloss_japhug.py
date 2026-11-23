import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.fetch_pangloss_na import fetch
from pipeline.enrich_pangloss_supplement import enrich
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_japhug import CORPUS_URL, japhug_cards
from pipeline.pangloss_na import catalogue_rows, compare_dates
from pipeline.pangloss_supplement import select_targets
from pipeline.review_queue import export
from tests.test_pangloss_na import catalogue, detail


class PanglossJaphugTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.corpus = self.root / 'japhug.html'
        self.corpus.write_text(catalogue().replace('yongning_na', 'japhug').replace('Yongning Na', 'Japhug'), encoding='utf-8')
        self.selection = self.root / 'selection.json'
        self.selection.write_text(json.dumps({'version': 1, 'corpus_url': CORPUS_URL,
            'selection_method': '按年代选择', 'limits': '非代表性',
            'groups': [{'id': 'sample', 'label': '详情选取', 'ids': ['0004341']}]}, ensure_ascii=False), encoding='utf-8')
        page = self.root / 'record-0004341.html'
        page.write_text(detail('0004341', 'Le mariage de la sœur', '08/11/2006'), encoding='utf-8')
        self.seed = self.root / 'seed.json'
        self.seed.write_text(json.dumps({'version': 1, 'records': [{'id': '0004341', 'path': page.name,
                                                                   'sha256': sha256(page.read_bytes()).hexdigest()}]}), encoding='utf-8')
        self.snapshots = self.root / 'snapshots'
        self.output = self.root / 'review'
        self.absent = self.root / 'absent'

    def prepare(self):
        with patch('pipeline.fetch_pangloss_na.robot_rules', return_value=(None, '404')):
            fetch(self.corpus, self.selection, self.snapshots, self.seed, corpus_name='Japhug', corpus_url=CORPUS_URL)
        return stage_batch(self.vault, 'asia_cn_pangloss_japhug',
                           japhug_cards(self.corpus, self.selection, self.snapshots), self.table, {})

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_full_catalogue_and_selected_detail_remain_distinct(self):
        staged = self.prepare()
        self.assertEqual(staged['counts'], {'records': 3, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        self.assertEqual(summary['collections'], {'asia': 3})
        self.assertEqual(summary['flags']['japhug_recording_not_story'], 3)
        self.assertEqual(summary['flags']['japhug_detail_unchecked'], 1)
        self.assertEqual(summary['flags']['japhug_license_per_record'], 1)
        self.assertNotIn('japhug_snapshot_invalid', summary['flags'])
        self.assertNotIn('japhug_fields_changed', summary['flags'])
        with (self.output / 'pangloss_japhug_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        by_id = {row['馆藏编号']: row for row in rows}
        self.assertEqual(by_id['0004341']['详情录音日期'], '08/11/2006')
        self.assertIn('CC-BY-NC-SA-2.5', by_id['0004341']['详情许可原字段'])
        self.assertTrue(by_id['0004341']['详情页面SHA256'])
        self.assertEqual(by_id['0004487']['详情状态'], '详情尚未采集')
        self.assertFalse(by_id['0004487']['详情页面SHA256'])
        self.assertTrue(all(row['语料背景研究'] == 'https://langsci-press.org/index.php/LangSci-Press/catalog/book/549' for row in rows))
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核'] == '待复核' for row in rows))

    def test_changed_fields_and_source_snapshots_are_flagged(self):
        self.prepare()
        card = self.vault / '00_drafts/asia_cn_pangloss_japhug/case_cn_japhug_0004341.md'
        text = card.read_text(encoding='utf-8')
        card.write_text(text.replace('"馆方目录录音日期": "2006-11-08"',
                                     '"馆方目录录音日期": "2006-11-09"'), encoding='utf-8')
        self.assertEqual(self.review()['flags']['japhug_fields_changed'], 1)
        page = self.snapshots / 'records/0004341/page.html'
        page.write_bytes(page.read_bytes() + b'changed')
        self.assertEqual(self.review()['flags']['source_hash_mismatch'], 1)

    def test_catalogue_identity_and_date_precision(self):
        self.assertEqual(len(catalogue_rows(self.corpus.read_bytes(), 'Japhug')), 2)
        with self.assertRaises(IntakeError):
            catalogue_rows(self.corpus.read_bytes(), 'Yongning Na')
        self.assertTrue(compare_dates('2005-07', '07/2005'))
        self.assertFalse(compare_dates('2005-08', '07/2005'))
        self.assertIsNone(compare_dates('2005', '07/2005'))
        self.assertIsNone(compare_dates('2005-13', '13/2005'))

    def test_japhug_detail_supplement_uses_the_same_review_gate(self):
        self.prepare()
        chosen = select_targets(self.vault,self.corpus,self.selection,'japhug',200)
        self.assertEqual(chosen['groups'][0]['ids'],['0004487'])
        folder = self.root/'supplement'
        folder.mkdir()
        selection_path = folder/'selection.json'
        selection_path.write_text(json.dumps(chosen,ensure_ascii=False,indent=2),encoding='utf-8')
        page = self.root/'record-0004487.html'
        page.write_text(detail('0004487','Sister wedding: another speaker','12/08/2009'),encoding='utf-8')
        seed = self.root/'supplement-seed.json'
        seed.write_text(json.dumps({'version':1,'records':[{'id':'0004487','path':page.name,
                        'sha256':sha256(page.read_bytes()).hexdigest()}]}),encoding='utf-8')
        with patch('pipeline.fetch_pangloss_na.robot_rules',return_value=(None,'404')):
            fetch(self.corpus,selection_path,folder,seed,corpus_name='Japhug',corpus_url=CORPUS_URL)
        result = enrich(self.vault,self.corpus,self.selection,folder,'japhug')
        self.assertEqual(result['cards_to_update'],1)
        summary = self.review()
        self.assertNotIn('japhug_detail_unchecked',summary['flags'])
        self.assertNotIn('japhug_supplement_invalid',summary['flags'])
        with (self.output/'pangloss_japhug_review.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows = {row['馆藏编号']:row for row in csv.DictReader(stream)}
        self.assertEqual(rows['0004487']['后续详情补充'],'是')
        self.assertEqual(rows['0004487']['详情录音日期'],'12/08/2009')


if __name__ == '__main__':
    unittest.main()
