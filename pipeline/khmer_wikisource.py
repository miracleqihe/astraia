"""Record the visible Wikisource volume counts, without copying story text."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError, _challenge_page

HOST = 'wikisource.org'
URL = ('https://wikisource.org/wiki/%E1%9E%94%E1%9F%92%E1%9E%9A%E1%9E%87%E1%9E%BB%E1%9F%86'
       '%E1%9E%9A%E1%9E%BF%E1%9E%84%E1%9E%96%E1%9F%92%E1%9E%9A%E1%9F%81%E1%9E%84'
       '%E1%9E%81%E1%9F%92%E1%9E%98%E1%9F%82%E1%9E%9A')
TITLE = 'ប្រជុំរឿងព្រេងខ្មែរ'
KHMER_DIGITS = '០១២៣៤៥៦៧៨៩'


def parse_catalogue(raw: bytes) -> dict:
    try:
        text = raw.decode('utf-8')
    except UnicodeError as error:
        raise IntakeError('Wikisource 目录编码无效。') from error
    soup = BeautifulSoup(text, 'html.parser')
    heading = soup.select_one('#firstHeading')
    revisions = set(re.findall(r'"wgRevisionId":(\d+)', text))
    if (_challenge_page(soup) or soup.contains_replacement_characters or not heading
            or heading.get_text(' ', strip=True) != TITLE or len(revisions) != 1):
        raise IntakeError('Wikisource 高棉文目录题名或版本不符。')
    matches = []
    for table in soup.select('table.wikitable'):
        rows = [[cell.get_text(' ', strip=True).replace('\u200b', '')
                 for cell in tr.find_all(['th', 'td'], recursive=False)] for tr in table.find_all('tr')]
        if len(rows) == 11 and rows[0] == ['ចំណងជើង', 'ចំនួនរឿង', 'ចំនួនទំព័រ']:
            matches.append(rows)
    if len(matches) != 1:
        raise IntakeError('Wikisource 卷次表不唯一或结构改变。')
    rows = matches[0]
    convert = str.maketrans(KHMER_DIGITS, '0123456789')
    counts, pages = [], []
    for volume, row in enumerate(rows[1:10], 1):
        if len(row) != 3 or row[0] != f'ភាគទី{KHMER_DIGITS[volume]}':
            raise IntakeError('Wikisource 卷名不连续。')
        numbers = [item.translate(convert) for item in row[1:]]
        if any(not item.isascii() or not item.isdigit() or int(item) < 1 for item in numbers):
            raise IntakeError('Wikisource 卷册数量无效。')
        counts.append(int(numbers[0]))
        pages.append(int(numbers[1]))
    total = [item.translate(convert) for item in rows[10][1:]]
    if rows[10][0] != 'សរុប' or total != [str(sum(counts)), str(sum(pages))]:
        raise IntakeError('Wikisource 目录合计与分卷不一致。')
    return {'revision_id': int(next(iter(revisions))), 'volume_counts': counts, 'volume_pages': pages,
            'total_stories': sum(counts), 'total_pages': sum(pages)}


def load_snapshot(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError('Wikisource 卷册字段索引无法读取。') from error
    if (not isinstance(data, dict) or data.get('version') != 1 or data.get('source_url') != URL
            or type(data.get('revision_id')) is not int or data['revision_id'] < 1
            or not isinstance(data.get('observed_at'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', str(data.get('raw_sha256', '')))
            or any(not isinstance(data.get(k), list) or len(data[k]) != 9
                   or any(type(n) is not int or n < 1 for n in data[k]) for k in ('volume_counts', 'volume_pages'))
            or data.get('total_stories') != sum(data['volume_counts'])
            or data.get('total_pages') != sum(data['volume_pages'])):
        raise IntakeError('Wikisource 卷册字段索引无效。')
    return data


def fetch(path: Path, delay: float = 2) -> dict:
    if path.exists():
        return load_snapshot(path)
    robots, status = robot_rules(HOST, delay)
    raw, observed = request_html(URL, HOST, robots, delay)
    parsed = parse_catalogue(raw)
    data = {'version': 1, 'source_url': URL, 'raw_sha256': sha256(raw).hexdigest(),
            'observed_at': observed, 'robots_status': status, **parsed,
            'scope': '仅保存目录卷册数量，不保存网页原响应或故事正文；原响应指纹无法离线重算'}
    path.parent.mkdir(parents=True, exist_ok=True)
    exclusive_write(path, json_bytes(data))
    return load_snapshot(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"Wikisource 目录版本 {result['revision_id']}：{len(result['volume_counts'])} 卷、{result['total_stories']} 篇。")


if __name__ == '__main__':
    main()
