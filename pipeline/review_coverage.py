"""Summarize selected Asian review batches without publishing draft records."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from pipeline.build_graph import PROJECT_ROOT
from pipeline.graph_output import publish_graph

DEFAULT_REGIONS = PROJECT_ROOT / 'web/public/review/regions.json'
DEFAULT_DATA = PROJECT_ROOT / 'web/public/review/data.js'
DEFAULT_OUTPUT = PROJECT_ROOT / 'web/public/data/asia_coverage.json'


def build_coverage(data_path: Path, regions_path: Path) -> dict:
    raw = data_path.read_text(encoding='utf-8')
    prefix = 'window.ASTRAIA_REVIEW_DATA='
    if not raw.startswith(prefix) or not raw.rstrip().endswith(';'):
        raise ValueError('复核数据格式不符。')
    data = json.loads(raw.removeprefix(prefix).rstrip()[:-1])
    regions = json.loads(regions_path.read_text(encoding='utf-8'))
    if data.get('version') != 1 or regions.get('version') != 1:
        raise ValueError('复核数据或地区目录版本不符。')
    mapping, groups = {}, []
    for group in regions['groups']:
        for batch in group['batches']:
            if batch in mapping:
                raise ValueError(f'地区目录重复批次：{batch}')
            mapping[batch] = group['id']
        groups.append({'id': group['id'], 'label': group['label'], 'pending': 0})
    totals = Counter()
    missing = set()
    for record in data['records']:
        if record['collection'] not in ('asia', 'nichibun'):
            continue
        area = mapping.get(record['batch'])
        if not area:
            missing.add(record['batch'])
        else:
            totals[area] += 1
    if missing:
        raise ValueError('亚洲批次尚未归入复核范围：' + '、'.join(sorted(missing)))
    for group in groups:
        group['pending'] = totals[group['id']]
    return {'version': 1, 'description': '本地待审目录快照；不代表已公开或已核实的故事数量。',
            'pending_total': sum(totals.values()), 'groups': groups}


def ensure_coverage_current(vault: Path, coverage: dict, regions_path: Path) -> None:
    regions = json.loads(regions_path.read_text(encoding='utf-8'))
    expected = {group['id']: sum(len(list((vault / '00_drafts' / batch).glob('*.md')))
                                 for batch in group['batches']) for group in regions['groups']}
    actual = {group['id']: group['pending'] for group in coverage['groups']}
    if actual != expected:
        raise ValueError('地区待审概览与草稿数量不一致，请先重新生成复核清单。')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-data', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--regions', type=Path, default=DEFAULT_REGIONS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        coverage = build_coverage(args.review_data, args.regions)
        publish_graph(args.output, coverage, 'json')
        print(f"已生成地区待审概览：{coverage['pending_total']} 条。")
    except (OSError, ValueError, KeyError) as error:
        print(f'地区待审概览未生成：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
