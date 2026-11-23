"""Prepare Northern Thai Folk Tale manuscript catalogue cards for human review."""
from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from pipeline.fetch_lanna import ENDPOINT, SEARCH_URL
from pipeline.fetch_lao_dllm import IDENTIFIER, PAYLOAD, parse_page
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import Manuscript, attribution, display_path, selected_fields
from pipeline.node_model import NodeMetadata

ROOT_ID='corpus_th_lanna_folktales'
PREFIX='corpus_th_lanna_'
VIEWER='https://iiif.crossasia.org/s/lanna/manifests/{}'


def load_snapshot(folder: Path):
    folder=folder.resolve(strict=True)
    selection_path=folder/'selection.json'
    selection=json.loads(selection_path.read_text(encoding='utf-8'))
    manifest_path=folder/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if (selection!={'version':1,'search_url':SEARCH_URL,'endpoint':ENDPOINT,'payload':PAYLOAD}
            or manifest.get('version')!=1 or manifest.get('search_url')!=SEARCH_URL
            or manifest.get('endpoint')!=ENDPOINT or manifest.get('payload')!=PAYLOAD
            or manifest.get('selection_sha256')!=sha256(selection_path.read_bytes()).hexdigest()
            or not isinstance(manifest.get('pages'),list) or type(manifest.get('total_results')) is not int
            or type(manifest.get('total_pages')) is not int or type(manifest.get('page_size')) is not int
            or len(manifest['pages'])!=manifest['total_pages']):
        raise IntakeError('北泰馆藏检索条件或批次清单不符。')
    records=[];seen=set()
    for number,entry in enumerate(manifest['pages'],1):
        path=folder/f'page-{number:03d}.json';receipt_path=folder/f'page-{number:03d}.receipt.json'
        raw=path.read_bytes();digest=sha256(raw).hexdigest()
        receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
        if (entry.get('page')!=number or entry.get('path')!=path.name or entry.get('sha256')!=digest
                or receipt!={'page':number,'url':ENDPOINT.format(number),'sha256':digest,'retrieved_at':entry.get('retrieved_at')}
                or not receipt['retrieved_at']):raise IntakeError('北泰检索分页与凭据不符。')
        document=parse_page(raw,number);page=document['pagination']
        if ((page['totalResults'],page['totalPages'],page['pageSize'])!=(manifest['total_results'],manifest['total_pages'],manifest['page_size'])
                or entry.get('records')!=len(document['results'])):raise IntakeError('北泰检索分页数与清单不符。')
        for item in document['results']:
            identifier=int(IDENTIFIER.fullmatch(item['resource_id']).group(1))
            if identifier in seen:raise IntakeError(f'北泰馆藏编号重复：{identifier}')
            seen.add(identifier);records.append(Manuscript(identifier,number,path,digest,item))
    if len(records)!=manifest['total_results']:raise IntakeError('北泰馆藏唯一记录数不符。')
    return manifest,records


def lanna_evidence(item,groups):
    fields=selected_fields(item.record)
    codes=fields.get('otherIdentifier.code_number',{}).get('none',[])
    candidates=sorted({other.identifier for code in codes for other in groups.get(code,[]) if other.identifier!=item.identifier})
    return {'馆藏字段':fields,'署名与许可':attribution(item.record) or '未提供',
            '相同档号馆藏候选':candidates,
            '字段说明':'馆藏地及坐标为保管地点线索；手稿日期不是叙事年代；馆藏号不是国际标准码。'}


def lanna_cards(folder: Path):
    manifest,records=load_snapshot(folder)
    groups=defaultdict(list)
    for item in records:
        for code in selected_fields(item.record).get('otherIdentifier.code_number',{}).get('none',[]):
            if code.strip():groups[code].append(item)
    manifest_path=folder/'manifest.json';manifest_hash=sha256(manifest_path.read_bytes()).hexdigest()
    common={'genre':'unclassified','credibility_tier':'B','is_fictional_quarantine':False,
            'temporal':None,'standards':{},'audit':{'created_at':date.today(),'reviewed_by_human':False}}
    root={**common,'id':ROOT_ID,'title':'北泰数字手稿馆 · Folk Tale 类馆藏',
          'node_type':'myth_corpus','z_layer':2,
          'spatial':{'precision':'culture_region','location_name':'泰国北部（馆藏范围；非叙事地点）','culture_region':'Southeast Asia · Thailand'},
          'sources':[{'citation':'Digital Library of Northern Thai Manuscripts，Folk Tale 分类检索快照。',
                      'type':'lanna_manifest','url':SEARCH_URL,
                      'locator':f"Folk Tale / {manifest['total_results']} 件 / {manifest['total_pages']} 页",
                      'local_path':display_path(manifest_path),'content_sha256':manifest_hash}]}
    yield NodeMetadata.model_validate(root),(
        f"\n## 馆藏范围\n\n馆方 Folk Tale 分类检索含 {manifest['total_results']} 件手稿馆藏，不等于独立故事数量。"
        '来源覆盖多种语言和文字，具体内容、抄本、版本及社区要求仍须逐件核查。'
        '馆藏地及其坐标是保管地点线索，不能直接作为叙事或采录地点；手稿日期不是故事发生年代。'
        '未下载影像或转写原文。馆方声明的许可、归属与可能的例外须按单件核对。\n')
    for item in records:
        data=lanna_evidence(item,groups);fields=data['馆藏字段']
        labels=item.record.get('label',{})
        names=[value.strip() for values in labels.values() if isinstance(values,list) for value in values if isinstance(value,str) and value.strip()] if isinstance(labels,dict) else []
        title=names[0] if names else f'馆藏 {item.identifier}'
        aliases=list(dict.fromkeys(value for key in ('title','dc:identifier','otherIdentifier.code_number')
            for values in fields.get(key,{}).values() for value in values if value.strip()))
        places=[value for values in fields.get('full_location_name',{}).values() for value in values if value.strip()]
        metadata={**common,'id':f'{PREFIX}{item.identifier}','title':f'北泰馆藏手稿 · {title}',
            'aliases':aliases,'node_type':'myth_corpus','z_layer':2,
            'spatial':{'precision':'culture_region','location_name':'馆藏地（非采录地或故事发生地）：'+(' / '.join(places) or '未登记'),
                       'culture_region':'Southeast Asia · Thailand'},
            'relations':[{'type':'PART_OF_MACRO_TREND','target':ROOT_ID,'note':'同属馆藏检索集合，不表示传播关系。'}],
            'sources':[{'citation':data['署名与许可'],'type':'lanna_search','url':SEARCH_URL,
                        'locator':f'Folk Tale / 第 {item.page} 页 / 馆藏 manifest {item.identifier}',
                        'local_path':display_path(item.snapshot),'content_sha256':item.digest},
                       {'citation':'北泰数字手稿馆单件页面与原始影像（本地未下载）。','type':'lanna_viewer',
                        'url':VIEWER.format(item.identifier),'locator':f'manifest {item.identifier} / 手稿影像'}]}
        body=('\n## 原始馆藏字段\n\n'+literal_block(json.dumps(data,ensure_ascii=False,indent=2))
              +'\n\n## 原图与复核\n\n这是手稿馆藏元数据，未下载影像，也未转录正文；可通过馆方单件链接查看原图。'
               '馆藏地点和坐标原字段不能自动作为采录地或故事发生地；馆藏日期不自动成为叙事年代。'
               '相同档号仅为待核候选，标准码须从本地码表人工核定。\n')
        yield NodeMetadata.model_validate(metadata),body
