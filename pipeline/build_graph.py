"""Validate the local Markdown vault and compile graph data."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import sqlite3
import sys

from pipeline.graph_analytics import research_metrics
from pipeline.graph_links import infer_standard_links, validate_explicit_links
from pipeline.graph_output import graph_json, publish_graph
from pipeline.node_model import CREDIBILITY_WEIGHT
from pipeline.vault import VaultCard, VaultError, load_vault
from pipeline.vault_write import vault_writer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS = {
    "json": PROJECT_ROOT / "web" / "public" / "data" / "graph_data.json",
    "sqlite": PROJECT_ROOT / ".local" / "graph_data.sqlite3",
}


def compile_graph(
    vault: Path, *, include_samples: bool = False, exclude_fiction: bool = False
) -> dict:
    return compile_cards(load_vault(vault), include_samples=include_samples, exclude_fiction=exclude_fiction)


def compile_cards(
    cards: dict[str, VaultCard], *, include_samples: bool = False, exclude_fiction: bool = False,
    include_drafts: bool = False,
) -> dict:
    cards = dict(sorted(cards.items()))
    explicit_links = validate_explicit_links(cards)
    approved = {
        node_id: card for node_id, card in cards.items()
        if include_drafts or card.metadata.audit.reviewed_by_human
        or (include_samples and card.metadata.audit.is_sample)
    }
    visible = {
        node_id: card for node_id, card in approved.items()
        if not exclude_fiction or not card.metadata.is_fictional_quarantine
    }
    links = {
        key: link for key, link in explicit_links.items()
        if link.source in visible and link.target in visible
    }
    unmatched_codes = infer_standard_links(visible, links)
    ordered_links = [links[key] for key in sorted(links)]
    metrics, sample_size = research_metrics(visible, ordered_links)
    connected_ids = {node_id for link in ordered_links for node_id in (link.source, link.target)}

    nodes = []
    for node_id, card in visible.items():
        node = card.metadata.model_dump(mode="json")
        node.update({
            "z": (card.metadata.z_layer - 1) * 120,
            "credibility_weight": CREDIBILITY_WEIGHT[card.metadata.credibility_tier],
            "markdown": card.markdown,
            "source_path": card.source_path,
            "metrics": metrics.get(node_id),
        })
        nodes.append(node)

    graph = {
        "schema_version": 1,
        "visibility": {"include_samples": include_samples, "exclude_fiction": exclude_fiction,
                       **({"include_drafts": True} if include_drafts else {})},
        "stats": {
            "vault_cards": len(cards),
            "visible_nodes": len(nodes),
            "visible_links": len(links),
            "excluded_drafts": len(cards) - len(approved),
            "excluded_fiction": len(approved) - len(visible),
            "isolated_node_ids": sorted(visible.keys() - connected_ids),
            "unmatched_standard_codes": unmatched_codes,
            "betweenness_sample_size": sample_size,
        },
        "nodes": nodes,
        "links": [asdict(link) for link in ordered_links],
    }
    graph["snapshot_id"] = sha256(graph_json(graph).encode("utf-8")).hexdigest()
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=PROJECT_ROOT / "vault", help="vault directory")
    parser.add_argument("--format", choices=DEFAULT_OUTPUTS, default="json", help="output format")
    parser.add_argument("--output", type=Path, help="override the default output file")
    parser.add_argument("--validate-only", action="store_true", help="validate without writing output")
    parser.add_argument("--include-samples", action="store_true", help="include marked sample cards")
    parser.add_argument("--exclude-fiction", action="store_true", help="drop quarantined nodes and links")
    args = parser.parse_args()
    output = (args.output or DEFAULT_OUTPUTS[args.format]).resolve()
    vault = args.vault.resolve()
    if not args.validate_only and output.is_relative_to(vault):
        parser.error("编译产物须保存到 vault 之外")

    try:
        options = {"include_samples": args.include_samples, "exclude_fiction": args.exclude_fiction}
        if args.validate_only:
            graph = compile_graph(vault, **options)
        else:
            with vault_writer(vault):
                graph = compile_graph(vault, **options)
                publish_graph(output, graph, args.format)
    except (VaultError, OSError, sqlite3.Error) as error:
        print(f"图谱编译失败\n{error}", file=sys.stderr)
        return 1

    stats = graph["stats"]
    print(f"校验通过。读取 {stats['vault_cards']} 张卡片，图谱包含 "
          f"{stats['visible_nodes']} 个节点、{stats['visible_links']} 条关系。")
    if not args.validate_only:
        print(f"已写入 {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
