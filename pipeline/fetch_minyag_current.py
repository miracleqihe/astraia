"""Capture one Cambridge item page for a documented catalogue cross-check."""
import argparse
from hashlib import sha256
from pathlib import Path

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError

HOST = 'www.repository.cam.ac.uk'
ITEM_URL = f'https://{HOST}/items/dac374fe-5e80-4b61-b5f9-b64000adfe01'


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    raw, observed = request_html(ITEM_URL, HOST, robots, delay)
    # The response is kept locally for research with its copyright notices intact.
    # This only downloads the HTML page, never the linked media or documents.
    exclusive_write(folder / 'item.html', raw)
    manifest = {'version': 1, 'robots_status': status, 'url': ITEM_URL, 'path': 'item.html',
                'sha256': sha256(raw).hexdigest(), 'observed_at': observed, 'bytes': len(raw),
                'scope': '单条馆藏元数据网页；不请求或复制音频及附件，单件标注 All Rights Reserved。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"已保存馆方单条网页：{result['url']}；未请求附件。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
