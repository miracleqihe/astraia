import csv
from hashlib import sha256
import html
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_na import CORPUS_URL, DOI_BASE
from pipeline import pangloss_na_catalogue as candidates
from pipeline.review_queue import export
from tests.test_pangloss_na import catalogue


class PanglossNaCatalogueTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.corpus = self.root / 'corpus.html'
        added = []
        for number, title in [('0004532', 'Les aînés (version 3)'), ('0004593', 'Daba: the priest'),
                              ('0012001', 'Vocabulaire : première enquête de vocabulaire. Document 1')]:
            safe = html.escape(title, quote=True)
            url = 'https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-3dd9341b-647a-33d3-b0fd-2b0ab0e7f638&amp;corpus=Yongning Na'
            added.append(f'<tr data-corpus="Yongning Na"><td><button data-doi="{DOI_BASE}{number}" data-title="{safe}"></button></td>'
                         f'<td><svg name="audio"></svg></td><td></td><td>00:05:12</td><td><a href="{url}"></a>{safe}</td>'
                         '<td>Researcher</td><td>讲述者</td><td>2009</td></tr>')
        self.corpus.write_text(catalogue().replace('</table>', ''.join(added) + '</table>'), encoding='utf-8')
        self.first, self.context = self.root / 'first.json', self.root / 'context.json'
        self.first.write_text(json.dumps({'version': 1, 'corpus_url': CORPUS_URL, 'selection_method': '首轮', 'limits': '非随机',
            'groups': [{'id': 'first', 'label': '首轮', 'ids': ['0004341']}]}, ensure_ascii=False), encoding='utf-8')
        self.context.write_text(json.dumps({'version': 1, 'corpus_url': CORPUS_URL, 'selection_method': '补充', 'limits': '非随机',
            'catalogue_sha256': sha256(self.corpus.read_bytes()).hexdigest(),
            'previous_selection_sha256': sha256(self.first.read_bytes()).hexdigest(),
            'selected_titles': {'0004487': 'Sister wedding: another speaker'},
            'groups': [{'id': 'context_0004487', 'label': '口述背景', 'ids': ['0004487']}]}, ensure_ascii=False), encoding='utf-8')
        pick_patch = patch.object(candidates, 'PICKS', [('0004532', '版本候选', '0004341'), ('0004593', '仪式背景', None)])
        pick_patch.start()
        self.addCleanup(pick_patch.stop)
        self.selection = self.root / 'selection.json'
        self.selection.write_text(json.dumps(candidates.build_selection(self.corpus, self.first, self.context), ensure_ascii=False), encoding='utf-8')
        self.absent, self.output = self.root / 'absent', self.root / 'review'

    def stage(self):
        return stage_batch(self.vault, 'asia_cn_pangloss_na_catalogue',
            candidates.cards(self.corpus, self.first, self.context, self.selection), self.table, {})

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_catalogue_candidates_and_full_inventory_stay_distinct(self):
        result = self.stage()
        self.assertEqual(result['counts'], {'records': 2, 'with_coordinates': 0, 'with_years': 0, 'fiction': 0, 'indexed': 0})
        summary = self.review()
        self.assertEqual(summary['flags']['na_candidate_detail_missing'], 2)
        self.assertEqual(summary['flags']['na_candidate_not_story'], 2)
        self.assertNotIn('na_candidate_fields_changed', summary['flags'])
        self.assertNotIn('na_candidate_index_invalid', summary['flags'])
        self.assertNotIn('pangloss_source_missing', summary['flags'])
        raw = (self.output / 'data.js').read_text(encoding='utf-8')
        document = json.loads(raw.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])
        record = next(item for item in document['records'] if item['id'] == 'case_cn_yongning_na_0004532')
        self.assertIsNone(record['spatial']['lat'])
        self.assertFalse(any(record['standards'].values()))
        self.assertEqual(record['evidence']['na_catalogue_candidate']['候选对照录音号'], '0004341')
        with (self.output / 'pangloss_yongning_na_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            inventory = {row['馆藏编号']: row for row in csv.DictReader(stream)}
        self.assertEqual(len(inventory), 5)
        self.assertEqual(inventory['0004532']['筛查状态'], '本轮候选，已有待审卡')
        self.assertEqual(inventory['0004341']['筛查状态'], '此前选取的卡片缺失')
        self.assertEqual(inventory['0012001']['筛查状态'], '未选入，未逐条筛查')
        self.assertEqual(inventory['0012001']['题名提示'], '题名为词汇调查')
        self.assertEqual(inventory['0012001']['人工复核'], '未建卡')
        with (self.output / 'pangloss_yongning_na_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])
        with self.assertRaisesRegex(IntakeError, '已存在卡片'):
            stage_batch(self.vault, 'another_batch', candidates.cards(self.corpus, self.first, self.context, self.selection), self.table, {})

    def test_changed_selection_or_source_fails_closed(self):
        document = json.loads(self.selection.read_text(encoding='utf-8'))
        document['choices'][0]['title'] = 'Changed'
        self.selection.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(IntakeError):
            candidates.validate_selection(self.corpus, self.first, self.context, self.selection)
        self.selection.write_text(json.dumps(candidates.build_selection(self.corpus, self.first, self.context), ensure_ascii=False), encoding='utf-8')
        self.stage()
        self.corpus.write_bytes(self.corpus.read_bytes() + b' ')
        summary = self.review()
        self.assertEqual(summary['flags']['source_hash_mismatch'], 2)
        with (self.output / 'pangloss_yongning_na_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])

    def test_changed_relation_is_flagged(self):
        self.stage()
        card = self.vault / '00_drafts/asia_cn_pangloss_na_catalogue/case_cn_yongning_na_0004532.md'
        text = card.read_text(encoding='utf-8')
        old, new = 'target: case_cn_yongning_na_0004341', 'target: case_cn_yongning_na_0004593'
        self.assertIn(old, text)
        card.write_text(text.replace(old, new), encoding='utf-8')
        self.assertEqual(self.review()['flags']['na_candidate_relation_changed'], 1)


if __name__ == '__main__':
    unittest.main()
