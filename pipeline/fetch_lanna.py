"""Capture the Northern Thai manuscript Folk Tale search, without manuscript images."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from pipeline.fetch_lao_dllm import IDENTIFIER, MAX_PAGE_BYTES, PAYLOAD, exclusive_write, parse_page
from pipeline.intake_sources import IntakeError

BASE='https://iiif.crossasia.org'
ENDPOINT=BASE+'/s/lanna/madoc/api/search?page={}'
SEARCH_URL=(BASE+'/s/lanna/search?facets=%5B%7B%22k%22%3A%22dc%3Asubject%22%2C%22v%22%3A%22Folk%20Tale%22%7D%5D&fulltext=')
AGENT='Astraia/0.1 (local research intake)'


def rules():
    url=BASE+'/robots.txt'
    try:
        with urlopen(Request(url,headers={'User-Agent':AGENT}),timeout=30) as response:
            raw=response.read(100_001)
            if len(raw)>100_000 or response.headers.get_content_type()!='text/plain':
                raise IntakeError('robots.txt 类型或大小不符。')
            parser=RobotFileParser();parser.set_url(url);parser.parse(raw.decode('utf-8-sig').splitlines())
            return parser,{'status':response.status,'sha256':sha256(raw).hexdigest()}
    except HTTPError as error:
        if error.code==404:
            return None,{'status':404,'sha256':None}
        raise


def fetch(output: Path, delay: float=2.0) -> dict:
    if delay<2:raise IntakeError('请求间隔至少为 2 秒。')
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():raise IntakeError('此目录已有完整批次，不覆盖。')
    robot,robot_info=rules()
    if robot and not robot.can_fetch(AGENT,ENDPOINT.format(1)):raise IntakeError('robots.txt 不允许检索接口。')
    selection={'version':1,'search_url':SEARCH_URL,'endpoint':ENDPOINT,'payload':PAYLOAD}
    selection_path=output/'selection.json'
    if selection_path.exists():
        if json.loads(selection_path.read_text(encoding='utf-8'))!=selection:
            raise IntakeError('既有检索条件与本批不符，停止续跑。')
    else:exclusive_write(selection_path,(json.dumps(selection,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    body=json.dumps(PAYLOAD,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    pages,seen,totals,number=[],set(),None,1
    while totals is None or number<=totals[1]:
        url=ENDPOINT.format(number)
        if robot and not robot.can_fetch(AGENT,url):raise IntakeError(f'robots.txt 不允许第 {number} 页。')
        path=output/f'page-{number:03d}.json'
        receipt_path=output/f'page-{number:03d}.receipt.json'
        if path.exists():
            raw=path.read_bytes()
            if not receipt_path.exists():raise IntakeError(f'第 {number} 页缺少凭据，保留快照并停止续跑。')
            receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
            if (receipt.get('page')!=number or receipt.get('url')!=url
                    or receipt.get('sha256')!=sha256(raw).hexdigest() or not receipt.get('retrieved_at')):
                raise IntakeError(f'第 {number} 页与凭据不符，保留快照并停止续跑。')
            retrieved=receipt['retrieved_at']
        else:
            if receipt_path.exists():raise IntakeError(f'第 {number} 页快照缺失但凭据已存在。')
            request=Request(url,data=body,method='POST',headers={'User-Agent':AGENT,'Content-Type':'application/json',
                'Accept':'application/json','Accept-Encoding':'identity'})
            with urlopen(request,timeout=30) as response:
                raw=response.read(MAX_PAGE_BYTES+1)
                if response.url!=url or response.headers.get_content_type()!='application/json' or len(raw)>MAX_PAGE_BYTES:
                    raise IntakeError('检索响应地址、类型或大小不符。')
            parse_page(raw,number)
            retrieved=datetime.now(timezone.utc).isoformat()
            exclusive_write(path,raw)
            receipt={'page':number,'url':url,'sha256':sha256(raw).hexdigest(),'retrieved_at':retrieved}
            exclusive_write(receipt_path,(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
            print(f'已保存北泰馆藏检索第 {number} 页。',flush=True)
            time.sleep(delay)
        document=parse_page(raw,number);page=document['pagination']
        current=(page['totalResults'],page['totalPages'],page['pageSize'])
        if totals is None:totals=current
        elif totals!=current:raise IntakeError('检索分页或总数变化，已保留现有快照。')
        for item in document['results']:
            identifier=IDENTIFIER.fullmatch(item['resource_id']).group(1)
            if identifier in seen:raise IntakeError(f'馆藏编号重复：{identifier}')
            seen.add(identifier)
        pages.append({'page':number,'path':path.name,'sha256':sha256(raw).hexdigest(),
                      'retrieved_at':retrieved,'records':len(document['results'])})
        number+=1
    if len(seen)!=totals[0]:raise IntakeError('唯一馆藏记录数与结果数不符。')
    manifest={'version':1,'search_url':SEARCH_URL,'endpoint':ENDPOINT,'payload':PAYLOAD,'robots':robot_info,
        'selection_sha256':sha256(selection_path.read_bytes()).hexdigest(),
        'total_results':totals[0],'total_pages':totals[1],'page_size':totals[2],'pages':pages,
        'scope':'Folk Tale 馆藏分类；手稿件数不是故事数；未下载手稿影像或转录正文。'}
    exclusive_write(output/'manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--delay',type=float,default=2)
    args=parser.parse_args()
    try:manifest=fetch(args.output,args.delay)
    except (ValueError,OSError,HTTPError,URLError) as error:
        print(f'北泰馆藏检索未完成，已保存快照保留：{error}',file=sys.stderr);return 1
    print(f"检索快照完成：{manifest['total_results']} 件，{manifest['total_pages']} 页。")
    return 0


if __name__=='__main__':raise SystemExit(main())
