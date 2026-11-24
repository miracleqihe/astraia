"""Import cited editorial records without inventing standard codes or review status."""

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
COLLECTION = ROOT / 'reference/modern_asian_stories_20261123.yaml'
NOTES = ROOT / 'reference/reading_notes.yaml'
VAULT = ROOT / 'vault'


def sources(items):
    return [Source.model_validate({'type': 'institutional_account', **item}) for item in items]


def run(collection=COLLECTION, manifest=None):
    data = yaml.load(collection.read_text(encoding='utf-8'), Loader=FrontmatterLoader)
    graph = json.loads((ROOT / 'web/public/data/graph_data.json').read_text(encoding='utf-8'))
    previous = {node['id']: node for node in graph['nodes']}
    original_notes = NOTES.read_text(encoding='utf-8')
    notes = yaml.load(original_notes, Loader=FrontmatterLoader) or {}
    if not isinstance(notes, dict):
        raise ValueError('阅读提要须按卡片编号存储。')
    all_items = data['themes'] + data['records']
    ids = [item['id'] for item in all_items]
    if len(ids) != len(set(ids)):
        raise ValueError('本批编号重复。')
    if set(ids) & set(previous):
        raise ValueError(f'节点已收录，未重复创建：{sorted(set(ids) & set(previous))}')
    titles = {node['title'] for node in previous.values()}
    duplicate_titles = [item['title'] for item in all_items if item['title'] in titles]
    if duplicate_titles:
        raise ValueError(f'标题已存在，未重复创建：{duplicate_titles}')
    known = set(previous) | set(ids)
    targets = {target for item in data['themes'] for target in item.get('peers', [])}
    targets.update(item['theme'] for item in data['records'])
    if targets - known:
        raise ValueError(f'关联目标不存在：{sorted(targets - known)}')
    planned, new_notes = {}, {}
    for item in all_items:
        node_id = item['id']
        is_theme = item in data['themes']
        is_corpus = node_id.startswith('corpus_')
        node_type = 'myth_corpus' if is_corpus else 'case'
        refs = sources(item['sources'])
        relation_targets = item.get('peers', []) if is_theme else [item['theme']]
        metadata = NodeMetadata.model_validate({
            'id': node_id, 'title': item['title'], 'aliases': item.get('aliases', []),
            'node_type': node_type, 'z_layer': 2 if is_corpus else 1,
            'genre': item.get('genre', 'historical_archive' if is_theme else 'folktale'),
            'credibility_tier': item.get('credibility_tier', 'A'), 'is_fictional_quarantine': False,
            'spatial': item.get('location'), 'temporal': item.get('temporal'), 'standards': {},
            'relations': [{'type': 'COMPARED_WITH', 'target': target, 'weight': 1.0,
                           'note': '同题并列阅读，不推断传播或共同起源。'} for target in relation_targets],
            'sources': [ref.model_dump(mode='json') for ref in refs],
            'audit': {'created_at': date.fromisoformat('2026-11-23'), 'reviewed_by_human': False},
        })
        body = '\n## 资料梗概\n\n' + '\n\n'.join(item['paragraphs']) + '\n'
        if item.get('location_note'):
            body += '\n## 地图锚点\n\n' + item['location_note'] + '\n'
        path = VAULT / card_directory(metadata) / (node_id + '.md')
        content = serialize_card(metadata, body)
        parse_card(content.decode('utf-8'))
        kind = ('research' if is_theme else 'history' if item.get('genre') == 'historical_archive'
                else 'story' if item.get('genre') in ('folktale', 'memorate') else 'legend')
        note = {'kind': kind,
                'paragraphs': item['paragraphs'], 'source_numbers': list(range(1, len(refs) + 1))}
        if item.get('location_note'):
            note.update(map_label=item['location']['location_name'], location_note=item['location_note'])
        EditorialNote.model_validate(note)
        planned[path] = content
        new_notes[node_id] = note
    for node_id, item in data['existing_notes'].items():
        if node_id not in previous:
            raise ValueError(f'原有节点不存在：{node_id}')
        source = sources([item['source']])[0]
        note = {'kind': 'story', 'paragraphs': item['paragraphs'],
                'source_numbers': [len(previous[node_id]['sources']) + 1],
                'additional_sources': [source.model_dump(mode='json', exclude_none=True)]}
        EditorialNote.model_validate(note)
        new_notes[node_id] = note
    overlap = set(new_notes).intersection(notes)
    if overlap:
        raise ValueError(f'阅读提要已存在，未覆盖：{sorted(overlap)}')
    collisions = [str(path) for path in planned if path.exists()]
    if collisions:
        raise ValueError(f'卡片已存在，未覆盖：{collisions}')
    created_manifest = {path.stem: path.relative_to(ROOT).as_posix() for path in planned}
    output = manifest or ROOT / '.local/modern-asia-20261123/manifest.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = yaml.safe_dump(new_notes, allow_unicode=True, sort_keys=False, width=1000)
    updated_notes = original_notes.rstrip() + '\n\n' + suffix if notes else suffix
    created = []
    notes_written = False
    with vault_writer(VAULT):
        try:
            for path, content in planned.items():
                create_card(path, content)
                created.append(path)
            replace_card(NOTES, updated_notes.encode('utf-8'))
            notes_written = True
            replace_card(output, (json.dumps(created_manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        except Exception:
            if notes_written:
                replace_card(NOTES, original_notes.encode('utf-8'))
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise
    print(f'已创建 {len(planned)} 个节点并补充 {len(data["existing_notes"])} 个现有节点的阅读提要。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=Path, default=COLLECTION)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    run(args.collection, args.manifest)
