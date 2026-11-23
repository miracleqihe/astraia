from hashlib import sha256
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_inventory import FIELDS, MEMBER, SOURCE_URL, build_inventory, main


class KoreaAKSInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root/'catalogue.zip'
        self.receipt = self.root/'receipt.json'
        self.candidates = self.root/'candidates.json'
        self.rows = [
            {'서명':'호랑이 이야기', '구연자':'', '채록지':'충청북도', '유형':'설화', '텍스트':''},
            {'서명':'호랑이 이야기', '구연자':'', '채록지':'충청북도', '유형':'설화', '텍스트':''},
            {'서명':'16대 조상의 이야기(金)', '구연자':'박종철', '채록지':'영동', '유형':'설화', '텍스트':'tsu_0721'},
        ]
        self.write_fixture()

    def write_fixture(self):
        content = io.StringIO(newline='')
        writer = csv.DictWriter(content, fieldnames=FIELDS, lineterminator='\r\n')
        writer.writeheader()
        writer.writerows(self.rows)
        member = content.getvalue().encode('utf-8-sig')
        with ZipFile(self.archive,'w') as archive:
            archive.writestr(MEMBER,member)
        blob = self.archive.read_bytes()
        archive_hash, member_hash = sha256(blob).hexdigest(), sha256(member).hexdigest()
        self.receipt.write_text(json.dumps({'datasetId':'15070383','pageUrl':SOURCE_URL,
            'bytes':len(blob),'sha256':archive_hash}),encoding='utf-8')
        self.candidates.write_text(json.dumps({'version':1,'archive_sha256':archive_hash,'member_sha256':member_hash,
            'candidates':[{'row':3,'title':self.rows[2]['서명'],'speaker':'박종철','place':'영동',
                'source_url':'https://kdp.aks.ac.kr/inde/gubi?id=POKS.GUBI.GUBI.1_13','note':'仅供人工复核。'}]},
            ensure_ascii=False),encoding='utf-8')

    def test_review_inventory_preserves_rows_duplicates_and_unassigned_fields(self):
        data, summary = build_inventory(self.archive,self.receipt,self.candidates)
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline='')))
        self.assertEqual(len(rows),3)
        self.assertEqual([row['目录数据行序号'] for row in rows],['1','2','3'])
        self.assertEqual(rows[0]['目录题名'],'호랑이 이야기')
        self.assertEqual(rows[0]['字段完全相同的行数'],'2')
        self.assertIn('保留全部原始行',rows[1]['待核问题'])
        self.assertIn('未填讲述者',rows[0]['待核问题'])
        self.assertEqual(rows[2]['文本字段原值'],'tsu_0721')
        self.assertEqual(rows[2]['候选单条页面'],'https://kdp.aks.ac.kr/inde/gubi?id=POKS.GUBI.GUBI.1_13')
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核']=='待复核' for row in rows))
        self.assertEqual(summary['duplicate_groups'],1)
        self.assertEqual(summary['duplicate_rows_after_first'],1)
        self.assertEqual(summary['manual_candidates'],1)

    def test_snapshot_or_candidate_changes_are_rejected(self):
        candidate = json.loads(self.candidates.read_text(encoding='utf-8'))
        candidate['candidates'][0]['title'] = '不同题名'
        self.candidates.write_text(json.dumps(candidate,ensure_ascii=False),encoding='utf-8')
        with self.assertRaises(IntakeError):
            build_inventory(self.archive,self.receipt,self.candidates)
        self.write_fixture()
        with self.archive.open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaises(IntakeError):
            build_inventory(self.archive,self.receipt,self.candidates)

    def test_spreadsheet_formula_is_rejected_and_existing_output_is_preserved(self):
        self.rows[0]['서명'] = '=1+1'
        self.write_fixture()
        with self.assertRaises(IntakeError):
            build_inventory(self.archive,self.receipt,self.candidates)
        self.rows[0]['서명'] = '호랑이 이야기'
        self.write_fixture()
        output = self.root/'existing.csv'
        output.write_bytes(b'user content')
        argv = ['inventory','--archive',str(self.archive),'--receipt',str(self.receipt),
                '--candidates',str(self.candidates),'--output',str(output)]
        with patch('sys.argv',argv), patch('sys.stderr',new_callable=io.StringIO):
            self.assertEqual(main(),1)
        self.assertEqual(output.read_bytes(),b'user content')


if __name__ == '__main__':
    unittest.main()
