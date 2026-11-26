"""Preflight independently researched regional batches before importing them.

This checks structure and flags possible duplicates; it does not establish that
the cited source supports a claim. Researchers must still inspect the sources.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import unicodedata
from urllib.parse import urlsplit

import yaml

from pipeline.node_model import NodeMetadata
from pipeline.vault import FrontmatterLoader


def normalize_name(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold()
                   if not unicodedata.category(c).startswith(('P', 'Z', 'C')))


def check_batches(collections: list[Path], graph: dict, book: dict) -> dict:
    errors, warnings, records = [], [], []
    for collection in collections:
        data = yaml.load(collection.read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        if not isinstance(data, dict) or not isinstance(data.get('records'), list):
            raise ValueError(f'{collection}: 缺少 records 列表')
        records.extend(data['records'])

    existing = {node['id']: node for node in graph['nodes']}
    book_ids = {entry['id'] for entry in book['entries'] if entry.get('body', '').strip()}
    batch_ids = [record.get('id') for record in records if isinstance(record, dict)]
    repeated_ids = {key for key, count in Counter(batch_ids).items() if count > 1}
    known_ids = set(existing) | set(batch_ids)
    names = defaultdict(set)
    for node in existing.values():
        for name in [node.get('title', ''), *(node.get('aliases') or [])]:
            if isinstance(name, str) and len(normalize_name(name)) >= 4:
                names[normalize_name(name)].add(node['id'])

    candidate_titles = {}
    candidate_names = defaultdict(set)
    for record in records:
        if not isinstance(record, dict):
            errors.append('条目不是映射')
            continue
        node_id = record.get('id') or '<missing id>'
        prefix = f'{node_id}: '
        if node_id in repeated_ids or node_id in existing:
            errors.append(prefix + '编号重复或已入库')
        try:
            tier = record['credibility_tier']
            NodeMetadata.model_validate({
                'id': record['id'], 'title': record['title'],
                'aliases': record.get('aliases', []), 'node_type': 'case', 'z_layer': 1,
                'genre': record['genre'], 'credibility_tier': tier,
                'is_fictional_quarantine': tier == 'F', 'spatial': record['location'],
                'temporal': record.get('temporal'), 'standards': {}, 'relations': [],
                'sources': record['sources'],
                'audit': {'created_at': date.today(), 'reviewed_by_human': False},
            })
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(prefix + f'元数据无效: {exc}')
            continue
        paragraphs = record.get('paragraphs')
        if not isinstance(paragraphs, list) or len(paragraphs) < 2 or any(
                not isinstance(p, str) or not p.strip() for p in paragraphs):
            errors.append(prefix + '至少需要两段可阅读正文')
        location = record['location']
        if location.get('lat') is None or location.get('lng') is None:
            errors.append(prefix + '地图坐标缺失')
        if not isinstance(record.get('location_note'), str) or not record['location_note'].strip():
            errors.append(prefix + '缺少坐标范围说明')
        if not record['sources']:
            errors.append(prefix + '缺少出处')
        for source in record['sources']:
            raw_url = str(source.get('url') or '').strip()
            parsed = urlsplit(raw_url)
            if raw_url and (parsed.scheme not in ('http', 'https') or not parsed.hostname or (
                    parsed.hostname.lower() in ('localhost', '127.0.0.1', '::1'))):
                errors.append(prefix + '出处网址须为公开 HTTP(S) 地址')
            if not raw_url and not source.get('locator'):
                errors.append(prefix + '无网址的纸本出处须注明页码或章节')
            if not source.get('locator'):
                warnings.append(prefix + '出处未注明具体段落或索引位置')
        linked = list(record.get('compare') or []) + list(record.get('motifs') or [])
        ostension = record.get('ostension_of') or []
        linked += [ostension] if isinstance(ostension, str) else list(ostension)
        if any(target not in known_ids or target == node_id for target in linked):
            errors.append(prefix + '关联目标不存在或指向自身')
        bridge = record.get('bridge') or {}
        if bridge.get('entry') not in book_ids:
            errors.append(prefix + '知识星桥目标不存在或没有正文')
        if not all(isinstance(bridge.get(k), str) and bridge[k].strip()
                   for k in ('cluster', 'trail', 'label', 'rationale')):
            errors.append(prefix + '知识星桥信息不完整')
        elif bridge['cluster'] not in {'sid_myth', 'sid_hag', 'sid_witch', 'sid_crypt', 'sid_liminal'} or (
                bridge['trail'] not in {'all', 'trail1', 'trail2', 'trail3', 'trail4', 'trail5'}):
            errors.append(prefix + '知识星桥分类不受支持')
        title = normalize_name(record['title'])
        if title in candidate_titles:
            warnings.append(prefix + f"题名与本批 {candidate_titles[title]} 重合")
        else:
            candidate_titles[title] = node_id
        possible = set()
        for name in [record['title'], *record.get('aliases', [])]:
            key = normalize_name(name)
            if len(key) >= 4:
                possible.update(names.get(key, set()))
        if possible:
            warnings.append(prefix + '题名或别名与既有节点相同，需核对: ' + ', '.join(sorted(possible)))
        batch_matches = set()
        for name in [record['title'], *record.get('aliases', [])]:
            key = normalize_name(name)
            if len(key) >= 4:
                batch_matches.update(candidate_names[key])
                candidate_names[key].add(node_id)
        if batch_matches:
            warnings.append(prefix + '题名或别名与本批其他节点相同，需核对: ' + ', '.join(sorted(batch_matches)))

    return {'records': len(records), 'errors': errors, 'warnings': warnings,
            'note': '结构检查不能替代对原文、坐标精度和权利的核对。'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('collections', nargs='+', type=Path)
    parser.add_argument('--graph', type=Path, default=Path('web/public/data/graph_data.json'))
    parser.add_argument('--book', type=Path, default=Path('web/public/knowledge/data.json'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = check_batches(args.collections, json.loads(args.graph.read_text(encoding='utf-8')),
                           json.loads(args.book.read_text(encoding='utf-8')))
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding='utf-8')
    print(output, end='')
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
