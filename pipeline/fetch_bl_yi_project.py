"""Snapshot the full BL EAP081 project search, without downloading images or audio."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from pipeline.archive_fetch import AGENT, MAX_HTML, json_bytes, robot_rules
from pipeline.bl_khmer import CC_BY, HOST, fields_for, read_json, soup_for
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

PROJECT = 'Preservation and Digitisation of Yi Archives in Public and Private Collections in Yunnan, China'
PAGE_SIZE = 100
SEARCH_FIELDS = ('Reference (shelfmark)', 'Title', 'Scope & Content', 'Collection Area', 'Languages', 'Date Range', 'Extent')


def page_url(page: int) -> str:
    if not isinstance(page, int) or not 1 <= page <= 30: raise IntakeError('项目检索页码超出范围。')
    args = [('f[project_collections_ssim][]', PROJECT), ('per_page', str(PAGE_SIZE)), ('sort', 'hierarchy')]
    if page > 1: args.append(('page', str(page)))
    return f'https://{HOST}/?' + urlencode(args)


def parse_page(raw: bytes, page: int, expected_total: int | None = None) -> tuple[list[dict], int]:
    soup = soup_for(raw)
    meta = soup.select_one('meta[name="totalResults"][content]')
    if not meta or not re.fullmatch(r'\d+', meta['content']): raise IntakeError('项目检索总数缺失。')
    total = int(meta['content'])
    if not 1 <= total <= 3000 or (expected_total is not None and total != expected_total):
        raise IntakeError('项目检索总数超出范围或采集时变化。')
    rows = []
    for position, doc in enumerate(soup.select('#documents .document'), 1):
        anchor = doc.select_one('h2 a[href]'); f = fields_for(doc)
        shelf = f.get('Reference (shelfmark)') or ''
        if not anchor: raise IntakeError('项目检索结果缺少链接。')
        target = urljoin(page_url(page), anchor['href']); parts = urlsplit(target)
        if (not re.fullmatch(r'EAP081/(?:\d{1,3})(?:/\d{1,3})*', shelf)
                or anchor.get_text(' ', strip=True) != shelf or not f.get('Title')
                or parts.scheme != 'https' or parts.netloc != HOST
                or not re.fullmatch(r'/catalog/\d{3}-\d{9}', parts.path) or parts.query or parts.fragment):
            raise IntakeError(f'项目检索结果的档号、题名或链接异常：{shelf}')
        rows.append({'page': page, 'position': position, 'shelfmark': shelf, 'record_id': parts.path.rsplit('/', 1)[-1],
                     'url': target, 'fields': {key: f.get(key) for key in SEARCH_FIELDS}})
    expected = min(PAGE_SIZE, max(0, total - (page - 1) * PAGE_SIZE))
    if len(rows) != expected: raise IntakeError(f'项目第 {page} 页结果数量不符。')
    return rows, total


def request_page(page: int, robots, delay: float) -> tuple[bytes, dict]:
    url = page_url(page)
    if delay < 2 or not robots.can_fetch(AGENT, url): raise IntakeError('项目检索请求受 robots.txt 限制。')
    time.sleep(delay)
    with urlopen(Request(url, headers={'User-Agent': AGENT, 'Accept': 'text/html', 'Accept-Encoding': 'identity'}), timeout=40) as response:
        if response.status != 200 or response.geturl() != url or response.headers.get_content_type() != 'text/html':
            raise IntakeError('项目检索页面状态、跳转或类型异常。')
        raw = response.read(MAX_HTML + 1)
    if not raw or len(raw) > MAX_HTML: raise IntakeError('项目检索页面为空或过大。')
    return raw, {'url': url, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
                 'observed_at': datetime.now(timezone.utc).isoformat()}


def _saved_page(folder: Path, name: str, page: int) -> tuple[bytes, dict]:
    path, meta = folder / name, folder / (name + '.json')
    if not path.is_file() or not meta.is_file(): raise IntakeError(f'项目网页或凭据不完整：{name}')
    raw, receipt = path.read_bytes(), read_json(meta)
    if (receipt.get('url') != page_url(page) or receipt.get('sha256') != sha256(raw).hexdigest()
            or receipt.get('bytes') != len(raw) or not receipt.get('observed_at')):
        raise IntakeError(f'项目网页或凭据不符：{name}')
    return raw, receipt


def load_snapshot(folder: Path) -> tuple[dict, list[dict]]:
    manifest, selection = read_json(folder / 'manifest.json'), read_json(folder / 'selection.json')
    total, pages = manifest.get('total'), manifest.get('pages')
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or manifest.get('catalogue_text_license') != CC_BY or manifest.get('project') != PROJECT
            or manifest.get('page_size') != PAGE_SIZE
            or not isinstance(total, int) or not 1 <= total <= 3000 or not isinstance(pages, list)
            or len(pages) != (total + PAGE_SIZE - 1) // PAGE_SIZE
            or manifest.get('selection_sha256') != sha256((folder / 'selection.json').read_bytes()).hexdigest()):
        raise IntakeError('彝文项目筛查快照清单无效。')
    rows = []
    for number, entry in enumerate(pages, 1):
        name = f'page-{number:02}.html'; raw, receipt = _saved_page(folder, name, number)
        parsed, _ = parse_page(raw, number, total)
        if entry != {'page': number, 'path': name, 'receipt_sha256': sha256((folder / (name + '.json')).read_bytes()).hexdigest(),
                     'count': len(parsed), **receipt}:
            raise IntakeError(f'项目第 {number} 页清单不符。')
        rows.extend(parsed)
    if (selection.get('version') != 1 or selection.get('rows') != rows or len(rows) != total
            or len({row['shelfmark'] for row in rows}) != total or len({row['record_id'] for row in rows}) != total):
        raise IntakeError('项目筛查索引与网页不符，或存在重复档号。')
    checks = manifest.get('boundary_checks')
    expected = sorted({1, len(pages)})
    if not isinstance(checks, list) or [x.get('page') for x in checks] != expected: raise IntakeError('首末检索核验缺失。')
    for entry in checks:
        number = entry['page']; name = f'boundary-{number:02}.html'; raw, receipt = _saved_page(folder, name, number)
        checked, _ = parse_page(raw, number, total)
        if (entry != {'page': number, 'path': name, 'receipt_sha256': sha256((folder / (name + '.json')).read_bytes()).hexdigest(), **receipt}
                or checked != [row for row in rows if row['page'] == number]):
            raise IntakeError(f'项目首末检索变动或凭据不符：{number}')
    return manifest, rows


def fetch(folder: Path, delay: float = 2) -> dict:
    if delay < 2: raise IntakeError('馆方请求间隔至少 2 秒。')
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / 'manifest.json').exists():
        load_snapshot(folder); return read_json(folder / 'manifest.json')
    robots, status = robot_rules(HOST, delay)
    pages, all_rows, total = [], [], None
    number = 1
    while total is None or number <= (total + PAGE_SIZE - 1) // PAGE_SIZE:
        name = f'page-{number:02}.html'; path, meta = folder / name, folder / (name + '.json')
        if path.exists() or meta.exists(): raw, receipt = _saved_page(folder, name, number)
        else:
            raw, receipt = request_page(number, robots, delay)
            parse_page(raw, number, total)
            exclusive_write(path, raw); exclusive_write(meta, json_bytes(receipt))
        rows, observed = parse_page(raw, number, total); total = observed
        pages.append({'page': number, 'path': name, 'receipt_sha256': sha256(meta.read_bytes()).hexdigest(), 'count': len(rows), **receipt})
        all_rows.extend(rows); print(f'已核验彝文项目目录页 {number}/{(total + PAGE_SIZE - 1)//PAGE_SIZE} · {len(rows)} 项', flush=True)
        number += 1
    if (len({row['shelfmark'] for row in all_rows}) != total or len({row['record_id'] for row in all_rows}) != total):
        raise IntakeError('项目跨页档号或馆方记录号重复。')
    selection_path = folder / 'selection.json'; selection = {'version': 1, 'rows': all_rows}
    if selection_path.exists():
        if read_json(selection_path) != selection: raise IntakeError('已有项目筛查索引与网页不符。')
    else: exclusive_write(selection_path, json_bytes(selection))
    checks = []
    for number in sorted({1, len(pages)}):
        name = f'boundary-{number:02}.html'; path, meta = folder / name, folder / (name + '.json')
        if path.exists() or meta.exists(): raw, receipt = _saved_page(folder, name, number)
        else:
            raw, receipt = request_page(number, robots, delay)
            checked, _ = parse_page(raw, number, total)
            if checked != [row for row in all_rows if row['page'] == number]: raise IntakeError('项目首末检索在采集期间变化。')
            exclusive_write(path, raw); exclusive_write(meta, json_bytes(receipt))
        checked, _ = parse_page(raw, number, total)
        if checked != [row for row in all_rows if row['page'] == number]: raise IntakeError('项目首末检索不一致。')
        checks.append({'page': number, 'path': name, 'receipt_sha256': sha256(meta.read_bytes()).hexdigest(), **receipt})
    manifest = {'version': 1, 'project': PROJECT, 'robots_status': status, 'catalogue_text_license': CC_BY,
                'total': total, 'page_size': PAGE_SIZE, 'selection_sha256': sha256(selection_path.read_bytes()).hexdigest(),
                'pages': pages, 'boundary_checks': checks,
                'scope': '公开项目检索目录网页；非故事计数；未请求手稿影像、音视频或转写。',
                'limits': '首末页重复核查，中间页未重复抓取；不能保证同时刻快照。检索摘要可能截断，单件条件和社区要求另核。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest)); load_snapshot(folder)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args(); manifest = fetch(args.output, args.delay)
    print(f"已核验 {manifest['total']} 条项目检索目录；未下载影像或媒体。")
    return 0


if __name__ == '__main__': raise SystemExit(main())
