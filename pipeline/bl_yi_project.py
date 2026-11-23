"""Describe a transparent, non-exhaustive screen of the full EAP081 catalogue."""
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.fetch_bl_yi_project import page_url
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_cn_bl_eap081_project'
GROUP_PREFIX = 'corpus_cn_bl_eap081_'
GROUP_ID = GROUP_PREFIX + '022'
CASE_PREFIX = 'case_cn_bl_eap081_'
OLD_GROUP = 'corpus_cn_bl_yi_eap081_25'

LABELS = (
    ('口述／口传', r'\boral\b'), ('故事', r'\bstor(?:y|ies)(?:book)?\b'),
    ('传说', r'\blegends?\b'), ('神话', r'\bmyths?\b'), ('民间', r'\bfolk(?:lore|tales?)?\b'),
    ('故事类型词', r'\btales?\b'), ('史诗', r'\bepics?\b'), ('叙事', r'\bnarratives?\b'),
    ('起源', r'\borigins?\b'),
)


def hints(row: dict) -> list[str]:
    fields = row['fields']
    text = ' '.join((fields.get('Title') or '', fields.get('Scope & Content') or ''))
    return [label for label, pattern in LABELS if re.search(pattern, text, re.I)]


def node_id(row: dict) -> str:
    match = re.fullmatch(r'EAP081/(\d{1,3})/(\d{1,3})', row['shelfmark'])
    if not match or not row['record_id'].startswith('040-'):
        raise IntakeError(f"项目记录不是本次可建卡的两级单件：{row['shelfmark']}")
    return f'{CASE_PREFIX}{int(match.group(1)):03}_{int(match.group(2)):03}'


def old_id(row: dict) -> str | None:
    if row['shelfmark'] == 'EAP081/25': return OLD_GROUP
    match = re.fullmatch(r'EAP081/25/([1-6])', row['shelfmark'])
    return OLD_GROUP + '_' + f'{int(match.group(1)):02}' if match else None


def reason(row: dict) -> list[str]:
    if not row['record_id'].startswith('040-') or old_id(row): return []
    result = hints(row)
    if re.fullmatch(r'EAP081/22/\d{1,2}', row['shelfmark']): result.insert(0, 'EAP081/22 完整馆藏上下文')
    return result


def selected(rows: list[dict]) -> list[dict]:
    """Only catalogue keywords or the explicitly chosen nine-item context; not story classification."""
    chosen = [row for row in rows if reason(row)]
    for row in chosen: node_id(row)
    return chosen


def group_id(row: dict) -> str:
    match = re.fullmatch(r'EAP081/(\d{1,3})', row['shelfmark'])
    if not match or not row['record_id'].startswith('032-'):
        raise IntakeError(f"项目记录不是父级馆藏：{row['shelfmark']}")
    return GROUP_PREFIX + f'{int(match.group(1)):03}'


def parent_ref(row: dict) -> str:
    return 'EAP081/' + row['shelfmark'].split('/')[1]


def normalized_title(row: dict) -> str:
    return ' '.join((row['fields'].get('Title') or '').casefold().split())


def title_peers(row: dict, rows: list[dict]) -> list[str]:
    name = normalized_title(row)
    return [candidate['shelfmark'] for candidate in rows if candidate['record_id'].startswith('040-')
            and candidate['shelfmark'] != row['shelfmark'] and name and normalized_title(candidate) == name]


def image_count(extent: str | None) -> int | None:
    match = re.fullmatch(r'\s*(\d+)\s+TIFF images?\s*', extent or '', re.I)
    return int(match.group(1)) if match else None


def viewer_url(row: dict, fields: dict) -> str | None:
    """Link only the exact item URL printed in the catalogue; do not fetch it."""
    expected = 'https://eap.bl.uk/archive-file/' + row['shelfmark'].replace('/', '-')
    raw = fields.get('Digitised Content') or ''
    if raw == expected or raw.startswith(expected + ' '): return expected
    return None


def group_evidence(parent: dict, fields: dict, rows: list[dict], item_details: list[tuple]) -> dict:
    all_children = [r for r in rows if r['record_id'].startswith('040-') and parent_ref(r) == parent['shelfmark']]
    included = [r for r in selected(rows) if parent_ref(r) == parent['shelfmark']]
    by_shelf = {row['shelfmark']: detail for row, _, detail in item_details}
    counts = [image_count(by_shelf[r['shelfmark']].get('Extent')) for r in included]
    complete = len(included) == len(all_children) and all(row['shelfmark'] in by_shelf for row in included)
    return {'馆方档号': parent['shelfmark'], '馆方题名': fields.get('Title'), '馆方内容说明': fields.get('Scope & Content'),
            '馆方范围原字段': fields.get('Extent'), '馆方语言原字段': fields.get('Languages'),
            '馆方文字原字段': fields.get('Scripts'), '馆方起始日期原字段': fields.get('Start Date'),
            '馆方结束日期原字段': fields.get('End Date'), '馆方日期范围原字段': fields.get('Date Range'),
            '馆方访问条件原字段': fields.get('User Conditions'), '馆方原件归属说明': fields.get('Information About Originals'),
            '馆方保管历史': fields.get('Custodial History'), '馆方排列说明': fields.get('Arrangement'),
            '项目检索所列单件数': len(all_children), '本批入选单件数': len(included), '本批覆盖该馆藏全部检索单件': complete,
            '完整馆藏单件影像数字相加': sum(counts) if complete and counts and all(n is not None for n in counts) else None,
            '范围说明': '检索单件、影像与独立故事不是同一单位；入选关键词仅为线索，未入选也可能含相关内容。',
            '权限说明': '馆方目录文字 CC BY 4.0（如有例外须依单件说明）；手稿影像、原件与社区要求另核。'}


def item_evidence(row: dict, fields: dict, parent: dict, parent_fields: dict, rows: list[dict], index_manifest: dict) -> dict:
    page = index_manifest['pages'][row['page'] - 1]
    return {'馆方档号': row['shelfmark'], '馆方记录号': row['record_id'], '馆方题名': fields.get('Title'),
            '馆方内容说明': fields.get('Scope & Content'), '馆方范围原字段': fields.get('Extent'),
            '馆方语言原字段': fields.get('Languages'), '馆方文字原字段': fields.get('Scripts'),
            '馆方起始日期原字段': fields.get('Start Date'), '馆方结束日期原字段': fields.get('End Date'),
            '馆方日期范围原字段': fields.get('Date Range'), '馆方数字内容原字段': fields.get('Digitised Content'),
            '馆方影像入口（未取得）': viewer_url(row, fields),
            '馆方单件访问条件原字段': fields.get('User Conditions'), '馆方原件归属说明': fields.get('Information About Originals'),
            '父级馆藏档号': parent['shelfmark'], '父级馆藏题名': parent_fields.get('Title'),
            '父级内容说明': parent_fields.get('Scope & Content'), '父级访问条件原字段': parent_fields.get('User Conditions'),
            '筛查线索（非体裁判定）': reason(row), '检索摘要原字段': row['fields'].get('Scope & Content'),
            '检索页面SHA256': page['sha256'], '检索观察时间': page['observed_at'],
            '同题目录档号（忽略大小写与空白）': title_peers(row, rows),
            '比对限制': '同题仅供人工查找，不能证明同一版本、作品或演述；目录检索摘要可能截断。'}


def root_evidence(index_manifest: dict, rows: list[dict], parents: list[tuple], items: list[tuple]) -> dict:
    chosen = selected(rows)
    return {'馆方项目': index_manifest['project'], '项目检索目录行数': len(rows),
            '其中父级馆藏行数': sum(r['record_id'].startswith('032-') for r in rows),
            '其中单件行数': sum(r['record_id'].startswith('040-') for r in rows),
            '本批单件候选数': len(chosen), '本批涉及父级馆藏数': len(parents),
            '本批已保存的单件目录页数': len(items), '已有 EAP081/25 目录行数': sum(old_id(r) is not None for r in rows),
            '筛查线索计数（可重复）': dict(sorted(Counter(label for row in chosen for label in reason(row)).items())),
            '筛选范围': '仅按检索题名或摘要出现的词筛查，并完整保留 EAP081/22 的九件上下文；关键词不等于故事。',
            '覆盖限制': '未命中不代表无关；全部检索行保留供人工查阅，检索摘要可能截断。',
            '快照限制': '项目检索首末页及详情采集后的首末页重复核对；中间页未复取，不能保证同一时刻。',
            '权利限制': '目录文字 CC BY 4.0（如有例外须依单件说明）；未获取影像或音视频，原件权利及相关社区要求另核。'}


def source_set(index_folder: Path, index_manifest: dict, details_folder: Path,
               row: dict | None = None, parent: dict | None = None, item_fields: dict | None = None) -> list[dict]:
    from pipeline.fetch_bl_yi_project_details import filename
    def source(kind, url, locator, path, citation):
        return {'type': kind, 'url': url, 'locator': locator, 'citation': citation,
                'local_path': display_path(path), 'content_sha256': sha256(path.read_bytes()).hexdigest()}
    indexed = row or parent
    page = indexed['page'] if indexed else 1
    entry = index_manifest['pages'][page - 1]
    index_citation = 'British Library Archives and Manuscripts Catalogue；项目检索目录文字 CC BY 4.0（例外另核）。'
    detail_citation = 'British Library Archives and Manuscripts Catalogue, EAP081；目录文字 CC BY 4.0（例外另核），原件权利另核。'
    result = [source('bl_yi_project_index', entry['url'], f"项目检索页 {page}" + (f" / {indexed['shelfmark']}" if indexed else ''),
                     index_folder / entry['path'], index_citation),
              source('bl_yi_project_index_manifest', page_url(1), '项目检索快照清单', index_folder / 'manifest.json', '项目完整检索快照清单。'),
              source('bl_yi_project_details_manifest', page_url(1), '父级及入选单件快照清单', details_folder / 'manifest.json', '选取及逐件馆方目录快照清单。')]
    if parent is not None:
        result.append(source('bl_yi_project_parent', parent['url'], parent['shelfmark'] + ' / 父级馆藏',
                             details_folder / filename(parent), detail_citation))
    if row is not None:
        result.append(source('bl_yi_project_item', row['url'], row['shelfmark'] + ' / 馆方单件',
                             details_folder / filename(row), detail_citation))
        viewer = viewer_url(row, item_fields or {})
        if viewer:
            result.append({'type': 'bl_yi_project_viewer', 'url': viewer,
                           'locator': row['shelfmark'] + ' / 馆方影像入口（未取得）',
                           'citation': '馆方目录所列影像入口；本地未取得影像，访问和使用条件须另核。'})
    return result


def cards(index_folder: Path, details_folder: Path):
    from pipeline.fetch_bl_yi_project import load_snapshot as load_index
    from pipeline.fetch_bl_yi_project_details import load_snapshot as load_details
    index_manifest, rows = load_index(index_folder)
    _, parents, items = load_details(details_folder, index_folder)
    parent_by_ref = {r['shelfmark']: (r, f) for r, _, f in parents}
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False, 'spatial': {'precision': 'culture_region',
              'location_name': '云南彝文档案项目；具体原件来源与叙事地点逐条待核', 'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    summary = root_evidence(index_manifest, rows, parents, items)
    model = {**common, 'id': ROOT_ID, 'title': '云南彝文档案项目 · 口传与叙事目录筛查',
             'sources': source_set(index_folder, index_manifest, details_folder)}
    body = ('\n## 项目检索与筛查范围\n\n' + literal_block(json.dumps(summary, ensure_ascii=False, indent=2))
            + '\n\n## 复核范围\n\n全部项目检索行均保留在筛查清单。依据题名或目录摘要词汇选出的单件并非已确认故事；'
              'EAP081/22 九件另作完整馆藏上下文，混有仪式等材料。未命中不表示无关。'
              '已保存馆方目录网页，未获取手稿影像或转录；目录文字 CC BY 4.0（例外另核），'
              '手稿权利、社区要求、地点、年代和标准码均须人工核实。\n')
    yield NodeMetadata.model_validate(model), body
    for parent, _, fields in parents:
        data = group_evidence(parent, fields, rows, items)
        model = {**common, 'id': group_id(parent), 'title': f"云南彝文档案 · {parent['shelfmark']} 馆藏",
                 'aliases': [parent['fields']['Title']], 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                     'note': '同属项目筛查范围，不表示故事、版本或演述存在关联。'}],
                 'sources': source_set(index_folder, index_manifest, details_folder, parent=parent)}
        body = ('\n## 馆方父级馆藏字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n按馆方档号保留馆藏上下文，不能把藏家、抄写者和讲述者自动等同。'
                  '未取得影像或转录；项目检索、馆藏范围、单件与社区条件须分别核实。\n')
        yield NodeMetadata.model_validate(model), body
    for row, _, fields in items:
        parent, parent_fields = parent_by_ref[parent_ref(row)]
        data = item_evidence(row, fields, parent, parent_fields, rows, index_manifest)
        model = {**common, 'node_type': 'case', 'z_layer': 1, 'id': node_id(row),
                 'title': f"云南彝文档案 · {row['shelfmark']}", 'aliases': [row['fields']['Title']],
                 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': group_id(parent),
                                'note': '同属馆方父级馆藏；不代表同篇故事、同一版本或采录地点。'}],
                 'sources': source_set(index_folder, index_manifest, details_folder, row, parent, fields)}
        body = ('\n## 馆方单件与父级字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n目录条目可能包含多篇材料，检索词不能替代阅读原件；同题记录不自动合并。'
                  '未下载影像或转录，不能把馆方题名翻译当作逐篇原文。原件、讲述者、地点、年代和权限须回查；'
                  '坐标及标准码留空，标准码须依据原文与本地码表人工匹配。\n')
        yield NodeMetadata.model_validate(model), body
