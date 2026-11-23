"""Save the Andersen Centre work register and translation as comparison sources."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from pipeline.early_asia_editions import ANDERSEN_REGISTER, ANDERSEN_TRANSLATION

USER_AGENT = 'AstraiaResearchIndex/1.0 (local research)'
URLS = {'register.html': ANDERSEN_REGISTER, 'translation.html': ANDERSEN_TRANSLATION}


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
    robots_url = 'https://andersen.sdu.dk/robots.txt'
    robots = fetch(robots_url)
    policy = RobotFileParser()
    policy.parse(robots.decode('utf-8').splitlines())
    if any(not policy.can_fetch(USER_AGENT, url) for url in URLS.values()):
        raise ValueError('站点 robots.txt 不允许获取至少一个来源。')
    args.output.mkdir(parents=True)
    (args.output / 'robots.txt').write_bytes(robots)
    manifest = {'retrieved_utc': datetime.now(timezone.utc).isoformat(), 'robots_url': robots_url,
                'robots_sha256': sha256(robots).hexdigest(), 'files': {}}
    for name, url in URLS.items():
        time.sleep(args.delay)
        data = fetch(url)
        with (args.output / name).open('xb') as stream:
            stream.write(data)
        manifest['files'][name] = {'url': url, 'sha256': sha256(data).hexdigest(), 'bytes': len(data)}
    with (args.output / 'manifest.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
