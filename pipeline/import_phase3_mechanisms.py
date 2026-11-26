"""Import Phase 3 L4 mechanism and theory cards with cited sources and reading notes."""

import argparse
from datetime import date
import json
from pathlib import Path

import yaml

from pipeline.ingest_agent import serialize_card
from pipeline.node_model import NodeMetadata, Source
from pipeline.reading_notes import EditorialNote
from pipeline.vault import FICTION_DIRECTORY, LAYER_DIRECTORIES, FrontmatterLoader, card_directory, parse_card
from pipeline.vault_write import create_card, replace_card, vault_writer

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / 'reference/phase3_mechanisms_20261125.yaml'
NOTES = ROOT / 'reference/reading_notes.yaml'
VAULT = ROOT / 'vault'
DEFAULT_BOUNDARY_NOTE = '本条目为阶段性学术综述，适用边界与个案关联须结合原始研究和独立证据逐项核对。'


def _normalize_section_body(value: object) -> str:
    """Convert a string or paragraph list into a clean Markdown block."""
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    elif isinstance(value, list):
        parts = [str(part).strip() for part in value if str(part).strip()]
        if parts:
            return '\n\n'.join(parts)
    raise ValueError('body_sections 内容须为非空文本或段落列表。')


def _format_source(index: int, ref: Source) -> str:
    parts = [f'{index}. {ref.citation}']
    if ref.locator:
        parts.append(ref.locator)
    parts.append(f'[来源]({ref.url})')
    return ' '.join(parts)


def format_body(paragraphs: list[str], refs: list[Source], body_sections: object = None) -> str:
    """Format L4 mechanism/theory Markdown sections cleanly without altering citations."""
    clean_paragraphs = [str(paragraph).strip() for paragraph in paragraphs]
    default_overview = '\n\n'.join(clean_paragraphs[:-1]) if len(clean_paragraphs) >= 2 else clean_paragraphs[0]
    default_boundary = clean_paragraphs[-1] if len(clean_paragraphs) >= 2 else DEFAULT_BOUNDARY_NOTE

    sections: list[tuple[str, str]] = []
    if body_sections is None:
        sections = [
            ('机制与理论概述', default_overview),
            ('适用边界与研究注记', default_boundary),
        ]
    elif isinstance(body_sections, dict):
        overview = body_sections.get('机制与理论概述') or body_sections.get('overview')
        boundary = (
            body_sections.get('适用边界与研究注记')
            or body_sections.get('limits')
            or body_sections.get('boundary')
            or body_sections.get('notes')
        )
        overview_text = _normalize_section_body(overview) if overview is not None else (
            '\n\n'.join(clean_paragraphs) if boundary is not None else default_overview
        )
        boundary_text = _normalize_section_body(boundary) if boundary is not None else default_boundary
        sections = [
            ('机制与理论概述', overview_text),
            ('适用边界与研究注记', boundary_text),
        ]
        handled = {'机制与理论概述', 'overview', '适用边界与研究注记', 'limits', 'boundary', 'notes'}
        for key, value in body_sections.items():
            if key not in handled:
                sections.append((str(key).strip(), _normalize_section_body(value)))
    elif isinstance(body_sections, list):
        extra: list[tuple[str, str]] = []
        for entry in body_sections:
            if not isinstance(entry, dict) or not entry.get('heading'):
                raise ValueError('body_sections 列表元素须包含 heading 与正文内容。')
            content = entry.get('body') or entry.get('text') or entry.get('paragraphs')
            extra.append((str(entry['heading']).strip(), _normalize_section_body(content)))
        headings = {heading for heading, _ in extra}
        if '机制与理论概述' not in headings:
            sections.append((
                '机制与理论概述',
                default_overview if '适用边界与研究注记' not in headings else '\n\n'.join(clean_paragraphs),
            ))
        sections.extend(extra)
        if '适用边界与研究注记' not in headings:
            sections.append(('适用边界与研究注记', default_boundary))
    else:
        raise ValueError('body_sections 须为映射或章节列表。')

    rendered = ''.join(f'\n## {heading}\n\n{content}\n' for heading, content in sections)
    rendered += '\n## 出处\n\n' + '\n'.join(_format_source(i, ref) for i, ref in enumerate(refs, 1)) + '\n'
    return rendered


def run(collection: Path = COLLECTION, created_at: date = date.fromisoformat('2026-11-25')) -> None:
    """Validate and atomically import Phase 3 L4 mechanism/theory cards."""
    payload = yaml.load(collection.read_text(encoding='utf-8'), Loader=FrontmatterLoader)
    if not isinstance(payload, dict) or not isinstance(payload.get('records'), list) or not payload['records']:
        raise ValueError('批次 records 须为非空列表。')
    records = payload['records']

    graph = json.loads((ROOT / 'web/public/data/graph_data.json').read_text(encoding='utf-8'))
    old_notes = NOTES.read_text(encoding='utf-8')
    notes = yaml.load(old_notes, Loader=FrontmatterLoader) or {}
    if not isinstance(notes, dict):
        raise ValueError('阅读提要须按卡片编号存储。')

    existing_ids = {node['id'] for node in graph['nodes']}
    if VAULT.is_dir():
        for directory in (*LAYER_DIRECTORIES.values(), FICTION_DIRECTORY):
            existing_ids.update(path.stem for path in (VAULT / directory).rglob('*.md'))

    new_ids = [record['id'] for record in records]
    if len(new_ids) != len(set(new_ids)) or set(new_ids) & (existing_ids | set(notes)):
        raise ValueError('本批编号重复或已经入库；未覆盖已有资料。')

    known_ids = existing_ids | set(new_ids)
    for item in records:
        compare_targets = item.get('compare') or []
        if any(target not in known_ids or target == item['id'] for target in compare_targets):
            raise ValueError(f"关联目标不存在或指向自身: {item['id']}")

    planned: dict[Path, bytes] = {}
    new_notes: dict[str, dict] = {}
    for item in records:
        node_id = item['id']
        node_type = item.get('node_type')
        if node_type not in {'mechanism', 'theory'}:
            raise ValueError(f"node_type 须为 mechanism 或 theory: {node_id}")
        refs = [Source.model_validate(source) for source in item['sources']]
        if not refs or any(ref.url is None or ref.url.scheme != 'https' for ref in refs):
            raise ValueError(f"来源须包含至少一条 https:// 链接: {node_id}")

        relations = [
            {'type': 'COMPARED_WITH', 'target': target, 'weight': 1.0,
             'note': '同题比较，非已证实的传播或因果关系。'}
            for target in dict.fromkeys(item.get('compare') or [])
        ]
        meta = NodeMetadata.model_validate({
            'id': node_id,
            'title': item['title'],
            'aliases': list(item.get('aliases') or []),
            'node_type': node_type,
            'z_layer': 4,
            'genre': 'academic_model',
            'credibility_tier': 'S',
            'is_fictional_quarantine': False,
            'spatial': None,
            'temporal': item.get('temporal'),
            'standards': {},
            'relations': relations,
            'sources': [ref.model_dump(mode='json') for ref in refs],
            'audit': {'created_at': created_at, 'reviewed_by_human': False},
        })

        note = {
            'kind': 'research',
            'paragraphs': item['paragraphs'],
            'source_numbers': list(range(1, len(refs) + 1)),
        }
        EditorialNote.model_validate(note)

        body = format_body(item['paragraphs'], refs, item.get('body_sections'))
        path = VAULT / card_directory(meta) / f'{node_id}.md'
        content = serialize_card(meta, body)
        parse_card(content.decode('utf-8'))
        planned[path] = content
        new_notes[node_id] = note

    if any(path.exists() for path in planned):
        raise ValueError('目标卡片已存在；未覆盖。')

    suffix = yaml.safe_dump(new_notes, allow_unicode=True, sort_keys=False, width=1000)
    updated_notes = old_notes.rstrip() + '\n\n' + suffix if notes else suffix
    created: list[Path] = []
    notes_written = False
    with vault_writer(VAULT):
        try:
            for path, content in planned.items():
                create_card(path, content)
                created.append(path)
            replace_card(NOTES, updated_notes.encode('utf-8'))
            notes_written = True
        except Exception:
            if notes_written:
                replace_card(NOTES, old_notes.encode('utf-8'))
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise
    print(f'已创建 {len(planned)} 张机制与理论卡片并更新阅读提要。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=Path, default=COLLECTION)
    parser.add_argument('--date', type=date.fromisoformat, default=date.fromisoformat('2026-11-25'))
    args = parser.parse_args()
    run(args.collection, args.date)
