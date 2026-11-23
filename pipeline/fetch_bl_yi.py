"""Snapshot the BL EAP081/25 catalogue, without requesting recordings."""
import argparse
from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.bl_khmer import CC_BY, HOST, fields_for, read_json, soup_for
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

ROOT_URL = f'https://{HOST}/catalog/032-001617335'


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def parse_root(raw: bytes) -> tuple[dict, list[dict]]:
    soup = soup_for(raw)
    fields = fields_for(soup)
    if (fields.get('Record Id') != '032-001617335' or fields.get('Reference (shelfmark)') != 'EAP081/25'
            or fields.get('Languages') != 'Nuosu' or '6 electronic folders' not in fields.get('Extent', '')
            or '81 mpa files' not in fields.get('Extent', '') or '2004' not in fields.get('Scope & Content', '')
            or '2009' not in fields.get('Scope & Content', '')):
        raise IntakeError('彝语馆藏组档号、数量、语言或项目范围不符。')
    label = next((dt for dt in soup.select('dt') if dt.get_text(' ', strip=True) == 'Contains:'), None)
    dd = label.find_next_sibling('dd') if label else None
    children = []
    for anchor in dd.find_all('a', href=True) if dd else []:
        bold = anchor.find('b')
        shelf = bold.get_text(' ', strip=True) if bold else ''
        target = urljoin(ROOT_URL, anchor['href'])
        parsed = urlsplit(target)
        if (shelf == 'EAP081/25' and parsed.scheme == 'https' and parsed.netloc == HOST and parsed.path == '/'
                and parse_qs(parsed.query).get('f[parent_reference_ssi][]') == [shelf]):
            continue
        match = re.fullmatch(r'EAP081/25/(\d)', shelf)
        if (not match or parsed.scheme != 'https' or parsed.netloc != HOST
                or not re.fullmatch(r'/catalog/040-\d{9}', parsed.path) or parsed.query or parsed.fragment):
            raise IntakeError('彝语馆藏子组链接无效。')
        children.append({'number': int(match.group(1)), 'record_id': parsed.path.rsplit('/', 1)[-1], 'url': target})
    if sorted(child['number'] for child in children) != list(range(1, 7)) or len({child['record_id'] for child in children}) != 6:
        raise IntakeError('彝语馆藏子组缺失或重复。')
    return fields, children


def parse_child(raw: bytes, child: dict) -> dict:
    soup = soup_for(raw)
    fields = fields_for(soup)
    shelf = f"EAP081/25/{child['number']}"
    if (fields.get('Record Id') != child['record_id'] or fields.get('Hierarchy Root Ancestor Record Id') != '032-001617335'
            or fields.get('Reference (shelfmark)') != shelf or fields.get('Languages') != 'Nuosu'
            or fields.get('Record Type (Level)') != 'File'
            or not fields.get('User Conditions', '').startswith('Access is for research purposes only')
            or not all(fields.get(key) for key in ('Title', 'Scope & Content', 'Extent'))):
        raise IntakeError(f'彝语馆藏子组档号、字段或研究访问条件不符：{shelf}')
    return {key: fields.get(key) for key in ('Record Id', 'Reference (shelfmark)', 'Title', 'Scope & Content', 'Extent',
            'Languages', 'Scripts', 'Start Date', 'End Date', 'Date Range', 'Digitised Content', 'User Conditions',
            'Information About Originals', 'Record Type (Level)')}


def load_snapshot(folder: Path) -> tuple[dict, dict, list[tuple[dict, Path, str, dict]]]:
    manifest, selection = read_json(folder / 'manifest.json'), read_json(folder / 'selection.json')
    root_path = folder / 'root.html'
    root, children = parse_root(root_path.read_bytes())
    if (selection.get('version') != 1 or selection.get('source_url') != ROOT_URL or selection.get('root_sha256') != digest(root_path)
            or selection.get('children') != children or manifest.get('version') != 1
            or manifest.get('selection_sha256') != digest(folder / 'selection.json')
            or manifest.get('catalogue_text_license') != CC_BY or len(manifest.get('records', [])) != 6):
        raise IntakeError('彝语馆藏快照清单不符。')
    result = []
    for child, entry in zip(children, manifest['records'], strict=True):
        number = child['number']
        name, meta = f'record-{number:02d}.html', f'record-{number:02d}.json'
        if entry.get('number') != number or entry.get('path') != name or entry.get('meta') != meta:
            raise IntakeError(f'彝语馆藏子组清单不符：{number}')
        path, metadata = folder / name, read_json(folder / meta)
        checksum = digest(path)
        if (entry.get('sha256') != checksum or entry.get('meta_sha256') != digest(folder / meta)
                or metadata.get('url') != child['url'] or metadata.get('sha256') != checksum
                or not isinstance(metadata.get('observed_at'), str)):
            raise IntakeError(f'彝语馆藏子组快照哈希不符：{number}')
        result.append((child, path, checksum, parse_child(path.read_bytes(), child)))
    return selection, root, result


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / 'manifest.json').exists():
        load_snapshot(folder)
        return read_json(folder / 'manifest.json')
    robots, status = robot_rules(HOST, delay)
    root_path, selection_path = folder / 'root.html', folder / 'selection.json'
    if root_path.exists() or selection_path.exists():
        if not root_path.is_file() or not selection_path.is_file():
            raise IntakeError('馆藏组快照或选取清单不完整，须核对后续跑。')
        selection = read_json(selection_path)
        _, children = parse_root(root_path.read_bytes())
        if selection.get('source_url') != ROOT_URL or selection.get('root_sha256') != digest(root_path) or selection.get('children') != children:
            raise IntakeError('已保存的馆藏组快照与清单不符。')
    else:
        raw, observed = request_html(ROOT_URL, HOST, robots, delay)
        _, children = parse_root(raw)
        exclusive_write(root_path, raw)
        selection = {'version': 1, 'source_url': ROOT_URL, 'root_sha256': sha256(raw).hexdigest(),
                     'observed_at': observed, 'children': children}
        exclusive_write(selection_path, json_bytes(selection))
    entries = []
    for child in children:
        number = child['number']
        path, meta = folder / f'record-{number:02d}.html', folder / f'record-{number:02d}.json'
        if path.exists() or meta.exists():
            if not path.is_file() or not meta.is_file():
                raise IntakeError(f'子组快照或指纹不完整：{number}')
            metadata = read_json(meta)
            if metadata.get('url') != child['url'] or metadata.get('sha256') != digest(path):
                raise IntakeError(f'子组快照或指纹不符：{number}')
            parse_child(path.read_bytes(), child)
        else:
            raw, observed = request_html(child['url'], HOST, robots, delay)
            parse_child(raw, child)
            exclusive_write(path, raw)
            exclusive_write(meta, json_bytes({'url': child['url'], 'sha256': sha256(raw).hexdigest(), 'observed_at': observed}))
        entries.append({'number': number, 'path': path.name, 'sha256': digest(path), 'meta': meta.name, 'meta_sha256': digest(meta)})
        print(f'已核验彝语录音子组 {number}/6 · EAP081/25/{number}', flush=True)
    manifest = {'version': 1, 'selection_sha256': digest(selection_path), 'robots_status': status,
                'catalogue_text_license': CC_BY, 'records': entries,
                'scope': '馆方目录网页；不请求音频、转写或受验证限制的数字内容。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    load_snapshot(folder)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    manifest = fetch(args.output, args.delay)
    print(f"已核验 {len(manifest['records'])} 个馆方子组目录；未请求音频。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
