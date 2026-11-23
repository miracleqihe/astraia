import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_crosswalk import crosswalk, in_dobong, load_search
from pipeline.korea_aks_search import BASE, fetch
from tests.test_korea_aks_search import FakeResponse, html_page


def source(identifier,title,speaker='안병초',genre='설화'):
    return {'id':identifier,'title':title,'candidate_url':BASE+'/inde/gubi?id='+identifier,
            'fields':{'사업구분':'한국구비문학대계(1차)','조사지역':'도봉구','자료구분':genre,
                      '채록시도':'서울','조사일시':'1979.03.17','조사자':'연구자','제보자':speaker},
            'search_url':BASE+'/inde/search?itemId=14&pageIndex=1&pageUnit=20',
            'page_sha256':'a'*64,'response_sha256':'b'*64}


class KoreaAKSCrosswalkTests(unittest.TestCase):
    def test_candidates_are_uncertain_and_ambiguous_rows_are_retained(self):
        first={'서명':'사신을 물리친 소년 김시습','구연자':'안병초','채록지':'서울시-도봉구-미아1동',
               '유형':'설화','텍스트':'tsu_0006'}
        second={'서명':'다른 이야기','구연자':'안병초','채록지':'서울시-도봉구-미아1동',
                '유형':'설화','텍스트':''}
        outside={'서명':first['서명'],'구연자':'안병초','채록지':'서울시-종로구-미아1동',
                 '유형':'설화','텍스트':'tsu_0006'}
        catalogue=[first,dict(first),second,outside]
        sources=[source('POKS.GUBI.GUBI.1_10117','사신을 물리친 김시습')]
        data,summary=crosswalk(catalogue,sources,'c'*64,'d'*64)
        records=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline='')))
        self.assertEqual(summary['scoped_catalogue_rows'],3)
        self.assertEqual(summary['catalogue_rows_with_candidates'],2)
        self.assertEqual(summary['source_records_with_multiple_catalogue_candidates'],1)
        self.assertEqual(summary['catalogue_rows_without_candidates'],1)
        self.assertEqual(records[0]['题名对照方式'],'相似待核')
        self.assertEqual(records[0]['单条详情状态'],'尚未回查')
        self.assertIn('多个目录候选',records[0]['待核问题'])
        self.assertIn('两处题名原字段不同',records[0]['待核问题'])
        self.assertFalse(records[2]['候选单条页面'])
        self.assertIn('不代表不存在',records[2]['待核问题'])
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核']=='待复核' for row in records))

    def test_region_and_speaker_are_required_and_formulas_are_rejected(self):
        self.assertTrue(in_dobong('서울특별시-도봉구-지역'))
        self.assertFalse(in_dobong('경기도-도봉구-지역'))
        row={'서명':'같은 이야기','구연자':'다른 사람','채록지':'서울시-도봉구-지역','유형':'설화','텍스트':''}
        _,summary=crosswalk([row],[source('POKS.GUBI.GUBI.1_3','같은 이야기')],'c'*64,'d'*64)
        self.assertEqual(summary['candidate_pairs'],0)
        row['서명']='=1+1'
        with self.assertRaises(IntakeError):crosswalk([row],[],'c'*64,'d'*64)

    def test_search_snapshot_is_bound_to_receipts_and_manifest(self):
        with TemporaryDirectory() as temp:
            folder=Path(temp)/'capture'
            rules=type('Rules',(),{'can_fetch':lambda self,*args:True})()
            def open_page(request,timeout):return FakeResponse(request.full_url,html_page(1,2))
            with patch('pipeline.korea_aks_search._read_robots',return_value=(rules,'a'*64)),\
                 patch('pipeline.korea_aks_search.urlopen',side_effect=open_page),\
                 patch('pipeline.korea_aks_search.time.sleep'),\
                 patch('sys.stdout',new_callable=io.StringIO):
                fetch(folder,expected_total=2,delay=3)
            records,_=load_search(folder)
            self.assertEqual(len(records),2)
            path=folder/'page-01.json'
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(IntakeError):load_search(folder)


if __name__=='__main__':
    unittest.main()
