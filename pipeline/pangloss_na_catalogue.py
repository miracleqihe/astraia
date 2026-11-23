"""Screen an existing Yongning Na catalogue snapshot without fetching media."""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata
from pipeline.pangloss_na import CORPUS_URL, ROOT_ID, catalogue_rows, json_object, load_selection
from pipeline.pangloss_na_context import validate_selection as validate_context

PREFIX = 'case_cn_yongning_na_'
MARKER = 'pangloss_na_catalogue_candidate'
# These are project selection reasons, not catalogue genres or claims about
# the recording content. The comparison targets identify existing recordings.
PICKS = [
    ('0004532', '家族口述题名的版本候选', '0004551'),
    ('0004884', '家族口述题名的版本候选', '0004551'),
    ('0004891', '葬仪访谈题名的版本候选', '0004571'),
    ('0004892', '葬仪访谈题名的版本候选', '0004571'),
    ('0004593', '宗教角色和仪式背景', None),
    ('0004594', '宗教角色题名的版本候选', '0004593'),
    ('0004603', '儿童与仪式背景', None),
    ('0004630', '生年与地方观念', None),
    ('0004872', '死亡及丧葬背景', None),
    ('0004898', '讲述者对记录情境的反思', None),
    ('0004899', '记录情境反思的续篇候选', '0004898'),
    ('0004925', '姓名与命名背景', None),
    ('0004623', '歌曲的使用情境', None),
    ('0004936', '歌曲使用情境的版本候选', '0004623'),
    ('0004937', '歌曲使用情境的前后录音线索', '0004936'),
    ('0004896', '天气与地方知识背景', None),
    ('0004908', '湖与平原的地方观念', None),
    ('0004913', '婚俗背景', None),
    ('0004616', '植物知识与文化背景', None),
    ('0004905', '器物及宗教文化背景', None),
    ('0004906', '器物和佛像题名的续篇候选', '0004905'),
    ('0004611', '讲述者面向听众的录音介绍', None),
    ('0004617', '社会与口述背景', None),
    ('0004625', '佛教饰物及家庭空间背景', None),
    ('0004530', '商队与地方生活背景', None),
    ('0004863', '商队题名的版本候选', '0004530'),
    ('0004888', '谚语题名候选', None),
    ('0004942', '俗语题名候选', None),
    ('0004901', '待客与地方习俗背景', None),
    ('0004582', '尊老与待客主题候选', None),
    ('0007684', '尊老与待客题名的版本候选', '0004582'),
]


def build_selection(corpus: Path, first: Path, context: Path) -> dict:
    catalog = catalogue_rows(corpus.read_bytes())
    validate_context(corpus, first, context)
    previous = {number for path in (first, context) for group in load_selection(path)['groups'] for number in group['ids']}
    choices = []
    for number, reason, target in PICKS:
        if number not in catalog or number in previous or (target and target not in catalog):
            raise IntakeError(f'候选或对照不在目录中，或与既有选取重复：{number}')
        choices.append({'id': number, 'title': catalog[number]['title'], 'reason': reason, 'compare_id': target})
    return {'version': 1, 'corpus_url': CORPUS_URL, 'catalogue_sha256': sha256(corpus.read_bytes()).hexdigest(),
            'first_selection_sha256': sha256(first.read_bytes()).hexdigest(),
            'context_selection_sha256': sha256(context.read_bytes()).hexdigest(),
            'method': '人工按目录题名选择仪式、口述背景和已有条目的版本候选；未读取或自动分类音频。',
            'limits': '题名及版本字样仅是对照线索，不证明题材、独立演述、同一来源或传播。',
            'choices': choices}


def validate_selection(corpus: Path, first: Path, context: Path, selection: Path) -> tuple[dict, dict, set[str]]:
    expected = build_selection(corpus, first, context)
    selected = json_object(selection)
    if selected != expected:
        raise IntakeError('永宁纳语本轮选取、题名或三个来源哈希不一致。')
    rows = catalogue_rows(corpus.read_bytes())
    previous = {number for path in (first, context) for group in load_selection(path)['groups'] for number in group['ids']}
    identifiers = [item['id'] for item in selected['choices']]
    if len(set(identifiers)) != len(identifiers):
        raise IntakeError('永宁纳语本轮选取含重复录音。')
    for item in selected['choices']:
        if not re.fullmatch(r'\d{7}', item['id']) or (item['compare_id'] and item['compare_id'] not in previous | set(identifiers)):
            raise IntakeError('候选对照对象必须属于既有或本轮选取的录音。')
    return rows, selected, previous


def evidence(row: dict, selected: dict) -> dict:
    return {'馆方录音号': row['id'], '馆方目录题名': row['title'], '馆方目录研究者': row['researchers'],
            '馆方目录讲述者': row['speakers'], '馆方目录录音日期': row['recorded'], '馆方时长': row['duration'],
            '馆方媒介图标': row['formats'], '馆方转写图标': row['transcription_icon'],
            '本项目选取理由': selected['reason'], '候选对照录音号': selected['compare_id'],
            '单条详情': '尚未取得；目录字段与当前页面须回查'}


def cards(corpus: Path, first: Path, context: Path, selection: Path):
    catalog, selected, _ = validate_selection(corpus, first, context, selection)
    common = {'node_type': 'case', 'z_layer': 1, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False, 'spatial': {'precision': 'culture_region',
              'location_name': '永宁纳语馆藏范围；单条录音地点尚未核实', 'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    local = [('pangloss_na_candidate_catalogue', corpus, 'Pangloss 永宁纳语馆藏目录快照'),
             ('pangloss_na_candidate_first', first, '本项目首轮选取索引'),
             ('pangloss_na_candidate_context', context, '本项目口述背景选取索引'),
             ('pangloss_na_candidate_selection', selection, '本项目本轮目录选取索引')]
    sources = [{'citation': citation, 'type': kind, 'url': CORPUS_URL, 'locator': '目录及选取范围核验',
                'local_path': display_path(path), 'content_sha256': sha256(path.read_bytes()).hexdigest()}
               for kind, path, citation in local]
    for item in selected['choices']:
        number, row = item['id'], catalog[item['id']]
        related = [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                    'note': '同一馆藏目录的录音资源，不表示同一故事、演述或采录地点。'}]
        if item['compare_id']:
            related.append({'type': 'COMPARED_WITH', 'target': PREFIX + item['compare_id'],
                            'note': '仅据目录题名或前后录音说明建立待核对照，不证明同一演述、共同来源或传播。'})
        original = {'citation': 'CNRS-LACITO，Pangloss 单条录音页面；本轮未取得详情。',
                    'type': MARKER, 'url': row['url'], 'doi': row['doi'].removeprefix('https://doi.org/'),
                    'locator': f'录音 {number}，单条详情及许可待核'}
        model = {**common, 'id': PREFIX + number, 'title': f"永宁纳语录音 · {row['title']}",
                 'aliases': [row['title']], 'relations': related, 'sources': [original, *sources]}
        body = ('\n## 馆方目录字段和选取理由\n\n' + literal_block(json.dumps(evidence(row, item), ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n本卡来自既有目录快照，单条页面、许可、音视频和转写未取得；'
                  '题名与项目选取理由不等于已核实体裁或内容。请分开核对研究者、讲述者、录音日期和实际地点；'
                  '录音日期不是叙事年代，馆藏语言范围不是采录地点或故事发生地。'
                  '目录的版本或前后顺序仅供比较，不证明同一次演述、同源或传播。'
                  '坐标、图谱年代和标准码留空，许可及相关社区要求待逐条复核。\n')
        yield NodeMetadata.model_validate(model), body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = build_selection(args.corpus, args.first, args.context)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f"已保存 {len(data['choices'])} 条目录候选选取；未联网。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
