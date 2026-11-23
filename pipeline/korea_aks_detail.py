"""Capture bounded AKS item metadata for existing, unreviewed crosswalk candidates."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import BadZipFile

from bs4 import BeautifulSoup

from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_crosswalk import crosswalk, load_catalogue, load_search
from pipeline.korea_aks_search import AGENT, BASE, ID_PATTERN, MAX_BYTES, _read_robots

FIELDS=('제목','자료분류','조사자','조사장소','조사일시','제보자','조사지역')


def parse_detail(raw: bytes) -> dict:
    if not raw or len(raw)>MAX_BYTES:
        raise IntakeError('馆方详情页为空或超过大小限制。')
    soup=BeautifulSoup(raw,'html.parser')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    if '한국 구비문학 대계' not in title:
        raise IntakeError('馆方详情页面标题不符。')
    fields={}
    for label in soup.find_all('dt'):
        name=label.get_text(' ',strip=True)
        if name not in FIELDS:
            continue
        if name in fields:
            raise IntakeError('馆方详情元数据字段重复。')
        value=label.find_next_sibling('dd')
        if not value:
            raise IntakeError('馆方详情元数据缺少值。')
        fields[name]=value.get_text(' ',strip=True)
    if set(fields)!=set(FIELDS) or not fields['제목'].strip():
        raise IntakeError('馆方详情元数据字段不完整。')
    return fields


def fetch(archive: Path, receipt: Path, search: Path, crosswalk_path: Path, output: Path, *, delay: float) -> dict:
    if delay<3:
        raise IntakeError('馆方详情请求间隔须至少 3 秒。')
    catalogue,archive_hash,member_hash=load_catalogue(archive,receipt)
    sources,search_hash=load_search(search)
    generated,summary=crosswalk(catalogue,sources,archive_hash,member_hash)
    if crosswalk_path.read_bytes()!=generated:
        raise IntakeError('目录对照清单与源字段或当前匹配规则不符；保留现有文件。')
    rows=list(csv.DictReader(io.StringIO(generated.decode('utf-8-sig'),newline='')))
    identifiers=sorted({row['馆方编号'] for row in rows if row['馆方编号']})
    source_by_id={source['id']:source for source in sources}
    if not identifiers or any(not ID_PATTERN.fullmatch(number) or number not in source_by_id for number in identifiers):
        raise IntakeError('待核候选编号不符。')
    control={'version':1,'archive_sha256':archive_hash,'member_sha256':member_hash,
             'search_manifest_sha256':search_hash,'crosswalk_sha256':sha256(generated).hexdigest(),
             'selected_ids':identifiers,'selection_scope':'对照清单中的馆方候选；不代表同一次采录。',
             'raw_html_saved':False,'rights':'仅保存馆方元数据字段，不保存正文、音视频；具体许可和社区要求须核对。'}
    output.mkdir(parents=True,exist_ok=True)
    selection=output/'selection.json'
    if selection.exists():
        if json.loads(selection.read_text(encoding='utf-8'))!=control:
            raise IntakeError('已有详情选取范围不同；请选择新的目录。')
    else:
        exclusive_write(selection,(json.dumps(control,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    rules,robots_hash=_read_robots()
    if any(not rules.can_fetch(AGENT,source_by_id[number]['candidate_url']) for number in identifiers):
        raise IntakeError('馆方 robots.txt 不允许访问所选详情页。')
    records,items=[],output/'records'
    items.mkdir(exist_ok=True)
    for number in identifiers:
        source=source_by_id[number]
        path=items/f'{number}.json'
        receipt_path=items/f'{number}.receipt.json'
        url=source['candidate_url']
        if path.exists():
            if not receipt_path.is_file():
                raise IntakeError(f'详情 {number} 缺少核验收据。')
            entry=json.loads(path.read_text(encoding='utf-8'))
            saved=json.loads(receipt_path.read_text(encoding='utf-8'))
            if (entry.get('version')!=1 or entry.get('id')!=number or entry.get('url')!=url
                    or entry.get('raw_response_saved') is not False
                    or not re.fullmatch(r'[0-9a-f]{64}',entry.get('response_sha256',''))
                    or entry.get('search_page_sha256')!=source['page_sha256']
                    or not isinstance(entry.get('fields'),dict) or set(entry['fields'])!=set(FIELDS)
                    or any(not isinstance(value,str) for value in entry['fields'].values())
                    or saved!={'id':number,'url':url,'index_sha256':sha256(path.read_bytes()).hexdigest(),
                               'response_sha256':entry.get('response_sha256')}):
                raise IntakeError(f'已保存详情 {number} 的字段或收据不符。')
        else:
            if receipt_path.exists():
                raise IntakeError(f'详情 {number} 收据存在但索引缺失。')
            time.sleep(delay)
            with urlopen(Request(url,headers={'User-Agent':AGENT}),timeout=45) as response:
                if response.status!=200 or response.headers.get_content_type()!='text/html' or response.url!=url:
                    raise IntakeError(f'详情 {number} 的响应状态或地址不符。')
                raw=response.read(MAX_BYTES+1)
            fields=parse_detail(raw)
            entry={'version':1,'id':number,'url':url,'search_page_sha256':source['page_sha256'],
                   'observed_at':datetime.now(timezone.utc).isoformat(),
                   'response_sha256':sha256(raw).hexdigest(),'raw_response_saved':False,'fields':fields}
            exclusive_write(path,(json.dumps(entry,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
            saved={'id':number,'url':url,'index_sha256':sha256(path.read_bytes()).hexdigest(),
                   'response_sha256':entry['response_sha256']}
            exclusive_write(receipt_path,(json.dumps(saved,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        records.append({'id':number,'path':f'records/{number}.json','sha256':sha256(path.read_bytes()).hexdigest(),
                        'response_sha256':entry['response_sha256']})
        print(f'已核验韩国馆方单条元数据 {len(records)}/{len(identifiers)} · {number}',flush=True)
    manifest={'version':1,'selection_sha256':sha256(selection.read_bytes()).hexdigest(),
              'robots_sha256':robots_hash,'records':records,
              'scope':'单条页面元数据字段索引；未保存网页原响应，响应哈希不能单凭本地索引重算。'}
    path=output/'manifest.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))!=manifest:
            raise IntakeError('已有详情清单与当前索引不符。')
    else:
        exclusive_write(path,(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    return manifest


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--search',type=Path,required=True)
    parser.add_argument('--crosswalk',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--delay',type=float,default=3.0)
    args=parser.parse_args()
    try:
        result=fetch(args.archive,args.receipt,args.search,args.crosswalk,args.output,delay=args.delay)
    except (ValueError,OSError,KeyError,TypeError,csv.Error,BadZipFile,HTTPError) as error:
        print(f'韩国馆方详情采集停止；已保存字段索引可核对后续跑：{error}',file=sys.stderr)
        return 1
    print(f"已保存 {len(result['records'])} 条韩国馆方单条元数据。")
    return 0


if __name__=='__main__':
    raise SystemExit(main())
