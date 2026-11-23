"""Derive page-exact, review-only OCR ranges from the existing Cole scan snapshot."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

from pipeline.archive_fetch import json_bytes
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError
from pipeline.philippines_cole import (IDENTIFIER, OCR_NAME, OCR_SHA, PAGE_INDEX_NAME, PAGE_INDEX_SHA,
    TOC, _normal, load_catalogue, node_id, scan_url)


def derive_segments(text: str, offsets: list, rows: list[dict]) -> list[dict]:
    """Keep page strings byte-equivalent after UTF-8 encoding; boundaries remain candidates."""
    if not isinstance(text, str) or not isinstance(offsets, list) or not rows:
        raise IntakeError('OCR 或目录格式无效。')
    last = 0
    for entry in offsets:
        if (not isinstance(entry, list) or len(entry) != 4 or any(type(n) is not int for n in entry)
                or entry[0] != last or not entry[0] <= entry[1] <= len(text)):
            raise IntakeError('OCR 页偏移不连续或越界。')
        last = entry[1]
    if last != len(text): raise IntakeError('OCR 页偏移未覆盖全文。')
    starts = [row['scan'] for row in rows]
    if starts != sorted(set(starts)) or any(type(n) is not int or not 1 <= n <= len(offsets) for n in starts):
        raise IntakeError('OCR 候选起始页无效或重复。')
    stops = []
    for scan in range(starts[-1] + 1, min(len(offsets), starts[-1] + 12) + 1):
        start, end = offsets[scan - 1][:2]
        lines = [line for line in text[start:end].splitlines() if line.strip()]
        if lines and _normal(lines[0]) == 'pronunciationofphilippinenames': stops.append(scan)
    if len(stops) != 1: raise IntakeError('末篇后的发音表起始页无法唯一识别。')
    final_stop = stops[0]; result = []
    for row, stop in zip(rows, starts[1:] + [final_stop], strict=True):
        start_scan = row['scan']
        if stop <= start_scan: raise IntakeError('OCR 篇章候选范围重叠或为空。')
        pages = []
        for scan in range(start_scan, stop):
            start, end = offsets[scan - 1][:2]; raw = text[start:end]
            pages.append({'scan': scan, 'scan_url': scan_url(scan), 'character_start': start, 'character_end': end,
                          'text_sha256': sha256(raw.encode('utf-8')).hexdigest(), 'text': raw})
        result.append({'id': node_id(row), 'printed_page': row['printed_page'], 'title': row['title'],
                       'start_scan': start_scan, 'end_scan_exclusive': stop,
                       'boundary_basis': '下一目录项的候选首扫描页' if stop != final_stop else '后续发音表的候选首扫描页',
                       'pages': pages})
    return result


def source_segments(toc: Path, snapshots: Path) -> tuple[list[dict], dict]:
    rows = load_catalogue(toc, snapshots)
    try:
        text = gzip.decompress((snapshots / OCR_NAME).read_bytes()).decode('utf-8')
        offsets = json.loads(gzip.decompress((snapshots / PAGE_INDEX_NAME).read_bytes()).decode('utf-8'))
    except (OSError, UnicodeError, EOFError, json.JSONDecodeError) as error:
        raise IntakeError(f'OCR 原始数据无法解码：{error}') from error
    return derive_segments(text, offsets, rows), {'toc_sha256': sha256(toc.read_bytes()).hexdigest(),
            'ocr_sha256': OCR_SHA, 'page_index_sha256': PAGE_INDEX_SHA, 'original_scan_count': len(offsets)}


def create(folder: Path, toc: Path, snapshots: Path) -> dict:
    segments, source = source_segments(toc, snapshots)
    folder.mkdir(parents=True, exist_ok=False)
    entries = []
    for segment in segments:
        name = segment['id'] + '.json'; path = folder / name
        exclusive_write(path, json_bytes(segment))
        entries.append({'id': segment['id'], 'path': name, 'sha256': sha256(path.read_bytes()).hexdigest()})
    manifest = {'version': 1, 'edition': IDENTIFIER, **source, 'entries': entries,
                'scope': '目录页码与未校对 OCR 的扫描页候选；逐页保留页眉、脚注、误字与原始换行，不自动修订。',
                'limits': '下一目录项的候选起始页只是页面范围线索，不能证明篇章边界；原书美国公有领域状态及其他地区、数字副本权利需分别核查。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    load(folder, toc, snapshots)
    return manifest


def load(folder: Path, toc: Path, snapshots: Path) -> tuple[dict, list[dict]]:
    try:
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f'OCR 候选范围清单无法读取：{error}') from error
    expected, source = source_segments(toc, snapshots)
    if not isinstance(manifest, dict):
        raise IntakeError('OCR 候选范围清单格式无效。')
    entries = manifest.get('entries')
    if (manifest.get('version') != 1 or manifest.get('edition') != IDENTIFIER
            or any(manifest.get(key) != value for key, value in source.items())
            or not isinstance(entries, list) or len(entries) != len(expected)):
        raise IntakeError('OCR 清单与原始目录、OCR 或分页索引不一致。')
    result = []
    for row, entry in zip(expected, entries, strict=True):
        name = row['id'] + '.json'; path = folder / name
        if not isinstance(entry, dict):
            raise IntakeError(f"OCR 候选范围清单条目格式无效：{row['id']}")
        try:
            raw = path.read_bytes()
            content = json.loads(raw.decode('utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise IntakeError(f"OCR 候选页文件无法读取：{row['id']} / {error}") from error
        if (entry.get('id') != row['id'] or entry.get('path') != name or entry.get('sha256') != sha256(raw).hexdigest()
                or content != row):
            raise IntakeError(f"OCR 页范围或文字与原始快照不符：{row['id']}")
        result.append(row)
    return manifest, result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--toc', type=Path, default=TOC)
    parser.add_argument('--snapshots', type=Path, required=True)
    args = parser.parse_args(); manifest = create(args.output, args.toc, args.snapshots)
    print(f"已按原始分页建立 {len(manifest['entries'])} 个未校对 OCR 候选范围。")
    return 0


if __name__ == '__main__': raise SystemExit(main())
