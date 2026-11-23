import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.chinese_heritage import heritage_cards as heritage_2006_cards
from pipeline.chinese_heritage_2011 import heritage_2011_cards
from pipeline.chinese_heritage_batches import CONFIG, base_identity, heritage_cards, register_rows
from pipeline.import_datasets import stage_batch
from pipeline.enrich_chinese_heritage_links import enrich
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from pipeline.vault import parse_card
from tests.test_chinese_heritage import fixture as fixture_2006
from tests.test_chinese_heritage_2011 import register_html as fixture_2011


def register_html(year):
    spec = CONFIG[year]
    header = '<tr>' + ''.join(f'<td>{x}</td>' for x in ('序号', spec['header'], '项目名称', '申报地区或单位')) + '</tr>'
    def row(index, number, title, area):
        return f'<tr><td>{index}</td><td>Ⅰ -{number}</td><td>{title}</td><td>{area}</td></tr>'
    primary = ''.join(row(spec['first_index'] + i, spec['first_number'] + i,
                          spec['first_title'] if i == 0 else spec['last_title'] if i == spec['count'] - 1 else
                          '徐福东渡传说' if year == 2008 and spec['first_index'] + i == 528 else f'项目{i}',
                          '申报地区甲') for i in range(spec['count']))
    def number(index):
        return index if index <= 31 else index - 487 if index <= 571 else index - 944
    extension = ''.join(row(index, number(index), '孟姜女传说' if index == 8 else f'扩展项目{index}', '申报地区乙')
                        for index in spec['extensions'])
    return (f'<html><body>{spec["heading"]}<p>一、民间文学（共计{spec["count"]}项）</p>'
            f'<table>{header}{primary}</table><p>扩展项目名录 一、民间文学（共计{spec["extension_count"]}项）</p>'
            f'<table>{header}{extension}</table></body></html>').encode('utf-8')


class ChineseHeritageBatchesTests(unittest.TestCase):
    def test_parser_validates_counts_project_pairs_and_merged_cells(self):
        for year, count in ((2008, 58), (2014, 37)):
            raw = register_html(year)
            rows = register_rows(raw, year)
            self.assertEqual(len(rows), count)
            self.assertEqual(rows[0]['project_number'], f'Ⅰ -{CONFIG[year]["first_number"]}')
            broken = raw.replace('Ⅰ -8'.encode(), 'Ⅰ -9'.encode(), 1)
            with self.assertRaises(IntakeError):
                register_rows(broken, year)
            broken = raw.replace('<td>8</td>'.encode(), '<td rowspan="2">8</td>'.encode(), 1)
            with self.assertRaises(IntakeError):
                register_rows(broken, year)
        self.assertEqual(base_identity(528, 41), 'corpus_cn_ich_2008_0528')
        with self.assertRaises(IntakeError):
            base_identity(528, 42)

    def test_cross_year_records_keep_original_text_and_independent_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / 'vault'
            vault.mkdir()
            table = root / 'standards.json'
            table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
            for year, raw in ((2006, fixture_2006()), (2011, fixture_2011()),
                              (2008, register_html(2008)), (2014, register_html(2014))):
                path = root / f'{year}.html'
                path.write_bytes(raw)
                cards = heritage_2006_cards(path) if year == 2006 else heritage_2011_cards(path) if year == 2011 else heritage_cards(path, year)
                manifest = stage_batch(vault, f'asia_chinese_heritage_{year}', cards, table, {})
                self.assertEqual(manifest['counts']['with_coordinates'], 0)
                self.assertEqual(manifest['counts']['indexed'], 0)
            edited = vault / '00_drafts/asia_chinese_heritage_2011/corpus_cn_ich_2011_ext_0528.md'
            edited.write_text(edited.read_text(encoding='utf-8') + '\n人工补充：保留此行。\n', encoding='utf-8')
            preview = enrich(vault, check=True)
            self.assertEqual((len(preview['to_update']), preview['skipped']), (8, []))
            result = enrich(vault)
            self.assertEqual((len(result['updated']), result['skipped']), (8, []))
            metadata, body = parse_card(edited.read_text(encoding='utf-8'))
            self.assertIn('人工补充：保留此行。', body)
            self.assertTrue(any(rel.type == 'COMPARED_WITH' and rel.target == 'corpus_cn_ich_2008_0528' for rel in metadata.relations))
            self.assertEqual(len(enrich(vault)['already_linked']), 8)
            absent, output = root / 'absent', root / 'review'
            def review():
                return export(vault, output, absent, absent, absent, absent, absent, table, absent)
            summary = review()
            self.assertEqual(summary['records'], 175)
            self.assertEqual(summary['flags']['heritage_batch_extension'], 12)
            self.assertNotIn('heritage_batch_fields_changed', summary['flags'])
            self.assertNotIn('heritage_2006_fields_changed', summary['flags'])
            script = (output / 'data.js').read_text(encoding='utf-8')
            records = json.loads(script.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])['records']
            by_id = {item['id']: item for item in records}
            ext = by_id['corpus_cn_ich_2014_ext_0008']
            targets = {other['id'] for other in ext['evidence']['heritage_comparisons']}
            self.assertEqual(targets, {'corpus_cn_ich_2006_08', 'corpus_cn_ich_2008_ext_0008', 'corpus_cn_ich_2011_ext_0008'})
            self.assertEqual(ext['dependencies'], ['corpus_cn_ich_2006_08'])
            self.assertTrue(any(flag['code'] == 'heritage_cross_year_title_variant' for flag in ext['issues']))
            with (output / 'chinese_heritage_2008_2014_review.csv').open(encoding='utf-8-sig', newline='') as f:
                batch = list(csv.DictReader(f))
            self.assertEqual(len(batch), 95)
            self.assertTrue(all(not row['坐标'] and not row['国际标准码'] for row in batch))
            with (output / 'chinese_heritage_cross_year_review.csv').open(encoding='utf-8-sig', newline='') as f:
                pairs = list(csv.DictReader(f))
            self.assertTrue(any(row['卡片A'] == 'corpus_cn_ich_2008_0528' and row['卡片B'] == 'corpus_cn_ich_2011_ext_0528'
                                and row['A名称'] == '徐福东渡传说' for row in pairs))
            self.assertTrue(all(row['A原表SHA256'] and row['B原表SHA256'] for row in pairs))
            original = vault / '00_drafts/asia_chinese_heritage_2006/corpus_cn_ich_2006_08.md'
            approved = vault / '02_myth_corpora/corpus_cn_ich_2006_08.md'
            approved.parent.mkdir()
            approved.write_text(original.read_text(encoding='utf-8').replace('genre: unclassified', 'genre: academic_model')
                                .replace('reviewed_by_human: false', 'reviewed_by_human: true'), encoding='utf-8')
            original.unlink()
            self.assertEqual(review()['records'],174)
            script = (output / 'data.js').read_text(encoding='utf-8')
            records = json.loads(script.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])['records']
            ext = next(item for item in records if item['id'] == 'corpus_cn_ich_2014_ext_0008')
            original_match = next(x for x in ext['evidence']['heritage_comparisons'] if x['id'] == 'corpus_cn_ich_2006_08')
            self.assertEqual(original_match['availability'], 'reviewed')
            with (output / 'chinese_heritage_cross_year_review.csv').open(encoding='utf-8-sig', newline='') as f:
                pairs = list(csv.DictReader(f))
            self.assertTrue(any(row['卡片A'] == 'corpus_cn_ich_2014_ext_0008' and row['卡片B'] == 'corpus_cn_ich_2006_08'
                                and row['B状态'] == '已复核入图' for row in pairs))
            old = root / '2008.html'
            old.write_bytes(old.read_bytes() + b'changed')
            changed = review()
            self.assertGreaterEqual(changed['flags']['source_hash_mismatch'], 1)
            script = (output / 'data.js').read_text(encoding='utf-8')
            records = json.loads(script.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])['records']
            ext = next(item for item in records if item['id'] == 'corpus_cn_ich_2014_ext_0008')
            self.assertNotIn('corpus_cn_ich_2008_ext_0008', {x['id'] for x in ext['evidence']['heritage_comparisons']})
            original_source = root / '2006.html'
            original_source.write_bytes(original_source.read_bytes() + b'changed')
            self.assertGreaterEqual(review()['flags']['heritage_reviewed_target_invalid'],1)


if __name__ == '__main__':
    unittest.main()
