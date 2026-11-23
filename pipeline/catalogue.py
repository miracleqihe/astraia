"""Create the explicitly requested public metadata catalogue without changing audit state."""

import argparse
from pathlib import Path
import sys

from pipeline.build_graph import compile_cards
from pipeline.graph_output import publish_graph
from pipeline.ingest_agent import DEFAULT_CODE_TABLE, DEFAULT_VAULT, verify_local_sources
from pipeline.local_standards import load_code_table, verify_codes
from pipeline.node_model import NodeMetadata
from pipeline.public_fingerprint import public_content_sha256
from pipeline.reading_notes import DEFAULT_NOTES, attach_reading
from pipeline.vault import VaultCard, load_vault, parse_card
from pipeline.vault_write import vault_writer


def build_catalogue(vault: Path, code_table: Path) -> dict:
    cards = load_vault(vault)
    table = load_code_table(code_table)
    for path in sorted((vault / '00_drafts').rglob('*.md')):
        if path.is_symlink():
            raise ValueError(f'待审资料不能使用符号链接：{path}')
        metadata, body = parse_card(path.read_text(encoding='utf-8-sig').replace('\r\n', '\n'))
        if metadata.id != path.stem or metadata.id in cards or metadata.audit.reviewed_by_human or metadata.audit.is_sample:
            raise ValueError(f'待审资料编号或状态不符：{path}')
        verify_codes(metadata.standards, table)
        cards[metadata.id] = VaultCard(metadata, path.relative_to(vault).as_posix(), body)

    public, cleared = {}, []
    for key, card in cards.items():
        metadata = card.metadata
        if metadata.audit.public_release:
            actual = public_content_sha256(metadata.model_dump(mode='json'), card.markdown)
            if actual != metadata.audit.public_content_sha256:
                raise ValueError(f'公开签核后卡片发生变化：{key}')
            cleared.append(card)
        data = metadata.model_dump(mode='json')
        for source in data['sources']:
            source['local_path'] = None
        data['audit']['review_note'] = None
        body = card.markdown if metadata.audit.public_release or metadata.audit.is_sample else ''
        public[key] = VaultCard(NodeMetadata.model_validate(data), f'资料目录/{key}', body)
    verify_local_sources(cleared)
    graph = compile_cards(public, include_samples=True, include_drafts=True)
    return attach_reading(graph, cards, DEFAULT_NOTES if vault.resolve() == DEFAULT_VAULT.resolve() else None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--code-table', type=Path, default=DEFAULT_CODE_TABLE)
    parser.add_argument('--output', type=Path, default=Path('.local/publication/catalogue.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        vault, output = args.vault.resolve(), args.output.resolve()
        if output.is_relative_to(vault):
            raise ValueError('公开目录须写在资料库之外。')
        with vault_writer(vault):
            graph = build_catalogue(vault, args.code_table)
            if not args.check:
                publish_graph(output, graph, 'json')
        nodes = graph['nodes']
        located = sum(bool(node.get('spatial')) and node['spatial'].get('lat') is not None for node in nodes)
        print(f"目录包含 {len(nodes)} 条资料、{len(graph['links'])} 条关系及 {located} 个已有坐标的节点。")
        if not args.check:
            print(f'已写入 {output}')
    except (OSError, ValueError) as error:
        print(f'公开目录未生成：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
