"""Attach a verified transcription to the existing unreviewed Li Tongpan card."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.ingest_agent import DEFAULT_VAULT, serialize_card
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer
from pipeline.zibuyu import EXISTING_ID, card_body, load_snapshot, source_set, volume_id


def enrich(vault: Path, snapshot: Path, expected_sha256: str, backup: Path | None, apply: bool = False) -> dict:
    path = vault / '00_drafts' / 'regional_sources' / f'{EXISTING_ID}.md'
    if path.is_symlink(): raise IntakeError('既有草稿不能为符号链接。')
    with vault_writer(vault):
        raw = path.read_bytes()
        before = sha256(raw).hexdigest()
        if before != expected_sha256: raise IntakeError('既有草稿已变化，保留原文并重新核对。')
        metadata, body = parse_card(raw.decode('utf-8-sig').replace('\r\n', '\n'))
        if (metadata.id != EXISTING_ID or metadata.audit.reviewed_by_human or metadata.audit.is_sample
                or metadata.relations or len(metadata.sources) != 1 or metadata.sources[0].type != 'primary_archive'
                or metadata.sources[0].locator != '卷一首篇' or '李通判' not in metadata.aliases):
            raise IntakeError('既有草稿状态或来源与预期不符，不覆盖。')
        manifest, _, volumes, _ = load_snapshot(snapshot)
        row = volumes[0][0]
        data = metadata.model_dump(mode='python')
        data['sources'] = source_set(snapshot, manifest, row=row)
        data['relations'] = [{'type': 'PART_OF_MACRO_TREND', 'target': volume_id(1),
                              'note': '维基文库卷一首篇；既有卡片与同页篇题对照。'}]
        updated = NodeMetadata.model_validate(data)
        content = serialize_card(updated, body.rstrip() + '\n' + card_body(row, manifest))
        result = {'id': EXISTING_ID, 'before_sha256': before, 'after_sha256': sha256(content).hexdigest(),
                  'snapshot_sha256': sha256((snapshot / 'manifest.json').read_bytes()).hexdigest(),
                  'reviewed_by_human': False, 'applied': apply}
        if apply:
            if backup is None: raise IntakeError('写入前须提供新的备份路径。')
            backup.parent.mkdir(parents=True, exist_ok=True)
            exclusive_write(backup, raw)
            with TemporaryDirectory(prefix='.astraia-enrich-', dir=path.parent) as temp:
                temporary = Path(temp) / 'card.md'
                temporary.write_bytes(content)
                if sha256(path.read_bytes()).hexdigest() != before:
                    raise IntakeError('写入期间草稿发生变化；原件与备份均已保留。')
                os.replace(temporary, path)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    result = enrich(args.vault, args.snapshots, args.expected_sha256, args.backup, args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
