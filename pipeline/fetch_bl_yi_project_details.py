"""Snapshot selected EAP081 catalogue pages and parent fonds, never images or media."""
import argparse
from hashlib import sha256
from pathlib import Path
import re

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.bl_khmer import CC_BY, HOST, fields_for, read_json, soup_for
from pipeline.bl_yi_project import selected
from pipeline.fetch_bl_yi_project import load_snapshot as load_index, parse_page, request_page
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

FIELDS = ('Record Id', 'Hierarchy Root Ancestor Record Id', 'Hierarchy Record Ids', 'Reference (shelfmark)',
          'Title', 'Scope & Content', 'Extent', 'Languages', 'Scripts', 'Start Date', 'End Date', 'Date Range',
          'Digitised Content', 'User Conditions', 'Information About Originals', 'Custodial History',
          'Arrangement', 'Record Type (Level)', 'Material Type')


def digest(path: Path) -> str: return sha256(path.read_bytes()).hexdigest()


def plan(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    items = selected(rows)
    groups = {row['shelfmark'].split('/')[1] for row in items}
    parents = [row for row in rows if row['shelfmark'].startswith('EAP081/')
               and len(row['shelfmark'].split('/')) == 2 and row['shelfmark'].split('/')[1] in groups]
    if (len(parents) != len(groups) or any(not row['record_id'].startswith('032-') for row in parents)
            or len({row['shelfmark'] for row in parents}) != len(parents)):
        raise IntakeError('筛选单件的父级馆藏不完整或不唯一。')
    return parents, items


def filename(row: dict) -> str:
    parts = row['shelfmark'].split('/')
    if len(parts) == 2: return f'parent-{int(parts[1]):03}.html'
    if len(parts) == 3: return f'item-{int(parts[1]):03}-{int(parts[2]):03}.html'
    raise IntakeError('馆藏档号层级超出筛查范围。')


def parse_detail(raw: bytes, row: dict, parent_ids: dict[str, str]) -> dict:
    fields = fields_for(soup_for(raw)); parts = row['shelfmark'].split('/')
    root = row['record_id'] if len(parts) == 2 else parent_ids.get('EAP081/' + parts[1])
    level = 'Fonds' if len(parts) == 2 else 'File'
    if (not root or fields.get('Record Id') != row['record_id'] or fields.get('Reference (shelfmark)') != row['shelfmark']
            or fields.get('Title') != row['fields']['Title'] or fields.get('Hierarchy Root Ancestor Record Id') != root
            or root not in fields.get('Hierarchy Record Ids', '') or fields.get('Record Type (Level)') != level):
        raise IntakeError(f"彝文项目目录身份、题名或所属馆藏不符：{row['shelfmark']}")
    return {key: fields.get(key) for key in FIELDS}


def _saved(folder: Path, row: dict) -> tuple[bytes, dict]:
    name = filename(row); path, meta = folder / name, folder / (name + '.json')
    if not path.is_file() or not meta.is_file(): raise IntakeError(f'馆方单件网页或凭据不完整：{row["shelfmark"]}')
    raw, receipt = path.read_bytes(), read_json(meta)
    if (receipt.get('url') != row['url'] or receipt.get('sha256') != sha256(raw).hexdigest()
            or receipt.get('bytes') != len(raw) or not receipt.get('observed_at')):
        raise IntakeError(f'馆方单件网页或凭据不符：{row["shelfmark"]}')
    return raw, receipt


def load_snapshot(folder: Path, index_folder: Path) -> tuple[dict, list[tuple[dict, Path, dict]], list[tuple[dict, Path, dict]]]:
    index_manifest, rows = load_index(index_folder); parents, items = plan(rows)
    selection, manifest = read_json(folder / 'selection.json'), read_json(folder / 'manifest.json')
    if (selection != {'version': 1, 'index_manifest_sha256': digest(index_folder / 'manifest.json'), 'parents': parents, 'items': items}
            or manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or manifest.get('catalogue_text_license') != CC_BY or manifest.get('index_manifest_sha256') != digest(index_folder / 'manifest.json')
            or manifest.get('selection_sha256') != digest(folder / 'selection.json')
            or len(manifest.get('parents', [])) != len(parents) or len(manifest.get('items', [])) != len(items)):
        raise IntakeError('彝文单件选取、项目索引或快照清单无效。')
    parent_ids = {row['shelfmark']: row['record_id'] for row in parents}; results = []
    for entries, records in ((parents, manifest['parents']), (items, manifest['items'])):
        group = []
        for row, entry in zip(entries, records, strict=True):
            name = filename(row); raw, receipt = _saved(folder, row); meta = folder / (name + '.json')
            if entry != {'shelfmark': row['shelfmark'], 'path': name, 'receipt_sha256': digest(meta), **receipt}:
                raise IntakeError(f"彝文馆方单件快照清单不符：{row['shelfmark']}")
            group.append((row, folder / name, parse_detail(raw, row, parent_ids)))
        results.append(group)
    boundaries = manifest.get('index_boundary_rechecks')
    expected = sorted({1, len(index_manifest['pages'])})
    if not isinstance(boundaries, list) or [v.get('page') for v in boundaries] != expected:
        raise IntakeError('详情采集后的项目检索首末复查缺失。')
    for entry in boundaries:
        number = entry['page']; name = f'index-recheck-{number:02}.html'; path, meta = folder / name, folder / (name + '.json')
        raw = path.read_bytes(); receipt = read_json(meta)
        parsed, total = parse_page(raw, number, index_manifest['total'])
        from pipeline.fetch_bl_yi_project import page_url
        if (receipt.get('url') != page_url(number) or receipt.get('sha256') != digest(path)
                or receipt.get('bytes') != len(raw) or not receipt.get('observed_at')
                or entry != {'page': number, 'path': name, 'receipt_sha256': digest(meta), **receipt}
                or total != index_manifest['total'] or parsed != [r for r in rows if r['page'] == number]):
            raise IntakeError('详情采集后的项目检索首末页或凭据不符。')
    return manifest, results[0], results[1]


def fetch(folder: Path, index_folder: Path, delay: float = 2) -> dict:
    if delay < 2: raise IntakeError('馆方请求间隔至少 2 秒。')
    index_manifest, rows = load_index(index_folder); parents, items = plan(rows)
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / 'manifest.json').exists():
        load_snapshot(folder, index_folder); return read_json(folder / 'manifest.json')
    selection_path = folder / 'selection.json'
    selection = {'version': 1, 'index_manifest_sha256': digest(index_folder / 'manifest.json'), 'parents': parents, 'items': items}
    if selection_path.exists():
        if read_json(selection_path) != selection: raise IntakeError('既有筛选清单与项目索引不符。')
    else: exclusive_write(selection_path, json_bytes(selection))
    robots, status = robot_rules(HOST, delay); parent_ids = {row['shelfmark']: row['record_id'] for row in parents}
    groups = []
    for label, entries in (('父级馆藏', parents), ('单件', items)):
        stored = []
        for number, row in enumerate(entries, 1):
            name = filename(row); path, meta = folder / name, folder / (name + '.json')
            if path.exists() or meta.exists(): raw, receipt = _saved(folder, row)
            else:
                raw, observed = request_html(row['url'], HOST, robots, delay); parse_detail(raw, row, parent_ids)
                receipt = {'url': row['url'], 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw), 'observed_at': observed}
                exclusive_write(path, raw); exclusive_write(meta, json_bytes(receipt))
            parse_detail(raw, row, parent_ids)
            stored.append({'shelfmark': row['shelfmark'], 'path': name, 'receipt_sha256': digest(meta), **receipt})
            print(f'已核验彝文项目{label} {number}/{len(entries)} · {row["shelfmark"]}', flush=True)
        groups.append(stored)
    checks = []
    for number in sorted({1, len(index_manifest['pages'])}):
        name = f'index-recheck-{number:02}.html'; path, meta = folder / name, folder / (name + '.json')
        if path.exists() or meta.exists():
            if not path.is_file() or not meta.is_file(): raise IntakeError('项目检索复查或凭据不完整。')
            raw, receipt = path.read_bytes(), read_json(meta)
        else:
            raw, receipt = request_page(number, robots, delay)
            parsed, _ = parse_page(raw, number, index_manifest['total'])
            if parsed != [row for row in rows if row['page'] == number]: raise IntakeError('详情采集期间项目首末检索变化。')
            exclusive_write(path, raw); exclusive_write(meta, json_bytes(receipt))
        checks.append({'page': number, 'path': name, 'receipt_sha256': digest(meta), **receipt})
    manifest = {'version': 1, 'robots_status': status, 'catalogue_text_license': CC_BY,
                'index_manifest_sha256': digest(index_folder / 'manifest.json'), 'selection_sha256': digest(selection_path),
                'parents': groups[0], 'items': groups[1], 'index_boundary_rechecks': checks,
                'scope': '馆方单件及父级目录网页；关键词是筛查线索，非故事分类；未请求影像或音视频。',
                'limits': '仅复查项目首页与末页，不能保证采集过程原子性；图像、具体权利和社区要求另核。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest)); load_snapshot(folder, index_folder)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args(); manifest = fetch(args.output, args.index, args.delay)
    print(f"已核验 {len(manifest['parents'])} 个父级馆藏和 {len(manifest['items'])} 件单件目录。")
    return 0


if __name__ == '__main__': raise SystemExit(main())
