"""Build a pending, scan-linked finding aid for Cole's 1916 anthology.

The table is a research transcription of the printed contents. Page positions
come from the Internet Archive OCR and its character-offset index, and remain
candidates until a person checks the scan.
"""

import csv
from datetime import date
from difflib import SequenceMatcher
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from pipeline.ingest_agent import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

IDENTIFIER = 'afl2786.0001.001.umich.edu'
BOOK_URL = f'https://archive.org/details/{IDENTIFIER}'
DOWNLOAD = f'https://archive.org/download/{IDENTIFIER}'
ROOT_ID = 'corpus_ph_cole_1916'
PREFIX = 'case_ph_cole_1916_p'
SPECIAL_ID = 'case_ph_cole_1916_p157'
TOC = PROJECT_ROOT / 'reference/philippine_cole_1916_toc.tsv'
OCR_NAME = f'{IDENTIFIER}_hocr_searchtext.txt.gz'
PAGE_INDEX_NAME = f'{IDENTIFIER}_hocr_pageindex.json.gz'
OCR_SHA = '892e3f60ba4c175ade736f8034ed3775965abe9c86a834fbf0fab62b48b3b910'
PAGE_INDEX_SHA = 'daf6fec84f7d43df7f380e629b7b0294175c65f0d1685997a5a0f0046d845c6a'
DOCUMENT = 'Mabel Cook Cole, Philippine Folk Tales, A. C. McClurg, Chicago, 1916; University of Michigan copy via Internet Archive.'


def _normal(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKD', value).casefold())


def _local(path: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def scan_url(scan: int) -> str:
    return f'{BOOK_URL}/page/n{scan - 1}/mode/1up'


def load_catalogue(toc: Path, snapshots: Path) -> list[dict]:
    """Recompute page candidates from the registered edition, failing closed."""
    try:
        ocr_bytes = (snapshots / OCR_NAME).read_bytes()
        page_bytes = (snapshots / PAGE_INDEX_NAME).read_bytes()
        if sha256(ocr_bytes).hexdigest() != OCR_SHA or sha256(page_bytes).hexdigest() != PAGE_INDEX_SHA:
            raise IntakeError('分页 OCR 或页索引哈希与登记的密歇根大学扫描本不一致。')
        text = gzip.decompress(ocr_bytes).decode('utf-8')
        offsets = json.loads(gzip.decompress(page_bytes).decode('utf-8'))
        with toc.open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream, delimiter='\t')
            if reader.fieldnames != ['group', 'subgroup', 'printed_page', 'title']:
                raise IntakeError('菲律宾目录字段格式不符。')
            raw = list(reader)
    except (OSError, UnicodeError, json.JSONDecodeError, EOFError) as error:
        raise IntakeError(f'菲律宾目录或分页 OCR 无法读取：{error}') from error
    if len(offsets) != 259 or len(raw) != 61:
        raise IntakeError('扫描页数或目录条目数不符；请重新核对来源。')
    last_end = 0
    for row in offsets:
        if (not isinstance(row, list) or len(row) != 4 or any(type(n) is not int for n in row)
                or row[0] != last_end or not row[0] <= row[1] <= len(text)):
            raise IntakeError('分页 OCR 字符索引不连续或越界。')
        last_end = row[1]
    if last_end != len(text):
        raise IntakeError('分页 OCR 字符索引未覆盖全文。')
    result = []
    for row in raw:
        if (set(row) != {'group', 'subgroup', 'printed_page', 'title'}
                or any(not isinstance(value, str) or not value.strip() or '\ufffd' in value for value in row.values())
                or not re.fullmatch(r'[1-9]\d{0,2}', row['printed_page'])):
            raise IntakeError('目录行缺少有效的题名、分类或印刷页码。')
        page_number = int(row['printed_page'])
        title = _normal(row['title'])
        matches = []
        for scan, (start, end, *_rest) in enumerate(offsets, 1):
            # This edition's front matter and inserted plates put the story
            # pages within this broad search window; it is not a page conversion.
            if not page_number + 18 <= scan <= page_number + 48:
                continue
            page_text = text[start:end]
            footers = re.findall(r'\[\s*(\d{1,3})\s*\]', page_text)
            footer = int(footers[-1]) if footers else None
            if footer is not None and footer != page_number:
                continue
            lines = [line for line in page_text.splitlines() if line.strip()][:4]
            for count in range(1, min(3, len(lines)) + 1):
                heading = _normal(' '.join(lines[:count]))
                if heading:
                    matches.append((SequenceMatcher(None, title, heading).ratio(), footer == page_number, scan))
        matches.sort(reverse=True)
        if not matches or matches[0][0] < .88:
            raise IntakeError(f'印刷第 {page_number} 页没有可靠的 OCR 起始页候选。')
        score, footer_match, scan = matches[0]
        if any(other_scan != scan and other_footer == footer_match and abs(other_score - score) < 0.000001
               for other_score, other_footer, other_scan in matches):
            raise IntakeError(f'印刷第 {page_number} 页有并列的 OCR 起始页候选。')
        page_text = text[offsets[scan - 1][0]:offsets[scan - 1][1]]
        footers = re.findall(r'\[\s*(\d{1,3})\s*\]', page_text)
        footer = int(footers[-1]) if footers else None
        result.append({**row, 'printed_page': page_number, 'scan': scan,
                       'heading_score': round(score, 3), 'footer_match': footer == page_number})
    if [row['printed_page'] for row in result] != sorted({row['printed_page'] for row in result}):
        raise IntakeError('目录印刷页码必须唯一且递增。')
    if [row['scan'] for row in result] != sorted({row['scan'] for row in result}):
        raise IntakeError('OCR 起始页候选必须唯一且递增。')
    return result


def node_id(row: dict) -> str:
    return f"{PREFIX}{row['printed_page']:03d}"


def evidence(row: dict) -> dict:
    return {'目录题名': row['title'], '原目录主组': row['group'], '原目录次组': row['subgroup'],
            '目录印刷页': row['printed_page'], 'OCR候选扫描序号': row['scan'],
            'OCR标题相似度': row['heading_score'], 'OCR页脚数字吻合': row['footer_match'],
            '原扫描候选链接': scan_url(row['scan'])}


def cole_cards(toc: Path, snapshots: Path):
    rows = load_catalogue(toc, snapshots)
    sources = [
        {'citation': '项目据原书目录和 OCR 转记的字段索引，待人工复核。', 'type': 'cole_toc_index',
         'locator': '目录 xi–xiii / 各条原题名与印刷页码', 'local_path': _local(toc),
         'content_sha256': sha256(toc.read_bytes()).hexdigest()},
        {'citation': DOCUMENT + ' 分页 OCR 检索文本。', 'type': 'cole_ocr',
         'url': f'{DOWNLOAD}/{OCR_NAME}', 'locator': '按分页字符索引获得候选标题与页脚，非校对本',
         'local_path': _local(snapshots / OCR_NAME), 'content_sha256': OCR_SHA},
        {'citation': DOCUMENT + ' OCR 页边界索引。', 'type': 'cole_page_index',
         'url': f'{DOWNLOAD}/{PAGE_INDEX_NAME}', 'locator': '259 页字符偏移索引',
         'local_path': _local(snapshots / PAGE_INDEX_NAME), 'content_sha256': PAGE_INDEX_SHA},
    ]
    common = {'genre': 'unclassified', 'credibility_tier': 'B', 'is_fictional_quarantine': False,
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False},
              'spatial': {'precision': 'culture_region', 'location_name': '菲律宾：书籍覆盖范围，非逐条采录点',
                          'culture_region': 'Southeast Asia · Philippines'}}
    root = {**common, 'id': ROOT_ID, 'title': '菲律宾故事选集 · Cole（1916）', 'node_type': 'myth_corpus',
            'z_layer': 2, 'sources': [{'citation': DOCUMENT, 'type': 'cole_scan_link',
                                       'url': scan_url(17), 'locator': '原书目录 xi–xiii / 扫描序号 17–19'}, *sources]}
    yield NodeMetadata.model_validate(root), (
        '\n## 资料范围\n\n本批依据 1916 年芝加哥版密歇根大学馆藏扫描本的目录，建立 61 条目录项；'
        '每项对应一个目录标题；《Mythology of Mindanao》包含叙事，其内部篇章边界须复核。资料组卡本身不含正文或影像；各子卡是否附 OCR 请以其草稿为准。'
        '编者前言称除亲闻叙述外也采用既有文献并经重述，逐篇讲述人、语言和采录时间地点仍待核对。'
        '原目录使用历史及殖民时期分类用语，仅作为出处原字段保留，不代表当代社群自称。'
        '出版年不是故事年代；扫描编号由 OCR 候选定位，需要查看影像。'
        '原书美国公有领域状态不等于全球权利许可；再利用条件及社区要求均待核。\n')
    for row in rows:
        page, scan = row['printed_page'], row['scan']
        relation = [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                     'note': '同属 1916 年编选本；不表示同一采录、族群、地点或传播路线。'}]
        if page == 105:
            relation.append({'type': 'COMPARED_WITH', 'target': 'case_asia_philippines_lumawig',
                             'note': '1922 年同题英文改写版本的待核对照，不证明同一次口述或相同原始采录。'})
        metadata = {**common, 'id': node_id(row), 'title': f"菲律宾 1916 年选集 · {row['title']}",
                    'aliases': [row['title']], 'node_type': 'case', 'z_layer': 1, 'relations': relation,
                    'sources': [{'citation': DOCUMENT, 'type': 'cole_scan_link', 'url': scan_url(scan),
                                 'locator': f'目录印刷页 {page} / OCR 候选扫描序号 {scan}，需核影像'}, *sources]}
        details = json.dumps(evidence(row), ensure_ascii=False, indent=2)
        extra = ('本条含叙事内容；其中的篇章边界、原始出处和是否含多个独立叙述须核。' if page == 157 else '')
        if page == 60:
            extra += '馆藏自动目录在扫描 88 误标另一篇；本卡保留原书目录题名。'
        if page == 68:
            extra += '馆藏自动目录把本条定位到扫描 100；OCR 起始标题位于扫描 96，两者须对照影像。'
        if page == 105:
            extra += '1922 年同题本列为对照候选；两版拼写及文字有差异，来源链和具体采录均须核验。'
        body = ('\n## 目录与候选定位\n\n```\n' + details + '\n```\n\n'
                '## 复核说明\n\n这是原书目录项，不等同于独立原始口述记录。目录组别是历史文献原词，'
                '并非当代族群自称或单条采录地点；采录者、讲述者、语种和时代未确定。'
                '请打开原扫描，核对目录、起始页、脚注与书目来源。扫描页码由未校对 OCR 推断；'
                '坐标和国际标准码为空。资料的再利用范围及社区要求待核。' + extra + '\n')
        yield NodeMetadata.model_validate(metadata), body
