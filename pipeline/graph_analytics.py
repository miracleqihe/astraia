"""Measure topology using only the non-fiction partition of a graph."""

from collections import Counter, defaultdict
from math import fsum, log2

import networkx as nx

from pipeline.graph_links import Link
from pipeline.vault import VaultCard


def research_metrics(
    cards: dict[str, VaultCard], links: list[Link]
) -> tuple[dict[str, dict], int | None]:
    topology = nx.DiGraph()
    topology.add_nodes_from(
        node_id for node_id, card in cards.items() if not card.metadata.is_fictional_quarantine
    )
    hub_cases: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if link.is_fictional_quarantine:
            continue
        topology.add_edge(link.source, link.target)
        source = cards[link.source].metadata
        if source.node_type == "case" and link.type in {"TAGGED_OCM", "HAS_MOTIF"}:
            hub_cases[link.target].add(source.id)

    sample_size = 128 if len(topology) > 500 else None
    betweenness = nx.betweenness_centrality(topology, k=sample_size, seed=0)
    metrics = {}
    for node_id in topology:
        metrics[node_id] = {
            "in_degree": topology.in_degree(node_id),
            "out_degree": topology.out_degree(node_id),
            "betweenness": betweenness[node_id],
        }
        if cards[node_id].metadata.node_type == "motif_index":
            cases = hub_cases[node_id]
            regions = Counter()
            for case_id in cases:
                spatial = cards[case_id].metadata.spatial
                if spatial is not None and spatial.culture_region:
                    regions[spatial.culture_region] += 1
            total = regions.total()
            entropy = fsum(-(count / total) * log2(count / total) for count in regions.values())
            metrics[node_id].update({
                "case_in_degree": len(cases),
                "culture_region_entropy_bits": entropy if total else None,
            })
    return metrics, sample_size
