"""Capture factual metadata from a bounded AKS search, without copying transcriptions."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup, Tag

from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

BASE = 'https://kdp.aks.ac.kr'
AGENT = 'AstraiaResearch/1.0 (local academic source verification)'
FIELDS = ('사업구분','조사지역','자료구분','채록시도','조사일시','조사자','제보자')
ID_PATTERN = re.compile(r'POKS\.GUBI\.GUBI\.\d+_\d+')
HREF_PATTERN = re.compile(r"javascript:goIndeData\('14','지역별','서울시','도봉구','','(POKS\.GUBI\.GUBI\.\d+_\d+)'\)")
MAX_BYTES = 8 * 1024 * 1024


def search_url(page: int) -> str:
    return f'{BASE}/inde/search?itemId=14&pageIndex={page}&pageUnit=20'


def parse_page(raw: bytes, page: int) -> tuple[int, list[dict]]:
    if not raw or len(raw) > MAX_BYTES:
        raise IntakeError('馆方检索页面为空或超过大小限制。')
    soup = BeautifulSoup(raw, 'html.parser')
    title = soup.title.get_text(' ',strip=True) if soup.title else ''
    if '한국 구비문학 대계' not in title:
        raise IntakeError('馆方检索页面标题不符。')
    match = re.search(r'총\s*([\d,]+)\s*개의\s*검색\s*결과', soup.get_text(' ',strip=True))
    if not match:
        raise IntakeError('馆方检索结果总数缺失。')
    total = int(match.group(1).replace(',',''))
    records, seen = [], set()
    for anchor in soup.find_all('a',href=HREF_PATTERN):
        selected = HREF_PATTERN.fullmatch(anchor['href'])
        item = anchor.find_parent('li')
        if not selected or not item:
            raise IntakeError('馆方检索条目的位置或链接不符。')
        identifier = selected.group(1)
        if identifier in seen:
            raise IntakeError('同一检索页面含重复馆方编号。')
        seen.add(identifier)
        fields = {}
        for label in item.select('span.meta-label'):
            name = label.get_text(' ',strip=True)
            if name not in FIELDS or name in fields:
                raise IntakeError('馆方检索元数据字段变化或重复。')
            values = []
            for sibling in label.next_siblings:
                if isinstance(sibling,Tag) and 'meta-label' in (sibling.get('class') or []):
                    break
                values.append(sibling.get_text(' ',strip=True) if isinstance(sibling,Tag) else str(sibling).strip())
            fields[name] = ' '.join(value for value in values if value).strip()
        if set(fields) != set(FIELDS) or fields['조사지역'] != '도봉구' or fields['채록시도'] != '서울':
            raise IntakeError('检索元数据缺失或不属于所选范围。')
        name = anchor.get_text(' ',strip=True)
        if not name:
            raise IntakeError('馆方检索题名为空。')
        records.append({'id':identifier,'title':name,'fields':fields,
                        'candidate_url':f'{BASE}/inde/gubi?id={identifier}'})
    expected = min(20,max(0,total-(page-1)*20))
    if len(records) != expected:
        raise IntakeError(f'馆方第 {page} 页条数与总数不符：{len(records)} / {expected}。')
    return total,records


def _read_robots() -> tuple[RobotFileParser, str]:
    with urlopen(Request(BASE+'/robots.txt',headers={'User-Agent':AGENT}),timeout=30) as response:
        raw=response.read(65537)
        if response.status != 200 or response.headers.get_content_type() != 'text/plain' or len(raw)>65536:
            raise IntakeError('无法核验馆方 robots.txt。')
    rules=RobotFileParser();rules.parse(raw.decode('utf-8-sig').splitlines())
    return rules,sha256(raw).hexdigest()


def fetch(output: Path, *, expected_total: int, delay: float) -> dict:
    if delay < 3 or not 1 <= expected_total <= 1000:
        raise IntakeError('馆方分页采集须限速至少 3 秒，且总量须在 1–1000 内。')
    count=(expected_total+19)//20
    rules,robots_hash=_read_robots()
    if any(not rules.can_fetch(AGENT,search_url(page)) for page in range(1,count+1)):
        raise IntakeError('馆方 robots.txt 不允许检索页面。')
    output.mkdir(parents=True,exist_ok=True)
    control={'version':1,'scope':'서울시 / 도봉구','expected_total':expected_total,'page_size':20,
             'source':'AKS 韩国口碑文学大系检索页','raw_html_saved':False,
             'rights':'仅保存题名、角色、区域、日期及链接字段；正文和音视频未复制，权利及社区要求须复核。'}
    control_path=output/'selection.json'
    if control_path.exists():
        if json.loads(control_path.read_text(encoding='utf-8')) != control:
            raise IntakeError('已有选取范围不同；请选择新的目录。')
    else:
        exclusive_write(control_path,(json.dumps(control,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    pages, identifiers = [], set()
    for page in range(1,count+1):
        path=output/f'page-{page:02}.json'
        receipt_path=output/f'page-{page:02}.receipt.json'
        if path.exists():
            if not receipt_path.is_file():
                raise IntakeError(f'已保存的第 {page} 页缺少核验收据。')
            data=json.loads(path.read_text(encoding='utf-8'))
            receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
            if (data.get('version')!=1 or data.get('page')!=page or data.get('url')!=search_url(page)
                    or data.get('total')!=expected_total or data.get('raw_response_saved') is not False
                    or not re.fullmatch(r'[0-9a-f]{64}',data.get('response_sha256',''))
                    or receipt != {'page':page,'url':search_url(page),'index_sha256':sha256(path.read_bytes()).hexdigest(),
                                   'response_sha256':data.get('response_sha256')}):
                raise IntakeError(f'已保存的第 {page} 页元数据不符。')
            records=data.get('records')
            if not isinstance(records,list) or len(records)!=min(20,expected_total-(page-1)*20):
                raise IntakeError(f'已保存的第 {page} 页条数不符。')
        else:
            if receipt_path.exists():
                raise IntakeError(f'第 {page} 页收据存在但索引缺失。')
            time.sleep(delay)
            url=search_url(page)
            request=Request(url,headers={'User-Agent':AGENT})
            with urlopen(request,timeout=45) as response:
                if (response.status!=200 or response.headers.get_content_type()!='text/html'
                        or not response.url.startswith(BASE+'/inde/search?')):
                    raise IntakeError('馆方检索响应状态或地址不符。')
                raw=response.read(MAX_BYTES+1)
            total,records=parse_page(raw,page)
            if total!=expected_total:
                raise IntakeError(f'馆方检索总数已变化：{total}；需重新核对范围。')
            data={'version':1,'page':page,'url':url,'total':total,
                  'observed_at':datetime.now(timezone.utc).isoformat(),
                  'response_sha256':sha256(raw).hexdigest(),'raw_response_saved':False,'records':records}
            exclusive_write(path,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
            receipt={'page':page,'url':url,'index_sha256':sha256(path.read_bytes()).hexdigest(),
                     'response_sha256':data['response_sha256']}
            exclusive_write(receipt_path,(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        for record in records:
            if (not isinstance(record,dict) or not ID_PATTERN.fullmatch(record.get('id',''))
                    or record['id'] in identifiers or not isinstance(record.get('title'),str)
                    or not record['title'].strip() or not isinstance(record.get('fields'),dict)
                    or set(record['fields']) != set(FIELDS)
                    or any(not isinstance(value,str) for value in record['fields'].values())
                    or record['fields']['조사지역']!='도봉구' or record['fields']['채록시도']!='서울'
                    or record.get('candidate_url') != f"{BASE}/inde/gubi?id={record['id']}"):
                raise IntakeError('馆方记录编号重复或字段不符。')
            identifiers.add(record['id'])
        pages.append({'page':page,'path':path.name,'sha256':sha256(path.read_bytes()).hexdigest(),
                      'records':len(records),'response_sha256':data['response_sha256']})
        print(f'已核验韩国馆方检索页 {page}/{count} · {len(identifiers)}/{expected_total} 条',flush=True)
    manifest={'version':1,'selection_sha256':sha256(control_path.read_bytes()).hexdigest(),
              'robots_sha256':robots_hash,'records':len(identifiers),'pages':pages,
              'scope':'检索页字段索引；未保存网页原响应，响应哈希无法单凭本地索引重算。'}
    path=output/'manifest.json'
    if path.exists():
        existing=json.loads(path.read_text(encoding='utf-8'))
        if existing!=manifest:
            raise IntakeError('已有检索清单与当前页面索引不符。')
    else:
        exclusive_write(path,(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    return manifest


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-total',type=int,default=202)
    parser.add_argument('--delay',type=float,default=3.0)
    args=parser.parse_args()
    try:
        result=fetch(args.output,expected_total=args.expected_total,delay=args.delay)
    except (ValueError,OSError,KeyError,TypeError,HTTPError) as error:
        print(f'韩国馆方检索采集停止；已保存页面索引可核对后续跑：{error}',file=sys.stderr)
        return 1
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
