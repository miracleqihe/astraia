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
from pipeline.pangloss_khmu import (CORPUS_URL, khmu_cards, load_comparisons, speaker_identity_unverified,
                                   title_suggests_multiple_or_part, title_mentions_other_language, compare_recording_ranges)
from pipeline.pangloss_na import DOI_BASE, catalogue_rows
from pipeline.pangloss_supplement import MARKER, select_targets, validate_selection
from pipeline.review_queue import export
from tests.test_pangloss_na import detail


def khmu_catalogue():
    rows = [
        ('0002048','86ff4ae9-7f1b-3332-9ba1-1c318f311142','Histoire de Sin Xay','Thao May (from Xieng Khouang)','1968-11'),
        ('0002049','3dd9341b-647a-33d3-b0fd-2b0ab0e7f638','Histoire de Sin Xay (Fin)','Thao May (from Xieng Khouang)','1968-11'),
        ('0001994','ff347c68-8747-3516-b2b5-e7b20b5e7774','Divers mythes de Clan et légendes','Unknown','start=1964;end=1965'),
    ]
    html = ['<html><title>Collection Pangloss | corpus khmu</title><body><table id="m_resources-table">']
    for number, suffix, title, speaker, recorded in rows:
        url = f'https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-{suffix}&amp;corpus=Khmu'
        html.append(f'<tr data-corpus="Khmu"><td><button data-doi="{DOI_BASE}{number}" data-title="{title}"></button></td>'
                    f'<td><svg name="audio"></svg></td><td></td><td>00:05:12</td><td><a href="{url}"></a>{title}</td>'
                    f'<td>Ferlus, Michel</td><td>{speaker}</td><td>{recorded}</td></tr>')
    return ''.join(html) + '</table></body></html>'


class PanglossKhmuTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version':1,'entries':[],'editions':[]}), encoding='utf-8')
        self.corpus = self.root / 'khmu.html'
        self.corpus.write_text(khmu_catalogue(), encoding='utf-8')
        self.catalog = catalogue_rows(self.corpus.read_bytes(), 'Khmu')
        self.selection = self.root / 'selection.json'
        self.selection.write_text(json.dumps({'version':1,'corpus_url':CORPUS_URL,'selection_method':'按目录选取',
            'limits':'不代表全部录音','groups':[{'id':'parts','label':'续集候选','ids':['0002048','0002049']}]}, ensure_ascii=False),encoding='utf-8')
        members = [{key:self.catalog[number][key] for key in ('id','title','speakers','recorded','doi','url')} for number in ('0002048','0002049')]
        self.comparisons = self.root / 'comparisons.json'
        self.comparisons.write_text(json.dumps({'version':1,'corpus_url':CORPUS_URL,
            'catalogue_sha256':sha256(self.corpus.read_bytes()).hexdigest(),'scope':'人工对照待核',
            'groups':[{'id':'sin_xay','label':'Sin Xay 续集候选','note':'题名提示续集，须回听。','members':members}]},ensure_ascii=False),encoding='utf-8')
        entries = []
        for number in ('0002048','0002049'):
            page = self.root / f'record-{number}.html'
            raw = detail(number,self.catalog[number]['title'],'11/1968',speaker='Thao May (from Xieng Khouang)')
            location = 'Vientiane (recorded at the Mission Catholique)' if number == '0002048' else 'France, Les Vans'
            raw = raw.replace('Michaud, Alexis','Ferlus, Michel').replace('Chine, province du Yunnan, comté de Yongning',location)
            page.write_text(raw,encoding='utf-8')
            entries.append({'id':number,'path':page.name,'sha256':sha256(page.read_bytes()).hexdigest()})
        self.seed = self.root / 'seed.json'
        self.seed.write_text(json.dumps({'version':1,'records':entries}),encoding='utf-8')
        self.snapshots = self.root / 'snapshots'
        self.output = self.root / 'review'
        self.absent = self.root / 'absent'

    def prepare(self):
        with patch('pipeline.fetch_pangloss_na.robot_rules',return_value=(None,'404')):
            fetch(self.corpus,self.selection,self.snapshots,self.seed,corpus_name='Khmu',corpus_url=CORPUS_URL)
        return stage_batch(self.vault,'asia_sea_pangloss_khmu',
                           khmu_cards(self.corpus,self.selection,self.snapshots,self.comparisons),self.table,{})

    def review(self):
        return export(self.vault,self.output,self.absent,self.absent,self.absent,
                      self.absent,self.absent,self.table,self.absent)

    def test_recordings_comparisons_and_unknown_fields(self):
        staged = self.prepare()
        self.assertEqual(staged['counts'],{'records':4,'with_coordinates':0,'with_years':0,'fiction':0,'indexed':0})
        summary = self.review()
        self.assertEqual(summary['collections'],{'asia':4})
        self.assertEqual(summary['flags']['khmu_comparison_unverified'],2)
        self.assertEqual(summary['flags']['khmu_detail_unchecked'],1)
        self.assertEqual(summary['flags']['khmu_speaker_unknown'],1)
        self.assertEqual(summary['flags']['khmu_speaker_origin'],2)
        self.assertEqual(summary['flags']['khmu_recorded_in_france'],1)
        self.assertNotIn('khmu_snapshot_invalid',summary['flags'])
        self.assertNotIn('khmu_comparison_relation_changed',summary['flags'])
        with (self.output/'pangloss_khmu_review.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows = {row['馆藏编号']:row for row in csv.DictReader(stream)}
        self.assertEqual(len(rows),3)
        self.assertEqual(rows['0002048']['详情录音地点'],'Vientiane (recorded at the Mission Catholique)')
        self.assertEqual(rows['0002048']['目录讲述者'],'Thao May (from Xieng Khouang)')
        self.assertEqual(rows['0002048']['待核对照编号'],'0002049')
        self.assertTrue(rows['0002048']['详情页面SHA256'])
        self.assertEqual(rows['0001994']['详情状态'],'详情尚未采集')
        self.assertTrue(all(not row['坐标'] and not row['标准码'] for row in rows.values()))

    def test_changed_relation_and_comparison_snapshot_are_flagged(self):
        self.prepare()
        card = self.vault/'00_drafts/asia_sea_pangloss_khmu/case_sea_khmu_0002049.md'
        text = card.read_text(encoding='utf-8')
        self.assertIn('target: case_sea_khmu_0002048',text)
        card.write_text(text.replace('target: case_sea_khmu_0002048','target: case_sea_khmu_0001994'),encoding='utf-8')
        self.assertEqual(self.review()['flags']['khmu_comparison_relation_changed'],1)
        self.comparisons.write_bytes(self.comparisons.read_bytes()+b' ')
        self.assertEqual(self.review()['flags']['source_hash_mismatch'],4)

    def test_comparison_rejects_mismatched_source_fields(self):
        index = json.loads(self.comparisons.read_text(encoding='utf-8'))
        index['groups'][0]['members'][0]['recorded'] = '1968-12'
        self.comparisons.write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
        with self.assertRaises(IntakeError):
            load_comparisons(self.comparisons,self.corpus,self.catalog)

    def test_unidentified_speakers_and_recording_boundaries(self):
        self.assertTrue(speaker_identity_unverified('Unknown'))
        self.assertTrue(speaker_identity_unverified('Maria — unknown'))
        self.assertTrue(speaker_identity_unverified('A local erudite'))
        self.assertFalse(speaker_identity_unverified('Thao May (from Xieng Khouang)'))
        self.assertTrue(title_suggests_multiple_or_part('Histoires khamoues 30, 31 et 32'))
        self.assertTrue(title_suggests_multiple_or_part('Histoire de Sin Xay (Fin)'))
        self.assertFalse(title_suggests_multiple_or_part('Histoire du Clan du Tigre'))
        self.assertTrue(title_mentions_other_language('Divers chants khamous, nhuan et lao'))
        self.assertFalse(title_mentions_other_language('Histoire khamoue du clan du tigre'))

    def test_date_ranges_compare_only_unambiguous_endpoints(self):
        self.assertTrue(compare_recording_ranges('start=1971-08-14; end=1971-08-15','1971-08-14-1971-08-15'))
        self.assertFalse(compare_recording_ranges('start=1971-08-14; end=1971-08-15','1971-08-14-1971-08-16'))
        self.assertIsNone(compare_recording_ranges('start=1963;end=1966','1963end=1966'))
        self.assertIsNone(compare_recording_ranges('start=1971-08-15;end=1971-08-14','1971-08-14-1971-08-15'))

    def test_chuang_paper_is_linked_only_to_its_identified_recording(self):
        updated = (self.corpus.read_text(encoding='utf-8').replace('0001994','0001986')
                   .replace('Divers mythes de Clan et légendes','Histoire de Chuang aux pouvoirs magnifiques'))
        self.corpus.write_text(updated,encoding='utf-8')
        index = json.loads(self.comparisons.read_text(encoding='utf-8'))
        index['catalogue_sha256'] = sha256(self.corpus.read_bytes()).hexdigest()
        self.comparisons.write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
        self.prepare()
        summary = self.review()
        self.assertEqual(summary['flags']['khmu_chuang_research_reference'],1)
        with (self.output/'pangloss_khmu_review.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows = {row['馆藏编号']:row for row in csv.DictReader(stream)}
        self.assertEqual(rows['0001986']['相关研究链接'],'https://doi.org/10.4000/clo.7019')
        self.assertFalse(rows['0002048']['相关研究链接'])

    def prepare_supplement(self):
        self.prepare()
        card = self.vault/'00_drafts/asia_sea_pangloss_khmu/case_sea_khmu_0001994.md'
        card.write_text(card.read_text(encoding='utf-8')+'\n## 人工备注\n\n保留这条备注。\n',encoding='utf-8')
        selected = select_targets(self.vault,self.corpus,self.selection,'khmu',200)
        self.assertEqual(selected['groups'][0]['ids'],['0001994'])
        folder = self.root/'supplement'
        folder.mkdir()
        selection_path = folder/'selection.json'
        selection_path.write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
        page = self.root/'record-0001994.html'
        raw = detail('0001994',self.catalog['0001994']['title'],'01/01/1964',speaker='Unknown')
        page.write_text(raw.replace('Michaud, Alexis','Ferlus, Michel'),encoding='utf-8')
        seed = self.root/'supplement-seed.json'
        seed.write_text(json.dumps({'version':1,'records':[{'id':'0001994','path':page.name,
                         'sha256':sha256(page.read_bytes()).hexdigest()}]}),encoding='utf-8')
        with patch('pipeline.fetch_pangloss_na.robot_rules',return_value=(None,'404')):
            fetch(self.corpus,selection_path,folder,seed,corpus_name='Khmu',corpus_url=CORPUS_URL)
        return card,folder,selected

    def test_detail_supplement_preserves_notes_and_is_reviewable(self):
        card,folder,_ = self.prepare_supplement()
        original = card.read_bytes()
        planned = enrich(self.vault,self.corpus,self.selection,folder,'khmu',check=True)
        self.assertEqual(planned['cards_to_update'],1)
        self.assertEqual(card.read_bytes(),original)
        applied = enrich(self.vault,self.corpus,self.selection,folder,'khmu')
        self.assertEqual(applied['cards_to_update'],1)
        text = card.read_text(encoding='utf-8')
        self.assertIn('保留这条备注。',text)
        self.assertIn(MARKER,text)
        self.assertIn('首轮馆方录音目录字段（历史状态）',text)
        self.assertEqual(enrich(self.vault,self.corpus,self.selection,folder,'khmu')['already_enriched'],1)
        summary = self.review()
        self.assertNotIn('khmu_detail_unchecked',summary['flags'])
        self.assertEqual(summary['flags']['khmu_license_per_record'],3)
        self.assertNotIn('khmu_supplement_invalid',summary['flags'])
        with (self.output/'pangloss_khmu_review.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows = {row['馆藏编号']:row for row in csv.DictReader(stream)}
        self.assertEqual(rows['0001994']['后续详情补充'],'是')
        self.assertEqual(rows['0001994']['详情录音日期'],'01/01/1964')
        self.assertTrue(rows['0001994']['详情页面SHA256'])
        text = card.read_text(encoding='utf-8')
        self.assertIn('Chine, province du Yunnan, comté de Yongning',text)
        card.write_text(text.replace('Chine, province du Yunnan, comté de Yongning','手工改写录音地'),encoding='utf-8')
        self.assertEqual(self.review()['flags']['khmu_supplement_invalid'],1)
        card.write_text(text,encoding='utf-8')
        page = folder/'records/0001994/page.html'
        page.write_bytes(page.read_bytes()+b'changed')
        self.assertEqual(self.review()['flags']['source_hash_mismatch'],1)

    def test_changed_card_is_skipped_and_selection_is_bound(self):
        card,folder,selected = self.prepare_supplement()
        changed = card.read_text(encoding='utf-8')+'\n## 后续人工修改\n\n不得覆盖。\n'
        card.write_text(changed,encoding='utf-8')
        result = enrich(self.vault,self.corpus,self.selection,folder,'khmu')
        self.assertEqual(result['cards_to_update'],0)
        self.assertEqual(result['skipped'][0]['id'],'0001994')
        self.assertEqual(card.read_text(encoding='utf-8'),changed)
        selected['base_selection_sha256'] = '0'*64
        with self.assertRaises(IntakeError):
            validate_selection(selected,self.corpus,self.selection,'khmu')

    def test_corrupt_detail_stops_before_any_card_is_written(self):
        card,folder,_ = self.prepare_supplement()
        before = card.read_bytes()
        page = folder/'records/0001994/page.html'
        page.write_bytes(page.read_bytes()+b'changed')
        with self.assertRaises(IntakeError):
            enrich(self.vault,self.corpus,self.selection,folder,'khmu')
        self.assertEqual(card.read_bytes(),before)


if __name__ == '__main__':
    unittest.main()
