"""Import source-linked regional stories and their editorial knowledge bridges."""

import argparse
from datetime import date
import json
from pathlib import Path

import yaml

from pipeline.ingest_agent import serialize_card
from pipeline.node_model import NodeMetadata, Source
from pipeline.reading_notes import EditorialNote
from pipeline.vault import FrontmatterLoader, card_directory, parse_card
from pipeline.vault_write import create_card, replace_card, vault_writer

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / 'reference/regional_folklore_20261125.yaml'
NOTES = ROOT / 'reference/reading_notes.yaml'
MANIFEST = ROOT / 'web/src/syzygy/bridges.json'
VAULT = ROOT / 'vault'


def format_source(index: int, source: Source) -> str:
    parts = [f'{index}. {source.citation}']
    if source.locator:
        parts.append(source.locator)
    if source.url:
        parts.append(f'[来源]({source.url})')
    return ' '.join(parts)


def run(collection: Path = COLLECTION, created_at: date = date.fromisoformat('2026-11-25')):
    records = yaml.load(collection.read_text(encoding='utf-8'), Loader=FrontmatterLoader)['records']
    graph = json.loads((ROOT / 'web/public/data/graph_data.json').read_text(encoding='utf-8'))
    book = json.loads((ROOT / 'web/public/knowledge/data.json').read_text(encoding='utf-8'))
    old_notes = NOTES.read_text(encoding='utf-8')
    old_manifest = MANIFEST.read_text(encoding='utf-8')
    notes = yaml.load(old_notes, Loader=FrontmatterLoader)
    bridges = json.loads(old_manifest)
    existing_ids = {node['id'] for node in graph['nodes']}
    new_ids = [record['id'] for record in records]
    if len(new_ids) != len(set(new_ids)) or set(new_ids) & (existing_ids | set(notes)):
        raise ValueError('本批编号重复或已经入库；未覆盖已有资料。')
    knowledge_ids = {entry['id'] for entry in book['entries'] if entry.get('body', '').strip()}
    known_ids = existing_ids | set(new_ids)
    for item in records:
        ost = item.get('ostension_of')
        ost_list = [ost] if isinstance(ost, str) else list(ost or [])
        linked = list(item.get('compare') or []) + ost_list + list(item.get('motifs') or [])
        if any(target not in known_ids or target == item['id'] for target in linked):
            raise ValueError(f"关联目标不存在或指向自身: {item['id']}")
    if any(item['bridge']['entry'] not in knowledge_ids for item in records):
        raise ValueError('知识星桥指向不存在或无正文的知识条目。')
    if any(item['id'] in {bridge['case'] for bridge in bridges} for item in records):
        raise ValueError('星桥个案已存在。')

    planned, new_notes = {}, {}
    numbers = [int(bridge['id'][4:]) for bridge in bridges if bridge['id'].startswith('SYZ-') and bridge['id'][4:].isdigit()]
    next_number = max(numbers, default=0) + 1
    for offset, item in enumerate(records):
        node_id = item['id']
        refs = [Source.model_validate(source) for source in item['sources']]
        tier = item.get('credibility_tier', 'A')
        ost = item.get('ostension_of')
        ost_list = [ost] if isinstance(ost, str) else list(ost or [])
        relations = [
            {'type': 'COMPARED_WITH', 'target': target, 'weight': 1.0,
             'note': '同题比较，非已证实的传播或因果关系。'}
            for target in dict.fromkeys(item.get('compare') or [])
        ] + [
            {'type': 'OSTENSION_OF', 'target': target, 'weight': 1.0,
             'note': '数字民俗示现与衍生叙事关联。'}
            for target in dict.fromkeys(ost_list)
        ] + [
            {'type': 'HAS_MOTIF', 'target': target, 'weight': 1.0,
             'note': '标准母题或比较索引对照。'}
            for target in dict.fromkeys(item.get('motifs') or [])
        ]
        meta = NodeMetadata.model_validate({
            'id': node_id, 'title': item['title'], 'aliases': item.get('aliases', []),
            'node_type': 'case', 'z_layer': 1, 'genre': item['genre'],
            'credibility_tier': tier, 'is_fictional_quarantine': tier == 'F',
            'spatial': item['location'], 'temporal': item.get('temporal'), 'standards': {},
            'relations': relations,
            'sources': [ref.model_dump(mode='json') for ref in refs],
            'audit': {'created_at': created_at, 'reviewed_by_human': False},
        })
        body = '\n## 故事梗概\n\n' + '\n\n'.join(item['paragraphs'])
        body += '\n\n## 地图与年代\n\n' + item['location_note']
        body += '\n\n## 出处\n\n' + '\n'.join(
            format_source(i, ref)
            for i, ref in enumerate(refs, 1)) + '\n'
        path = VAULT / card_directory(meta) / f'{node_id}.md'
        content = serialize_card(meta, body)
        parse_card(content.decode('utf-8'))
        note_kind = item.get('note_kind') or (
            'history' if item['genre'] == 'historical_archive'
            else ('story' if item['genre'] in {'myth', 'folktale'} else 'legend')
        )
        note = {'kind': note_kind,
                'paragraphs': item['paragraphs'], 'source_numbers': list(range(1, len(refs) + 1)),
                'map_label': item.get('map_label') or item['location']['location_name'],
                'location_note': item['location_note']}
        EditorialNote.model_validate(note)
        planned[path], new_notes[node_id] = content, note
        spec = item['bridge']
        bridges.append({'id': f'SYZ-{next_number + offset:02d}', 'trail': spec['trail'],
                        'label': spec['label'], 'cluster': spec['cluster'], 'case': node_id,
                        'related': None, 'entry': spec['entry'], 'relation': 'THEMATIC',
                        'rationale': spec['rationale']})
    if any(path.exists() for path in planned):
        raise ValueError('目标卡片已存在；未覆盖。')
    suffix = yaml.safe_dump(new_notes, allow_unicode=True, sort_keys=False, width=1000)
    new_manifest = json.dumps(bridges, ensure_ascii=False, indent=2) + '\n'
    created = []
    with vault_writer(VAULT):
        try:
            for path, content in planned.items():
                create_card(path, content)
                created.append(path)
            replace_card(NOTES, (old_notes.rstrip() + '\n\n' + suffix).encode('utf-8'))
            replace_card(MANIFEST, new_manifest.encode('utf-8'))
        except Exception:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            replace_card(NOTES, old_notes.encode('utf-8'))
            replace_card(MANIFEST, old_manifest.encode('utf-8'))
            raise
    print(f'已创建 {len(planned)} 张带出处及坐标的卡片和 {len(records)} 条专题星桥。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=Path, default=COLLECTION)
    parser.add_argument('--created-at', type=date.fromisoformat, default=date.fromisoformat('2026-11-25'))
    args = parser.parse_args()
    run(args.collection, args.created_at)
