"""Turn a minimal Palu'e collection field index into review-only drafts."""
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.fetch_palue_inventory import FIELDS, PAGE_SIZE, page_url
from pipeline.fetch_palue_sample import COLLECTION_ID, COLLECTION_URL, HOST
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_sea_palue_audio'
PREFIX = 'case_sea_palue_sd1_'
MARKER = 'palue_original'
POLICY = 'https://manoa.hawaii.edu/library/research/scholarly-communication/repositories/policies-guidelines/copyright-policy/'
GENRE_SCOPES = {'目录说明显式 Genre 标签；未核对录音', '说明含 Genre 标签但无法安全提取，须回查',
                '未提取到显式 Genre 标签；不代表无体裁'}


def _receipt(receipt: object, page: int) -> bool:
    return (isinstance(receipt, dict) and receipt.get('url') == page_url(page)
            and isinstance(receipt.get('sha256'), str) and bool(re.fullmatch(r'[a-f0-9]{64}', receipt['sha256']))
            and isinstance(receipt.get('bytes'), int) and receipt['bytes'] > 0
            and isinstance(receipt.get('observed_at'), str) and bool(receipt['observed_at']))


def load_inventory(folder: Path) -> tuple[dict, list[dict]]:
    """Validate all local field pages and receipts; raw HTTP bodies were not retained."""
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    total, pages = manifest.get('total'), manifest.get('pages')
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or manifest.get('collection_url') != COLLECTION_URL or manifest.get('scope_uuid') != COLLECTION_ID
            or manifest.get('page_size') != PAGE_SIZE or not isinstance(total, int) or not 0 < total <= 5000
            or not isinstance(pages, list) or len(pages) != (total + PAGE_SIZE - 1) // PAGE_SIZE):
        raise IntakeError('Palu’e 目录清单范围、版本或分页异常。')
    rows = []
    for number, entry in enumerate(pages):
        filename = f'page-{number:03d}.json'
        raw = (folder / filename).read_bytes()
        expected_count = min(PAGE_SIZE, total - number * PAGE_SIZE)
        if (entry.get('page') != number or entry.get('path') != filename
                or entry.get('sha256') != sha256(raw).hexdigest() or entry.get('count') != expected_count
                or not _receipt(entry.get('response'), number)):
            raise IntakeError(f'Palu’e 第 {number + 1} 页字段索引或凭据异常。')
        page = json.loads(raw.decode('utf-8'))
        if page.get('version') != 1 or page.get('page') != number or not isinstance(page.get('items'), list) or len(page['items']) != expected_count:
            raise IntakeError('Palu’e 字段索引页结构或数量异常。')
        for row in page['items']:
            if not isinstance(row, dict): raise IntakeError('Palu’e 目录项格式异常。')
            identifier, uid, handle, fields = row.get('id'), row.get('uuid'), row.get('handle'), row.get('fields')
            hint, scope = row.get('genre_hint'), row.get('genre_hint_scope')
            if (not isinstance(identifier, str) or not re.fullmatch(r'SD1-\d{3}', identifier)
                    or not isinstance(uid, str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', uid)
                    or not isinstance(handle, str) or not re.fullmatch(r'10125/\d+', handle)
                    or row.get('item_url') != f'https://{HOST}/items/{uid}' or not isinstance(fields, dict)
                    or set(fields) != set(FIELDS) or any(not isinstance(v, list) or any(not isinstance(s, str) for s in v) for v in fields.values())
                    or fields['dc.title'] != [identifier] or scope not in GENRE_SCOPES
                    or (hint is not None and (not isinstance(hint, str) or not re.fullmatch(r"[A-Za-z0-9 /()&,'’+\-]{1,55}", hint) or len(hint.split()) > 7))
                    or ((hint is not None) != (scope == '目录说明显式 Genre 标签；未核对录音'))):
                raise IntakeError(f'Palu’e 目录字段格式异常：{identifier}')
            rows.append({**row, 'page': number})
    if ([row['id'] for row in rows] != sorted(row['id'] for row in rows)
            or any(len({row[key] for row in rows}) != total for key in ('id', 'uuid', 'handle'))):
        raise IntakeError('Palu’e 目录跨页排序或唯一标识异常。')
    checks = manifest.get('boundary_checks')
    expected = sorted({0, len(pages) - 1})
    if (not isinstance(checks, list) or [entry.get('page') for entry in checks] != expected
            or any(not _receipt(entry.get('response'), entry['page']) for entry in checks)):
        raise IntakeError('Palu’e 首页与末页重复核验凭据异常。')
    return manifest, rows


def node_id(row: dict) -> str:
    return PREFIX + row['id'][-3:]


def group_evidence(manifest: dict, rows: list[dict]) -> dict:
    labels = Counter(label for row in rows for label in row['fields']['dc.subject.language'])
    selected = sum('Sound' in row['fields']['dc.type.dcmi'] for row in rows)
    return {'馆藏目录对象数': len(rows), '类型字段显式含 Sound': selected, '类型字段未列 Sound': len(rows) - selected,
            '计数说明': '目录对象、音频文件及独立故事不是相同单位；未列 Sound 不代表没有录音。',
            '主题语种字段计数': dict(sorted(labels.items())), '采集核验': '本地字段索引逐页校验；采集期间仅重复核验首页与末页。',
            '原响应哈希说明': '未保留原始响应，不能从本地字段重算原响应哈希。',
            '权利说明': '权限须逐件及按相关社区要求复核，字段为空不等于无限制。'}


def evidence(row: dict, manifest: dict) -> dict:
    f, entry = row['fields'], manifest['pages'][row['page']]
    return {'馆方编号': row['id'], '馆方单件链接': row['item_url'], '永久标识': 'https://hdl.handle.net/' + row['handle'],
            '类型字段 dc.type.dcmi': f['dc.type.dcmi'], '语言学类型字段': f['dc.type.linguistictype'],
            '目录显式 Genre 标签': row['genre_hint'], '标签范围': row['genre_hint_scope'],
            '说话人（speaker）字段': f['dc.contributor.speaker'], '采录者（recorder）字段': f['dc.contributor.recorder'],
            '研究者字段': f['dc.contributor.researcher'], '存交者字段': f['dc.contributor.depositor'],
            '顾问字段': f['dc.contributor.consultant'], '转写者字段': f['dc.contributor.transcriber'],
            '译者字段': f['dc.contributor.translator'], '日期起始原字段（性质待核）': f['dc.date.begin'],
            '日期结束原字段（性质待核）': f['dc.date.finish'], '主题语种原字段': f['dc.subject.language'],
            '主题语种代码原字段': f['dc.subject.languagecode'], '内容语言原字段': f['dc.content.language'],
            '内容语言代码原字段': f['dc.content.languagecode'], '国家原字段': f['dc.coverage.iso3166'],
            '地区原字段（未转为事件坐标）': f['dc.description.region'], '格式时长原字段': f['dc.format.extent'],
            '权利原字段': f['dc.rights'], '访问权利原字段': f['dc.rights.access'],
            '检索页码（从零计）': row['page'], '检索接口页': entry['response']['url'], '字段索引 SHA256': entry['sha256'],
            '原始响应 SHA256（未保存原响应）': entry['response']['sha256'], '观察时间': entry['response']['observed_at']}


def cards(folder: Path):
    manifest, rows = load_inventory(folder)
    receipt = folder / 'manifest.json'
    manifest_source = {'citation': 'Palu’e 馆藏本地字段索引清单；原始响应、媒体和转写未保存。',
        'type': 'palue_manifest', 'url': COLLECTION_URL, 'locator': '公开检索与字段索引清单',
        'local_path': display_path(receipt), 'content_sha256': sha256(receipt.read_bytes()).hexdigest()}
    def index_source(row):
        entry = manifest['pages'][row['page']]
        return {'citation': 'University of Hawai‘i, Kaipuleohone 馆藏检索字段索引。',
                'type': 'palue_index', 'url': entry['response']['url'], 'locator': f"目录检索页 {row['page']} / {row['id']}",
                'local_path': display_path(folder / entry['path']), 'content_sha256': entry['sha256']}
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False, 'spatial': {'precision': 'culture_region',
              'location_name': '印尼馆藏总体范围；单条采录与叙事地点待核', 'culture_region': 'Southeast Asia · Indonesia'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    group = group_evidence(manifest, rows)
    root = {**common, 'id': ROOT_ID, 'title': '印尼 Palu’e 口述资料馆藏 · 目录筛查',
            'sources': [index_source(rows[0]), manifest_source]}
    body = ('\n## 馆藏筛查字段\n\n' + literal_block(json.dumps(group, ensure_ascii=False, indent=2))
            + f'\n\n## 复核范围\n\n公开目录对象混合体裁，不能将 Sound 字段或目录对象数直接当作故事数。'
              '日期与地区原字段的具体性质待核，采录时间与地点不等于叙事发生时间与地点；主题语种和内容语言须分别核实。'
              '仅保存必要目录字段，不保存叙事描述、音频或转写。权限字段为空不等于开放，'
              f'请回查[馆方使用说明]({POLICY})与每条记录及相关社区要求；中间分页未重复抽验。\n')
    yield NodeMetadata.model_validate(root), body
    for row in rows:
        if 'Sound' not in row['fields']['dc.type.dcmi']: continue
        original = {'citation': 'Kaipuleohone 单件目录，引用时核对演述者、采录者、编辑、转写和译者及访问日期。',
                    'type': MARKER, 'url': row['item_url'], 'locator': f"馆方单件目录 / {row['id']}"}
        model = {**common, 'node_type': 'case', 'z_layer': 1, 'id': node_id(row),
                 'title': f"印尼 Palu’e 馆藏目录 · {row['id']}", 'aliases': [row['id']],
                 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                                'note': '同属馆藏目录；不证明同一语种、作品、演述或发生地。'}],
                 'sources': [original, index_source(row), manifest_source]}
        text = ('\n## 公开目录核对字段\n\n' + literal_block(json.dumps(evidence(row, manifest), ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n目录 Sound 字段不证明媒体已访问或作品已确认为故事；体裁未分类。'
                  '主题语种与内容语言是不同字段，后者可能包括标注或译文语言。目录日期与地区字段的性质须回查，不能直接作为叙事年代或发生坐标。'
                  '未下载音频、转写或叙事内容。逐件权利、社区要求、具体体裁与语境须回查；坐标、叙事年代和标准码留空。\n')
        yield NodeMetadata.model_validate(model), text
