"""Stage two historic English editions and cautious, source-linked comparisons."""

import csv
from datetime import date
from difflib import SequenceMatcher
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from pipeline.ingest_agent import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

JADE = 'jadestorybooksto00cous'
SALEEBY = 'studiesinmorohi00salegoog'
JADE_ROOT = 'corpus_asia_jade_1922'
JADE_PREFIX = 'case_asia_jade_1922_p'
SALEEBY_ROOT = 'corpus_ph_saleeby_1905'
SALEEBY_CASE = 'case_ph_saleeby_1905_p016'
LUMAWIG_EXISTING = 'case_asia_philippines_lumawig'
JADE_TOC = PROJECT_ROOT / 'reference/jade_1922_toc.tsv'
JADE_BOOK = f'https://archive.org/details/{JADE}'
SALEEBY_BOOK = f'https://archive.org/details/{SALEEBY}'
JADE_CITATION = 'Penrhyn W. Coussens, The Jade Story Book, New York: Duffield & Company, 1922; Library of Congress copy via Internet Archive.'
SALEEBY_CITATION = 'Najeeb M. Saleeby, Studies in Moro History, Law, and Religion, Manila: Bureau of Public Printing, 1905; Harvard copy via Internet Archive.'
ANDERSEN_REGISTER = 'https://andersen.sdu.dk/vaerk/register/info.html?vid=64'
ANDERSEN_TRANSLATION = 'https://andersen.sdu.dk/vaerk/hersholt/TheNightingale.html'
FILES = {
    JADE: {'ocr': '280ad566628f33b1249e757e27c424e09cd19f9ec794e00739075712d56c9eeb',
           'index': '9ecd409cb59bae590e0afe71ba53382e4b7c240e501a149d6d9daa778f4ae615',
           'scandata': '98775e926be358516202df8d6bb9c84dfcc86c791915dc84c6d94e615201173b'},
    SALEEBY: {'ocr': '2f042ef7ab0ac0974a9a8f0882e7fcd5e684822a5b22320008fd7dd2a416511d',
              'index': '2e882738d202b846832339ab0ac659e276e7f9333c34e983804b1024772b072e',
              'scandata': '9caa7ed93178e472852b81b83e5af95611d9b58460559f256b312c7e896eef54'},
}
ANDERSEN_SHA = {'register.html': 'f0b581ddc6b462edc48f6f14c1d754e807dd4bc3a24f5a6afd344dac870c3d26',
                'translation.html': '5d70ea4e60ce7dee60f6026d79a8f26271ee6e1ce03ad5299f5a3937a66eda04'}
COMPARISONS = {198: ('case_ph_cole_1916_p147', '1916 年同题目录项；前言提到菲律宾材料使用 Cole 选集，具体采录及文本差异待核。'),
               247: ('case_ph_cole_1916_p210', '1916 年同题目录项；前言提到菲律宾材料使用 Cole 选集，具体采录及文本差异待核。'),
               298: ('case_ph_cole_1916_p196', '1916 年同题目录项；前言提到菲律宾材料使用 Cole 选集，具体采录及文本差异待核。'),
               326: ('case_ph_cole_1916_p163', '1916 年同题目录项；前言提到菲律宾材料使用 Cole 选集，具体采录及文本差异待核。')}


def _normal(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKD', value).casefold())


def _local(path: Path) -> str:
    path = path.resolve(strict=True)
    try:
        return path.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def scan_url(identifier: str, viewer_index: int) -> str:
    return f'https://archive.org/details/{identifier}/page/n{viewer_index}/mode/1up'


def scan_mapping(root: Path, identifier: str) -> list[dict]:
    """Map OCR order through IA's excluded leaves to viewer n-index."""
    try:
        raw = (root / identifier / f'{identifier}_scandata.xml').read_bytes()
        if sha256(raw).hexdigest() != FILES[identifier]['scandata']:
            raise IntakeError('扫描清单哈希不符。')
        document = ET.fromstring(raw)
    except (OSError, ET.ParseError) as error:
        raise IntakeError(f'扫描清单无法读取：{error}') from error
    items = document.findall('./pageData/page')
    expected = 394 if identifier == JADE else 175
    if len(items) != expected or document.findtext('./bookData/leafCount') != str(expected):
        raise IntakeError('扫描清单页数不符。')
    mapping, previous_leaf, viewer = [], None, 0
    for item in items:
        leaf = item.get('leafNum', '')
        access = item.findtext('addToAccessFormats')
        if not leaf.isdigit() or access not in ('true', 'false'):
            raise IntakeError('扫描叶号或访问标志无效。')
        leaf = int(leaf)
        if previous_leaf is not None and leaf != previous_leaf + 1:
            raise IntakeError('扫描叶号不连续。')
        mapping.append({'leaf': leaf, 'viewer': viewer if access == 'true' else None})
        viewer += access == 'true'
        previous_leaf = leaf
    return mapping


def read_pages(root: Path, identifier: str) -> list[str]:
    if identifier not in FILES:
        raise IntakeError('未知的馆藏扫描本。')
    folder = root / identifier
    ocr = folder / f'{identifier}_hocr_searchtext.txt.gz'
    index = folder / f'{identifier}_hocr_pageindex.json.gz'
    try:
        raw, raw_index = ocr.read_bytes(), index.read_bytes()
        if sha256(raw).hexdigest() != FILES[identifier]['ocr'] or sha256(raw_index).hexdigest() != FILES[identifier]['index']:
            raise IntakeError('分页 OCR 或页边界索引与指定扫描本的哈希不符。')
        text = gzip.decompress(raw).decode('utf-8')
        offsets = json.loads(gzip.decompress(raw_index).decode('utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError, EOFError) as error:
        raise IntakeError(f'分页 OCR 无法读取：{error}') from error
    expected = 394 if identifier == JADE else 175
    if not isinstance(offsets, list) or len(offsets) != expected:
        raise IntakeError('扫描页数与登记的来源不符。')
    pages, cursor = [], 0
    for item in offsets:
        if (not isinstance(item, list) or len(item) != 4 or any(type(value) is not int for value in item)
                or item[0] != cursor or not item[0] <= item[1] <= len(text)):
            raise IntakeError('分页字符索引不连续或越界。')
        pages.append(text[item[0]:item[1]])
        cursor = item[1]
    if cursor != len(text):
        raise IntakeError('分页字符索引未覆盖全文。')
    return pages


def read_andersen(folder: Path) -> dict:
    sources = {}
    for name, digest in ANDERSEN_SHA.items():
        path = folder / name
        try:
            data = path.read_bytes()
        except OSError as error:
            raise IntakeError(f'安徒生中心快照无法读取：{error}') from error
        if sha256(data).hexdigest() != digest:
            raise IntakeError('安徒生中心参考网页哈希不符。')
        soup = BeautifulSoup(data, 'html.parser')
        content = soup.get_text(' ', strip=True)
        if (name == 'register.html' and ('Nattergalen' not in content or '11. november 1843' not in content)):
            raise IntakeError('安徒生中心作品登记缺少题名或首发日期。')
        if name == 'translation.html' and ('Nightingale' not in content or 'Emperor of China' not in content):
            raise IntakeError('安徒生中心译文缺少作品题名或角色。')
        sources[name] = path
    return sources


def load_jade(toc: Path, root: Path) -> list[dict]:
    pages = read_pages(root, JADE)
    mapping = scan_mapping(root, JADE)
    try:
        with toc.open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream, delimiter='\t')
            if reader.fieldnames != ['chapter', 'printed_page', 'toc_title', 'title', 'label']:
                raise IntakeError('1922 年目录字段格式不符。')
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise IntakeError(f'1922 年目录无法读取：{error}') from error
    if len(rows) != 33:
        raise IntakeError('1922 年目录转记条目数不符。')
    result = []
    for ordinal, row in enumerate(rows, 1):
        if (set(row) != {'chapter', 'printed_page', 'toc_title', 'title', 'label'}
                or row['chapter'] != str(ordinal) or not re.fullmatch(r'[1-9]\d{0,2}', row['printed_page'])
                or any(not isinstance(value, str) or not value.strip() or '\ufffd' in value for value in row.values())):
            raise IntakeError(f'1922 年目录第 {ordinal} 行不完整。')
        printed = int(row['printed_page'])
        expected = _normal(row['title'])
        candidates = []
        for scan, content in enumerate(pages, 1):
            # This scan copy contains front matter; the interval is only a
            # search window, not proof of a universal page conversion.
            if not printed + 13 <= scan <= printed + 23:
                continue
            footer = re.search(rf'(?<!\d){printed}\s*$', content) is not None
            lines = [line for line in content.splitlines() if line.strip()][:4]
            for count in range(1, min(3, len(lines)) + 1):
                heading = _normal(' '.join(lines[:count]))
                if heading:
                    score = 1.0 if heading.startswith(expected) else SequenceMatcher(None, expected, heading).ratio()
                    # Prefer a matching OCR page number; then heading quality,
                    # proximity to this copy's common offset, shortest heading.
                    candidates.append((footer, score, -abs(scan - (printed + 17)), -len(heading), scan, heading))
        if not candidates:
            raise IntakeError(f'1922 年印刷第 {printed} 页缺少 OCR 候选。')
        footer, score, _, _, scan, heading = max(candidates)
        if score < .88:
            raise IntakeError(f'1922 年印刷第 {printed} 页的 OCR 标题候选不足以定位。')
        leaf = mapping[scan - 1]
        if leaf['viewer'] is None:
            raise IntakeError(f'1922 年印刷第 {printed} 页的 OCR 候选不在查看器中。')
        result.append({**row, 'chapter': ordinal, 'printed_page': printed, 'scan': scan,
                       'heading_score': round(score, 3), 'footer_match': footer,
                       'heading_extended': heading.startswith(expected) and heading != expected,
                       'leaf': leaf['leaf'], 'viewer': leaf['viewer']})
    if [row['printed_page'] for row in result] != sorted({row['printed_page'] for row in result}):
        raise IntakeError('1922 年目录页码须唯一并递增。')
    if [row['scan'] for row in result] != sorted({row['scan'] for row in result}):
        raise IntakeError('1922 年扫描候选须唯一并递增。')
    return result


def jade_id(row: dict) -> str:
    return LUMAWIG_EXISTING if row['printed_page'] == 316 else f"{JADE_PREFIX}{row['printed_page']:03d}"


def jade_evidence(row: dict) -> dict:
    return {'目录原题名': row['toc_title'], '整理题名': row['title'], '原目录分类': row['label'],
            '正文阅读顺序（非原编号）': row['chapter'], '目录印刷页': row['printed_page'],
            'OCR候选扫描序号': row['scan'], 'OCR标题相似度': row['heading_score'],
            'OCR页脚数字吻合': row['footer_match'], 'OCR标题较目录扩展': row['heading_extended'],
            '扫描叶号': row['leaf'], '查看器索引': row['viewer'],
            '扫描候选链接': scan_url(JADE, row['viewer']), '关联卡片': jade_id(row)}


def _book_sources(root: Path, identifier: str, citation: str, prefix: str) -> list[dict]:
    result = []
    for kind, suffix in (('ocr', 'hocr_searchtext.txt.gz'), ('index', 'hocr_pageindex.json.gz'), ('scandata', 'scandata.xml')):
        name = f'{identifier}_{suffix}'
        path = root / identifier / name
        description = {'ocr': ' 分页 OCR。', 'index': ' OCR 页边界索引。', 'scandata': ' 扫描叶号与访问清单。'}
        result.append({'citation': citation + description[kind],
                       'type': f'{prefix}_{kind}', 'url': f'https://archive.org/download/{identifier}/{name}',
                       'locator': ('分页 OCR 文本，未经校对' if kind == 'ocr' else
                                   '扫描页对应字符偏移' if kind == 'index' else '原始叶号与可浏览页标志'),
                       'local_path': _local(path), 'content_sha256': FILES[identifier][kind]})
    return result


def _scan_source(identifier: str, citation: str, viewer: int, locator: str, prefix: str) -> dict:
    return {'citation': citation, 'type': f'{prefix}_scan', 'url': scan_url(identifier, viewer), 'locator': locator}


def early_edition_cards(toc: Path, root: Path, andersen: Path):
    rows = load_jade(toc, root)
    saleeby_pages = read_pages(root, SALEEBY)
    jade_mapping = scan_mapping(root, JADE)
    saleeby_mapping = scan_mapping(root, SALEEBY)
    if 'themythologyofmindanao' not in _normal(saleeby_pages[22]) or 'magindanao' not in _normal(saleeby_pages[22]):
        raise IntakeError('1905 年印刷第 16 页候选未检出指定章节。')
    reference = read_andersen(andersen)
    toc_source = {'citation': '项目根据 1922 年书中目录转记并整理的字段索引；待人工复核。',
                  'type': 'jade_toc', 'locator': '目录 vii–viii / 原题名、原分类和印刷页',
                  'local_path': _local(toc), 'content_sha256': sha256(toc.read_bytes()).hexdigest()}
    jade_sources = [toc_source, *_book_sources(root, JADE, JADE_CITATION, 'jade')]
    common = {'genre': 'unclassified', 'credibility_tier': 'B', 'is_fictional_quarantine': False,
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    aggregate = {**common, 'id': JADE_ROOT, 'title': '《The Jade Story Book》1922 年选集',
                 'node_type': 'myth_corpus', 'z_layer': 2,
                 'spatial': {'precision': 'culture_region', 'location_name': '书中目录覆盖多个地区，非单条采录地点',
                             'culture_region': 'Asia'},
                 'relations': [{'type': 'COMPARED_WITH', 'target': 'corpus_asia_jade_philippines',
                                'note': '同一 1922 年书籍的菲律宾子集；并非独立口述来源。'}],
                 'sources': [_scan_source(JADE, JADE_CITATION, jade_mapping[13]['viewer'], '原书目录 vii–viii / OCR 扫描 14–15', 'jade'), *jade_sources]}
    yield NodeMetadata.model_validate(aggregate), (
        '\n## 资料范围\n\n1922 年纽约出版的面向儿童英文选集；原目录按题名字母排列，本索引的阅读顺序按印刷页编排，'
        '不是原书章节编号。目录共 33 项，现有 Lumawig 卡片沿用，新增其余 32 项。'
        '书中“China”“Japan”等是编者的分类或故事场景，不能推定采录地点、口述来源或原生传统。'
        '前言说明部分内容为改写；个别故事与安徒生、豪夫的作品有关，具体译本及版权待核。'
        '原书、数字副本和社区资料的权利适用范围分别核查；未复制故事正文或图像。\n')
    for row in rows:
        if row['printed_page'] == 316:
            continue  # Keep the existing 1922 Lumawig draft; do not duplicate.
        page, scan = row['printed_page'], row['scan']
        relations = [{'type': 'PART_OF_MACRO_TREND', 'target': JADE_ROOT,
                      'note': '同属 1922 年英文选集；不表示同一地点、共同采录或传播路线。'}]
        if page in COMPARISONS:
            target, note = COMPARISONS[page]
            relations.append({'type': 'COMPARED_WITH', 'target': target, 'note': note})
        source = [_scan_source(JADE, JADE_CITATION, row['viewer'],
                               f"目录印刷页 {page} / OCR 候选扫描 {scan} / 叶号 {row['leaf']} / 查看器 n{row['viewer']}，待核影像", 'jade'), *jade_sources]
        extra = ''
        if page == 3:
            for name, url, locator in [('register.html', ANDERSEN_REGISTER, 'Nattergalen / 首发日期与作品登记'),
                                       ('translation.html', ANDERSEN_TRANSLATION, 'The Nightingale / Jean Hersholt 英译对照')]:
                source.append({'citation': '南丹麦大学安徒生中心作品登记与英译文本；译者与数字文本权利另核。',
                               'type': 'jade_andersen_reference', 'url': url, 'locator': locator,
                               'local_path': _local(reference[name]), 'content_sha256': ANDERSEN_SHA[name]})
            extra = ('本篇的宫殿、夜莺和机械鸟等情节与安徒生《夜莺》高度相似；安徒生中心登记该作首发于 1843 年。'
                     '这是一条文学版本对照线索，具体译本及改写关系待核，不能把“中国”标签当作在地口述证据。')
        elif page == 119:
            extra = '编者前言将本篇归于 Wilhelm Hauff 的作品；原作、译本与本版的具体关系需核。'
        item = {**common, 'id': jade_id(row), 'title': f"1922 年英文选集 · {row['title']}",
                'aliases': [row['title']], 'node_type': 'case', 'z_layer': 1,
                'spatial': {'precision': 'culture_region', 'location_name': f"原目录分类：{row['label']}（历史文献标签，非采录地）",
                            'culture_region': 'Asia'}, 'relations': relations, 'sources': source}
        details = json.dumps(jade_evidence(row), ensure_ascii=False, indent=2)
        body = ('\n## 原目录与候选定位\n\n```\n' + details + '\n```\n\n## 复核说明\n\n'
                '目录题名保留原排列，整理题名调整倒置冠词；阅读顺序由本项目按印刷页排列。'
                '目录地区或族群标签是编者分类，既非单篇采录地点，也不能保证故事来自该地区的口述传统。'
                '本卡不复制故事正文；请打开原扫描，核对标题、页码、编写或翻译来源和具体版本。'
                '采录地点、叙事年代和标准码均未赋值；原书与数字文本的再利用条件待核。' + extra + '\n')
        yield NodeMetadata.model_validate(item), body
    saleeby_sources = _book_sources(root, SALEEBY, SALEEBY_CITATION, 'saleeby')
    spatial = {'precision': 'culture_region', 'location_name': '书中讨论的菲律宾南部地区；非逐条采录地点',
               'culture_region': 'Southeast Asia · Philippines'}
    saleeby_viewer = saleeby_mapping[22]['viewer']
    if saleeby_viewer is None:
        raise IntakeError('1905 年印刷第 16 页不在查看器中。')
    scan = _scan_source(SALEEBY, SALEEBY_CITATION, saleeby_viewer,
                        f'印刷第 16 页 / OCR 扫描 23 / 查看器 n{saleeby_viewer} / 章节起始待核影像', 'saleeby')
    root_card = {**common, 'id': SALEEBY_ROOT, 'title': 'Saleeby 菲律宾南部史与法律著作（1905）',
                 'node_type': 'myth_corpus', 'z_layer': 2, 'spatial': spatial, 'sources': [scan, *saleeby_sources]}
    yield NodeMetadata.model_validate(root_card), ('\n## 资料范围\n\n本书包含历史、法律、宗教及叙事等不同材料；'
        '本批只建立印刷第 16 页同题章节的版本对照，不能把整本书作为单一神话或一次采录。'
        '原书与扫描本的权利、作者角色、原始语种和采录背景均待核。\n')
    case = {**common, 'id': SALEEBY_CASE, 'title': '菲律宾 1905 年文献 · The Mythology of Mindanao',
            'node_type': 'case', 'z_layer': 1, 'spatial': spatial,
            'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': SALEEBY_ROOT,
                           'note': '同属 1905 年出版物；不证明同一次口述。'},
                          {'type': 'COMPARED_WITH', 'target': 'case_ph_cole_1916_p157',
                           'note': '同题、相应情节与 1916 年脚注共同形成版本对照线索；具体底本和原始采录待核。'}],
            'sources': [scan, *saleeby_sources]}
    yield NodeMetadata.model_validate(case), ('\n## 版本对照\n\n1905 年书中该章节从印刷第 16 页开始，'
        '与 Cole 1916 年同题章节有相应情节。Cole 页下注明 Saleeby，但没有给出书名，'
        '不能据此认定 1905 年这一具体出版物就是她的直接底本。两版开头分别使用 Magindanao 和 Mindanao，'
        'Saleeby 前文区分两者范围；请以原文回查，不能自动推导坐标或故事传播。未复制正文。\n')
