"""Add checked AKS item metadata to a review-only crosswalk without signing records."""
import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile

from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_crosswalk import crosswalk, load_catalogue, load_search, normal
from pipeline.korea_aks_detail import FIELDS as DETAIL_FIELDS
from pipeline.korea_aks_search import BASE, ID_PATTERN

DETAIL_COLUMNS=['馆方详情题名','馆方详情讲述者','馆方详情类别','馆方详情采录地点','馆方详情调查日期（非叙事年代）',
                '馆方详情调查者','馆方详情地区','检索与详情题名','检索与详情讲述者','检索与详情类别',
                '检索与详情日期','目录与详情采录地点','详情字段索引SHA256','详情网页响应SHA256']


def compare_text(left: str,right: str) -> bool | None:
    if not left.strip() or not right.strip():
        return None
    return normal(left)==normal(right)


def compare_places(catalogue: str, detail: str) -> bool | None:
    def tokens(value):
        values=[normal(part) for part in re.split(r'[\s\-–—,/]+',value) if part.strip()]
        converted=[]
        for value in values:
            value='서울' if value in {'서울시','서울특별시','서울'} else value
            if not converted or converted[-1]!=value:
                converted.append(value)
        return converted
    left,right=tokens(catalogue),tokens(detail)
    if not left or not right or any(value in {'미상','불명','기타'} for value in left+right):
        return None
    if left==right:
        return True
    if len(left)!=len(right) and (left[:len(right)]==right or right[:len(left)]==left):
        return None
    return False


def load_details(folder: Path, sources: list[dict], base_bytes: bytes, archive_hash: str,
                 member_hash: str, search_hash: str) -> tuple[dict,str]:
    selection_path=folder/'selection.json'
    selection=json.loads(selection_path.read_text(encoding='utf-8'))
    manifest_path=folder/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    rows=list(csv.DictReader(io.StringIO(base_bytes.decode('utf-8-sig'),newline='')))
    selected=sorted({row['馆方编号'] for row in rows if row['馆方编号']})
    source_by_id={source['id']:source for source in sources}
    if (selection.get('version')!=1 or selection.get('archive_sha256')!=archive_hash
            or selection.get('member_sha256')!=member_hash or selection.get('search_manifest_sha256')!=search_hash
            or selection.get('crosswalk_sha256')!=sha256(base_bytes).hexdigest()
            or selection.get('selected_ids')!=selected or selection.get('raw_html_saved') is not False
            or manifest.get('version')!=1 or manifest.get('selection_sha256')!=sha256(selection_path.read_bytes()).hexdigest()
            or not isinstance(manifest.get('records'),list) or len(manifest['records'])!=len(selected)):
        raise IntakeError('馆方详情选取、来源或清单不符。')
    details={}
    for number,entry in zip(selected,manifest['records'],strict=True):
        if not ID_PATTERN.fullmatch(number) or number not in source_by_id:
            raise IntakeError('馆方详情编号不属于检索范围。')
        path=folder/'records'/f'{number}.json'
        receipt_path=folder/'records'/f'{number}.receipt.json'
        if not isinstance(entry,dict) or entry.get('id')!=number or entry.get('path')!=f'records/{number}.json':
            raise IntakeError('馆方详情清单的路径或编号不符。')
        raw=path.read_bytes();digest=sha256(raw).hexdigest()
        saved=json.loads(receipt_path.read_text(encoding='utf-8'))
        data=json.loads(raw.decode('utf-8'))
        url=f'{BASE}/inde/gubi?id={number}'
        if (entry.get('sha256')!=digest or data.get('version')!=1 or data.get('id')!=number
                or data.get('url')!=url or data.get('raw_response_saved') is not False
                or data.get('search_page_sha256')!=source_by_id[number]['page_sha256']
                or not re.fullmatch(r'[0-9a-f]{64}',data.get('response_sha256',''))
                or entry.get('response_sha256')!=data['response_sha256']
                or saved!={'id':number,'url':url,'index_sha256':digest,'response_sha256':data['response_sha256']}
                or not isinstance(data.get('fields'),dict) or set(data['fields'])!=set(DETAIL_FIELDS)
                or any(not isinstance(value,str) for value in data['fields'].values())):
            raise IntakeError(f'馆方详情 {number} 与字段索引或收据不符。')
        details[number]={'fields':data['fields'],'index_sha256':digest,'response_sha256':data['response_sha256']}
    return details,sha256(manifest_path.read_bytes()).hexdigest()


def reconcile(base_bytes: bytes, details: dict) -> tuple[bytes,dict]:
    reader=csv.DictReader(io.StringIO(base_bytes.decode('utf-8-sig'),newline=''))
    if not reader.fieldnames or any(name in reader.fieldnames for name in DETAIL_COLUMNS):
        raise IntakeError('基础对照清单字段不符或已包含详情。')
    rows=list(reader)
    candidate_ids={row['馆方编号'] for row in rows if row['馆方编号']}
    if candidate_ids!=set(details):
        raise IntakeError('详情编号与基础对照候选不一致。')
    def unsafe(value):
        return value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r'))
    if any(unsafe(value) for detail in details.values() for value in detail['fields'].values()):
        raise IntakeError('详情字段可能被电子表格解释为公式，需先选择安全的显示方式。')
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=reader.fieldnames+DETAIL_COLUMNS,lineterminator='\r\n')
    writer.writeheader()
    stats={'detail_candidate_pairs':0,'place_equal_pairs':0,'place_different_pairs':0,'place_uncertain_pairs':0,
           'listing_detail_disagreement_pairs':0,'unmatched_rows':0}
    label=lambda value: '一致' if value is True else '不同' if value is False else '无法比较'
    for row in rows:
        result={key:'' for key in DETAIL_COLUMNS}
        number=row['馆方编号']
        if number:
            entry=details[number];fields=entry['fields']
            comparisons={'检索与详情题名':compare_text(row['馆方检索题名'],fields['제목']),
                         '检索与详情讲述者':compare_text(row['馆方讲述者'],fields['제보자']),
                         '检索与详情类别':compare_text(row['馆方检索类别'],fields['자료분류']),
                         '检索与详情日期':compare_text(row['馆方调查日期（非叙事年代）'],fields['조사일시'])}
            place=compare_places(row['目录采录地原字段'],fields['조사장소'])
            stats['detail_candidate_pairs']+=1
            stats['place_equal_pairs']+=place is True
            stats['place_different_pairs']+=place is False
            stats['place_uncertain_pairs']+=place is None
            stats['listing_detail_disagreement_pairs']+=any(value is False for value in comparisons.values())
            flags=row['待核问题'].replace('单条详情尚未回查，须核对具体采录地点、日期与版本',
                                       '单条详情字段已采集；同一次演述、日期与版本仍须人工核对')
            if place is False:flags+='；目录与详情采录地点写法不同，须核对历史地名和范围'
            elif place is None:flags+='；采录地点字段无法直接比较'
            if any(value is False for value in comparisons.values()):flags+='；馆方检索与详情字段不一致'
            result={'馆方详情题名':fields['제목'],'馆方详情讲述者':fields['제보자'],'馆方详情类别':fields['자료분류'],
                    '馆方详情采录地点':fields['조사장소'],'馆方详情调查日期（非叙事年代）':fields['조사일시'],
                    '馆方详情调查者':fields['조사자'],'馆方详情地区':fields['조사지역'],
                    **{key:label(value) for key,value in comparisons.items()},'目录与详情采录地点':label(place),
                    '详情字段索引SHA256':entry['index_sha256'],'详情网页响应SHA256':entry['response_sha256']}
            row['单条详情状态']='元数据已采集，待人工复核'
            row['待核问题']=flags
        else:
            stats['unmatched_rows']+=1
        writer.writerow({**row,**result})
    data=b'\xef\xbb\xbf'+output.getvalue().encode('utf-8')
    return data,{**stats,'unique_details':len(details),'rows':len(rows),'output_sha256':sha256(data).hexdigest(),
                 'pending_only':True,'scope':'字段对照与候选链接，未复制正文；不证明同一次演述。'}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--search',type=Path,required=True)
    parser.add_argument('--crosswalk',type=Path,required=True)
    parser.add_argument('--details',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        catalogue,archive_hash,member_hash=load_catalogue(args.archive,args.receipt)
        sources,search_hash=load_search(args.search)
        base,_=crosswalk(catalogue,sources,archive_hash,member_hash)
        if args.crosswalk.read_bytes()!=base:
            raise IntakeError('基础对照清单与馆方字段不符；保留现有文件。')
        details,detail_hash=load_details(args.details,sources,base,archive_hash,member_hash,search_hash)
        data,summary=reconcile(base,details)
        summary['detail_manifest_sha256']=detail_hash
        with args.output.open('xb') as stream:stream.write(data)
    except (ValueError,OSError,KeyError,TypeError,csv.Error,BadZipFile) as error:
        print(f'韩国详情对照清单未生成：{error}',file=sys.stderr)
        return 1
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
