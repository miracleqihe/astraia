"""Save two Internet Archive book OCRs and page indexes as source snapshots."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

EDITIONS = ('studiesinmorohi00salegoog', 'jadestorybooksto00cous')
USER_AGENT = 'AstraiaResearchIndex/1.0 (local research)'
SUFFIXES = ('djvu.txt', 'hocr_searchtext.txt.gz', 'hocr_pageindex.json.gz', 'scandata.xml')


def fetch(url: str) -> bytes:
    with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=45) as response:
        data = response.read(2_000_001)
        if response.status != 200 or not data or len(data) > 2_000_000:
            raise ValueError(f'来源响应异常：{url}')
        return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    if args.delay < 1:
        parser.error('请求间隔不能少于 1 秒。')
    if args.output.exists():
        parser.error('输出目录已存在，拒绝覆盖。')
    robots_url = 'https://archive.org/robots.txt'
    robots = fetch(robots_url)
    policy = RobotFileParser()
    policy.parse(robots.decode('utf-8').splitlines())
    urls = {identifier: [f'https://archive.org/download/{identifier}/{identifier}_{suffix}' for suffix in SUFFIXES]
            for identifier in EDITIONS}
    if any(not policy.can_fetch(USER_AGENT, url) for group in urls.values() for url in group):
        raise ValueError('站点 robots.txt 不允许获取至少一个来源。')
    args.output.mkdir(parents=True)
    (args.output / 'robots.txt').write_bytes(robots)
    manifest = {'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                'robots_url': robots_url, 'robots_sha256': sha256(robots).hexdigest(), 'editions': {}}
    for identifier, group in urls.items():
        folder = args.output / identifier
        folder.mkdir()
        files = []
        for url in group:
            time.sleep(args.delay)
            body = fetch(url)
            name = url.rsplit('/', 1)[-1]
            with (folder / name).open('xb') as stream:
                stream.write(body)
            files.append({'name': name, 'url': url, 'sha256': sha256(body).hexdigest(), 'bytes': len(body)})
            print(f'已保存 {identifier} / {name}', flush=True)
        manifest['editions'][identifier] = {'item_url': f'https://archive.org/details/{identifier}', 'files': files}
    with (args.output / 'manifest.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
