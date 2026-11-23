"""Capture Chinese Wikisource's 24-volume transcription for local review."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError, _challenge_page

HOST = 'zh.wikisource.org'
ROOT = '子不語'
VOLUMES = 24


def page_url(volume: int) -> str:
    if not isinstance(volume, int) or not 0 <= volume <= VOLUMES:
        raise IntakeError('子不语卷次无效。')
    title = ROOT if volume == 0 else f'{ROOT}/卷{volume}'
    return f'https://{HOST}/wiki/{quote(title)}'


def page_info(raw: bytes, volume: int) -> dict:
    text = raw.decode('utf-8')
    soup = BeautifulSoup(text, 'html.parser')
    first = soup.select_one('#firstHeading')
    content = soup.select_one('#mw-content-text > .mw-parser-output')
    expected = ROOT if volume == 0 else f'{ROOT}/卷{volume}'
    revisions = set(re.findall(r'"wgRevisionId":(\d+)', text))
    if (_challenge_page(soup) or soup.contains_replacement_characters or not first or first.get_text(' ', strip=True) != expected
            or not content or len(revisions) != 1 or int(next(iter(revisions))) <= 0):
        raise IntakeError(f'子不语目录题名、修订号或页面结构异常：{volume}')
    if volume and not content.find_all('h3'):
        raise IntakeError(f'子不语分卷未发现篇题：{volume}')
    return {'revision_id': int(next(iter(revisions))), 'title': expected}


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2: raise IntakeError('页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    pages = []
    for volume in range(VOLUMES + 1):
        url = page_url(volume)
        raw, observed = request_html(url, HOST, robots, delay)
        info = page_info(raw, volume)
        name = 'index.html' if volume == 0 else f'volume-{volume:02d}.html'
        exclusive_write(folder / name, raw)
        pages.append({'volume': volume, 'path': name, 'url': url, 'sha256': sha256(raw).hexdigest(),
                      'bytes': len(raw), 'observed_at': observed, **info})
        print(f'已保存子不语公开转录 {volume}/{VOLUMES} 页 · 修订 {info["revision_id"]}。', flush=True)
    # Check index revision once more; per-volume revisions are pinned independently.
    raw, observed = request_html(page_url(0), HOST, robots, delay)
    check = page_info(raw, 0)
    if check['revision_id'] != pages[0]['revision_id']:
        raise IntakeError('子不语总目录在采集期间发生修订；须重新核对。')
    manifest = {'version': 1, 'robots_status': status, 'pages': pages,
                'index_recheck': {'url': page_url(0), 'revision_id': check['revision_id'],
                                  'sha256': sha256(raw).hexdigest(), 'bytes': len(raw), 'observed_at': observed},
                'scope': '中文维基文库在线转录原网页快照，分卷固定修订；古籍底本、排校及数字转录条款须核。',
                'limits': '采集期间仅复查总目录修订号；各分卷并非同一时刻的原子快照。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f'已登记 {len(result["pages"]) - 1} 卷与总目录；正文及版本须逐条复核。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
