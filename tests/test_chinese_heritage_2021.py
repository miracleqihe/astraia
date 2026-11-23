import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.chinese_heritage import heritage_cards as cards_2006
from pipeline.chinese_heritage_2011 import heritage_2011_cards
from pipeline.chinese_heritage_2021 import (EXPECTED_EXTENSIONS, PDF_URL, heritage_2021_cards,
                                            load_index, parse_page)
from pipeline.chinese_heritage_batches import heritage_cards
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from tests.test_chinese_heritage import fixture as fixture_2006
from tests.test_chinese_heritage_2011 import register_html as fixture_2011
from tests.test_chinese_heritage_batches import register_html as fixture_batch


def page_text(page):
    full = str.maketrans('0123456789', '０１２３４５６７８９')
    def line(index, number, title):
        return f'{str(index).translate(full)} Ⅰ－{str(number).translate(full)} {title} 申报地区{index}'
    if page == 24:
        title = '第五批国家级非物质文化遗产代表性项目名录'
        rows = [line(1373+i, 156+i, '八大处传说' if i == 0 else '都玛简收' if i == 11 else f'新增名称{i}') for i in range(12)]
    else:
        title = '国家级非物质文化遗产代表性项目名录扩展项目名录'
        def number(index):
            return index if index <= 31 else index - 487 if index <= 571 else index - 944
        rows = [line(index, number(index), f'扩展名称{index}') for index in EXPECTED_EXTENSIONS]
    return title + f'\n一、民间文学(共计{len(rows)}项)\n' + '\n'.join(rows) + '\n二、传统音乐'


def make_index(pdf, index):
    data = {'version': 1, 'source_url': PDF_URL, 'pdf_sha256': sha256(pdf.read_bytes()).hexdigest(),
            'pdf_pages': 77, 'observed_at': '2026-11-22T00:00:00+00:00', 'pdfium_version': 'test',
            'extraction_checks': [{'pdf_page': page, 'printed_page': page-1, 'rows': count,
                 'pdfium_text_sha256': '0'*64, 'poppler_text_sha256': '1'*64} for page,count in ((24,12),(33,9))],
            'records': parse_page(page_text(24), page_text(24), 24) + parse_page(page_text(33), page_text(33), 33)}
    index.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


class ChineseHeritage2021Tests(unittest.TestCase):
    def test_two_extractions_must_agree_and_sequence_must_be_complete(self):
        self.assertEqual(len(parse_page(page_text(24), page_text(24), 24)), 12)
        self.assertEqual(len(parse_page(page_text(33), page_text(33), 33)), 9)
        with self.assertRaises(IntakeError):
            parse_page(page_text(24), page_text(24).replace('八大处传说', '不同名称'), 24)
        with self.assertRaises(IntakeError):
            parse_page(page_text(24).replace('１３７４', '１３７５', 1), page_text(24), 24)

    def test_pdf_index_and_review_require_both_hashes(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); vault=root/'vault'; vault.mkdir()
            table=root/'standards.json'; table.write_text(json.dumps({'version':1,'entries':[],'editions':[]}),encoding='utf-8')
            for year,raw in ((2006,fixture_2006()),(2008,fixture_batch(2008)),(2011,fixture_2011())):
                path=root/f'{year}.html';path.write_bytes(raw)
                cards=cards_2006(path) if year==2006 else heritage_2011_cards(path) if year==2011 else heritage_cards(path,year)
                stage_batch(vault,f'asia_chinese_heritage_{year}',cards,table,{})
            pdf=root/'gazette.pdf'; pdf.write_bytes(b'%PDF-1.4\nsynthetic test file')
            index=root/'index.json'; make_index(pdf,index)
            self.assertEqual(len(load_index(pdf,index)['records']),21)
            manifest=stage_batch(vault,'asia_chinese_heritage_2021',heritage_2021_cards(pdf,index),table,{})
            self.assertEqual(manifest['counts']['records'],21)
            self.assertEqual(manifest['counts']['with_coordinates'],0)
            self.assertEqual(manifest['counts']['indexed'],0)
            output,absent=root/'review',root/'absent'
            def review(): return export(vault,output,absent,absent,absent,absent,absent,table,absent)
            summary=review()
            self.assertEqual(summary['flags']['heritage_2021_extension'],9)
            self.assertNotIn('heritage_2021_fields_changed',summary['flags'])
            with (output/'chinese_heritage_2021_review.csv').open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),21)
            self.assertTrue(all(not row['坐标'] and not row['国际标准码'] for row in rows))
            self.assertTrue(all(row['原始公报链接'].endswith('#page=24') for row in rows if row['名录类别']=='新增项目'))
            self.assertTrue(all(row['原始公报链接'].endswith('#page=33') for row in rows if row['名录类别']=='扩展项目'))
            index.write_text(index.read_text(encoding='utf-8')+' ',encoding='utf-8')
            self.assertGreaterEqual(review()['flags']['source_hash_mismatch'],1)


if __name__ == '__main__':
    unittest.main()
