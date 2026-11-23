"""Fetch public DataCite registration metadata for DOI references in the Na book."""

import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pipeline.archive_fetch import AGENT, json_bytes, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError
from pipeline.na_tone_book import DATACITE_API, selection

MAX_BYTES = 2 * 1024 * 1024


def validate_envelope(envelope: dict, number: str) -> dict | None:
    if (not isinstance(envelope, dict) or envelope.get('id') != number
            or envelope.get('url') != DATACITE_API + number or envelope.get('status') not in (200, 404)
            or not isinstance(envelope.get('observed_at'), str)):
        raise IntakeError(f'DataCite 回执格式无效：{number}')
    try:
        when = datetime.fromisoformat(envelope['observed_at'])
        raw = base64.b64decode(envelope['raw_base64'], validate=True)
        payload = json.loads(raw.decode('utf-8'))
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        raise IntakeError(f'DataCite 回执内容无效：{number}') from error
    if when.utcoffset() is None or not raw or len(raw) > MAX_BYTES or sha256(raw).hexdigest() != envelope.get('raw_sha256'):
        raise IntakeError(f'DataCite 原始响应哈希或时间无效：{number}')
    if envelope['status'] == 404:
        return None  # An observed 404 is not proof that the object does not exist.
    data = payload.get('data') if isinstance(payload, dict) else None
    attrs = data.get('attributes') if isinstance(data, dict) else None
    expected = f'10.24397/pangloss-{number}'
    if (not isinstance(attrs, dict) or str(data.get('id', '')).lower() != expected
            or str(attrs.get('doi', '')).lower() != expected or attrs.get('state') != 'findable'):
        raise IntakeError(f'DataCite 返回的 DOI 或公开状态不符：{number}')
    return attrs


def fetch_one(number: str, robots, delay: float) -> dict:
    if not re.fullmatch(r'\d{7}', number) or delay < 2:
        raise IntakeError('DOI 编号无效或请求间隔小于 2 秒。')
    url = DATACITE_API + number
    if not robots.can_fetch(AGENT, url):
        raise IntakeError(f'DataCite robots.txt 不允许获取：{number}')
    time.sleep(delay)
    try:
        with urlopen(Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json',
                                          'Accept-Encoding': 'identity'}), timeout=30) as response:
            if response.status != 200 or response.geturl() != url or response.headers.get_content_type() != 'application/json':
                raise IntakeError(f'DataCite 状态、跳转或响应类型不符：{number}')
            status, raw = response.status, response.read(MAX_BYTES + 1)
    except HTTPError as error:
        if error.code != 404:
            raise  # In particular, stop on 403 or 429; never bypass access limits.
        if error.geturl() != url:
            raise IntakeError(f'DataCite 404 响应经过未知跳转：{number}') from error
        status, raw = 404, error.read(MAX_BYTES + 1)
    envelope = {'id': number, 'url': url, 'status': status, 'observed_at': datetime.now(timezone.utc).isoformat(),
                'raw_sha256': sha256(raw).hexdigest(), 'raw_base64': base64.b64encode(raw).decode('ascii')}
    validate_envelope(envelope, number)
    return envelope


def fetch(book: Path, tex: Path, corpus: Path, folder: Path, *, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError('DataCite 请求间隔至少为 2 秒。')
    expected = selection(book, tex, corpus)
    folder.mkdir(parents=True, exist_ok=True)
    selection_path, manifest_path = folder / 'selection.json', folder / 'manifest.json'
    if manifest_path.exists():
        raise IntakeError('此目录已有完整清单；请保留并另建目录。')
    if selection_path.exists():
        if selection_path.is_symlink() or json.loads(selection_path.read_text(encoding='utf-8')) != expected:
            raise IntakeError('已存在的 DOI 选取范围或来源哈希不同。')
    else:
        exclusive_write(selection_path, json_bytes(expected))
    records_dir = folder / 'records'
    records_dir.mkdir(exist_ok=True)
    robots, robots_status = robot_rules('api.datacite.org', delay)
    entries = []
    for number in expected['fetch_ids']:
        path = records_dir / f'{number}.json'
        if path.exists():
            if path.is_symlink():
                raise IntakeError(f'DataCite 快照不能是符号链接：{number}')
            envelope = json.loads(path.read_text(encoding='utf-8'))
            validate_envelope(envelope, number)
        else:
            envelope = fetch_one(number, robots, delay)
            exclusive_write(path, json_bytes(envelope))
        entries.append({'id': number, 'path': f'records/{number}.json', 'status': envelope['status'],
                        'sha256': sha256(path.read_bytes()).hexdigest()})
        print(f"已核验 DataCite {len(entries)}/{len(expected['fetch_ids'])} · {number} · HTTP {envelope['status']}", flush=True)
    manifest = {'version': 1, 'selection_sha256': sha256(selection_path.read_bytes()).hexdigest(),
                'robots_status': robots_status, 'metadata_license': 'CC0 1.0', 'records': entries,
                'scope': '仅保存 DataCite 公共 DOI 注册元数据的原始响应；资源与附件权利另核。'}
    exclusive_write(manifest_path, json_bytes(manifest))
    load(folder, book, tex, corpus)
    return manifest


def load(folder: Path, book: Path, tex: Path, corpus: Path) -> tuple[dict, dict, dict]:
    try:
        expected = selection(book, tex, corpus)
        selected = json.loads((folder / 'selection.json').read_text(encoding='utf-8'))
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise IntakeError('DataCite 清单格式无效。')
        records = manifest.get('records')
        if (selected != expected or manifest.get('version') != 1
                or manifest.get('selection_sha256') != sha256((folder / 'selection.json').read_bytes()).hexdigest()
                or not isinstance(records, list) or len(records) != len(expected['fetch_ids'])):
            raise IntakeError('DataCite 清单与书籍、目录或选取范围不符。')
        result = {}
        for number, entry in zip(expected['fetch_ids'], records, strict=True):
            path = folder / 'records' / f'{number}.json'
            if (not isinstance(entry, dict) or entry.get('id') != number or entry.get('path') != f'records/{number}.json'
                    or path.is_symlink() or sha256(path.read_bytes()).hexdigest() != entry.get('sha256')):
                raise IntakeError(f'DataCite 快照索引或哈希不符：{number}')
            envelope = json.loads(path.read_text(encoding='utf-8'))
            attrs = validate_envelope(envelope, number)
            if entry.get('status') != envelope['status']:
                raise IntakeError(f'DataCite HTTP 状态与清单不符：{number}')
            result[number] = attrs
        return selected, manifest, result
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f'DataCite 索引无法读取：{error}') from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book', type=Path, required=True)
    parser.add_argument('--tex', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2.0)
    args = parser.parse_args()
    try:
        manifest = fetch(args.book, args.tex, args.corpus, args.output, delay=args.delay)
    except (ValueError, OSError, TypeError, HTTPError) as error:
        print(f'DataCite 获取停止；同一范围内已保存的快照可续跑：{error}', file=sys.stderr)
        return 1
    print(f"已完成 {len(manifest['records'])} 条 DOI 登记元数据核验。")
    return 0


if __name__ == '__main__': raise SystemExit(main())
