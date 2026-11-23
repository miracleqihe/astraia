import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_crosswalk import crosswalk
from pipeline.korea_aks_detail import FIELDS, fetch, parse_detail
from tests.test_korea_aks_crosswalk import source
from tests.test_korea_aks_search import FakeResponse


def detail_html():
    values={'제목':'사신을 물리친 김시습','자료분류':'설화','조사자':'연구자',
            '조사장소':'서울시 도봉구 미아1동','조사일시':'1979.03.17','제보자':'안병초','조사지역':'서울'}
    fields=''.join(f'<dt>{key}</dt><dd>{values[key]}</dd>' for key in FIELDS)
    return ('<html><head><title>한국 구비문학 대계 [한국학자료통합플랫폼]</title></head><body>'
            f'<dl>{fields}</dl><p>TRANSCRIPTION MUST NOT BE STORED</p></body></html>').encode('utf-8')


class KoreaAKSDetailTests(unittest.TestCase):
    def test_extracts_only_metadata_and_rejects_changed_structure(self):
        fields=parse_detail(detail_html())
        self.assertEqual(fields['제목'],'사신을 물리친 김시습')
        self.assertEqual(fields['조사장소'],'서울시 도봉구 미아1동')
        self.assertNotIn('TRANSCRIPTION',str(fields))
        with self.assertRaises(IntakeError):parse_detail(detail_html().replace('조사지역'.encode(),'다른필드'.encode()))

    def test_resumes_only_with_matching_index_receipt_and_preserves_edits(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            archive,receipt,search,crosswalk_path,output=(root/name for name in ('archive.zip','receipt.json','search','crosswalk.csv','details'))
            row={'서명':'사신을 물리친 소년 김시습','구연자':'안병초','채록지':'서울시-도봉구-미아1동',
                 '유형':'설화','텍스트':'tsu_0006'}
            sources=[source('POKS.GUBI.GUBI.1_10117','사신을 물리친 김시습')]
            csv_data,_=crosswalk([row],sources,'c'*64,'d'*64)
            crosswalk_path.write_bytes(csv_data)
            rules=type('Rules',(),{'can_fetch':lambda self,*args:True})()
            def open_page(request,timeout):return FakeResponse(request.full_url,detail_html())
            with patch('pipeline.korea_aks_detail.load_catalogue',return_value=([row],'c'*64,'d'*64)),\
                 patch('pipeline.korea_aks_detail.load_search',return_value=(sources,'e'*64)),\
                 patch('pipeline.korea_aks_detail._read_robots',return_value=(rules,'f'*64)),\
                 patch('pipeline.korea_aks_detail.urlopen',side_effect=open_page) as network,\
                 patch('pipeline.korea_aks_detail.time.sleep'),patch('sys.stdout',new_callable=io.StringIO):
                first=fetch(archive,receipt,search,crosswalk_path,output,delay=3)
                self.assertEqual(len(first['records']),1)
                self.assertEqual(fetch(archive,receipt,search,crosswalk_path,output,delay=3),first)
                self.assertEqual(network.call_count,1)
                record=output/'records/POKS.GUBI.GUBI.1_10117.json'
                before=record.read_bytes()
                self.assertNotIn(b'TRANSCRIPTION',before)
                record.write_bytes(before+b' ')
                with self.assertRaises(IntakeError):fetch(archive,receipt,search,crosswalk_path,output,delay=3)
                self.assertEqual(record.read_bytes(),before+b' ')


if __name__=='__main__':
    unittest.main()
