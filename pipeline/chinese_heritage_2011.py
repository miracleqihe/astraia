"""Index the 2011 Chinese national folk-literature register and extensions.

Projects are finding aids, not individual oral performances or stories. An
extension row reuses a project number but records another submitting area.
"""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError, _challenge_page
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

SOURCE_URL = 'https://zwgk.mct.gov.cn/zfxxgkml/fwzwhyc/202012/t20201206_916812.html'
SOURCE_TITLE = '国务院关于公布第三批国家级非物质文化遗产名录的通知（2011），民间文学及扩展项目'
HEADERS = ['序号', '项目编号', '项目名称', '申报地区或单位']


def register_rows(raw: bytes) -> list[dict]:
    try:
        soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    except UnicodeError as error:
        raise IntakeError('2011 年非遗名录不是有效的 UTF-8。') from error
    body = soup.select_one('.gsj_htmlcon_bot')
    if not body or soup.contains_replacement_characters or _challenge_page(soup):
        raise IntakeError('2011 年非遗名录页面结构或编码不可靠。')
    full = re.sub(r'\s+', '', body.get_text(' ', strip=True))
    if ('第三批国家级非物质文化遗产名录' not in full or '民间文学（共计41项）' not in full
            or '民间文学（共计8项）' not in full or '扩展项目名录' not in full):
        raise IntakeError('2011 年非遗名录的批次或项目数量不符。')
    candidates = []
    for table in body.select('table'):
        rows = []
        for tr in table.select('tr'):
            cells = tr.find_all(['td', 'th'], recursive=False)
            if any(c.get('rowspan') not in (None, '1') or c.get('colspan') not in (None, '1') for c in cells):
                rows = []
                break
            rows.append([c.get_text(' ', strip=True) for c in cells])
        if rows and rows[0] == HEADERS:
            candidates.append(rows)
    primary = [rows for rows in candidates if len(rows) == 42 and rows[1][:2] == ['1029', 'I-85']]
    extensions = [rows for rows in candidates if len(rows) == 9 and rows[1][:2] == ['1', 'I-1']]
    if len(primary) != 1 or len(extensions) != 1:
        raise IntakeError('2011 年新增或扩展民间文学表不唯一。')
    result = []
    for kind, table in (('新增项目', primary[0]), ('扩展项目', extensions[0])):
        for position, cells in enumerate(table[1:], 1):
            if (len(cells) != 4 or not cells[0].isascii() or not cells[0].isdigit()
                    or not re.fullmatch(r'I-[1-9]\d*', cells[1]) or not cells[2] or not cells[3]
                    or any('\ufffd' in cell for cell in cells)):
                raise IntakeError(f'2011 年非遗名录字段无效：{kind} / {position}')
            if kind == '新增项目' and (int(cells[0]) != 1028 + position or int(cells[1][2:]) != 84 + position):
                raise IntakeError('2011 年新增项目序号不连续。')
            result.append({'kind': kind, 'position': position, 'index': int(cells[0]),
                           'project_number': cells[1], 'title': cells[2], 'area': cells[3]})
    if (result[0]['title'], result[40]['title'], result[41]['title'], result[-1]['title']) != (
            '天坛传说', '谚语（沪谚）', '苗族古歌', '司岗里'):
        raise IntakeError('2011 年非遗名录首尾项目不符。')
    if len({(row['kind'], row['index']) for row in result}) != 49:
        raise IntakeError('2011 年非遗名录序号重复。')
    return result


def row_id(row: dict) -> str:
    return f"corpus_cn_ich_2011_{'ext_' if row['kind'] == '扩展项目' else ''}{row['index']:04d}"


def evidence(row: dict) -> dict:
    return {'名录类别': row['kind'], '表内顺序': row['position'], '序号': row['index'],
            '项目编号（非母题标准码）': row['project_number'], '项目名称': row['title'],
            '申报地区或单位（原表）': row['area']}


def heritage_2011_cards(path: Path):
    path = path.resolve(strict=True)
    raw = path.read_bytes()
    checksum = sha256(raw).hexdigest()
    for row in register_rows(raw):
        locator = f"{row['kind']} / 民间文学 / 序号 {row['index']} / 项目编号 {row['project_number']}"
        data = {'id': row_id(row), 'title': f"2011 年国家级非遗{row['kind']} · {row['title']}",
                'aliases': [f"国家级非遗项目 {row['project_number']}"], 'node_type': 'myth_corpus', 'z_layer': 2,
                'genre': 'unclassified', 'credibility_tier': 'B', 'is_fictional_quarantine': False,
                'spatial': {'precision': 'culture_region', 'location_name': f"2011 年申报地区或单位：{row['area']}",
                            'culture_region': 'East Asia · China'}, 'temporal': None, 'standards': {},
                'sources': [{'citation': SOURCE_TITLE, 'type': 'heritage_register_2011', 'url': SOURCE_URL,
                             'locator': locator, 'local_path': display_path(path), 'content_sha256': checksum}],
                'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
        explanation = ('\n## 名录原表字段\n\n' + literal_block(json.dumps(evidence(row), ensure_ascii=False, indent=2)) +
                       '\n\n## 复核说明\n\n本卡记录国家级非遗名录项目，并非单篇故事或具体演述。'
                       '申报地区或单位不等于采录地、发生地或传承范围；行政名称按 2011 年原表保留。'
                       '项目编号是行政登记号，不是 ATU、汤普森、别列兹金或 OCM 标准码。'
                       '具体版本、讲述者、语言和采录出处尚待核实；坐标、年代、体裁及标准码留空。\n')
        if row['kind'] == '扩展项目':
            explanation += '\n扩展项目沿用既有项目编号，新增申报地区须与原名录逐项核对；不得自动当成新故事或传播路线。\n'
        yield NodeMetadata.model_validate(data), explanation
