"""Preflight parallel, source-linked thematic lexicon proposals without importing them."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from urllib.parse import urlsplit

from pipeline.check_regional_batch import normalize_name


def check_batches(paths: list[Path], lexicon_dir: Path, taxonomy: dict, graph: dict) -> dict:
    errors, warnings = [], []
    domains = {domain['id']: domain for domain in taxonomy['domains']}
    node_ids = {node['id'] for node in graph['nodes']}
    old_ids, old_names = set(), defaultdict(set)
    for path in lexicon_dir.glob('*.json'):
        payload = json.loads(path.read_text(encoding='utf-8'))
        for entry in payload.get('entries', []):
            old_ids.add(entry['id'])
            for name in [entry.get('term', ''), *entry.get('aliases', [])]:
                if isinstance(name, str) and len(normalize_name(name)) >= 2:
                    old_names[normalize_name(name)].add(entry['id'])
    seen_ids, batch_names, count = set(), defaultdict(set), 0
    for path in paths:
        payload = json.loads(path.read_text(encoding='utf-8'))
        domain_id, entries = payload.get('domain_id'), payload.get('entries')
        if domain_id not in domains or not isinstance(entries, list):
            errors.append(f'{path.name}: 专题或 entries 列表无效')
            continue
        hubs = {hub for group in domains[domain_id]['groups'] for hub in group.get('hub_ids', [])}
        for entry in entries:
            count += 1
            node_id = entry.get('id', '<missing id>')
            prefix = f'{node_id}: '
            if not isinstance(node_id, str) or not node_id or node_id in seen_ids or node_id in old_ids:
                errors.append(prefix + '编号缺失、重复或已经入库')
            seen_ids.add(node_id)
            if entry.get('hub_id') not in node_ids or entry.get('hub_id') not in hubs:
                errors.append(prefix + '枢纽不存在，或不属于该专题')
            for key in ('term', 'summary', 'category', 'secondary_ref'):
                if not isinstance(entry.get(key), str) or not entry[key].strip():
                    errors.append(prefix + f'{key} 缺失')
            sources = entry.get('primary_sources')
            if not isinstance(sources, list) or not sources:
                errors.append(prefix + '缺少可核对的原典来源')
            else:
                secure = False
                located_print = False
                for source in sources:
                    if not isinstance(source, dict):
                        errors.append(prefix + '来源字段无效')
                        continue
                    raw_url = str(source.get('url') or '').strip()
                    url = urlsplit(raw_url)
                    if not source.get('citation'):
                        errors.append(prefix + '来源须含书目信息')
                    if raw_url and (url.scheme not in ('http', 'https') or not url.hostname
                                    or url.hostname.lower() in ('localhost', '127.0.0.1', '::1')):
                        errors.append(prefix + '来源网址须为公开 HTTP(S) 地址')
                    if not raw_url and not source.get('locator'):
                        errors.append(prefix + '无网址的纸本来源须有页码或章节')
                    secure |= url.scheme == 'https'
                    located_print |= not raw_url and bool(source.get('locator'))
                if not secure and not located_print:
                    errors.append(prefix + '需要 HTTPS 来源或带页码的纸本来源')
            ref = entry.get('secondary_ref', '')
            locators = ' '.join(str(source.get('locator') or '') for source in (sources or [])
                                if isinstance(source, dict))
            if isinstance(ref, str) and ref and not any(x in (ref + locators) for x in ('页', '章', '卷', '节', '目录')):
                warnings.append(prefix + '尚未注明所读参考书的页码或章节')
            terms = [entry.get('term', ''), *(entry.get('aliases') or [])]
            existing, siblings = set(), set()
            for term in terms:
                if not isinstance(term, str):
                    errors.append(prefix + '别名必须为文本')
                    continue
                key = normalize_name(term)
                if len(key) >= 2:
                    existing.update(old_names[key])
                    siblings.update(batch_names[key])
                    batch_names[key].add(node_id)
            siblings.discard(node_id)
            if existing:
                warnings.append(prefix + '与已有辞条同名或同别名，需核对: ' + ', '.join(sorted(existing)))
            if siblings:
                warnings.append(prefix + '与本批辞条同名或同别名，需核对: ' + ', '.join(sorted(siblings)))
    return {'records': count, 'errors': errors, 'warnings': warnings,
            'note': '此检查不替代逐条核查原文、参考书页码和知识关联。'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batches', nargs='+', type=Path)
    parser.add_argument('--lexicon-dir', type=Path, default=Path('reference/lexicon'))
    parser.add_argument('--taxonomy', type=Path, default=Path('reference/thematic_taxonomy.json'))
    parser.add_argument('--graph', type=Path, default=Path('web/public/data/graph_data.json'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = check_batches(args.batches, args.lexicon_dir,
                           json.loads(args.taxonomy.read_text(encoding='utf-8')),
                           json.loads(args.graph.read_text(encoding='utf-8')))
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding='utf-8')
    print(output, end='')
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
