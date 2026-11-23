"""Index the 2021 national folk-literature tables from the State Council gazette.

Capture compares PDFium text with Poppler extraction. The indexed source remains
the official PDF; two page renders and final human review are still required.
"""
import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from pipeline.chinese_heritage_batches import base_identity, project_number
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

PDF_URL = 'https://www.gov.cn/gbgl/92e7fad3d97742f1b1b2beb1fda9c049/files/8525ced0638e4480a1368790d9433924.pdf'
TITLE = '国务院公报 2021 年第 18 号：第五批国家级非遗代表性项目名录及扩展项目'
EXPECTED_EXTENSIONS = [1, 12, 13, 26, 565, 1035, 1040, 1058, 1069]


def norm(text: str) -> str:
    return unicodedata.normalize('NFKC', re.sub(r'\s+', '', text))


def parse_page(text: str, poppler_text: str, page: int) -> list[dict]:
    if page not in (24, 33):
        raise IntakeError('2021 年名录 PDF 页码不符。')
    clean = norm(text)
    heading = '第五批国家级非物质文化遗产代表性项目名录' if page == 24 else '代表性项目名录扩展项目名录'
    count = 12 if page == 24 else 9
    if heading not in clean or f'民间文学(共计{count}项)' not in clean or '二、传统音乐' not in clean:
        raise IntakeError(f'2021 年名录 PDF 第 {page} 页标题或数量不符。')
    section = text.split('一、民间文学', 1)[1].split('二、传统音乐', 1)[0]
    poppler = norm(poppler_text)
    rows = []
    for line in (line.strip() for line in section.splitlines() if line.strip()):
        if not re.match(r'^[０-９0-9]', line):
            continue
        match = re.fullmatch(r'([０-９0-9]+)\s+([ⅠI][－—–-][０-９0-9]+)\s+(\S+)\s+(\S+)', line)
        if not match:
            raise IntakeError(f'2021 年 PDF 第 {page} 页项目行结构无效：{line}')
        index_raw, code, title, area = match.groups()
        if any(norm(value) not in poppler for value in (index_raw, code, title, area)):
            raise IntakeError(f'2021 年 PDF 两种文字提取结果不一致：{line}')
        number, index = project_number(code), int(unicodedata.normalize('NFKC', index_raw))
        position = len(rows) + 1
        if page == 24 and (index, number) != (1372 + position, 155 + position):
            raise IntakeError('2021 年新增项目的序号不连续。')
        if page == 33:
            if position > len(EXPECTED_EXTENSIONS) or index != EXPECTED_EXTENSIONS[position - 1]:
                raise IntakeError('2021 年扩展项目的序号不符。')
            base_identity(index, number)
        rows.append({'year': 2021, 'kind': '新增项目' if page == 24 else '扩展项目',
                     'position': position, 'index': index, 'index_raw': index_raw, 'project_number': code,
                     'number': number, 'title': title, 'area': area, 'pdf_page': page, 'printed_page': page - 1})
    if len(rows) != count:
        raise IntakeError(f'2021 年 PDF 第 {page} 页记录数量不符。')
    if page == 24 and (rows[0]['title'], rows[-1]['title']) != ('八大处传说', '都玛简收'):
        raise IntakeError('2021 年新增项目首尾题名不符。')
    return rows


def capture(pdf: Path, output: Path) -> dict:
    if output.exists():
        raise IntakeError('2021 年字段索引已存在，不覆盖。')
    import pypdfium2
    pdf = pdf.resolve(strict=True)
    raw = pdf.read_bytes()
    if not raw.startswith(b'%PDF-'):
        raise IntakeError('2021 年名录来源不是 PDF。')
    document = pypdfium2.PdfDocument(str(pdf))
    if len(document) != 77:
        raise IntakeError('2021 年公报 PDF 总页数变化，请重新核对。')
    records, checks = [], []
    for page in (24, 33):
        pdfium = document[page - 1].get_textpage().get_text_range()
        run = subprocess.run(['pdftotext', '-f', str(page), '-l', str(page), '-layout', str(pdf), '-'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        poppler = run.stdout.decode('utf-8')
        rows = parse_page(pdfium, poppler, page)
        records.extend(rows)
        checks.append({'pdf_page': page, 'printed_page': page - 1, 'rows': len(rows),
                       'pdfium_text_sha256': sha256(pdfium.encode('utf-8')).hexdigest(),
                       'poppler_text_sha256': sha256(run.stdout).hexdigest(),
                       'poppler_warnings': run.stderr.decode('utf-8', errors='replace').strip()})
    data = {'version': 1, 'source_url': PDF_URL, 'pdf_sha256': sha256(raw).hexdigest(),
            'pdf_pages': len(document), 'observed_at': datetime.now(timezone.utc).isoformat(),
            'pdfium_version': importlib.metadata.version('pypdfium2'), 'extraction_checks': checks,
            'scope': '仅两页的项目字段；PDFium 与 Poppler 逐字段对照，原表图像及字体映射仍须人工复核',
            'records': records}
    output.parent.mkdir(parents=True, exist_ok=True)
    exclusive_write(output, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return load_index(pdf, output)


def load_index(pdf: Path, path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        raw = pdf.read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError('2021 年 PDF 或字段索引无法读取。') from error
    if (not isinstance(data, dict) or data.get('version') != 1 or data.get('source_url') != PDF_URL
            or not raw.startswith(b'%PDF-') or data.get('pdf_sha256') != sha256(raw).hexdigest()
            or data.get('pdf_pages') != 77 or not isinstance(data.get('records'), list)
            or len(data['records']) != 21 or not isinstance(data.get('extraction_checks'), list)
            or len(data['extraction_checks']) != 2):
        raise IntakeError('2021 年 PDF 与字段索引不一致。')
    expected_keys = {'year', 'kind', 'position', 'index', 'index_raw', 'project_number', 'number',
                     'title', 'area', 'pdf_page', 'printed_page'}
    for offset, row in enumerate(data['records']):
        page, position, kind = (24, offset + 1, '新增项目') if offset < 12 else (33, offset - 11, '扩展项目')
        if (not isinstance(row, dict) or set(row) != expected_keys or row['year'] != 2021
                or row['kind'] != kind or row['position'] != position or row['pdf_page'] != page
                or row['printed_page'] != page - 1 or type(row['index']) is not int or type(row['number']) is not int
                or not isinstance(row['index_raw'], str) or not norm(row['index_raw']).isdigit()
                or int(norm(row['index_raw'])) != row['index']
                or not isinstance(row['project_number'], str) or project_number(row['project_number']) != row['number']
                or not all(isinstance(row[k], str) and row[k] and '\ufffd' not in row[k] for k in ('title', 'area'))):
            raise IntakeError('2021 年字段索引行无效。')
        if page == 24 and (row['index'], row['number']) != (1372 + position, 155 + position):
            raise IntakeError('2021 年新增项目编号不连续。')
        if page == 33:
            if row['index'] != EXPECTED_EXTENSIONS[position - 1]:
                raise IntakeError('2021 年扩展项目序号不符。')
            base_identity(row['index'], row['number'])
    if (data['records'][0]['title'], data['records'][11]['title']) != ('八大处传说', '都玛简收'):
        raise IntakeError('2021 年项目首尾题名不符。')
    for check, page, count in zip(data['extraction_checks'], (24, 33), (12, 9), strict=True):
        if (not isinstance(check, dict) or check.get('pdf_page') != page or check.get('printed_page') != page - 1
                or check.get('rows') != count or any(not re.fullmatch(r'[0-9a-f]{64}', str(check.get(key, '')))
                                                     for key in ('pdfium_text_sha256', 'poppler_text_sha256'))):
            raise IntakeError('2021 年双引擎提取检查记录无效。')
    return data


def row_id(row: dict) -> str:
    return f"corpus_cn_ich_2021_{'ext_' if row['kind'] == '扩展项目' else ''}{row['index']:04d}"


def evidence(row: dict) -> dict:
    return {'名录年份': 2021, '名录类别': row['kind'], '表内顺序': row['position'], '序号原文': row['index_raw'],
            '序号': row['index'], '项目编号（非母题标准码）': row['project_number'], '项目名称': row['title'],
            '申报地区或单位（原表）': row['area'], 'PDF 页码': row['pdf_page'], '印刷页码': row['printed_page']}


def heritage_2021_cards(pdf: Path, index: Path):
    pdf, index = pdf.resolve(strict=True), index.resolve(strict=True)
    data = load_index(pdf, index)
    pdf_hash, index_hash = sha256(pdf.read_bytes()).hexdigest(), sha256(index.read_bytes()).hexdigest()
    for row in data['records']:
        locator = f"PDF 第 {row['pdf_page']} 页 / 公报第 {row['printed_page']} 页 / {row['kind']} / 序号 {row['index']} / {row['project_number']}"
        url = f"{PDF_URL}#page={row['pdf_page']}"
        relations = []
        if row['kind'] == '扩展项目':
            relations = [{'type': 'COMPARED_WITH', 'target': base_identity(row['index'], row['number']),
                          'note': '扩展名录沿用原项目的序号及行政编号；名称与申报地区需对照，不能推断单篇故事或传播路线。'}]
        model = {'id': row_id(row), 'title': f"2021 年国家级非遗{row['kind']} · {row['title']}",
                 'aliases': [f"国家级非遗项目 {row['project_number']}"], 'node_type': 'myth_corpus', 'z_layer': 2,
                 'genre': 'unclassified', 'credibility_tier': 'B', 'is_fictional_quarantine': False,
                 'spatial': {'precision': 'culture_region', 'location_name': f"2021 年申报地区或单位：{row['area']}",
                             'culture_region': 'East Asia · China'}, 'temporal': None, 'standards': {}, 'relations': relations,
                 'sources': [{'citation': TITLE, 'type': 'heritage_register_2021_pdf', 'url': url, 'locator': locator,
                              'local_path': display_path(pdf), 'content_sha256': pdf_hash},
                             {'citation': '两页名录字段研究索引，PDFium 与 Poppler 提取对照；仍须人工复核原表。',
                              'type': 'heritage_register_2021_index', 'url': url, 'locator': locator,
                              'local_path': display_path(index), 'content_sha256': index_hash}],
                 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
        body = ('\n## 公报原表字段\n\n' + literal_block(json.dumps(evidence(row), ensure_ascii=False, indent=2)) +
                '\n\n## 复核说明\n\n本卡是国家级非遗名录项目，不是单篇故事或具体演述。'
                '来源 PDF 个别字体未嵌入或缺少 Unicode 映射；本页字段已用两套引擎提取并对照页面，仍须人工核对原表。'
                '申报地区不等于采录地或发生地；行政项目编号不是国际故事类型或母题码。'
                '坐标、故事年代、体裁及标准码留空。\n')
        if relations:
            body += '\n扩展项目沿用原项目序号和行政编号；名称、申报地区及对应关系仍须人工核对。\n'
        yield NodeMetadata.model_validate(model), body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.pdf, args.output)
    print(f"2021 年名录字段索引完成：{len(result['records'])} 项，原 PDF 与两引擎指纹已记录。")


if __name__ == '__main__':
    main()
