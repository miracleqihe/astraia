"""Build a review-only index of the AKS oral-literature catalogue ZIP."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit
from zipfile import BadZipFile, ZipFile

from pipeline.intake_sources import IntakeError

SOURCE_URL = 'https://www.data.go.kr/data/15070383/fileData.do'
MEMBER = '한국구비문학대계(1).csv'
FIELDS = ['서명', '구연자', '채록지', '유형', '텍스트']
COLUMNS = ['目录数据行序号', '目录题名', '讲述者原字段', '采录地原字段', '馆方类别', '文本字段原值',
           '字段完全相同的行数', '候选单条页面', '候选说明', '待核问题', '坐标', '标准码',
           '馆方数据目录', '压缩包SHA256', '子文件SHA256', '人工复核']
MAX_BYTES = 100 * 1024 * 1024


def build_inventory(archive: Path, receipt: Path, candidates_path: Path) -> tuple[bytes, dict]:
    raw = archive.read_bytes()
    if not raw or len(raw) > MAX_BYTES:
        raise IntakeError('目录压缩包为空或超过大小限制。')
    archive_hash = sha256(raw).hexdigest()
    info = json.loads(receipt.read_text(encoding='utf-8'))
    if (info.get('datasetId') != '15070383' or info.get('pageUrl') != SOURCE_URL
            or info.get('sha256') != archive_hash or info.get('bytes') != len(raw)):
        raise IntakeError('馆方下载凭据与目录压缩包不符。')
    with ZipFile(io.BytesIO(raw)) as zipped:
        entries = [entry for entry in zipped.infolist() if entry.filename == MEMBER and not entry.is_dir()]
        if len(entries) != 1 or entries[0].file_size > MAX_BYTES:
            raise IntakeError('目录子文件不存在、重复或超过大小限制。')
        member = zipped.read(entries[0])  # Never extract a ZIP path to disk.
    member_hash = sha256(member).hexdigest()
    reader = csv.DictReader(io.StringIO(member.decode('utf-8-sig'), newline=''))
    if reader.fieldnames != FIELDS:
        raise IntakeError('馆方目录字段发生变化。')
    rows = list(reader)
    if not rows or any(set(row) != set(FIELDS) or any(not isinstance(row[key], str) for key in FIELDS) for row in rows):
        raise IntakeError('目录存在空文件、缺失字段或额外字段。')
    # Do not silently modify an original field that a spreadsheet could interpret as a formula.
    if any(value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r'))
           for row in rows for value in row.values()):
        raise IntakeError('目录有可能被电子表格解释为公式的字段；需先选择安全的显示方式。')

    manual = json.loads(candidates_path.read_text(encoding='utf-8'))
    if (manual.get('version') != 1 or manual.get('archive_sha256') != archive_hash
            or manual.get('member_sha256') != member_hash or not isinstance(manual.get('candidates'), list)):
        raise IntakeError('人工对照候选与目录快照不符。')
    candidates = {}
    for candidate in manual['candidates']:
        if not isinstance(candidate, dict) or type(candidate.get('row')) is not int:
            raise IntakeError('候选行号无效。')
        index = candidate['row']
        url = urlsplit(candidate.get('source_url', ''))
        query = parse_qs(url.query, strict_parsing=True)
        if (index < 1 or index > len(rows) or index in candidates or url.scheme != 'https'
                or url.netloc != 'kdp.aks.ac.kr' or url.path != '/inde/gubi' or url.fragment
                or set(query) != {'id'} or len(query['id']) != 1
                or not re.fullmatch(r'POKS\.GUBI\.GUBI\.\d+_\d+', query['id'][0])
                or not isinstance(candidate.get('note'), str) or not candidate['note'].strip()):
            raise IntakeError('候选来源链接、说明或行号无效。')
        row = rows[index-1]
        if (candidate.get('title') != row['서명'] or candidate.get('speaker') != row['구연자']
                or candidate.get('place') != row['채록지']):
            raise IntakeError('候选来源与指定原始行不符。')
        candidates[index] = candidate

    duplicates = Counter(tuple(row[key] for key in FIELDS) for row in rows)
    csv_buffer = io.StringIO(newline='')
    writer = csv.DictWriter(csv_buffer, fieldnames=COLUMNS, lineterminator='\r\n')
    writer.writeheader()
    for index, row in enumerate(rows, 1):
        group_size = duplicates[tuple(row[key] for key in FIELDS)]
        candidate = candidates.get(index)
        flags = ['馆方类别须人工核对；采录地点不等于叙事发生地；坐标与标准码待核']
        if not row['구연자'].strip():
            flags.append('目录未填讲述者')
        if not row['텍스트'].strip():
            flags.append('文本字段为空')
        if group_size > 1:
            flags.append('目录字段完全相同，保留全部原始行待核')
        flags.append('单条页面为人工候选，尚未签核' if candidate else '未核实单条页面；短编号不得自动转换链接')
        writer.writerow({'目录数据行序号':index, '目录题名':row['서명'], '讲述者原字段':row['구연자'],
                         '采录地原字段':row['채록지'], '馆方类别':row['유형'], '文本字段原值':row['텍스트'],
                         '字段完全相同的行数':group_size if group_size > 1 else '',
                         '候选单条页面':candidate['source_url'] if candidate else '',
                         '候选说明':candidate['note'] if candidate else '', '待核问题':'；'.join(flags),
                         '坐标':'', '标准码':'', '馆方数据目录':SOURCE_URL, '压缩包SHA256':archive_hash,
                         '子文件SHA256':member_hash, '人工复核':'待复核'})
    data = b'\xef\xbb\xbf' + csv_buffer.getvalue().encode('utf-8')
    summary = {'catalogue_rows':len(rows), 'source_types':dict(Counter(row['유형'] for row in rows)),
               'missing_speakers':sum(not row['구연자'].strip() for row in rows),
               'missing_text_fields':sum(not row['텍스트'].strip() for row in rows),
               'duplicate_groups':sum(n > 1 for n in duplicates.values()),
               'duplicate_rows_after_first':sum(n-1 for n in duplicates.values() if n > 1),
               'manual_candidates':len(candidates), 'archive_sha256':archive_hash,
               'member_sha256':member_hash, 'candidate_index_sha256':sha256(candidates_path.read_bytes()).hexdigest(),
               'inventory_sha256':sha256(data).hexdigest(), 'pending_only':True}
    return data, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    try:
        data, summary = build_inventory(args.archive,args.receipt,args.candidates)
        with args.output.open('xb') as stream:
            stream.write(data)
    except (OSError, ValueError, KeyError, TypeError, csv.Error, BadZipFile) as error:
        print(f'韩国口碑目录清单未生成：{error}',file=sys.stderr)
        return 1
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
