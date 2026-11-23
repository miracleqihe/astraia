"""Screen Palu'e public catalogue fields without persisting descriptions or media."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pipeline.archive_fetch import AGENT, json_bytes, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.fetch_palue_sample import COLLECTION_ID, COLLECTION_URL, HOST
from pipeline.intake_sources import IntakeError

BASE = f'https://{HOST}/server/api/discover/search/objects'
PAGE_SIZE = 50
MAX_JSON = 2 * 1024 * 1024
FIELDS = ('dc.title', 'dc.contributor.depositor', 'dc.contributor.researcher', 'dc.contributor.consultant',
          'dc.contributor.recorder', 'dc.contributor.speaker', 'dc.contributor.transcriber', 'dc.contributor.translator',
          'dc.date.begin', 'dc.date.finish', 'dc.subject.language', 'dc.subject.languagecode',
          'dc.content.language', 'dc.content.languagecode', 'dc.coverage.iso3166', 'dc.description.region',
          'dc.type.dcmi', 'dc.type.linguistictype', 'dc.format.extent', 'dc.rights', 'dc.rights.access')


def page_url(page: int) -> str:
    if not isinstance(page, int) or page < 0: raise IntakeError('页码无效。')
    return BASE + '?' + urlencode({'scope': COLLECTION_ID, 'sort': 'dc.title,ASC', 'size': PAGE_SIZE, 'page': page})


def genre_hint(metadata: dict) -> tuple[str | None, str]:
    """Keep only a bounded explicit genre label, never narrative or medical details."""
    descriptions = metadata.get('dc.description', [])
    if not isinstance(descriptions, list): raise IntakeError('目录描述字段结构异常。')
    for value in descriptions:
        if not isinstance(value, dict) or not isinstance(value.get('value'), str):
            raise IntakeError('目录描述字段值异常。')
        text = value['value']
        match = re.search(r'(?im)^\s*genre\s*:\s*([^\n.]{1,65})', text)
        if match:
            label = re.split(r'\s+(?:title|theme|recorded)\s*:', match.group(1), flags=re.I)[0].strip(' :;')
            if re.fullmatch(r"[A-Za-z0-9 /()&,'’+\-]{1,55}", label) and len(label.split()) <= 7:
                return label, '目录说明显式 Genre 标签；未核对录音'
            return None, '说明含 Genre 标签但无法安全提取，须回查'
    return None, '未提取到显式 Genre 标签；不代表无体裁'


def selected_item(item: dict) -> dict:
    if not isinstance(item, dict) or item.get('type') != 'item':
        raise IntakeError('馆藏检索结果并非单件记录。')
    identifier, name, handle = item.get('uuid'), item.get('name'), item.get('handle')
    if (not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', identifier)
            or not isinstance(name, str) or not re.fullmatch(r'SD1-\d{3}', name)
            or not isinstance(handle, str) or not re.fullmatch(r'10125/\d+', handle)):
        raise IntakeError('馆藏单件编号、UUID 或永久标识异常。')
    metadata = item.get('metadata')
    if not isinstance(metadata, dict): raise IntakeError(f'馆藏元数据结构异常：{name}')
    fields = {}
    for field in FIELDS:
        values = metadata.get(field, [])
        if not isinstance(values, list) or any(not isinstance(v, dict) or not isinstance(v.get('value'), str) for v in values):
            raise IntakeError(f'馆藏元数据格式异常：{name} / {field}')
        fields[field] = [v['value'] for v in values]
    if fields['dc.title'] != [name]: raise IntakeError(f'馆藏题名和编号不符：{name}')
    label, label_scope = genre_hint(metadata)
    return {'id': name, 'uuid': identifier, 'handle': handle, 'item_url': f'https://{HOST}/items/{identifier}',
            'fields': fields, 'genre_hint': label, 'genre_hint_scope': label_scope}


def parse_page(document: dict, page: int, expected_total: int | None = None) -> tuple[list[dict], int, int]:
    try:
        sort, result = document['sort'], document['_embedded']['searchResult']
        info, objects = result['page'], result['_embedded']['objects']
        if (sort != {'by': 'dc.title', 'order': 'ASC'} or info['number'] != page or info['size'] != PAGE_SIZE
                or not isinstance(info['totalElements'], int) or not isinstance(info['totalPages'], int)
                or info['totalElements'] < 0 or info['totalPages'] != (info['totalElements'] + PAGE_SIZE - 1) // PAGE_SIZE
                or (expected_total is not None and info['totalElements'] != expected_total)):
            raise IntakeError('馆藏检索排序、分页或总数变化。')
        items = [selected_item(hit['_embedded']['indexableObject']) for hit in objects]
    except (KeyError, TypeError) as error:
        raise IntakeError('馆藏检索响应结构异常。') from error
    expected_size = min(PAGE_SIZE, max(0, info['totalElements'] - PAGE_SIZE * page))
    if len(items) != expected_size or [item['id'] for item in items] != sorted(item['id'] for item in items):
        raise IntakeError('馆藏检索页数量或排序不符。')
    return items, info['totalElements'], info['totalPages']


def request_page(page: int, robots, delay: float) -> tuple[dict, dict]:
    url = page_url(page)
    if not robots.can_fetch(AGENT, url): raise IntakeError('馆藏检索接口受 robots.txt 限制。')
    time.sleep(delay)
    request = Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/hal+json', 'Accept-Encoding': 'identity'})
    with urlopen(request, timeout=30) as response:
        if response.status != 200 or response.geturl() != url or response.headers.get_content_type() not in ('application/hal+json', 'application/json'):
            raise IntakeError('馆藏检索接口状态、跳转或类型异常。')
        raw = response.read(MAX_JSON + 1)
    if not raw or len(raw) > MAX_JSON: raise IntakeError('馆藏检索响应为空或过大。')
    document = json.loads(raw.decode('utf-8'))
    if not isinstance(document, dict): raise IntakeError('馆藏检索响应不是对象。')
    return document, {'url': url, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
                      'observed_at': datetime.now(timezone.utc).isoformat()}


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2: raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    entries, all_items, total, total_pages = [], [], None, None
    page = 0
    while total_pages is None or page < total_pages:
        document, receipt = request_page(page, robots, delay)
        items, observed_total, observed_pages = parse_page(document, page, total)
        total, total_pages = observed_total, observed_pages
        if page >= 100 or total > 5000: raise IntakeError('馆藏结果超出本次有界获取范围。')
        index = folder / f'page-{page:03d}.json'
        exclusive_write(index, json_bytes({'version': 1, 'page': page, 'items': items}))
        entries.append({'page': page, 'path': index.name, 'sha256': sha256(index.read_bytes()).hexdigest(),
                        'count': len(items), 'response': receipt})
        all_items.extend(items)
        print(f'已保存公开目录字段第 {page + 1}/{total_pages} 页 · {len(items)} 项。', flush=True)
        page += 1
    for key in ('id', 'uuid', 'handle'):
        if len({item[key] for item in all_items}) != total:
            raise IntakeError(f'馆藏目录 {key} 出现重复或缺失。')
    if [item['id'] for item in all_items] != sorted(item['id'] for item in all_items):
        raise IntakeError('馆藏目录跨页排序不一致。')
    checks = []
    for page in sorted({0, total_pages - 1}):
        document, receipt = request_page(page, robots, delay)
        checked, _, _ = parse_page(document, page, total)
        saved = json.loads((folder / f'page-{page:03d}.json').read_text(encoding='utf-8'))['items']
        if checked != saved: raise IntakeError('馆藏首页或末页在采集期间变化，须重取并核对。')
        checks.append({'page': page, 'response': receipt})
    manifest = {'version': 1, 'robots_status': status, 'collection_url': COLLECTION_URL, 'scope_uuid': COLLECTION_ID,
                'total': total, 'page_size': PAGE_SIZE, 'pages': entries, 'boundary_checks': checks,
                'scope': '公开目录字段索引；未保存原始接口响应、叙事描述、音视频或转写。',
                'limits': '检索期间只重复核验首页与末页；原始响应哈希无法仅凭本地字段重算，逐条权利和社区要求待核。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"已登记 {result['total']} 条公开目录字段；未下载叙事正文或媒体。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
