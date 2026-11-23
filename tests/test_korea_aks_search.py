import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_search import BASE, FIELDS, fetch, parse_page, search_url


def html_page(page, total):
    start=(page-1)*20
    count=min(20,max(0,total-start))
    items=[]
    for index in range(start+1,start+count+1):
        fields={'사업구분':'한국구비문학대계(1차)','조사지역':'도봉구','자료구분':'설화',
                '채록시도':'서울','조사일시':'1979.07.03','조사자':'연구자','제보자':'김장수'}
        meta=' '.join(f'<span class="meta-label">{key}</span> {fields[key]}' for key in FIELDS)
        items.append(f"<li><h4><a href=\"javascript:goIndeData('14','지역별','서울시','도봉구','','POKS.GUBI.GUBI.1_{index}')\">"
                     f'이야기 {index}</a></h4><p>TRANSCRIPTION MUST NOT BE STORED</p><div>{meta}</div></li>')
    return ('<html><head><title>한국 구비문학 대계 [한국학자료통합플랫폼]</title></head>'
            f'<body>총 {total}개의 검색 결과가 있습니다.<ul>'+''.join(items)+'</ul></body></html>').encode('utf-8')


class FakeResponse:
    def __init__(self,url,content):
        self.url,self.content,self.status=url,content,200
        self.headers=type('Headers',(),{'get_content_type':lambda self:'text/html'})()
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,*args): return self.content


class KoreaAKSSearchTests(unittest.TestCase):
    def test_search_fields_are_extracted_without_transcriptions(self):
        total,records=parse_page(html_page(1,2),1)
        self.assertEqual(total,2)
        self.assertEqual(len(records),2)
        self.assertEqual(records[0]['fields']['제보자'],'김장수')
        self.assertEqual(records[0]['candidate_url'],BASE+'/inde/gubi?id=POKS.GUBI.GUBI.1_1')
        self.assertNotIn('TRANSCRIPTION',json.dumps(records,ensure_ascii=False))

    def test_rejects_changed_region_or_pagination(self):
        with self.assertRaises(IntakeError):
            parse_page(html_page(1,2).replace('도봉구'.encode(), '종로구'.encode()),1)
        with self.assertRaises(IntakeError):
            parse_page(html_page(1,2),2)

    def test_resume_verifies_page_receipts_and_never_overwrites(self):
        with TemporaryDirectory() as temp:
            output=Path(temp)/'capture'
            rules=type('Rules',(),{'can_fetch':lambda self,*args:True})()
            def open_page(request,timeout):
                page=int(request.full_url.split('pageIndex=')[1].split('&')[0])
                return FakeResponse(request.full_url,html_page(page,21))
            with patch('pipeline.korea_aks_search._read_robots',return_value=(rules,'a'*64)),\
                 patch('pipeline.korea_aks_search.urlopen',side_effect=open_page),\
                 patch('pipeline.korea_aks_search.time.sleep'),\
                 patch('sys.stdout',new_callable=io.StringIO):
                first=fetch(output,expected_total=21,delay=3)
                self.assertEqual(first['records'],21)
                second=fetch(output,expected_total=21,delay=3)
                self.assertEqual(second,first)
                path=output/'page-01.json'
                before=path.read_bytes()
                path.write_bytes(before+b' ')
                with self.assertRaises(IntakeError):
                    fetch(output,expected_total=21,delay=3)
                self.assertEqual(path.read_bytes(),before+b' ')


if __name__=='__main__':
    unittest.main()
