import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_crosswalk import crosswalk
from pipeline.korea_aks_detail import fetch
from pipeline.korea_aks_reconcile import compare_places, load_details, reconcile
from tests.test_korea_aks_crosswalk import source
from tests.test_korea_aks_detail import detail_html
from tests.test_korea_aks_search import FakeResponse


class KoreaAKSReconcileTests(unittest.TestCase):
    def test_recording_places_preserve_mismatch_and_ambiguity(self):
        self.assertTrue(compare_places('서울시-도봉구-도봉구 미아1동','서울특별시 도봉구 미아1동'))
        self.assertFalse(compare_places('서울시-도봉구-미아1동','서울시 도봉구 수유3동'))
        self.assertIsNone(compare_places('서울시-도봉구-','서울시 도봉구 미아1동'))
        self.assertIsNone(compare_places('','서울시 도봉구 미아1동'))

    def test_metadata_differences_are_flags_not_signoffs(self):
        row={'서명':'사신을 물리친 소년 김시습','구연자':'안병초','채록지':'서울시-도봉구-미아1동',
             '유형':'설화','텍스트':'tsu_0006'}
        missing={'서명':'다른 이야기','구연자':'안병초','채록지':'서울시-도봉구-','유형':'설화','텍스트':''}
        sources=[source('POKS.GUBI.GUBI.1_10117','사신을 물리친 김시습')]
        base,_=crosswalk([row,missing],sources,'c'*64,'d'*64)
        metadata={'제목':'사신을 물리친 김시습','자료분류':'설화','조사자':'연구자',
                  '조사장소':'서울시 도봉구 수유3동','조사일시':'1979.03.17','제보자':'다른 사람','조사지역':'서울'}
        details={'POKS.GUBI.GUBI.1_10117':{'fields':metadata,'index_sha256':'e'*64,'response_sha256':'f'*64}}
        result,summary=reconcile(base,details)
        rows=list(csv.DictReader(io.StringIO(result.decode('utf-8-sig'),newline='')))
        self.assertEqual(summary['place_different_pairs'],1)
        self.assertEqual(summary['listing_detail_disagreement_pairs'],1)
        self.assertEqual(rows[0]['目录与详情采录地点'],'不同')
        self.assertEqual(rows[0]['检索与详情讲述者'],'不同')
        self.assertIn('馆方检索与详情字段不一致',rows[0]['待核问题'])
        self.assertEqual(rows[0]['人工复核'],'待复核')
        self.assertFalse(rows[0]['坐标'] or rows[0]['标准码'])
        self.assertEqual(summary['unmatched_rows'],1)
        with self.assertRaises(IntakeError):reconcile(base,{})

    def test_detail_manifest_and_receipts_bind_index_content(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            archive,receipt,search,base_path,folder=(root/name for name in ('archive','receipt','search','base.csv','details'))
            row={'서명':'사신을 물리친 소년 김시습','구연자':'안병초','채록지':'서울시-도봉구-미아1동',
                 '유형':'설화','텍스트':'tsu_0006'}
            sources=[source('POKS.GUBI.GUBI.1_10117','사신을 물리친 김시습')]
            base,_=crosswalk([row],sources,'c'*64,'d'*64)
            base_path.write_bytes(base)
            rules=type('Rules',(),{'can_fetch':lambda self,*args:True})()
            def open_page(request,timeout):return FakeResponse(request.full_url,detail_html())
            with patch('pipeline.korea_aks_detail.load_catalogue',return_value=([row],'c'*64,'d'*64)),\
                 patch('pipeline.korea_aks_detail.load_search',return_value=(sources,'e'*64)),\
                 patch('pipeline.korea_aks_detail._read_robots',return_value=(rules,'f'*64)),\
                 patch('pipeline.korea_aks_detail.urlopen',side_effect=open_page),\
                 patch('pipeline.korea_aks_detail.time.sleep'),patch('sys.stdout',new_callable=io.StringIO):
                fetch(archive,receipt,search,base_path,folder,delay=3)
            details,_=load_details(folder,sources,base,'c'*64,'d'*64,'e'*64)
            self.assertEqual(len(details),1)
            path=folder/'records/POKS.GUBI.GUBI.1_10117.json'
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(IntakeError):load_details(folder,sources,base,'c'*64,'d'*64,'e'*64)


if __name__=='__main__':unittest.main()
