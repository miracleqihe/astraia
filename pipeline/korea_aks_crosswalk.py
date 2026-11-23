"""Create review-only candidates between an open AKS catalogue and AKS search fields."""
import argparse
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
import unicodedata
from zipfile import BadZipFile, ZipFile

from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_inventory import FIELDS as CATALOGUE_FIELDS, MEMBER, SOURCE_URL
from pipeline.korea_aks_search import BASE, FIELDS as SEARCH_FIELDS, ID_PATTERN, search_url

THRESHOLD=0.80
COLUMNS=['目录数据行序号','目录题名','目录讲述者','目录采录地原字段','目录类别','目录文本字段',
         '候选数','馆方编号','馆方检索题名','馆方讲述者','馆方检索类别','馆方检索区域','馆方调查日期（非叙事年代）',
         '馆方调查者','题名对照方式','题名相似度','该馆方记录的目录候选数','候选单条页面',
         '单条详情状态','待核问题','坐标','标准码','馆方检索页','检索字段索引SHA256','检索网页响应SHA256',
         '目录压缩包SHA256','目录子文件SHA256','人工复核']


def normal(value: str) -> str:
    return ''.join(unicodedata.normalize('NFKC',value).casefold().split())


def load_catalogue(archive: Path, receipt: Path) -> tuple[list[dict],str,str]:
    raw=archive.read_bytes()
    digest=sha256(raw).hexdigest()
    info=json.loads(receipt.read_text(encoding='utf-8'))
    if (info.get('datasetId')!='15070383' or info.get('pageUrl')!=SOURCE_URL
            or info.get('sha256')!=digest or info.get('bytes')!=len(raw)):
        raise IntakeError('馆方目录压缩包与下载凭据不符。')
    with ZipFile(io.BytesIO(raw)) as zipped:
        members=[item for item in zipped.infolist() if item.filename==MEMBER and not item.is_dir()]
        if len(members)!=1 or members[0].file_size>100*1024*1024:
            raise IntakeError('馆方目录子文件缺失、重复或过大。')
        member=zipped.read(members[0])
    reader=csv.DictReader(io.StringIO(member.decode('utf-8-sig'),newline=''))
    if reader.fieldnames!=CATALOGUE_FIELDS:
        raise IntakeError('馆方目录字段不符。')
    rows=list(reader)
    if not rows or any(set(row)!=set(CATALOGUE_FIELDS) or any(not isinstance(v,str) for v in row.values()) for row in rows):
        raise IntakeError('馆方目录记录不完整。')
    return rows,digest,sha256(member).hexdigest()


def load_search(folder: Path) -> tuple[list[dict],str]:
    selection_path=folder/'selection.json'
    selection=json.loads(selection_path.read_text(encoding='utf-8'))
    manifest_path=folder/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if (selection.get('version')!=1 or selection.get('scope')!='서울시 / 도봉구'
            or selection.get('page_size')!=20 or selection.get('raw_html_saved') is not False
            or type(selection.get('expected_total')) is not int or selection['expected_total']<1
            or manifest.get('version')!=1
            or manifest.get('selection_sha256')!=sha256(selection_path.read_bytes()).hexdigest()
            or manifest.get('records')!=selection['expected_total'] or not isinstance(manifest.get('pages'),list)):
        raise IntakeError('馆方检索范围或清单不符。')
    total=selection['expected_total']
    if len(manifest['pages'])!=(total+19)//20:
        raise IntakeError('馆方检索清单页数不符。')
    records,seen=[],set()
    for page,entry in enumerate(manifest['pages'],1):
        path=folder/f'page-{page:02}.json'
        receipt_path=folder/f'page-{page:02}.receipt.json'
        if not isinstance(entry,dict) or entry.get('page')!=page or entry.get('path')!=path.name:
            raise IntakeError('馆方检索分页顺序或路径不符。')
        raw=path.read_bytes();digest=sha256(raw).hexdigest()
        data=json.loads(raw.decode('utf-8'))
        receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
        if (entry.get('sha256')!=digest or data.get('page')!=page or data.get('version')!=1
                or data.get('total')!=total or data.get('url')!=search_url(page)
                or data.get('raw_response_saved') is not False
                or not re.fullmatch(r'[0-9a-f]{64}',data.get('response_sha256',''))
                or entry.get('response_sha256')!=data['response_sha256']
                or receipt!={'page':page,'url':search_url(page),'index_sha256':digest,'response_sha256':data['response_sha256']}
                or not isinstance(data.get('records'),list)
                or len(data['records'])!=min(20,total-(page-1)*20) or entry.get('records')!=len(data['records'])):
            raise IntakeError('馆方检索页、收据与清单不符。')
        for record in data['records']:
            if (not isinstance(record,dict) or not ID_PATTERN.fullmatch(record.get('id',''))
                    or record['id'] in seen or not isinstance(record.get('title'),str) or not record['title'].strip()
                    or not isinstance(record.get('fields'),dict) or set(record['fields'])!=set(SEARCH_FIELDS)
                    or any(not isinstance(value,str) for value in record['fields'].values())
                    or record['fields']['조사지역']!='도봉구' or record['fields']['채록시도']!='서울'
                    or record.get('candidate_url')!=f"{BASE}/inde/gubi?id={record['id']}"):
                raise IntakeError('馆方检索记录编号、区域或字段不符。')
            seen.add(record['id'])
            records.append({**record,'search_url':search_url(page),'page_sha256':digest,
                            'response_sha256':data['response_sha256']})
    if len(records)!=total:
        raise IntakeError('馆方检索记录总数不符。')
    return records,sha256(manifest_path.read_bytes()).hexdigest()


def in_dobong(place: str) -> bool:
    parts=[normal(part) for part in place.split('-')]
    return len(parts)>=2 and parts[0] in {'서울','서울시','서울특별시'} and parts[1]=='도봉구'


def crosswalk(catalogue: list[dict], sources: list[dict], archive_hash: str, member_hash: str) -> tuple[bytes,dict]:
    scoped=[(number,row) for number,row in enumerate(catalogue,1) if in_dobong(row['채록지'])]
    def unsafe(value):
        return value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r'))
    if (any(unsafe(value) for _,row in scoped for value in row.values())
            or any(unsafe(value) for source in sources for value in [source['title'],*source['fields'].values()])):
        raise IntakeError('目录或馆方字段可能被电子表格解释为公式，需先选择安全的显示方式。')
    index=defaultdict(list)
    for source in sources:
        fields=source['fields']
        if fields['사업구분']=='한국구비문학대계(1차)' and fields['제보자'].strip():
            index[(normal(fields['제보자']),normal(fields['자료구분']))].append(source)
    matches={}
    source_degree=Counter()
    for number,row in scoped:
        candidates=[]
        if row['구연자'].strip():
            for source in index[(normal(row['구연자']),normal(row['유형']))]:
                left,right=normal(row['서명']),normal(source['title'])
                score=SequenceMatcher(None,left,right,autojunk=False).ratio()
                if score>=THRESHOLD and (min(len(left),len(right))>=4 or score==1.0):
                    candidates.append((source,score))
            candidates.sort(key=lambda item:(-item[1],item[0]['id']))
        matches[number]=candidates
        source_degree.update(source['id'] for source,_ in candidates)
    buffer=io.StringIO(newline='')
    writer=csv.DictWriter(buffer,fieldnames=COLUMNS,lineterminator='\r\n')
    writer.writeheader()
    for number,row in scoped:
        candidates=matches[number]
        for source,score in candidates or [(None,None)]:
            flags=['候选由题名、讲述者、馆方类别和道峰区范围生成，均须人工核对',
                   '采录地点与日期不等于故事发生时空；坐标和标准码待核']
            if not row['구연자'].strip():flags.append('目录未填写讲述者')
            if source is None:
                flags.append('本次馆方检索未找到候选，不代表不存在')
            else:
                flags.append('单条详情尚未回查，须核对具体采录地点、日期与版本')
                if row['서명']!=source['title']:flags.append('两处题名原字段不同')
                if len(candidates)>1:flags.append('此目录行存在多个馆方候选')
                if source_degree[source['id']]>1:flags.append('此馆方记录对应多个目录候选')
            fields=source['fields'] if source else {}
            writer.writerow({'目录数据行序号':number,'目录题名':row['서명'],'目录讲述者':row['구연자'],
                '目录采录地原字段':row['채록지'],'目录类别':row['유형'],'目录文本字段':row['텍스트'],
                '候选数':len(candidates),'馆方编号':source['id'] if source else '',
                '馆方检索题名':source['title'] if source else '', '馆方讲述者':fields.get('제보자',''),
                '馆方检索类别':fields.get('자료구분',''),'馆方检索区域':f"{fields['채록시도']} / {fields['조사지역']}" if source else '',
                '馆方调查日期（非叙事年代）':fields.get('조사일시',''),'馆方调查者':fields.get('조사자',''),
                '题名对照方式':('规范化一致' if score==1 else '相似待核') if source else '',
                '题名相似度':f'{score:.3f}' if source else '',
                '该馆方记录的目录候选数':source_degree[source['id']] if source else '',
                '候选单条页面':source['candidate_url'] if source else '',
                '单条详情状态':'尚未回查' if source else '', '待核问题':'；'.join(flags),
                '坐标':'','标准码':'','馆方检索页':source['search_url'] if source else search_url(1),
                '检索字段索引SHA256':source['page_sha256'] if source else '',
                '检索网页响应SHA256':source['response_sha256'] if source else '',
                '目录压缩包SHA256':archive_hash,'目录子文件SHA256':member_hash,'人工复核':'待复核'})
    data=b'\xef\xbb\xbf'+buffer.getvalue().encode('utf-8')
    all_matches=[item for candidates in matches.values() for item in candidates]
    summary={'source_search_records':len(sources),'scoped_catalogue_rows':len(scoped),
             'catalogue_rows_with_candidates':sum(bool(value) for value in matches.values()),
             'catalogue_rows_without_candidates':sum(not value for value in matches.values()),
             'candidate_pairs':len(all_matches),'title_normalized_equal_pairs':sum(score==1 for _,score in all_matches),
             'title_similar_pairs':sum(score<1 for _,score in all_matches),
             'catalogue_rows_with_multiple_candidates':sum(len(value)>1 for value in matches.values()),
             'source_records_with_multiple_catalogue_candidates':sum(value>1 for value in source_degree.values()),
             'title_similarity_threshold':THRESHOLD,'archive_sha256':archive_hash,'member_sha256':member_hash,
             'crosswalk_sha256':sha256(data).hexdigest(),'pending_only':True,
             'scope':'仅按目录字段生成待核候选；不代表同一次演述，也未回查单条详情。'}
    return data,summary


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--search',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        catalogue,archive_hash,member_hash=load_catalogue(args.archive,args.receipt)
        sources,manifest_hash=load_search(args.search)
        data,summary=crosswalk(catalogue,sources,archive_hash,member_hash)
        summary['search_manifest_sha256']=manifest_hash
        with args.output.open('xb') as stream:
            stream.write(data)
    except (ValueError,OSError,KeyError,TypeError,csv.Error,BadZipFile) as error:
        print(f'韩国目录对照清单未生成：{error}',file=sys.stderr)
        return 1
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
