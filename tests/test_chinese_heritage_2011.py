import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.chinese_heritage_2011 import heritage_2011_cards, register_rows
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export


def register_html():
    header = '<tr>' + ''.join(f'<td>{x}</td>' for x in ('序号', '项目编号', '项目名称', '申报地区或单位')) + '</tr>'
    def row(index, code, title, area):
        return f'<tr><td>{index}</td><td>{code}</td><td>{title}</td><td>{area}</td></tr>'
    primary = ''.join(row(1029 + i, f'I-{85 + i}', '天坛传说' if i == 0 else
                          '谚语（沪谚）' if i == 40 else f'民间文学项目{i}', '北京市东城区') for i in range(41))
    ext_indexes = (1, 8, 9, 522, 523, 528, 537, 561)
    ext_codes = (1, 8, 9, 35, 36, 41, 50, 74)
    extension = ''.join(row(index, f'I-{code}', '苗族古歌' if i == 0 else
                            '司岗里' if i == 7 else f'扩展项目{i}', '湖南省花垣县')
                        for i, (index, code) in enumerate(zip(ext_indexes, ext_codes, strict=True)))
    return ('<html><body><div class="gsj_htmlcon_bot">第三批国家级非物质文化遗产名录'
            '<p>一、民间文学（共计 41 项）</p><table>' + header + primary + '</table>'
            '<p>国家级非物质文化遗产名录扩展项目名录 一、民间文学（共计8项）</p>'
            '<table>' + header + extension + '</table></div></body></html>').encode('utf-8')


class ChineseHeritage2011Tests(unittest.TestCase):
    def test_parser_rejects_missing_rows_and_invalid_sequences(self):
        self.assertEqual(len(register_rows(register_html())), 49)
        for raw in (register_html().replace(b'I-86', b'I-87', 1),
                    register_html().replace(b'<td>1030</td>', b'<td>1035</td>', 1)):
            with self.assertRaises(IntakeError):
                register_rows(raw)

    def test_review_distinguishes_expansion_and_rechecks_hash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'register.html'
            source.write_bytes(register_html())
            vault = root / 'vault'
            vault.mkdir()
            table = root / 'standards.json'
            table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
            manifest = stage_batch(vault, 'asia_chinese_heritage_2011', heritage_2011_cards(source), table, {})
            self.assertEqual(manifest['counts']['records'], 49)
            self.assertEqual(manifest['counts']['with_coordinates'], 0)
            self.assertEqual(manifest['counts']['indexed'], 0)
            absent, output = root / 'absent', root / 'review'
            def review():
                return export(vault, output, absent, absent, absent, absent, absent, table, absent)
            summary = review()
            self.assertEqual(summary['flags']['heritage_2011_extension'], 8)
            self.assertEqual(summary['flags']['heritage_2011_project_scope'], 49)
            self.assertNotIn('heritage_2011_fields_changed', summary['flags'])
            with (output / 'chinese_heritage_2011_review.csv').open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 49)
            self.assertEqual(sum(row['名录类别'] == '扩展项目' for row in rows), 8)
            self.assertTrue(all(not row['坐标'] and not row['国际标准码'] for row in rows))
            ext = next(row for row in rows if row['卡片ID'] == 'corpus_cn_ich_2011_ext_0001')
            self.assertEqual((ext['项目名称'], ext['项目编号（非母题标准码）']), ('苗族古歌', 'I-1'))
            source.write_bytes(source.read_bytes() + b'changed')
            self.assertGreaterEqual(review()['flags']['source_hash_mismatch'], 1)


if __name__ == '__main__':
    unittest.main()
