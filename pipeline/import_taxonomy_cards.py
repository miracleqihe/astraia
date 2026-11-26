"""Import Phase 5 L3 (motif_index) and L2 (myth_corpus) taxonomy hub cards cleanly."""

import argparse
from datetime import date
import json
from pathlib import Path

import yaml

from pipeline.ingest_agent import serialize_card
from pipeline.node_model import LAYER_BY_TYPE, NodeMetadata, Source
from pipeline.reading_notes import EditorialNote
from pipeline.vault import FICTION_DIRECTORY, LAYER_DIRECTORIES, FrontmatterLoader, card_directory, parse_card
from pipeline.vault_write import create_card, replace_card, vault_writer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / 'reference/wugu_talisman_hubs_phase5_20261126.yaml'
DEFAULT_NOTES = ROOT / 'reference/reading_notes.yaml'
DEFAULT_GRAPH = ROOT / 'web/public/data/graph_data.json'
VAULT = ROOT / 'vault'
SUPPORTED_TYPES = {'motif_index', 'myth_corpus'}
DEFAULT_NOTES_BY_TYPE = {
    'motif_index': '本条目为跨文本母题与民俗分类索引节点，具体个案归属与文化区分布须结合原始文献核对。',
    'myth_corpus': '本条目为多文献汇集的专类资料组，用于专题检索与跨文本对照，不替代原始版本校勘。',
}


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
    if ref.url is not None:
        parts.append(f'[来源]({ref.url})')
    return ' '.join(parts)


def format_body(
    node_type: str,
    paragraphs: list[str],
    refs: list[Source],
    body_sections: object = None,
    raw_markdown: str | None = None,
) -> str:
    """Format L2/L3 Markdown sections cleanly without altering citations."""
    if isinstance(raw_markdown, str) and raw_markdown.strip():
        body = raw_markdown.strip('\n')
        if '## 出处' not in body:
            body += '\n\n## 出处\n\n' + '\n'.join(_format_source(i, ref) for i, ref in enumerate(refs, 1))
        return f'\n{body}\n'

    clean_paragraphs = [str(paragraph).strip() for paragraph in paragraphs if str(paragraph).strip()]
    if not clean_paragraphs:
        raise ValueError('缺乏可用于生成卡片正文的有效段落或 markdown。')

    primary_heading = '母题界定与比较范围' if node_type == 'motif_index' else '文献谱系与资料梗概'
    note_heading = '研究与索引注记' if node_type == 'motif_index' else '校勘与阅读提示'
    default_overview = '\n\n'.join(clean_paragraphs[:-1]) if len(clean_paragraphs) >= 2 else clean_paragraphs[0]
    default_note = clean_paragraphs[-1] if len(clean_paragraphs) >= 2 else DEFAULT_NOTES_BY_TYPE[node_type]

    sections: list[tuple[str, str]] = []
    if body_sections is None:
        sections = [
            (primary_heading, default_overview),
            (note_heading, default_note),
        ]
    elif isinstance(body_sections, dict):
        overview = body_sections.get(primary_heading) or body_sections.get('overview')
        note = body_sections.get(note_heading) or body_sections.get('notes') or body_sections.get('boundary')
        overview_text = _normalize_section_body(overview) if overview is not None else (
            '\n\n'.join(clean_paragraphs) if note is not None else default_overview
        )
        note_text = _normalize_section_body(note) if note is not None else default_note
        sections = [
            (primary_heading, overview_text),
            (note_heading, note_text),
        ]
        handled = {primary_heading, 'overview', note_heading, 'notes', 'boundary'}
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
        if primary_heading not in headings:
            sections.append((
                primary_heading,
                default_overview if note_heading not in headings else '\n\n'.join(clean_paragraphs),
            ))
        sections.extend(extra)
        if note_heading not in headings:
            sections.append((note_heading, default_note))
    else:
        raise ValueError('body_sections 须为映射或章节列表。')

    rendered = ''.join(f'\n## {heading}\n\n{content}\n' for heading, content in sections)
    rendered += '\n## 出处\n\n' + '\n'.join(_format_source(i, ref) for i, ref in enumerate(refs, 1)) + '\n'
    return rendered


def _load_existing_layers(vault: Path, graph_path: Path) -> dict[str, int]:
    """Collect existing node ID -> z_layer mappings from graph_data.json and vault/."""
    known_layers: dict[str, int] = {}
    if graph_path.is_file():
        graph = json.loads(graph_path.read_text(encoding='utf-8'))
        for node in graph.get('nodes', []):
            if isinstance(node, dict) and node.get('id') and node.get('z_layer') is not None:
                known_layers[node['id']] = int(node['z_layer'])
    if vault.is_dir():
        for layer, directory in LAYER_DIRECTORIES.items():
            target_dir = vault / directory
            if target_dir.is_dir():
                for path in target_dir.rglob('*.md'):
                    known_layers[path.stem] = layer
        fiction_dir = vault / FICTION_DIRECTORY
        if fiction_dir.is_dir():
            for path in fiction_dir.rglob('*.md'):
                metadata, _ = parse_card(path.read_text(encoding='utf-8-sig'))
                known_layers[metadata.id] = metadata.z_layer
    return known_layers


def _extract_records(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        records = payload.get('records')
    elif isinstance(payload, list):
        records = payload
    else:
        records = None
    if not isinstance(records, list) or not records or not all(isinstance(item, dict) for item in records):
        raise ValueError('输入 YAML 须包含非空 records 列表或顶层记录列表。')
    return records


def _build_relations(item: dict, node_id: str, z_layer: int, known_layers: dict[str, int]) -> list[dict]:
    raw_relations: list[dict] = []
    for entry in item.get('relations') or []:
        if not isinstance(entry, dict):
            raise ValueError(f'relations 元素须为对象: {node_id}')
        raw_relations.append(dict(entry))
    for target in dict.fromkeys(item.get('compare') or []):
        raw_relations.append({
            'type': 'COMPARED_WITH',
            'target': target,
            'weight': 1.0,
            'note': '同题比较，非已证实的传播或因果关系。',
        })
    for target in dict.fromkeys(item.get('motifs') or []):
        raw_relations.append({
            'type': 'HAS_MOTIF',
            'target': target,
            'weight': 1.0,
            'note': '标准母题或比较索引对照。',
        })

    deduped: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    for rel in raw_relations:
        rel_type = rel.get('type')
        target = rel.get('target')
        key = (str(rel_type), str(target))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if not target or target not in known_layers or target == node_id:
            raise ValueError(f'关联目标不存在或指向自身: {node_id} -> {target}')
        target_layer = known_layers[target]
        if rel_type == 'EXPLAINED_BY' and target_layer != 4:
            raise ValueError(f'EXPLAINED_BY 须指向 L4 节点: {node_id} -> {target}')
        if rel_type in {'HAS_MOTIF', 'TAGGED_OCM'} and target_layer != 3:
            raise ValueError(f'{rel_type} 须指向 L3 节点: {node_id} -> {target}')
        if rel_type == 'ATTESTS_MOTIF' and (z_layer != 2 or target_layer != 3 or not str(rel.get('note') or '').strip()):
            raise ValueError(f'ATTESTS_MOTIF 须由 L2 指向 L3 并附注记: {node_id} -> {target}')
        deduped.append(rel)
    return deduped


def _extract_reading_note(item: dict, refs: list[Source]) -> tuple[dict | None, list[str]]:
    note_spec = item.get('reading_note') or item.get('editorial_note')
    if note_spec is not None and not isinstance(note_spec, dict):
        raise ValueError(f"reading_note / editorial_note 须为映射: {item['id']}")

    raw_paragraphs = note_spec.get('paragraphs') if note_spec is not None else item.get('paragraphs')
    paragraphs: list[str] = []
    if raw_paragraphs is not None:
        if not isinstance(raw_paragraphs, list):
            raise ValueError(f"paragraphs 须为列表: {item['id']}")
        paragraphs = [str(p).strip() for p in raw_paragraphs if str(p).strip()]

    has_note_input = note_spec is not None or 'paragraphs' in item or 'note_kind' in item
    if not has_note_input or not paragraphs:
        summary = str(item.get('summary') or '').strip()
        fallback = paragraphs or ([summary] if summary else [str(item['title']).strip()])
        return None, fallback

    note_kind = (note_spec.get('kind') if note_spec else None) or item.get('note_kind') or 'research'
    source_numbers = (
        (note_spec.get('source_numbers') if note_spec else None)
        or item.get('source_numbers')
        or list(range(1, len(refs) + 1))
    )
    note: dict[str, object] = {
        'kind': note_kind,
        'paragraphs': paragraphs,
        'source_numbers': source_numbers,
    }
    map_label = (note_spec.get('map_label') if note_spec else None) or item.get('map_label')
    location_note = (note_spec.get('location_note') if note_spec else None) or item.get('location_note')
    if map_label:
        note['map_label'] = map_label
    if location_note:
        note['location_note'] = location_note
    EditorialNote.model_validate(note)
    if max(note['source_numbers']) > len(refs):  # type: ignore[arg-type]
        raise ValueError(f"reading_note source_numbers 超出出处数量: {item['id']}")
    return note, paragraphs


def run(
    collection: Path = DEFAULT_INPUT,
    created_at: date = date.fromisoformat('2026-11-26'),
    *,
    vault: Path = VAULT,
    notes_path: Path | None = DEFAULT_NOTES,
    graph_path: Path = DEFAULT_GRAPH,
    pending_yaml: list[Path] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Validate and atomically import Phase 5 L2/L3 taxonomy hub cards."""
    payload = yaml.load(collection.read_text(encoding='utf-8'), Loader=FrontmatterLoader)
    records = _extract_records(payload)

    new_ids = [record.get('id') for record in records]
    if any(not isinstance(node_id, str) or not node_id for node_id in new_ids) or len(new_ids) != len(set(new_ids)):
        raise ValueError('批次存在缺失或重复的节点 ID。')

    known_layers = _load_existing_layers(vault, graph_path)
    for extra_path in pending_yaml or []:
        extra_payload = yaml.load(extra_path.read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        for extra_record in _extract_records(extra_payload):
            extra_id = extra_record.get('id')
            extra_type = extra_record.get('node_type')
            if isinstance(extra_id, str) and extra_id and extra_type in LAYER_BY_TYPE:
                known_layers.setdefault(extra_id, LAYER_BY_TYPE[extra_type])
    for record in records:
        node_type = record.get('node_type')
        if node_type not in SUPPORTED_TYPES:
            raise ValueError(f"node_type 须为 motif_index 或 myth_corpus: {record.get('id')} ({node_type})")
        expected_layer = LAYER_BY_TYPE[node_type]
        if record.get('z_layer') is not None and int(record['z_layer']) != expected_layer:
            raise ValueError(f"z_layer 与 node_type 不匹配: {record['id']}")
        known_layers[record['id']] = expected_layer

    old_notes = ''
    notes: dict = {}
    if notes_path is not None and notes_path.is_file():
        old_notes = notes_path.read_text(encoding='utf-8')
        notes = yaml.load(old_notes, Loader=FrontmatterLoader) or {}
        if not isinstance(notes, dict):
            raise ValueError('阅读提要须按卡片编号存储。')

    planned_create: dict[Path, bytes] = {}
    skipped_cards = 0
    new_notes: dict[str, dict] = {}
    skipped_notes = 0

    for item in records:
        node_id = item['id']
        node_type = item['node_type']
        z_layer = LAYER_BY_TYPE[node_type]

        refs = [Source.model_validate(source) for source in (item.get('sources') or [])]
        if not refs or not any(ref.url is not None and ref.url.scheme == 'https' for ref in refs):
            raise ValueError(f'来源须包含至少一条 https:// 链接: {node_id}')
        if any(ref.url is not None and ref.url.scheme != 'https' for ref in refs):
            raise ValueError(f'来源链接须使用 https://: {node_id}')

        relations = _build_relations(item, node_id, z_layer, known_layers)
        for mech in item.get('mechanisms') or []:
            target_id = mech.get('target_id') if isinstance(mech, dict) else None
            if not target_id or target_id not in known_layers or target_id == node_id or known_layers[target_id] != 4:
                raise ValueError(f'mechanisms 目标须为已存在的 L4 节点: {node_id} -> {target_id}')

        tier = item.get('credibility_tier') or item.get('tier') or 'A'
        spatial = item['spatial'] if 'spatial' in item else item.get('location')
        audit_created = item.get('created_at') or created_at
        meta = NodeMetadata.model_validate({
            'id': node_id,
            'title': item['title'],
            'aliases': list(item.get('aliases') or []),
            'node_type': node_type,
            'z_layer': z_layer,
            'genre': item.get('genre') or 'academic_model',
            'credibility_tier': tier,
            'is_fictional_quarantine': tier == 'F',
            'spatial': spatial,
            'temporal': item.get('temporal'),
            'standards': dict(item.get('standards') or {}),
            'mechanisms': list(item.get('mechanisms') or []),
            'relations': relations,
            'sources': [ref.model_dump(mode='json') for ref in refs],
            'audit': {'created_at': audit_created, 'reviewed_by_human': False},
        })

        note, body_paragraphs = _extract_reading_note(item, refs)
        body = format_body(node_type, body_paragraphs, refs, item.get('body_sections'), item.get('markdown'))
        path = vault / card_directory(meta) / f'{node_id}.md'
        content = serialize_card(meta, body)
        parsed_meta, _ = parse_card(content.decode('utf-8'))
        if parsed_meta != meta:
            raise ValueError(f'卡片序列化往返校验不一致: {node_id}')

        if path.exists():
            existing_text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
            if existing_text == content.decode('utf-8'):
                skipped_cards += 1
            else:
                raise ValueError(f'目标卡片已存在且内容不一致，未覆盖: {path}')
        else:
            planned_create[path] = content

        if note is not None and notes_path is not None:
            if node_id in notes:
                if EditorialNote.model_validate(notes[node_id]) == EditorialNote.model_validate(note):
                    skipped_notes += 1
                else:
                    raise ValueError(f'阅读提要已存在且内容不一致，未覆盖: {node_id}')
            else:
                new_notes[node_id] = note

    if dry_run:
        print(
            f'[dry-run] 校验通过：{len(records)} 条分类枢纽卡'
            f'（待新建 {len(planned_create)} 张，已一致跳过 {skipped_cards} 张；'
            f'待新增提要 {len(new_notes)} 条，已一致跳过 {skipped_notes} 条）。'
        )
        return {
            'total': len(records),
            'created': len(planned_create),
            'skipped_cards': skipped_cards,
            'notes_added': len(new_notes),
            'skipped_notes': skipped_notes,
        }

    if not planned_create and not new_notes:
        print(f'全部 {len(records)} 张分类枢纽卡与阅读提要均已存在且内容一致，无需写入。')
        return {
            'total': len(records),
            'created': 0,
            'skipped_cards': skipped_cards,
            'notes_added': 0,
            'skipped_notes': skipped_notes,
        }

    updated_notes: str | None = None
    if new_notes and notes_path is not None:
        suffix = yaml.safe_dump(new_notes, allow_unicode=True, sort_keys=False, width=1000)
        updated_notes = old_notes.rstrip() + '\n\n' + suffix if notes else suffix

    created: list[Path] = []
    notes_written = False
    with vault_writer(vault):
        try:
            for path, content in planned_create.items():
                create_card(path, content)
                created.append(path)
            if updated_notes is not None and notes_path is not None:
                notes_path.parent.mkdir(parents=True, exist_ok=True)
                replace_card(notes_path, updated_notes.encode('utf-8'))
                notes_written = True
        except Exception:
            if notes_written and notes_path is not None:
                replace_card(notes_path, old_notes.encode('utf-8'))
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise

    print(
        f'已创建 {len(created)} 张分类枢纽卡（跳过已存在一致 {skipped_cards} 张），'
        f'新增阅读提要 {len(new_notes)} 条。'
    )
    return {
        'total': len(records),
        'created': len(created),
        'skipped_cards': skipped_cards,
        'notes_added': len(new_notes),
        'skipped_notes': skipped_notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', '--collection', dest='input_path', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--date', type=date.fromisoformat, default=date.fromisoformat('2026-11-26'))
    parser.add_argument('--vault', type=Path, default=VAULT)
    parser.add_argument('--notes', type=Path, default=DEFAULT_NOTES)
    parser.add_argument('--no-notes', action='store_true')
    parser.add_argument('--graph', type=Path, default=DEFAULT_GRAPH)
    parser.add_argument('--pending-yaml', nargs='*', type=Path, default=[])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.pending_yaml and not args.dry_run:
        parser.error('--pending-yaml 仅用于 --dry-run 预检，正式入库须先导入前置批次。')
    run(
        args.input_path,
        args.date,
        vault=args.vault,
        notes_path=None if args.no_notes else args.notes,
        graph_path=args.graph,
        pending_yaml=args.pending_yaml,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
