"""Stage Burma gramophone catalogue records and cautious DSAL candidates for review."""
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.fetch_bl_burma import ROOT_URL, SERIES_URL, load_snapshot as load_bl
from pipeline.fetch_dsal_burma import COLLECTION_URL, TERMS_URL, detail_url, load_snapshot as load_dsal
from pipeline.ingest_agent import literal_block
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_mm_bl_ior_s_2_3'
PREFIX = 'case_mm_bl_ior_s_2_3_'
REMOTE_MARKER = 'dsal_burma_candidate'


def candidates(fields: dict, rows: list[dict]) -> list[dict]:
    """Compare explicit original record identifiers, preserving ambiguous matches."""
    ref = fields.get('Former External References') or ''
    match = re.fullmatch(r'(\d{4})-AK', ref.strip())
    if not match: return []
    target = match.group(1) + 'AK.mp3'
    return [r for r in rows if r['fields']['recording_number'] == target
            and r['fields']['gramophone_records_volume'] == 'Burma']


def half_candidates(fields: dict, rows: list[dict]) -> list[dict]:
    """Weaker textual clue only: BL 1/2 and DSAL HALF, not an established identity."""
    match = re.fullmatch(r'(\d{4}) 1/2-AK', (fields.get('Former External References') or '').strip())
    if not match: return []
    target = match.group(1) + 'HALFAK.mp3'
    return [r for r in rows if r['fields']['recording_number'] == target
            and r['fields']['gramophone_records_volume'] == 'Burma']


def selected_candidate(fields: dict, rows: list[dict]) -> tuple[dict | None, str]:
    exact = candidates(fields, rows)
    if len(exact) == 1: return exact[0], '严格编号候选，待核'
    if exact: return None, '严格编号候选不唯一'
    half = half_candidates(fields, rows)
    if len(half) == 1: return half[0], '1/2 与 HALF 文字线索，待核'
    return None, '半号文字候选不唯一' if half else '未找到候选'


def group_evidence(root: dict, series: dict, records: list, dsal_rows: list[dict]) -> dict:
    counts = Counter(len(candidates(fields, dsal_rows)) for _, _, fields in records)
    return {'馆方档号': root.get('Reference (shelfmark)'), '馆方题名': root.get('Title'),
            '馆方范围': root.get('Extent'), '单件目录数': len(records),
            '系列内容说明': series.get('Scope & Content'), '系列访问条件': series.get('User Conditions'),
            'DSAL三个语言卷目录行数': len(dsal_rows),
            '其中原字段标为Burma的目录行数': sum(r['fields']['gramophone_records_volume'] == 'Burma' for r in dsal_rows),
            '唯一编号候选的唱片数': counts.get(1, 0), '无严格编号候选的唱片数': counts.get(0, 0),
            '存在多个编号候选的唱片数': sum(v for k, v in counts.items() if k > 1),
            '其中唯一半号文字线索的唱片数': sum(selected_candidate(f, dsal_rows)[1] == '1/2 与 HALF 文字线索，待核' for _, _, f in records),
            '计数与对应说明': '目录唱片、数字文件与独立故事为不同单位；跨馆对应为编号或较弱的半号文字候选，须核实版本与录音面。',
            '殖民采集语境': '系列说明记录了某其他分组中的强制采集情节；不能据此推定本缅甸分组的个人遭遇，须逐件调查。',
            '许可与访问': '馆方目录文字 CC BY 4.0；音频、转写、数字资源及相关社区要求和访问条件另核。'}


def item_evidence(child: dict, fields: dict, dsal_rows: list[dict], dsal_manifest: dict) -> dict:
    hits = candidates(fields, dsal_rows)
    match, method = selected_candidate(fields, dsal_rows)
    page = dsal_manifest['pages'][match['page']] if match else None
    return {'馆方档号': child['shelfmark'], '馆方记录号': child['record_id'], '馆方题名': fields.get('Title'),
            '馆方内容说明': fields.get('Scope & Content'), '馆方语言原字段': fields.get('Languages'),
            '馆方文字原字段': fields.get('Scripts'), '馆方起始日期原字段': fields.get('Start Date'),
            '馆方结束日期原字段': fields.get('End Date'), '馆方日期范围原字段': fields.get('Date Range'),
            '馆方唱片原编号': fields.get('Former External References'), '馆方数字内容原字段': fields.get('Digitised Content'),
            '馆方访问条件原字段': fields.get('User Conditions'), '馆方载体': fields.get('Extent'),
            'DSAL严格编号候选数': len(hits), 'DSAL半号文字候选数': len(half_candidates(fields, dsal_rows)),
            'DSAL候选方式': method, 'DSAL候选目录字段': match['fields'] if match else None,
            'DSAL候选页面（未核实）': detail_url(match['volume'], match['fields']['recording_number']) if match else None,
            'DSAL字段索引SHA256': page['sha256'] if page else None,
            'DSAL原响应SHA256（原响应未保存）': page['response']['sha256'] if page else None,
            'DSAL观察时间': page['response']['observed_at'] if page else None,
            '对应限制': '按严格编号或 1/2 与 HALF 文字线索及 Burma 原字段列候选，不证明录音面、内容或版本一致；题名、语言及说话人需另核。'}


def source_set(bl_folder: Path, bl_manifest: dict, dsal_folder: Path, dsal_manifest: dict,
               child: dict | None = None, fields: dict | None = None, dsal_rows: list[dict] | None = None) -> list[dict]:
    def source(kind, url, locator, path, citation):
        return {'type': kind, 'url': url, 'locator': locator, 'citation': citation,
                'local_path': display_path(path), 'content_sha256': sha256(path.read_bytes()).hexdigest()}
    citation = 'British Library Archives and Manuscripts Catalogue；目录文字 CC BY 4.0，录音权利另核。'
    result = [source('bl_burma_root', ROOT_URL, 'IOR/S/2/3 / 缅甸馆藏组', bl_folder / 'root.html', citation),
              source('bl_burma_series', SERIES_URL, 'IOR/S/2 / 系列与访问条件', bl_folder / 'series.html', citation),
              source('bl_burma_manifest', ROOT_URL, '馆方单件及检索快照清单', bl_folder / 'manifest.json', '馆方网页快照清单。'),
              source('dsal_burma_manifest', COLLECTION_URL, 'DSAL 三卷字段索引清单', dsal_folder / 'manifest.json', 'DSAL 本地字段索引清单；原始响应未保存。')]
    if child is None:
        result.append(source('dsal_burma_terms', TERMS_URL, 'DSAL 使用和版权说明', dsal_folder / 'terms.html', 'University of Chicago DSAL 使用说明。'))
    else:
        result.append(source('bl_burma_item', child['url'], child['shelfmark'] + ' / 唱片单件',
                             bl_folder / f"item-{child['number']:02}.html", citation))
        hit, method = selected_candidate(fields or {}, dsal_rows or [])
        if hit is not None:
            page = dsal_manifest['pages'][hit['page']]
            result.append(source('dsal_burma_index', page['response']['url'], hit['fields']['recording_number'] + ' / 卷目录字段',
                                 dsal_folder / page['path'], 'University of Chicago DSAL 卷目录字段；原始响应未保存。'))
            result.append({'type': REMOTE_MARKER, 'url': detail_url(hit['volume'], hit['fields']['recording_number']),
                           'locator': hit['fields']['recording_number'] + ' / 待核候选',
                           'citation': 'University of Chicago DSAL 单件页面候选（' + method + '）；尚未核对页面、媒体及录音面。'})
    return result


def cards(bl_folder: Path, dsal_folder: Path):
    bl_manifest, root, series, records = load_bl(bl_folder)
    dsal_manifest, dsal_rows = load_dsal(dsal_folder)
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False, 'spatial': {'precision': 'culture_region',
              'location_name': '馆方旧称缅甸分组；单条采录和叙事地点待核', 'culture_region': 'Southeast Asia · Myanmar'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    group = group_evidence(root, series, records, dsal_rows)
    model = {**common, 'id': ROOT_ID, 'title': '缅甸多语唱片目录 · IOR/S/2/3',
             'sources': source_set(bl_folder, bl_manifest, dsal_folder, dsal_manifest)}
    body = ('\n## 馆藏组与跨馆候选筛查\n\n' + literal_block(json.dumps(group, ensure_ascii=False, indent=2))
            + '\n\n## 复核范围\n\n本组为殖民时期的语言调查唱片目录，唱片数不等于故事数；'
              '系列列有圣经故事和其他材料，不可自动当作当地口述传统。唱片日期不等于叙事年代。'
              '系列另一个分组记有强制采集，不能推定缅甸样本的个人遭遇，需单件调查。'
              '跨馆对应仅为严格编号或半号文字线索；未获取音频、转写或数字内容。馆方目录文字 CC BY 4.0；'
              '录音、数字资源、社区知情同意与使用条件须单独核实。\n')
    yield NodeMetadata.model_validate(model), body
    for child, _, fields in records:
        number = child['number']; data = item_evidence(child, fields, dsal_rows, dsal_manifest)
        model = {**common, 'node_type': 'case', 'z_layer': 1, 'id': f'{PREFIX}{number:02}',
                 'title': f"缅甸多语唱片目录 · {child['shelfmark']}", 'aliases': [child['title']],
                 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                                'note': '同属馆藏目录；不表示单篇故事或同一叙事发生地。'}],
                 'sources': source_set(bl_folder, bl_manifest, dsal_folder, dsal_manifest, child, fields, dsal_rows)}
        body = ('\n## 馆方唱片与待核候选字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n此卡代表一件唱片目录，可能含多段材料；题名、语种、音面、说话人及跨馆候选须逐件核实。'
                  '未获取音频或转写，不把录音日期和馆藏分组当作叙事年代、发生地或坐标。'
                  '目录文字 CC BY 4.0；数字资源、音频权利和相关社区要求另核。标准码须从本地码表人工匹配，当前留空。\n')
        yield NodeMetadata.model_validate(model), body
