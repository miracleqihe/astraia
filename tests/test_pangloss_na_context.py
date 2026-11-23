import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.fetch_pangloss_na import fetch
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_na import CORPUS_URL, pangloss_cards
from pipeline.pangloss_na_context import context_cards, validate_selection
from pipeline.review_queue import export
from tests.test_pangloss_na import catalogue, detail


class PanglossNaContextTests(unittest.TestCase):
    def setUp(self):
        temporary=TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.vault=self.root/'vault';self.vault.mkdir()
        self.table=self.root/'standards.json'
        self.table.write_text(json.dumps({'version':1,'entries':[],'editions':[]}),encoding='utf-8')
        self.absent=self.root/'absent';self.corpus=self.root/'corpus.html'
        self.corpus.write_text(catalogue(),encoding='utf-8')
        self.previous=self.root/'previous.json'
        self.previous.write_text(json.dumps({'version':1,'corpus_url':CORPUS_URL,'selection_method':'首轮','limits':'非随机',
            'groups':[{'id':'first','label':'首轮','ids':['0004341']}]},ensure_ascii=False),encoding='utf-8')
        self.selection=self.root/'context.json'
        self.selection.write_text(json.dumps({'version':1,'corpus_url':CORPUS_URL,'selection_method':'补充','limits':'非随机',
            'catalogue_sha256':sha256(self.corpus.read_bytes()).hexdigest(),
            'previous_selection_sha256':sha256(self.previous.read_bytes()).hexdigest(),
            'selected_titles':{'0004487':'Sister wedding: another speaker'},
            'groups':[{'id':'context_0004487','label':'口述背景 · 0004487','ids':['0004487']}]},ensure_ascii=False),encoding='utf-8')
        for number,title,when in [('0004341','Le mariage de la sœur','08/11/2006'),
                                  ('0004487','Sister wedding: another speaker','12/08/2009')]:
            (self.root/f'record-{number}.html').write_text(detail(number,title,when),encoding='utf-8')
        self.first=self.root/'first';self.extra=self.root/'extra'
        for number,selection,folder in [('0004341',self.previous,self.first),('0004487',self.selection,self.extra)]:
            file=self.root/f'record-{number}.html';seed=self.root/f'seed-{number}.json'
            seed.write_text(json.dumps({'version':1,'records':[{'id':number,'path':file.name,
                'sha256':sha256(file.read_bytes()).hexdigest()}]}),encoding='utf-8')
            with patch('pipeline.fetch_pangloss_na.robot_rules',return_value=(None,'404')):
                fetch(self.corpus,selection,folder,seed)

    def review(self):
        return export(self.vault,self.root/'review',self.absent,self.absent,self.absent,self.absent,self.absent,self.table,self.absent)

    def test_adds_singleton_record_without_replacing_the_original_selection(self):
        stage_batch(self.vault,'asia_cn_pangloss_na',pangloss_cards(self.first,self.corpus,self.previous),self.table,{})
        old=self.vault/'00_drafts/asia_cn_pangloss_na/case_cn_yongning_na_0004341.md'
        old_hash=sha256(old.read_bytes()).hexdigest()
        staged=stage_batch(self.vault,'asia_cn_pangloss_na_context',
            context_cards(self.extra,self.corpus,self.previous,self.selection),self.table,{})
        self.assertEqual(staged['counts']['records'],1)
        self.assertEqual(sha256(old.read_bytes()).hexdigest(),old_hash)
        summary=self.review()
        self.assertEqual(summary['flags']['pangloss_na_context_not_story'],1)
        self.assertNotIn('pangloss_fields_changed',summary['flags'])
        self.assertNotIn('pangloss_snapshot_invalid',summary['flags'])
        with (self.root/'review/pangloss_yongning_na_review.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),2)
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核']=='待复核' for row in rows))

    def test_rejects_overlaps_changed_titles_and_changed_source_manifest(self):
        data=json.loads(self.selection.read_text(encoding='utf-8'))
        data['selected_titles']['0004487']='wrong'
        self.selection.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaises(IntakeError):validate_selection(self.corpus,self.previous,self.selection)
        data['selected_titles']={'0004341':'Le mariage de la sœur'}
        data['groups'][0]['ids']=['0004341']
        self.selection.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaises(IntakeError):validate_selection(self.corpus,self.previous,self.selection)

    def test_manifest_changes_are_flagged_for_the_context_record(self):
        stage_batch(self.vault,'asia_cn_pangloss_na',pangloss_cards(self.first,self.corpus,self.previous),self.table,{})
        stage_batch(self.vault,'asia_cn_pangloss_na_context',context_cards(self.extra,self.corpus,self.previous,self.selection),self.table,{})
        manifest=self.extra/'manifest.json';manifest.write_bytes(manifest.read_bytes()+b' ')
        flags=self.review()['flags']
        self.assertGreaterEqual(flags['source_hash_mismatch'],1)
        self.assertGreaterEqual(flags['pangloss_snapshot_invalid'],1)

    def test_outside_location_and_researcher_disagreement_are_visible(self):
        stage_batch(self.vault,'asia_cn_pangloss_na',pangloss_cards(self.first,self.corpus,self.previous),self.table,{})
        file=self.root/'record-0004487.html'
        text=file.read_text(encoding='utf-8').replace('Chine, province du Yunnan, comté de Yongning',
                                                    'Wuzhiluo, Sichuan, China')
        text=text.replace('<h1>Chercheur(s)</h1>Michaud, Alexis',
                          '<h1>Chercheur(s)</h1>Another researcher')
        file.write_text(text,encoding='utf-8')
        seed=self.root/'seed-sichuan.json'
        seed.write_text(json.dumps({'version':1,'records':[{'id':'0004487','path':file.name,
            'sha256':sha256(file.read_bytes()).hexdigest()}]}),encoding='utf-8')
        extra=self.root/'outside'
        with patch('pipeline.fetch_pangloss_na.robot_rules',return_value=(None,'404')):
            fetch(self.corpus,self.selection,extra,seed)
        cards=list(context_cards(extra,self.corpus,self.previous,self.selection))
        self.assertNotIn('云南',cards[0][0].spatial.location_name)
        stage_batch(self.vault,'asia_cn_pangloss_na_context',iter(cards),self.table,{})
        flags=self.review()['flags']
        self.assertEqual(flags['pangloss_na_context_sichuan_recording'],1)
        self.assertEqual(flags['pangloss_credits_conflict'],1)


if __name__=='__main__':unittest.main()
