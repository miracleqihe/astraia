"""Snapshot the British Library Burma gramophone catalogue, without audio."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from pipeline.archive_fetch import AGENT, MAX_HTML, json_bytes, request_html, robot_rules
from pipeline.bl_khmer import CC_BY, HOST, fields_for, read_json, soup_for
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

ROOT_URL = f'https://{HOST}/catalog/037-000091137'
SERIES_URL = f'https://{HOST}/catalog/036-000091073'
SEARCH_URL = f'https://{HOST}/?' + urlencode([('f[parent_reference_ssi][]', 'IOR/S/2/3'),
                                              ('per_page', '100'), ('sort', 'hierarchy')])
EXPECTED = 35


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def parse_root(raw: bytes) -> dict:
    f = fields_for(soup_for(raw))
    if (f.get('Record Id') != '037-000091137' or f.get('Reference (shelfmark)') != 'IOR/S/2/3'
            or f.get('Title') != 'Burma' or f.get('Extent') != '35 gramophone records'
            or f.get('Record Type (Level)') != 'SubSeries'):
        raise IntakeError('缅甸录音馆藏组档号或数量不符。')
    return f


def parse_series(raw: bytes) -> dict:
    f = fields_for(soup_for(raw))
    description = f.get('Scope & Content', '')
    if (f.get('Record Id') != '036-000091073' or f.get('Reference (shelfmark)') != 'IOR/S/2'
            or not all(value in description for value in ('Burma', 'Parable of the Prodigal Son', 'S/2/2/1'))
            or not f.get('User Conditions')):
        raise IntakeError('语言调查总体目录或访问说明不符。')
    return f


def parse_search(raw: bytes) -> list[dict]:
    soup = soup_for(raw)
    children = []
    for doc in soup.select('#documents .document'):
        anchor = doc.select_one('h2 a[href]')
        f = fields_for(doc)
        if not anchor: raise IntakeError('缅甸录音检索结果缺少单件链接。')
        shelf, title = f.get('Reference (shelfmark)'), f.get('Title')
        match = re.fullmatch(r'IOR/S/2/3/(\d{1,2})', shelf or '')
        target = urljoin(ROOT_URL, anchor['href'])
        parts = urlsplit(target)
        if (not match or anchor.get_text(' ', strip=True) != shelf or not title
                or parts.scheme != 'https' or parts.netloc != HOST or not re.fullmatch(r'/catalog/040-\d{9}', parts.path)
                or parts.query or parts.fragment):
            raise IntakeError('缅甸录音检索结果的档号、题名或链接异常。')
        children.append({'number': int(match.group(1)), 'shelfmark': shelf, 'title': title,
                         'record_id': parts.path.rsplit('/', 1)[-1], 'url': target})
    if (len(children) != EXPECTED or [x['number'] for x in children] != list(range(1, EXPECTED + 1))
            or len({x['record_id'] for x in children}) != EXPECTED):
        raise IntakeError('缅甸录音检索结果数量、顺序或唯一编号不符。')
    return children


def parse_item(raw: bytes, child: dict) -> dict:
    f = fields_for(soup_for(raw))
    if (f.get('Record Id') != child['record_id'] or f.get('Reference (shelfmark)') != child['shelfmark']
            or f.get('Hierarchy Root Ancestor Record Id') != '032-000090901'
            or '037-000091137' not in f.get('Hierarchy Record Ids', '') or f.get('Record Type (Level)') != 'File'
            or f.get('Title') != child['title'] or f.get('Extent') != '1 gramophone record'
            or not f.get('Languages') or not f.get('Scope & Content')):
        raise IntakeError(f"缅甸录音单件身份、题名或目录字段不符：{child['shelfmark']}")
    return {key: f.get(key) for key in ('Record Id', 'Reference (shelfmark)', 'Title', 'Scope & Content', 'Extent',
            'Languages', 'Scripts', 'Start Date', 'End Date', 'Date Range', 'Digitised Content', 'User Conditions',
            'Former External References', 'Record Type (Level)', 'Material Type')}


def request_search(robots, delay: float) -> tuple[bytes, str]:
    from datetime import datetime, timezone
    if delay < 2 or not robots.can_fetch(AGENT, SEARCH_URL):
        raise IntakeError('馆藏检索地址或 robots.txt 不允许访问。')
    time.sleep(delay)
    with urlopen(Request(SEARCH_URL, headers={'User-Agent': AGENT, 'Accept': 'text/html', 'Accept-Encoding': 'identity'}), timeout=30) as response:
        if response.status != 200 or response.geturl() != SEARCH_URL or response.headers.get_content_type() != 'text/html':
            raise IntakeError('馆藏检索页面状态、跳转或内容类型异常。')
        raw = response.read(MAX_HTML + 1)
    if not raw or len(raw) > MAX_HTML: raise IntakeError('馆藏检索页面为空或过大。')
    raw.decode('utf-8')
    return raw, datetime.now(timezone.utc).isoformat()


def load_snapshot(folder: Path) -> tuple[dict, dict, dict, list[tuple[dict, Path, dict]]]:
    manifest, selection = read_json(folder / 'manifest.json'), read_json(folder / 'selection.json')
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or manifest.get('catalogue_text_license') != CC_BY or manifest.get('selection_sha256') != digest(folder / 'selection.json')):
        raise IntakeError('缅甸录音快照清单无效。')
    expected_pages = [('root.html', ROOT_URL), ('series.html', SERIES_URL), ('search.html', SEARCH_URL), ('search-final.html', SEARCH_URL)]
    if len(manifest.get('pages', [])) != len(expected_pages): raise IntakeError('馆藏组或检索快照缺失。')
    for entry, (name, url) in zip(manifest['pages'], expected_pages, strict=True):
        raw = (folder / name).read_bytes()
        if (entry.get('path') != name or entry.get('url') != url or entry.get('sha256') != sha256(raw).hexdigest()
                or entry.get('bytes') != len(raw) or not entry.get('observed_at')):
            raise IntakeError(f'馆藏组或检索快照哈希不符：{name}')
    root, series = parse_root((folder / 'root.html').read_bytes()), parse_series((folder / 'series.html').read_bytes())
    children = parse_search((folder / 'search.html').read_bytes())
    if (parse_search((folder / 'search-final.html').read_bytes()) != children or selection.get('version') != 1
            or selection.get('search_sha256') != digest(folder / 'search.html') or selection.get('children') != children
            or len(manifest.get('records', [])) != EXPECTED):
        raise IntakeError('缅甸录音目录首末检索或选取清单不一致。')
    result = []
    for child, entry in zip(children, manifest['records'], strict=True):
        number = child['number']; path = folder / f'item-{number:02d}.html'; meta = folder / f'item-{number:02d}.json'
        info = read_json(meta)
        if (entry.get('number') != number or entry.get('path') != path.name or entry.get('meta') != meta.name
                or entry.get('sha256') != digest(path) or entry.get('meta_sha256') != digest(meta)
                or info.get('url') != child['url'] or info.get('sha256') != digest(path) or not info.get('observed_at')):
            raise IntakeError(f'缅甸录音单件网页或凭据不符：{number}')
        result.append((child, path, parse_item(path.read_bytes(), child)))
    return manifest, root, series, result


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2: raise IntakeError('馆藏请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / 'manifest.json').exists():
        load_snapshot(folder)
        return read_json(folder / 'manifest.json')
    robots, status = robot_rules(HOST, delay)
    pages = []
    for name, url in [('root.html', ROOT_URL), ('series.html', SERIES_URL), ('search.html', SEARCH_URL)]:
        path, meta = folder / name, folder / (name + '.json')
        if path.exists() or meta.exists():
            if not path.is_file() or not meta.is_file(): raise IntakeError(f'馆藏组快照或凭据不完整：{name}')
            receipt = read_json(meta)
            if receipt.get('url') != url or receipt.get('sha256') != digest(path): raise IntakeError(f'馆藏组快照或凭据不符：{name}')
        else:
            raw, observed = request_search(robots, delay) if name == 'search.html' else request_html(url, HOST, robots, delay)
            if name == 'root.html': parse_root(raw)
            elif name == 'series.html': parse_series(raw)
            else: parse_search(raw)
            exclusive_write(path, raw)
            receipt = {'url': url, 'sha256': digest(path), 'bytes': len(raw), 'observed_at': observed}
            exclusive_write(meta, json_bytes(receipt))
        pages.append({'path': name, **receipt})
    children = parse_search((folder / 'search.html').read_bytes())
    selection_path = folder / 'selection.json'
    selection = {'version': 1, 'search_sha256': digest(folder / 'search.html'), 'children': children}
    if selection_path.exists():
        if read_json(selection_path) != selection: raise IntakeError('已有单件选取清单与检索不符。')
    else: exclusive_write(selection_path, json_bytes(selection))
    entries = []
    for child in children:
        number = child['number']; path = folder / f'item-{number:02d}.html'; meta = folder / f'item-{number:02d}.json'
        if path.exists() or meta.exists():
            if not path.is_file() or not meta.is_file(): raise IntakeError(f'单件网页或凭据不完整：{number}')
            info = read_json(meta)
            if info.get('url') != child['url'] or info.get('sha256') != digest(path): raise IntakeError(f'单件网页或凭据不符：{number}')
            parse_item(path.read_bytes(), child)
        else:
            raw, observed = request_html(child['url'], HOST, robots, delay)
            parse_item(raw, child)
            exclusive_write(path, raw)
            exclusive_write(meta, json_bytes({'url': child['url'], 'sha256': digest(path), 'observed_at': observed}))
        entries.append({'number': number, 'path': path.name, 'sha256': digest(path), 'meta': meta.name, 'meta_sha256': digest(meta)})
        print(f'已核验缅甸唱片目录 {number}/{EXPECTED} · {child["shelfmark"]}', flush=True)
    final, final_meta = folder / 'search-final.html', folder / 'search-final.html.json'
    if final.exists() or final_meta.exists():
        if not final.is_file() or not final_meta.is_file(): raise IntakeError('末次检索快照或凭据不完整。')
        receipt = read_json(final_meta)
        if receipt.get('url') != SEARCH_URL or receipt.get('sha256') != digest(final): raise IntakeError('末次检索凭据不符。')
        raw = final.read_bytes()
    else:
        raw, observed = request_search(robots, delay)
        if parse_search(raw) != children: raise IntakeError('采集期间检索结果变化，须重核。')
        exclusive_write(final, raw)
        receipt = {'url': SEARCH_URL, 'sha256': digest(final), 'bytes': len(raw), 'observed_at': observed}
        exclusive_write(final_meta, json_bytes(receipt))
    if parse_search(raw) != children: raise IntakeError('首末检索结果不一致。')
    pages.append({'path': final.name, **receipt})
    manifest = {'version': 1, 'robots_status': status, 'catalogue_text_license': CC_BY,
                'selection_sha256': digest(selection_path), 'pages': pages, 'records': entries,
                'scope': '馆方目录网页；未请求音频、转写或数字媒体，录音权利与社区要求另核。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    load_snapshot(folder)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"已核验 {len(result['records'])} 件缅甸唱片目录；未下载音频。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
