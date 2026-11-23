"""Prepare Dongjing performance and oral-history catalogue items for review."""
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.fetch_bl_dongjing import ROOT_URL, SERIES_URL, load_snapshot
from pipeline.ingest_agent import literal_block
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_cn_bl_eap012_dongjing'
PREFIX = 'case_cn_bl_eap012_dongjing_'


def extent_file_count(extent: str | None) -> int | None:
    """Count only the explicit first single-format quantity, never infer missing media."""
    value = extent or ''
    match = re.match(r'^(\d+)\s+(?:MP3|WAV|DAT|VOB)(?:\s+files?)?,', value, re.I)
    formats = re.findall(r'\b(?:MP3|WAV|DAT|VOB)\b', value, re.I)
    return int(match.group(1)) if match and len(formats) == 1 else None


def title_year_range(fields: dict) -> tuple[int | None, bool | None]:
    """Only compare the year explicitly printed in brackets to numeric date fields."""
    title = re.search(r'\[((?:19|20)\d{2})\]', fields.get('Title') or '')
    start, end = fields.get('Start Date') or '', fields.get('End Date') or ''
    year = int(title.group(1)) if title else None
    if year is None or not re.fullmatch(r'\d{4}', start) or not re.fullmatch(r'\d{4}', end): return year, None
    if int(start) > int(end): return year, None
    return year, int(start) <= year <= int(end)


def date_range_years(fields: dict) -> tuple[list[int], bool | None]:
    """Compare explicit years in the separate Date Range field with start/end only."""
    years = [int(value) for value in re.findall(r'\b(?:19|20)\d{2}\b', fields.get('Date Range') or '')]
    start, end = fields.get('Start Date') or '', fields.get('End Date') or ''
    if not years or not re.fullmatch(r'\d{4}', start) or not re.fullmatch(r'\d{4}', end) or int(start) > int(end):
        return years, None
    return years, all(int(start) <= year <= int(end) for year in years)


def topic_hints(fields: dict) -> list[str]:
    text = (fields.get('Scope & Content') or '').lower()
    return [label for phrase, label in [('oral history interview', '内容说明含 oral history interview'),
                                        ('performance', '内容说明含 performance'), ('ritual', '内容说明含 ritual')]
            if phrase in text]


def group_evidence(series: dict, fonds: dict, entries: list) -> dict:
    counts = [extent_file_count(fields.get('Extent')) for _, _, fields in entries]
    material = Counter(fields.get('Material Type') or '未列' for _, _, fields in entries)
    title_ranges = Counter('不在范围内' if title_year_range(fields)[1] is False else
                           '在范围内' if title_year_range(fields)[1] is True else '无法比较' for _, _, fields in entries)
    return {'系列档号': series.get('Reference (shelfmark)'), '系列题名': series.get('Title'),
            '系列内容说明': series.get('Scope & Content'), '系列范围原字段': series.get('Extent'),
            '系列排列说明': series.get('Arrangement'), '系列语言原字段': series.get('Languages'),
            '系列日期起始原字段': series.get('Start Date'), '系列日期结束原字段': series.get('End Date'),
            '系列日期范围原字段': series.get('Date Range'), '系列访问条件原字段': series.get('User Conditions'),
            '系列原件说明': series.get('Information About Originals'), '父级档号': fonds.get('Reference (shelfmark)'),
            '父级内容说明': fonds.get('Scope & Content'), '父级访问条件原字段': fonds.get('User Conditions'),
            '单件目录数': len(entries), '馆方单件材料类型计数': dict(sorted(material.items())),
            '单件范围字段可解析数': sum(value is not None for value in counts),
            '单件范围字段首项文件数相加': sum(counts) if all(value is not None for value in counts) else None,
            '题名年份与单件起止字段比较': dict(sorted(title_ranges.items())),
            '数量说明': '系列文件数、单件范围首项数量、文件夹和独立作品不是相同单位；差额和统计口径须回查。',
            '日期说明': '题名、内容说明与目录日期字段可能描述不同环节；不自动判为错误或叙事年代。',
            '许可说明': '目录文字 CC BY 4.0；父级限研究使用，音视频、单件条件及相关社区要求须另核。'}


def item_evidence(child: dict, fields: dict) -> dict:
    year, in_range = title_year_range(fields)
    range_years, range_inside = date_range_years(fields)
    return {'馆方档号': child['shelfmark'], '馆方记录号': child['record_id'], '馆方题名': fields.get('Title'),
            '馆方内容说明': fields.get('Scope & Content'), '馆方范围原字段': fields.get('Extent'),
            '范围字段首项文件数（待核）': extent_file_count(fields.get('Extent')),
            '馆方材料类型': fields.get('Material Type'), '馆方语言原字段': fields.get('Languages'),
            '馆方文字原字段': fields.get('Scripts'), '馆方起始日期原字段': fields.get('Start Date'),
            '馆方结束日期原字段': fields.get('End Date'), '馆方日期范围原字段': fields.get('Date Range'),
            '题名方括号年份': year, '题名年份落在起止字段范围': in_range,
            '日期范围所列年份': range_years, '日期范围年份落在起止字段范围': range_inside,
            '馆方内部项目标识原字段': fields.get('Former Internal References'),
            '馆方数字内容原字段': fields.get('Digitised Content'), '馆方单件访问条件原字段': fields.get('User Conditions'),
            '内容提示（非体裁判定）': topic_hints(fields),
            '日期与角色限制': '保留原字段；题名年份不自动等于叙事年代，项目标识数字不自动解释为日期，受访者、采访者和录音者不能合并。'}


def source_set(folder: Path, manifest: dict, child: dict | None = None) -> list[dict]:
    def source(kind, url, locator, path, citation):
        return {'type': kind, 'url': url, 'locator': locator, 'citation': citation,
                'local_path': display_path(path), 'content_sha256': sha256(path.read_bytes()).hexdigest()}
    citation = 'British Library Archives and Manuscripts Catalogue, EAP012/6/2；目录文字 CC BY 4.0，音视频权利另核。'
    result = [source('bl_dongjing_series', ROOT_URL, 'EAP012/6/2 / 表演和访谈系列', folder / 'root.html', citation),
              source('bl_dongjing_fonds', SERIES_URL, 'EAP012/6 / 父级馆藏与访问条件', folder / 'series.html', citation),
              source('bl_dongjing_manifest', ROOT_URL, '单件和首末检索快照清单', folder / 'manifest.json', '馆方目录网页快照清单。')]
    if child is not None:
        result.append(source('bl_dongjing_item', child['url'], child['shelfmark'] + ' / 电子文件夹',
                             folder / f"item-{child['number']:02}.html", citation))
    return result


def cards(folder: Path):
    manifest, series, fonds, entries = load_snapshot(folder)
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False, 'spatial': {'precision': 'culture_region',
              'location_name': '云南洞经馆藏系列；逐条采录与叙事地点待核', 'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    data = group_evidence(series, fonds, entries)
    model = {**common, 'id': ROOT_ID, 'title': '云南洞经表演与访谈 · EAP012/6/2',
             'sources': source_set(folder, manifest)}
    body = ('\n## 馆藏系列与父级字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
            + '\n\n## 复核范围\n\n本系列由馆方为识别材料编排，混有演出、仪式和口述历史访谈；'
              '文件夹数或文件数不等于独立故事数。系列文件总数与单件字段首项相加的口径需回查。'
              '系列和单件的题名、内容说明、日期及项目标识须分别核实，不能自动作为叙事年代。'
              '本地未下载音视频或转写；目录文字 CC BY 4.0，父级限研究使用，单件及社区要求另核。\n')
    yield NodeMetadata.model_validate(model), body
    for child, _, fields in entries:
        model = {**common, 'node_type': 'case', 'z_layer': 1, 'id': f"{PREFIX}{child['number']:02}",
                 'title': f"云南洞经表演与访谈 · {child['shelfmark']}", 'aliases': [child['title']],
                 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                                'note': '同属馆藏系列，不表示一段录音、单篇故事或同一叙事发生地。'}],
                 'sources': source_set(folder, manifest, child)}
        data = item_evidence(child, fields)
        body = ('\n## 馆方单件目录原字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n一件目录可含多个文件、曲目或访谈，不自动判作单篇故事。'
                  '受访者、表演团体、采访者和录音者以目录原文为线索分别回查；'
                  '标题、说明、日期字段和项目标识可能记录不同环节，不能自行统一或当成叙事年代。'
                  '未下载音视频或转写；目录文字 CC BY 4.0，父级限研究使用，单件及社区要求另核。'
                  '地点、标准码和叙事年代留空，标准码须依据实际内容与本地码表人工匹配。\n')
        yield NodeMetadata.model_validate(model), body
