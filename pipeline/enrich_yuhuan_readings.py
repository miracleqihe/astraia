"""Attach source-linked reading summaries and regional map anchors to existing Yuhuan cards."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

import yaml

from pipeline.ingest_agent import DEFAULT_VAULT, serialize_card
from pipeline.node_model import NodeMetadata
from pipeline.reading_notes import DEFAULT_NOTES, EditorialNote
from pipeline.vault import FrontmatterLoader, parse_card
from pipeline.vault_write import replace_card, vault_writer

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'reference/yuhuan_readings_20261123.yaml'
SCAN = ROOT / '.local/import-sources/china-yuhuan/yuhuan-oral-literature-2008.pdf'
MARKER = '<!-- astraia:yuhuan-reading-20261123 -->'
OLD_LOCATION = '流传区域不等于具体采录点或故事发生地；未自动填坐标、年代或标准码。'
NEW_LOCATION = '地图标点为所记故事背景或流传区域参考；年代和标准码未自动填写。'
OLD_PUBLICATION = '人工作出复核决定前不编入正式图谱。'
NEW_PUBLICATION = '档案保留原有复核状态。'


def plan_updates(batch_path: Path, vault: Path, notes_path: Path, scan: Path) -> dict[Path, bytes]:
    batch = yaml.load(batch_path.read_text(encoding='utf-8'), Loader=FrontmatterLoader)
    if not isinstance(batch, dict) or set(batch) != {'version', 'pdf_sha256', 'records', 'hub'} or batch['version'] != 1:
        raise ValueError('阅读稿批次格式不符。')
    digest = sha256(scan.read_bytes()).hexdigest()
    if digest != batch['pdf_sha256']:
        raise ValueError('原书扫描文件的哈希与批次不一致。')
    original_notes = notes_path.read_text(encoding='utf-8')
    existing = yaml.load(original_notes, Loader=FrontmatterLoader)
    if not isinstance(existing, dict):
        raise ValueError('阅读稿索引不是按编号编排的映射。')
    additions = {}
    updates = {}
    for item in batch['records']:
        node_id = item['id']
        if not re.fullmatch(r'case_cn_yuhuan_2008_p\d{3}', node_id) or node_id in additions or node_id in existing:
            raise ValueError(f'档案编号重复或不符合格式：{node_id}')
        path = vault / '00_drafts' / 'asia_yuhuan_2008' / f'{node_id}.md'
        original = path.read_bytes()
        if sha256(original).hexdigest() != item['original_sha256']:
            raise ValueError(f'档案已变更，未覆盖：{node_id}')
        metadata, body = parse_card(original.decode('utf-8-sig').replace('\r\n', '\n'))
        if (metadata.id != node_id or metadata.audit.reviewed_by_human or metadata.audit.is_sample
                or not metadata.spatial or metadata.spatial.lat is not None or metadata.spatial.lng is not None):
            raise ValueError(f'档案状态或原始坐标与预期不同：{node_id}')
        original_scans = [s for s in metadata.sources if s.type == 'yuhuan_scan' and s.url]
        if not original_scans or any(s.content_sha256 != digest for s in original_scans):
            raise ValueError(f'原书出处不符：{node_id}')
        if body.count(OLD_LOCATION) != 1 or body.count(OLD_PUBLICATION) != 1 or MARKER in body:
            raise ValueError(f'档案正文结构与预期不同：{node_id}')
        data = metadata.model_dump(mode='json')
        data['spatial'] = item['spatial']
        data['genre'] = 'folktale'
        data['sources'].extend(item['geo_sources'])
        revised = NodeMetadata.model_validate(data)
        if (revised.spatial is None or revised.spatial.lat is None or revised.spatial.precision == 'exact'
                or not item['location_note'] or len(item['paragraphs']) < 2):
            raise ValueError(f'地区参考点或梗概不完整：{node_id}')
        source_numbers = [i for i, source in enumerate(revised.sources, 1) if source.type == 'yuhuan_scan' and source.url]
        source_numbers.extend(range(len(metadata.sources) + 1, len(revised.sources) + 1))
        note = {'kind': 'story', 'paragraphs': item['paragraphs'], 'source_numbers': source_numbers,
                'map_label': item['map_label'], 'location_note': item['location_note']}
        EditorialNote.model_validate(note)
        additions[node_id] = note
        body = body.replace(OLD_LOCATION, NEW_LOCATION).replace(OLD_PUBLICATION, NEW_PUBLICATION).rstrip()
        body += '\n\n' + MARKER + '\n## 故事梗概\n\n' + '\n\n'.join(item['paragraphs'])
        body += '\n\n## 地图参考\n\n' + item['location_note'] + '\n'
        updates[path] = serialize_card(revised, body)

    hub = dict(batch['hub'])
    hub_id = hub.pop('id')
    if hub_id != 'corpus_cn_yuhuan_2008' or hub_id in existing or hub_id in additions:
        raise ValueError('选辑总览编号重复或不符。')
    hub_path = vault / '00_drafts' / 'asia_yuhuan_2008' / f'{hub_id}.md'
    hub_metadata, _ = parse_card(hub_path.read_text(encoding='utf-8-sig').replace('\r\n', '\n'))
    if hub_metadata.id != hub_id or max(hub['source_numbers']) > len(hub_metadata.sources):
        raise ValueError('选辑总览出处不符。')
    EditorialNote.model_validate(hub)
    additions[hub_id] = hub
    prefix = original_notes.rstrip() + '\n\n' if existing else ''
    updates[notes_path] = (prefix + yaml.safe_dump(
        additions, allow_unicode=True, sort_keys=False, width=1000)).encode('utf-8')
    return updates


def apply_updates(updates: dict[Path, bytes]) -> None:
    originals = {path: path.read_bytes() for path in updates}
    written = []
    try:
        for path, content in updates.items():
            replace_card(path, content)
            written.append(path)
    except OSError:
        for path in reversed(written):
            replace_card(path, originals[path])
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, default=BATCH)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--notes', type=Path, default=DEFAULT_NOTES)
    parser.add_argument('--scan', type=Path, default=SCAN)
    parser.add_argument('--check', action='store_true', help='校验变更，不写入文件')
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    with vault_writer(args.vault):
        updates = plan_updates(args.batch, args.vault, args.notes, args.scan)
        if not args.check:
            apply_updates(updates)
    if args.manifest:
        manifest = {p.stem: p.relative_to(ROOT).as_posix() for p in updates if p.suffix == '.md'}
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{"已校验" if args.check else "已更新"} {len(updates) - 1} 篇故事和选辑阅读总览。')


if __name__ == '__main__':
    main()
