"""Build a public snapshot solely from human-reviewed, publication-cleared cards."""

import argparse
from pathlib import Path
import sys

from pipeline.build_graph import compile_cards
from pipeline.graph_output import publish_graph
from pipeline.ingest_agent import DEFAULT_CODE_TABLE, DEFAULT_VAULT, verify_local_sources
from pipeline.local_standards import load_code_table, verify_codes
from pipeline.node_model import NodeMetadata
from pipeline.public_fingerprint import public_content_sha256
from pipeline.vault import VaultCard, load_vault
from pipeline.vault_write import vault_writer


def build_public_graph(vault: Path, code_table: Path) -> dict:
    cards = load_vault(vault)
    chosen = {key: card for key, card in cards.items() if card.metadata.audit.public_release}
    table = load_code_table(code_table)
    for card in chosen.values():
        audit = card.metadata.audit
        if not audit.reviewed_by_human or audit.is_sample or not audit.public_rights_note:
            raise ValueError(f'缺少人工复核或公开许可依据：{card.metadata.id}')
        actual = public_content_sha256(card.metadata.model_dump(mode='json'), card.markdown)
        if actual != audit.public_content_sha256:
            raise ValueError(f'公开签核后卡片内容发生变化，请重新复核：{card.metadata.id}')
        if not card.metadata.sources:
            raise ValueError(f'公开卡片缺少出处：{card.metadata.id}')
        verify_codes(card.metadata.standards, table)
    verify_local_sources(list(chosen.values()))

    public = {}
    for key, card in chosen.items():
        payload = card.metadata.model_dump(mode='json')
        payload['relations'] = [relation for relation in payload['relations'] if relation['target'] in chosen]
        payload['mechanisms'] = [mechanism for mechanism in payload['mechanisms'] if mechanism['target_id'] in chosen]
        for source in payload['sources']:
            source['local_path'] = None
        payload['audit']['review_note'] = None
        public[key] = VaultCard(NodeMetadata.model_validate(payload), f'公开资料/{key}', card.markdown)
    return compile_cards(public, include_samples=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--code-table', type=Path, default=DEFAULT_CODE_TABLE)
    parser.add_argument('--output', type=Path, default=Path('.local/publication/graph_data.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        vault = args.vault.resolve()
        output = args.output.resolve()
        if output.is_relative_to(vault):
            raise ValueError('公开快照须写入资料库之外。')
        with vault_writer(vault):
            graph = build_public_graph(vault, args.code_table)
            count = len(graph['nodes'])
            print(f'可公开的已复核资料：{count} 条；关联：{len(graph["links"])} 条。')
            if not args.check:
                if not count:
                    raise ValueError('尚无确认可公开的已复核资料；没有覆盖现有网站。')
                output.parent.mkdir(parents=True, exist_ok=True)
                publish_graph(output, graph, 'json')
                print(f'已生成公开快照：{output}')
    except (OSError, ValueError) as error:
        print(f'公开快照未生成：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
