"""Stage Khmu recording catalogue entries and explicitly provisional comparisons."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata
from pipeline.pangloss_japhug import recording_evidence
from pipeline.pangloss_na import json_object, load_snapshots

CORPUS_NAME = 'Khmu'
CORPUS_URL = 'https://pangloss.cnrs.fr/corpus/Khmu'
ROOT_ID = 'corpus_sea_khmu_pangloss'
CASE_PREFIX = 'case_sea_khmu_'
MEMBER_KEYS = ('id', 'title', 'speakers', 'recorded', 'doi', 'url')


def speaker_identity_unverified(value: str) -> bool:
    return not value.strip() or bool(re.search(r'(?<![A-Za-z])unknown(?![A-Za-z])|\ba local erudite\b', value, re.IGNORECASE))


def title_suggests_multiple_or_part(value: str) -> bool:
    return bool(re.search(r'divers|\b(?:histoires|légendes|chants|prières|trois|quatre|plusieurs)\b|partie|\bpart\b|suite|\bfin\b|inachev',
                          value, re.IGNORECASE))


def title_mentions_other_language(value: str) -> bool:
    return bool(re.search(r'\b(?:nhuan|lao)\b', value, re.IGNORECASE))


def compare_recording_ranges(catalogue: str, detail: str | None) -> bool | None:
    """Compare explicitly delimited ranges without rewriting either original field."""
    if not detail:
        return None
    def endpoints(value: str) -> tuple[str,str] | None:
        match = (re.fullmatch(r'start=(\d{4}(?:-\d{2}){0,2});\s*end=(\d{4}(?:-\d{2}){0,2})',value)
                 or re.fullmatch(r'(\d{4}-\d{2}-\d{2})-(\d{4}-\d{2}-\d{2})',value)
                 or re.fullmatch(r'(\d{4})-(\d{4})',value))
        if not match:
            return None
        start,end = match.groups()
        if len(start) != len(end):
            return None
        try:
            for part in (start,end):
                if len(part) == 4:
                    date(int(part),1,1)
                elif len(part) == 7:
                    date(int(part[:4]),int(part[5:]),1)
                else:
                    date.fromisoformat(part)
        except ValueError:
            return None
        return (start,end) if start <= end else None
    first,second = endpoints(catalogue),endpoints(detail)
    if not first or not second or len(first[0]) != len(second[0]):
        return None
    return first == second


def load_comparisons(path: Path, corpus: Path, catalog: dict) -> dict:
    document = json_object(path)
    if (document.get('version') != 1 or document.get('corpus_url') != CORPUS_URL
            or document.get('catalogue_sha256') != sha256(corpus.read_bytes()).hexdigest()
            or not isinstance(document.get('scope'), str) or not document['scope'].strip()
            or not isinstance(document.get('groups'), list) or not document['groups']):
        raise IntakeError('Khmu 对照索引与馆方目录快照不符。')
    group_ids, members = set(), set()
    for group in document['groups']:
        if (not isinstance(group, dict) or not re.fullmatch(r'[a-z][a-z0-9_]*', str(group.get('id', '')))
                or group['id'] in group_ids or any(not isinstance(group.get(k), str) or not group[k].strip() for k in ('label','note'))
                or not isinstance(group.get('members'), list) or len(group['members']) < 2):
            raise IntakeError('Khmu 对照分组无效或重复。')
        group_ids.add(group['id'])
        for member in group['members']:
            if not isinstance(member, dict):
                raise IntakeError('Khmu 对照项目字段无效。')
            number = member.get('id')
            if (not isinstance(number, str) or not re.fullmatch(r'\d{7}', number) or number in members
                    or number not in catalog or set(member) != set(MEMBER_KEYS)
                    or any(member[key] != catalog[number][key] for key in MEMBER_KEYS)):
                raise IntakeError(f'Khmu 对照项目与馆方目录不符或重复：{number}')
            members.add(number)
    return document


def comparison_evidence(group: dict | None) -> dict | None:
    if not group:
        return None
    return {'id': group['id'], 'label': group['label'], 'note': group['note'],
            'members': [{**member, 'node_id': CASE_PREFIX + member['id']} for member in group['members']]}


def khmu_cards(corpus: Path, selection: Path, snapshots: Path, comparisons: Path):
    catalog, selected, details = load_snapshots(snapshots, corpus, selection,
                                                corpus_name=CORPUS_NAME, corpus_url=CORPUS_URL)
    compared = load_comparisons(comparisons, corpus, catalog)
    selected_by_id = {number: group for group in selected['groups'] for number in group['ids']}
    compared_by_id = {member['id']: group for group in compared['groups'] for member in group['members']}
    corpus_hash = sha256(corpus.read_bytes()).hexdigest()
    selection_hash = sha256(selection.read_bytes()).hexdigest()
    comparison_hash = sha256(comparisons.read_bytes()).hexdigest()
    common = {'genre': 'unclassified', 'credibility_tier': 'B', 'is_fictional_quarantine': False,
              'spatial': {'precision': 'culture_region', 'location_name': 'Khmu 语馆藏（单条录音地点待核）',
                          'culture_region': 'Khmu 语录音馆藏'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}

    def catalog_source(locator: str) -> dict:
        return {'citation': 'CNRS-LACITO，Pangloss Khmu 馆藏目录，保留目录网页快照。',
                'type': 'pangloss_khmu_catalogue', 'url': CORPUS_URL, 'locator': locator,
                'local_path': display_path(corpus), 'content_sha256': corpus_hash}

    def selection_source(locator: str) -> dict:
        return {'citation': 'Astraia 首轮详情选取索引；分组只表示选取方法。',
                'type': 'pangloss_khmu_selection', 'url': CORPUS_URL, 'locator': locator,
                'local_path': display_path(selection), 'content_sha256': selection_hash}

    def comparison_source(locator: str) -> dict:
        return {'citation': 'Astraia 目录字段对照索引；关系仅供人工核查。',
                'type': 'pangloss_khmu_comparison', 'url': CORPUS_URL, 'locator': locator,
                'local_path': display_path(comparisons), 'content_sha256': comparison_hash}

    root = {**common, 'id': ROOT_ID, 'title': '东南亚 Khmu 口语录音目录 · Pangloss',
            'node_type': 'myth_corpus', 'z_layer': 2,
            'sources': [catalog_source('Khmu / 资源目录'), selection_source('首轮详情选取方法'),
                        comparison_source('目录题名对照索引')]}
    body = (f'\n## 馆藏和核查范围\n\n本次目录快照列出 {len(catalog)} 条 Khmu 录音资源，'
            f'其中 {len(details)} 条已保存并核验单条详情。馆藏兼含叙事、歌唱、祈祷、访谈、'
            '词汇和其他材料；一条录音也可能包含多个故事或故事片段，录音件数不是故事数。'
            '首轮按题名及资料形式目的性选择，不是随机样本。题名相似或分段提示仅供回听和版本对照，'
            '不证明同一次演述、历史事件或传播。录音地、讲述者来源地与叙事发生地须分别核查；'
            '馆藏名称不保证每段都只用 Khmu 语，部分目录题名还提到其他语言。'
            '坐标、图谱年代与标准码留空。未复制音视频或转写正文，许可及社区要求逐条核对。\n')
    yield NodeMetadata.model_validate(root), body

    for number, row in catalog.items():
        fields, group, comparison = details.get(number), selected_by_id.get(number), compared_by_id.get(number)
        if fields:
            detail_path = snapshots / 'records' / number / 'page.html'
            source = {'citation': 'CNRS-LACITO，Pangloss 单条录音元数据；具体许可见原字段。',
                      'type': 'pangloss_khmu_detail', 'url': row['url'],
                      'doi': row['doi'].removeprefix('https://doi.org/'), 'locator': f'录音 {number}',
                      'local_path': display_path(detail_path), 'content_sha256': sha256(detail_path.read_bytes()).hexdigest()}
        else:
            source = {'citation': 'CNRS-LACITO，Pangloss 单条录音页面；详情尚未采集，需回查。',
                      'type': 'pangloss_khmu_original', 'url': row['url'],
                      'doi': row['doi'].removeprefix('https://doi.org/'), 'locator': f'录音 {number}'}
        sources = [catalog_source(f'Khmu / DOI {number}'), source,
                   selection_source(group['label'] if group else '未选入首轮详情'),
                   comparison_source(comparison['label'] if comparison else '无目录对照分组')]
        data = recording_evidence(row, fields, group)
        comparison_data = comparison_evidence(comparison)
        aliases = [row['title']]
        if fields:
            aliases.extend(item['title'] for item in fields['alternate_titles'] if item['title'] not in aliases)
        relations = [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                      'note': '同一馆藏目录的录音资源；不表示同一故事、采录地点或传播关系。'}]
        if comparison and number != comparison['members'][0]['id']:
            relations.append({'type': 'COMPARED_WITH', 'target': CASE_PREFIX + comparison['members'][0]['id'],
                              'note': comparison['note']})
        model = {**common, 'id': CASE_PREFIX + number, 'title': f"Khmu 录音目录 · {row['title']}",
                 'aliases': aliases, 'node_type': 'case', 'z_layer': 1, 'relations': relations, 'sources': sources}
        body = ('\n## 馆方录音目录字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2)))
        if comparison_data:
            body += '\n\n## 目录对照候选（待复核）\n\n' + literal_block(json.dumps(comparison_data, ensure_ascii=False, indent=2))
        body += ('\n\n## 原音、转写与复核\n\n本卡只索引一条馆藏录音，不自动判定为一篇故事；'
                 '一条录音可能包含多个故事、片段、歌唱、祈祷或访谈。相似题名与分段提示须回听，'
                 '不证明同一演述、母题、传播或历史事件。讲述者籍贯与具体录音地点不是同一字段；'
                 '录音日期不是叙事年代，馆藏名称不保证每段都只用 Khmu 语。音视频与转写正文未复制；'
                 '具体许可和相关社区要求须逐项核查。\n')
        yield NodeMetadata.model_validate(model), body
