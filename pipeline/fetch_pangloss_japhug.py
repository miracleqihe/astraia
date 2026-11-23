"""Fetch a bounded, resumable set of Japhug metadata pages without media."""
import argparse
from pathlib import Path
import sys
from urllib.error import HTTPError

from pipeline.fetch_pangloss_na import fetch
from pipeline.intake_sources import IntakeError

CORPUS_URL = 'https://pangloss.cnrs.fr/corpus/Japhug'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2.0)
    args = parser.parse_args()
    try:
        manifest = fetch(args.corpus, args.selection, args.output, delay=args.delay,
                         corpus_name='Japhug', corpus_url=CORPUS_URL)
    except (ValueError, OSError, KeyError, TypeError, HTTPError) as error:
        print(f'Japhug 元数据获取停止；已保存的快照可在同一选择范围下续跑：{error}', file=sys.stderr)
        return 1
    print(f"已保存 {len(manifest['records'])} 条 Japhug 详情元数据。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
