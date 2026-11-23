"""Capture only catalogue fields from DSAL volume indexes; never media or transcripts."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from pipeline.archive_fetch import AGENT, json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

HOST = 'dsal.uchicago.edu'
COLLECTION_URL = f'https://{HOST}/LSI/'
TERMS_URL = f'https://{HOST}/about.html'
VOLUMES = ('II Mōn-Khmēr and Tai', 'III Tibeto-Burman', 'XI Karen')
FIELDS = ('recording_title', 'language', 'language_dialect', 'narrator', 'narrator_origin_district',
          'location_populated_place', 'districts_where_spoken', 'gramophone_records_volume',
          'lsi_volume_number', 'lsi_volume_title', 'linguistic_family', 'recording_number',
          'language_alt', 'location_province', 'lsi_volume_text', 'language_family')
MAX_JSON = 2 * 1024 * 1024


def volume_url(volume: str) -> str:
    if volume not in VOLUMES: raise IntakeError('卷名不在本次有界筛查范围。')
    return COLLECTION_URL + 'api/recordings/volume/' + quote(volume, safe='')


def detail_url(volume: str, number: str) -> str:
    if volume not in VOLUMES or not isinstance(number, str) or not re.fullmatch(r'\d{4,5}(?:HALF)?AK\.mp3', number):
        raise IntakeError('音档编号无法构造馆方页面链接。')
    return COLLECTION_URL + 'volume/' + quote(volume, safe='') + '/recording/' + quote(number, safe='')


def selected_items(document: object) -> list[dict]:
    if not isinstance(document, list) or len(document) > 200: raise IntakeError('DSAL 目录索引结构异常。')
    rows = []
    for item in document:
        if not isinstance(item, dict) or any(key not in item for key in FIELDS):
            raise IntakeError('DSAL 目录字段缺失。')
        fields = {key: item[key] for key in FIELDS}
        if (any(value is not None and not isinstance(value, str) for value in fields.values())
                or not fields['recording_number'] or not fields['recording_title']):
            raise IntakeError('DSAL 目录字段值异常。')
        rows.append(fields)
    return rows


def request_volume(volume: str, robots, delay: float) -> tuple[list[dict], dict]:
    url = volume_url(volume)
    if delay < 2 or not robots.can_fetch(AGENT, url): raise IntakeError('DSAL 请求被 robots.txt 限制。')
    time.sleep(delay)
    with urlopen(Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json', 'Accept-Encoding': 'identity'}), timeout=30) as response:
        if response.status != 200 or response.geturl() != url or response.headers.get_content_type() != 'application/json':
            raise IntakeError('DSAL 目录状态、跳转或响应类型异常。')
        raw = response.read(MAX_JSON + 1)
    if not raw or len(raw) > MAX_JSON: raise IntakeError('DSAL 索引响应为空或过大。')
    rows = selected_items(json.loads(raw.decode('utf-8')))
    return rows, {'url': url, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
                  'observed_at': datetime.now(timezone.utc).isoformat()}


def load_snapshot(folder: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    pages = manifest.get('pages')
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or not isinstance(pages, list) or len(pages) != len(VOLUMES)):
        raise IntakeError('DSAL 目录清单无效。')
    all_rows = []
    for index, (volume, page) in enumerate(zip(VOLUMES, pages, strict=True)):
        name = f'page-{index:02}.json'; raw = (folder / name).read_bytes()
        receipt = page.get('response', {})
        if (page.get('path') != name or page.get('volume') != volume or page.get('sha256') != sha256(raw).hexdigest()
                or receipt.get('url') != volume_url(volume) or not re.fullmatch(r'[0-9a-f]{64}', receipt.get('sha256', ''))
                or not isinstance(receipt.get('bytes'), int) or receipt['bytes'] <= 0 or not receipt.get('observed_at')):
            raise IntakeError('DSAL 字段索引或响应凭据不符。')
        doc = json.loads(raw.decode('utf-8'))
        if doc.get('version') != 1 or doc.get('volume') != volume: raise IntakeError('DSAL 字段索引范围不符。')
        if not isinstance(doc.get('items'), list) or any(not isinstance(row, dict) or set(row) != set(FIELDS) for row in doc['items']):
            raise IntakeError('DSAL 本地索引含非必要字段或缺少字段。')
        rows = selected_items(doc.get('items'))
        if len(rows) != page.get('count'): raise IntakeError('DSAL 字段索引数量不符。')
        all_rows.extend({'volume': volume, 'page': index, 'fields': row} for row in rows)
    terms = manifest.get('terms', {}); raw = (folder / 'terms.html').read_bytes()
    if (terms.get('url') != TERMS_URL or terms.get('path') != 'terms.html' or terms.get('sha256') != sha256(raw).hexdigest()
            or terms.get('bytes') != len(raw) or not terms.get('observed_at')):
        raise IntakeError('DSAL 使用说明快照不符。')
    return manifest, all_rows


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2: raise IntakeError('馆藏请求间隔至少 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    entries = []
    for index, volume in enumerate(VOLUMES):
        rows, receipt = request_volume(volume, robots, delay)
        path = folder / f'page-{index:02}.json'
        exclusive_write(path, json_bytes({'version': 1, 'volume': volume, 'items': rows}))
        entries.append({'volume': volume, 'path': path.name, 'count': len(rows),
                        'sha256': sha256(path.read_bytes()).hexdigest(), 'response': receipt})
        print(f'已登记 DSAL 语言卷 {index + 1}/{len(VOLUMES)} · {len(rows)} 项目录字段。', flush=True)
    raw, observed = request_html(TERMS_URL, HOST, robots, delay)
    exclusive_write(folder / 'terms.html', raw)
    manifest = {'version': 1, 'robots_status': status, 'pages': entries,
                'terms': {'url': TERMS_URL, 'path': 'terms.html', 'sha256': sha256(raw).hexdigest(),
                          'bytes': len(raw), 'observed_at': observed},
                'scope': '仅保存三个语言卷公开目录中的必要字段及使用说明；未保存原始接口响应、音频、转写或叙事正文。',
                'limits': '不能从本地字段索引重算原始响应哈希；记录与馆方唱片的对应、录音及各资源权利须人工逐条核查。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    load_snapshot(folder)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"已保存 {sum(p['count'] for p in result['pages'])} 项目录字段；未下载媒体或转写。")
    return 0


if __name__ == '__main__': raise SystemExit(main())
