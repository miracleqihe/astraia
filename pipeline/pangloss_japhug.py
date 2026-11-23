"""Stage a Japhug catalogue as reviewable recordings, not presumed folktales."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from pipeline.ingest_agent import literal_block
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata
from pipeline.pangloss_na import compare_credits, compare_dates, load_snapshots

CORPUS_NAME = 'Japhug'
CORPUS_URL = 'https://pangloss.cnrs.fr/corpus/Japhug'
ROOT_ID = 'corpus_cn_japhug_pangloss'
CASE_PREFIX = 'case_cn_japhug_'


def recording_evidence(row: dict, detail: dict | None, group: dict | None) -> dict:
    return {
        '馆方目录题名': row['title'], '馆方目录研究者': row['researchers'],
        '馆方目录讲述者': row['speakers'], '馆方目录录音日期': row['recorded'],
        '馆方时长': row['duration'], '馆方媒介图标': row['formats'],
        '馆方转写图标': row['transcription_icon'],
        '详情采集状态': '已保存并核验详情元数据' if detail else '详情尚未采集',
        '详情选取依据': group['label'] if group else None,
        '馆方详情字段': detail,
        '目录与详情研究者字段是否对应': compare_credits(row['researchers'], detail['researchers']) if detail else None,
        '目录与详情讲述者字段是否对应': compare_credits(row['speakers'], detail['speakers']) if detail else None,
        '目录与详情录音日期是否一致': compare_dates(row['recorded'], detail['recorded']) if detail else None,
    }


def japhug_cards(corpus: Path, selection: Path, snapshots: Path):
    catalog, selected, details = load_snapshots(snapshots, corpus, selection,
                                                corpus_name=CORPUS_NAME, corpus_url=CORPUS_URL)
    groups = {number: group for group in selected['groups'] for number in group['ids']}
    corpus_hash = sha256(corpus.read_bytes()).hexdigest()
    selection_hash = sha256(selection.read_bytes()).hexdigest()
    common = {'genre': 'unclassified', 'credibility_tier': 'B', 'is_fictional_quarantine': False,
              'spatial': {'precision': 'culture_region', 'location_name': '中国四川（馆藏语言范围；单条采录地待核）',
                          'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}

    def catalog_source(locator: str) -> dict:
        return {'citation': 'CNRS-LACITO，Pangloss Japhug 馆藏目录，保留目录网页快照。',
                'type': 'pangloss_japhug_catalogue', 'url': CORPUS_URL, 'locator': locator,
                'local_path': display_path(corpus), 'content_sha256': corpus_hash}

    def selection_source(locator: str) -> dict:
        return {'citation': 'Astraia 首轮详情选取索引；分组只表示选取方法。',
                'type': 'pangloss_japhug_selection', 'url': CORPUS_URL, 'locator': locator,
                'local_path': display_path(selection), 'content_sha256': selection_hash}

    root = {**common, 'id': ROOT_ID, 'title': '四川嘉绒语 Japhug 录音目录 · Pangloss',
            'node_type': 'myth_corpus', 'z_layer': 2,
            'sources': [catalog_source('Japhug / 资源目录'), selection_source('首轮详情选取方法')]}
    body = (f'\n## 馆藏和核查范围\n\n本次目录快照列出 {len(catalog)} 条 Japhug 录音资源，'
            f'其中 {len(details)} 条已保存并核验单条详情。目录包含叙事、生活、技艺及语言资料，'
            '录音件数不能当作故事数；部分叙述可能源自书面作品，须核对单条详情和版本。'
            '首轮详情按目录中不同讲述者及录音年份目的性选取，不是随机或代表性样本。'
            '本地未复制音视频或转写正文；各资源许可、相关社区要求、体裁和采录背景均须复核。'
            '馆藏语言范围不等于单条采录地或叙事发生地，坐标、图谱年代及标准码留空。\n')
    yield NodeMetadata.model_validate(root), body

    for number, row in catalog.items():
        fields, group = details.get(number), groups.get(number)
        if fields:
            detail_path = snapshots / 'records' / number / 'page.html'
            source = {'citation': 'CNRS-LACITO，Pangloss 单条录音元数据；具体许可见原字段。',
                      'type': 'pangloss_japhug_detail', 'url': row['url'],
                      'doi': row['doi'].removeprefix('https://doi.org/'), 'locator': f'录音 {number}',
                      'local_path': display_path(detail_path), 'content_sha256': sha256(detail_path.read_bytes()).hexdigest()}
        else:
            source = {'citation': 'CNRS-LACITO，Pangloss 单条录音页面；详情尚未采集，需回查。',
                      'type': 'pangloss_japhug_original', 'url': row['url'],
                      'doi': row['doi'].removeprefix('https://doi.org/'), 'locator': f'录音 {number}'}
        sources = [catalog_source(f'Japhug / DOI {number}'), source,
                   selection_source(group['label'] if group else '未选入首轮详情')]
        data = recording_evidence(row, fields, group)
        aliases = [row['title']]
        if fields:
            aliases.extend(item['title'] for item in fields['alternate_titles'] if item['title'] not in aliases)
        model = {**common, 'id': CASE_PREFIX + number, 'title': f"嘉绒语录音目录 · {row['title']}",
                 'aliases': aliases, 'node_type': 'case', 'z_layer': 1,
                 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                                'note': '同一馆藏目录的录音资源；不表示同一故事、采录地点或传播关系。'}],
                 'sources': sources}
        body = ('\n## 馆方录音目录字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + '\n\n## 原音、转写与复核\n\n本卡只索引一条馆藏录音，不自动判定为民间故事；'
                  '目录题名或内部编号不证明题材、版本或来源。可能包含书面改写、叙事、技艺和语言材料，'
                  '应查看馆方单条页面并核对演述背景和相关社区意见。音频与转写正文未复制；'
                  '单条许可及附件许可须分别核查。录音日期不是故事发生年代，'
                  '采录地点、坐标和标准码不从馆藏范围推定。\n')
        yield NodeMetadata.model_validate(model), body
