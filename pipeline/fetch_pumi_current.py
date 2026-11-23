"""Capture one Cambridge Pumi item page without downloading its attachments."""
import argparse
from hashlib import sha256
from pathlib import Path

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

HOST = 'www.repository.cam.ac.uk'
ITEM_URL = f'https://{HOST}/items/59e872c1-2935-47bb-a584-d696a6484494'


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    raw, observed = request_html(ITEM_URL, HOST, robots, delay)
    exclusive_write(folder / 'item.html', raw)
    manifest = {'version': 1, 'robots_status': status, 'url': ITEM_URL, 'path': 'item.html',
                'sha256': sha256(raw).hexdigest(), 'bytes': len(raw), 'observed_at': observed,
                'scope': '单件馆方目录网页，不请求音频、PDF或其他附件；单件权利另核。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    item = fetch(args.output, args.delay)
    print(f"已保存单件目录网页：{item['url']}；未请求附件。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
