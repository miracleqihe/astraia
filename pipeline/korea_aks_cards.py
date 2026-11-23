"""Stage AKS Dobong catalogue rows and source candidates for human review."""
from collections import defaultdict
import csv
from datetime import date
from hashlib import sha256
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_crosswalk import crosswalk, in_dobong, load_catalogue, load_search
from pipeline.korea_aks_inventory import SOURCE_URL
from pipeline.korea_aks_reconcile import load_details, reconcile
from pipeline.korea_aks_search import BASE
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID='corpus_kr_aks_dobong'
CASE_PREFIX='case_kr_aks_dobong_'
SEARCH_URL=BASE+'/inde/search?itemId=14&pageIndex=1&pageUnit=20'


def load_bundle(archive: Path, receipt: Path, search: Path, base_path: Path,
                details_folder: Path, reconciled_path: Path) -> dict:
    catalogue,archive_hash,member_hash=load_catalogue(archive,receipt)
    sources,search_hash=load_search(search)
    base,base_summary=crosswalk(catalogue,sources,archive_hash,member_hash)
    if base_path.read_bytes()!=base:
        raise IntakeError('韩国基础对照清单与来源字段不符。')
    details,detail_hash=load_details(details_folder,sources,base,archive_hash,member_hash,search_hash)
    enriched,detail_summary=reconcile(base,details)
    if reconciled_path.read_bytes()!=enriched:
        raise IntakeError('韩国详情对照清单与来源字段不符。')
    rows=list(csv.DictReader(io.StringIO(enriched.decode('utf-8-sig'),newline='')))
    grouped=defaultdict(list)
    for row in rows:
        grouped[int(row['目录数据行序号'])].append(row)
    scoped={number for number,row in enumerate(catalogue,1) if in_dobong(row['채록지'])}
    if set(grouped)!=scoped or len(grouped)!=base_summary['scoped_catalogue_rows']:
        raise IntakeError('韩国目录范围与对照行不符。')
    return {'catalogue':catalogue,'sources':{source['id']:source for source in sources},
            'details':details,'grouped':dict(grouped),'archive_hash':archive_hash,'member_hash':member_hash,
            'search_hash':search_hash,'detail_hash':detail_hash,'base_hash':sha256(base).hexdigest(),
            'reconciled_hash':sha256(enriched).hexdigest(),'base_summary':base_summary,'detail_summary':detail_summary}


def evidence(number: int, original: dict, rows: list[dict]) -> dict:
    candidates=[]
    for row in rows:
        if not row['馆方编号']:
            continue
        candidates.append({key:row[key] for key in ('馆方编号','馆方检索题名','馆方讲述者','馆方检索类别','馆方检索区域',
            '馆方调查日期（非叙事年代）','馆方调查者','题名对照方式','题名相似度','该馆方记录的目录候选数',
            '候选单条页面','馆方详情题名','馆方详情讲述者','馆方详情类别','馆方详情采录地点',
            '馆方详情调查日期（非叙事年代）','馆方详情调查者','馆方详情地区','检索与详情题名','检索与详情讲述者',
            '检索与详情类别','检索与详情日期','目录与详情采录地点','详情字段索引SHA256','详情网页响应SHA256','待核问题')})
    return {'目录数据行序号':number,'目录字段':{key:original[key] for key in ('서명','구연자','채록지','유형','텍스트')},
            '馆方候选':candidates,'候选数':len(candidates),
            '范围说明':'候选来自道峰区检索字段；录音或目录行不等于独立故事，短编号不是标准码。'}


def korea_cards(archive: Path, receipt: Path, search: Path, base_path: Path,
                details_folder: Path, reconciled_path: Path):
    bundle=load_bundle(archive,receipt,search,base_path,details_folder,reconciled_path)
    common={'genre':'unclassified','credibility_tier':'B','is_fictional_quarantine':False,
            'spatial':{'precision':'culture_region','location_name':'韩国首尔道峰区（目录采录范围；叙事地点待核）',
                       'culture_region':'East Asia · Korea'},
            'temporal':None,'standards':{},'audit':{'created_at':date.today(),'reviewed_by_human':False}}
    def source(citation,kind,url,locator,path,digest):
        return {'citation':citation,'type':kind,'url':url,'locator':locator,
                'local_path':display_path(path),'content_sha256':digest}
    def common_sources(locator):
        return [source('韩国公共数据门户，韩国学中央研究院声音资料目录原始压缩包。',
                       'korea_aks_catalogue',SOURCE_URL,locator,archive,bundle['archive_hash']),
                source('项目下载凭据；目录文件许可与音视频、正文许可分别核对。',
                       'korea_aks_receipt',SOURCE_URL,'目录下载凭据',receipt,sha256(receipt.read_bytes()).hexdigest()),
                source('馆方检索字段索引清单；未保存网页原响应。',
                       'korea_aks_search_manifest',SEARCH_URL,'道峰区检索字段索引',search/'manifest.json',bundle['search_hash']),
                source('馆方单条详情字段索引清单；未复制正文或音视频。',
                       'korea_aks_detail_manifest',SEARCH_URL,'候选详情字段索引',details_folder/'manifest.json',bundle['detail_hash']),
                source('项目来源候选基础对照；匹配仅供人工复核。',
                       'korea_aks_crosswalk_base',SEARCH_URL,'道峰区来源候选',base_path,bundle['base_hash']),
                source('项目来源候选及详情字段对照；响应指纹不能离线重算。',
                       'korea_aks_crosswalk_detail',SEARCH_URL,'道峰区详情对照',reconciled_path,bundle['reconciled_hash'])]
    root={**common,'id':ROOT_ID,'title':'韩国首尔道峰区口碑目录 · AKS',
          'node_type':'myth_corpus','z_layer':2,'sources':common_sources('口碑文学目录 / 道峰区筛查')}
    summary=bundle['base_summary'];detail_summary=bundle['detail_summary']
    body=(f"\n## 馆藏与核查范围\n\n开放目录中 {summary['scoped_catalogue_rows']} 行的采录地字段属于首尔道峰区；"
          f"馆方检索页列出 {summary['source_search_records']} 条记录。{summary['catalogue_rows_with_candidates']} 行得到来源候选，"
          f"{summary['catalogue_rows_without_candidates']} 行暂未找到；候选来源共 {detail_summary['unique_details']} 条已保存单条元数据字段。"
          '这些是目录与检索行数，不是独立故事数；候选不证明同一次演述。未保存音视频、转写或馆方网页原响应，'
          '网页响应指纹不能单凭字段索引离线重算。单条许可、版本、体裁和相关社区要求须人工核对；坐标、叙事年代和标准码留空。\n')
    yield NodeMetadata.model_validate(root),body
    for number,rows in sorted(bundle['grouped'].items()):
        original=bundle['catalogue'][number-1]
        data=evidence(number,original,rows)
        sources=common_sources(f'{MEMBER_LABEL} / 数据行 {number}')
        for item in data['馆方候选']:
            identifier=item['馆方编号'];listing=bundle['sources'][identifier];detail=bundle['details'][identifier]
            parsed=urlsplit(listing['search_url']);page=int(parse_qs(parsed.query)['pageIndex'][0])
            sources.append(source('AKS 馆方检索字段索引；原网页未保存，响应指纹不可离线重算。',
                'korea_aks_search_index',listing['search_url'],identifier,search/f'page-{page:02}.json',listing['page_sha256']))
            sources.append(source('AKS 馆方单条元数据字段索引；原文和音视频请在馆方页面查看。',
                'korea_aks_detail_index',listing['candidate_url'],identifier,details_folder/'records'/f'{identifier}.json',detail['index_sha256']))
        metadata={**common,'id':f'{CASE_PREFIX}{number:06d}','title':f"韩国口碑目录 · {original['서명']}",
                  'aliases':[original['서명']],'node_type':'case','z_layer':1,'sources':sources,
                  'relations':[{'type':'PART_OF_MACRO_TREND','target':ROOT_ID,
                                'note':'同一开放目录筛查范围，不表示同一故事或传播关系。'}]}
        body=('\n## 馆方目录及来源候选\n\n'+literal_block(json.dumps(data,ensure_ascii=False,indent=2))
              +'\n\n## 原文与复核\n\n本卡保留原目录字段及待核来源候选，未保存转写正文或音视频；'
               '可通过候选来源链接查看馆方单条页面。题名相似、讲述者和采录区域对应仍不证明同一次演述。'
               '馆方调查日期与采录地点不自动成为故事发生时空；具体版本、许可及相关社区要求须逐项核对。'
               '目录文本短编号不是国际标准码，标准码仅可从本地码表核定。\n')
        yield NodeMetadata.model_validate(metadata),body


MEMBER_LABEL='한국구비문학대계(1).csv'
