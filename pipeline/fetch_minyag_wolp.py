"""Snapshot the public Mi nyag catalogue and its website terms; never fetch audio."""
import argparse
from hashlib import sha256
from pathlib import Path

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

HOST = 'www.oralliterature.org'
CATALOGUE_URL = f'https://{HOST}/collections/bkrashis001.html'
TERMS_URL = f'https://{HOST}/terms.html'


def fetch(folder: Path, delay: float = 2.0) -> dict:
    """Create an immutable, self-describing pair of original HTML responses."""
    if delay < 2:
        raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    entries = []
    for name, url in [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)]:
        raw, observed = request_html(url, HOST, robots, delay)
        exclusive_write(folder / name, raw)
        entries.append({'path': name, 'url': url, 'sha256': sha256(raw).hexdigest(),
                        'observed_at': observed, 'bytes': len(raw)})
    manifest = {'version': 1, 'robots_status': status, 'pages': entries,
                'scope': '原始目录及站点条款；不请求音频、转写或单条档案。',
                'rights': '仅供本地个人或内部非商业研究；进一步使用须分别核对站点及单条资源权利。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    manifest = fetch(args.output, args.delay)
    print(f"已保存 {len(manifest['pages'])} 份原始网页；未请求音频或转写。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
