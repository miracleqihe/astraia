"""Capture the Wikisource discussion describing this transcription's editing history."""
import argparse
from hashlib import sha256
from pathlib import Path

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.zibuyu import TALK_URL, load_talk


def fetch(folder: Path, delay: float = 2.0) -> dict:
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules('zh.wikisource.org', delay)
    raw, observed = request_html(TALK_URL, 'zh.wikisource.org', robots, delay)
    exclusive_write(folder / 'talk.html', raw)
    receipt = {'version': 1, 'url': TALK_URL, 'robots_status': status, 'observed_at': observed,
               'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)}
    exclusive_write(folder / 'manifest.json', json_bytes(receipt))
    load_talk(folder)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"已保存版本讨论页 · SHA-256 {result['sha256']}；古籍底本仍待核。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
