"""Index the 2008 and 2014 national folk-literature project registers.

These official register rows describe projects and submitting areas, not
individual performances or international folklore classifications.
"""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from bs4 import BeautifulSoup

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError, _challenge_page
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

CONFIG = {
    2008: {'url': 'https://www.ihchina.cn/zhengce_details/11664',
           'title': '国务院关于公布第二批国家级非物质文化遗产名录和第一批扩展项目名录的通知（2008），民间文学',
           'heading': '第二批国家级非物质文化遗产名录', 'header': '编号',
           'count': 53, 'extension_count': 5, 'first_index': 519, 'first_number': 32,
           'first_title': '八达岭长城传说', 'last_title': '笑话（万荣笑话）',
           'extensions': [8, 9, 13, 22, 31]},
    2014: {'url': 'https://www.ln.gov.cn/web/zwgkx/lnsrmzfgb/2015n/qk/2015n_dyq/gwywj/831B66689DB14A69B972FFBD5EF5169E/index.shtml',
           'title': '国务院关于公布第四批国家级非物质文化遗产代表性项目名录的通知（2014），民间文学',
           'heading': '第四批国家级非物质文化遗产代表性项目名录', 'header': '项目编号',
           'count': 30, 'extension_count': 7, 'first_index': 1220, 'first_number': 126,
           'first_title': '卢沟桥传说', 'last_title': '常山喝彩歌谣',
           'extensions': [8, 13, 27, 521, 565, 1043, 1069]},
}


def project_number(value: str) -> int:
    compact = unicodedata.normalize('NFKC', re.sub(r'\s+', '', value))
    match = re.fullmatch(r'[IⅠ][—–－-]([1-9]\d*)', compact)
    if not match:
        raise IntakeError(f'民间文学行政项目编号无效：{value}')
    return int(match.group(1))


def base_identity(index: int, number: int) -> str:
    """Return the original project card ID only for a validated register pair."""
    if 1 <= index <= 31 and number == index:
        return f'corpus_cn_ich_2006_{index:02d}'
    if 519 <= index <= 571 and number == index - 487:
        return f'corpus_cn_ich_2008_{index:04d}'
    if 1029 <= index <= 1069 and number == index - 944:
        return f'corpus_cn_ich_2011_{index:04d}'
    raise IntakeError(f'扩展项目与已知原登记序号、编号范围不符：{index} / {number}')


def register_rows(raw: bytes, year: int) -> list[dict]:
    if year not in CONFIG:
        raise IntakeError('不支持的国家级名录年份。')
    spec = CONFIG[year]
    try:
        soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    except UnicodeError as error:
        raise IntakeError(f'{year} 年非遗名录不是有效 UTF-8。') from error
    text = re.sub(r'\s+', '', soup.get_text(' ', strip=True))
    if (soup.contains_replacement_characters or _challenge_page(soup) or spec['heading'] not in text
            or f"民间文学（共计{spec['count']}项）" not in text
            or f"民间文学（共计{spec['extension_count']}项）" not in text or '扩展项目名录' not in text):
        raise IntakeError(f'{year} 年名录批次、项目数量或页面结构不符。')
    tables = []
    headers = ['序号', spec['header'], '项目名称', '申报地区或单位']
    for table in soup.select('table'):
        rows = []
        for tr in table.select('tr'):
            cells = tr.find_all(['td', 'th'], recursive=False)
            if any(c.get('rowspan') not in (None, '1') or c.get('colspan') not in (None, '1') for c in cells):
                rows = []
                break
            rows.append([c.get_text(' ', strip=True) for c in cells])
        if rows and rows[0] == headers:
            tables.append(rows)
    primary = [t for t in tables if len(t) == spec['count'] + 1 and t[1][0] == str(spec['first_index'])]
    extension = [t for t in tables if len(t) == spec['extension_count'] + 1 and t[1][0] == str(spec['extensions'][0])]
    if len(primary) != 1 or len(extension) != 1:
        raise IntakeError(f'{year} 年新增或扩展民间文学表不唯一。')
    result = []
    for kind, table in (('新增项目', primary[0]), ('扩展项目', extension[0])):
        for position, cells in enumerate(table[1:], 1):
            if (len(cells) != 4 or not cells[0].isascii() or not cells[0].isdigit()
                    or any(not value or '\ufffd' in value or '\0' in value for value in cells)):
                raise IntakeError(f'{year} 年名录字段无效：{kind} / {position}')
            index, number = int(cells[0]), project_number(cells[1])
            if kind == '新增项目':
                if (index, number) != (spec['first_index'] + position - 1, spec['first_number'] + position - 1):
                    raise IntakeError(f'{year} 年新增项目序号不连续。')
            else:
                if index != spec['extensions'][position - 1]:
                    raise IntakeError(f'{year} 年扩展项目序号不符。')
                base_identity(index, number)
            result.append({'year': year, 'kind': kind, 'position': position, 'index': index,
                           'project_number': cells[1], 'number': number, 'title': cells[2], 'area': cells[3]})
    if result[0]['title'] != spec['first_title'] or result[spec['count'] - 1]['title'] != spec['last_title']:
        raise IntakeError(f'{year} 年新增名录首尾项目不符。')
    if len({(r['kind'], r['index']) for r in result}) != len(result):
        raise IntakeError(f'{year} 年名录序号重复。')
    return result


def row_id(row: dict) -> str:
    return f"corpus_cn_ich_{row['year']}_{'ext_' if row['kind'] == '扩展项目' else ''}{row['index']:04d}"


def evidence(row: dict) -> dict:
    return {'名录年份': row['year'], '名录类别': row['kind'], '表内顺序': row['position'], '序号': row['index'],
            '项目编号（非母题标准码）': row['project_number'], '项目名称': row['title'], '申报地区或单位（原表）': row['area']}


def heritage_cards(path: Path, year: int):
    path = path.resolve(strict=True)
    raw, spec = path.read_bytes(), CONFIG[year]
    checksum = sha256(raw).hexdigest()
    for row in register_rows(raw, year):
        locator = f"{row['kind']} / 民间文学 / 序号 {row['index']} / 项目编号 {row['project_number']}"
        relations = []
        if row['kind'] == '扩展项目':
            relations = [{'type': 'COMPARED_WITH', 'target': base_identity(row['index'], row['number']),
                          'note': '扩展名录沿用原项目的序号及行政编号；名称与申报地区需对照，不能推断单篇故事或传播路线。'}]
        model = {'id': row_id(row), 'title': f"{year} 年国家级非遗{row['kind']} · {row['title']}",
                 'aliases': [f"国家级非遗项目 {row['project_number']}"], 'node_type': 'myth_corpus', 'z_layer': 2,
                 'genre': 'unclassified', 'credibility_tier': 'B', 'is_fictional_quarantine': False,
                 'spatial': {'precision': 'culture_region', 'location_name': f"{year} 年申报地区或单位：{row['area']}",
                             'culture_region': 'East Asia · China'}, 'temporal': None, 'standards': {}, 'relations': relations,
                 'sources': [{'citation': spec['title'], 'type': f'heritage_register_{year}', 'url': spec['url'],
                              'locator': locator, 'local_path': display_path(path), 'content_sha256': checksum}],
                 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
        body = ('\n## 名录原表字段\n\n' + literal_block(json.dumps(evidence(row), ensure_ascii=False, indent=2)) +
                f'\n\n## 复核说明\n\n本卡记录 {year} 年国家级非遗名录项目，并非单篇故事或具体演述。'
                '申报地区或单位不等于采录地、发生地或传承范围；行政名称按原表保留。'
                '项目编号是行政登记号，不是 ATU、汤普森、别列兹金或 OCM 标准码。'
                '具体版本、讲述者、语言和采录出处尚待核实；坐标、年代、体裁及标准码留空。\n')
        if relations:
            body += '\n扩展项目沿用原项目序号和行政编号；名称、申报地区及对应关系仍须人工核对。\n'
        yield NodeMetadata.model_validate(model), body
