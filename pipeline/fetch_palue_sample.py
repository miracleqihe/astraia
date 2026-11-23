"""Capture two public Palu'e item-metadata summaries, without media or transcripts."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pipeline.archive_fetch import AGENT, json_bytes, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

HOST = 'scholarspace.manoa.hawaii.edu'
COLLECTION_ID = '8e4c3ded-2f0b-44ad-98ff-6d93969f029e'
COLLECTION_URL = f'https://{HOST}/collections/{COLLECTION_ID}'
ITEMS = [('SD1-045', 'd1cfab2f-ce9c-4135-873f-1192969821d0'),
         ('SD1-046', 'bc20189d-1e02-4013-84df-46b8e427bc67')]
FIELDS = ('dc.title', 'dc.contributor.depositor', 'dc.contributor.researcher', 'dc.contributor.consultant',
          'dc.contributor.recorder', 'dc.contributor.speaker', 'dc.date.begin', 'dc.date.finish',
          'dc.subject.language', 'dc.subject.languagecode', 'dc.content.language', 'dc.content.languagecode',
          'dc.coverage.iso3166', 'dc.description.region', 'dc.rights', 'dc.rights.access')
MAX_JSON = 2 * 1024 * 1024


def fetch_json(url: str, robots, delay: float) -> tuple[dict, dict]:
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.netloc != HOST or parts.query or parts.fragment
            or not robots.can_fetch(AGENT, url)):
        raise IntakeError(f'馆藏接口地址或 robots.txt 不允许访问：{url}')
    time.sleep(delay)
    request = Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/hal+json', 'Accept-Encoding': 'identity'})
    with urlopen(request, timeout=30) as response:
        if response.status != 200 or response.geturl() != url or response.headers.get_content_type() not in ('application/hal+json', 'application/json'):
            raise IntakeError(f'馆藏接口状态、跳转或类型异常：{url}')
        raw = response.read(MAX_JSON + 1)
    if not raw or len(raw) > MAX_JSON:
        raise IntakeError(f'馆藏接口响应为空或过大：{url}')
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict):
        raise IntakeError('馆藏接口响应不是对象。')
    return data, {'url': url, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
                  'observed_at': datetime.now(timezone.utc).isoformat()}


def selected_fields(item: dict, name: str, identifier: str) -> dict:
    if item.get('type') != 'item' or item.get('uuid') != identifier or item.get('name') != name:
        raise IntakeError(f'Palu’e 单条档号或类型不符：{name}')
    handle, metadata = item.get('handle'), item.get('metadata')
    if not isinstance(handle, str) or not handle.startswith('10125/') or not isinstance(metadata, dict):
        raise IntakeError(f'Palu’e 单条馆藏标识或元数据缺失：{name}')
    result = {}
    for field in FIELDS:
        values = metadata.get(field, [])
        if not isinstance(values, list) or any(not isinstance(v, dict) or not isinstance(v.get('value'), str) for v in values):
            raise IntakeError(f'Palu’e 单条元数据格式异常：{name} / {field}')
        result[field] = [v['value'] for v in values]
    if result['dc.title'] != [name] or not result['dc.contributor.speaker']:
        raise IntakeError(f'Palu’e 单条题名或演述者字段缺失：{name}')
    return {'id': name, 'uuid': identifier, 'handle': handle, 'item_url': f'https://{HOST}/items/{identifier}',
            'collection_url': COLLECTION_URL, 'fields': result,
            'scope': '公开目录字段抽样，不保存原响应、叙事描述、音视频或转写；权限及社群要求待核。'}


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2: raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    records = []
    for name, identifier in ITEMS:
        url = f'https://{HOST}/server/api/core/items/{identifier}'
        item, item_receipt = fetch_json(url, robots, delay)
        data = selected_fields(item, name, identifier)
        collection_url = item.get('_links', {}).get('owningCollection', {}).get('href')
        if collection_url != url + '/owningCollection':
            raise IntakeError(f'Palu’e 单条所属馆藏链接异常：{name}')
        collection, collection_receipt = fetch_json(collection_url, robots, delay)
        if collection.get('type') != 'collection' or collection.get('uuid') != COLLECTION_ID:
            raise IntakeError(f'Palu’e 单条所属馆藏不符：{name}')
        index_path = folder / f'{name}.json'
        exclusive_write(index_path, json_bytes(data))
        records.append({'id': name, 'path': index_path.name, 'index_sha256': sha256(index_path.read_bytes()).hexdigest(),
                        'item_response': item_receipt, 'collection_response': collection_receipt})
        print(f'已登记公开目录字段：{name}；未请求音视频或转写。', flush=True)
    manifest = {'version': 1, 'robots_status': status, 'collection_url': COLLECTION_URL, 'records': records,
                'scope': '两条公开目录字段抽样；原响应哈希无法从本地字段索引重算；单件权限和社区要求待核。',
                'citation': '参照馆藏说明保留演述者、来源、观察时间；引用还需核对转写者、译者及编辑者。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"已登记 {len(result['records'])} 条公开目录字段样本；未下载原始内容。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
