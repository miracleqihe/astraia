"""Resolve explicit edges and connect cards to their standard-code hubs."""

from dataclasses import dataclass, field
from typing import Literal

from pipeline.node_model import CREDIBILITY_WEIGHT, ExplanationStatus, RelationType, Standards
from pipeline.vault import VaultCard, VaultError

STANDARD_RELATION_TYPES: dict[str, RelationType] = {
    "atu_types": "HAS_MOTIF",
    "thompson_motifs": "HAS_MOTIF",
    "berezkin_codes": "HAS_MOTIF",
    "ocm_codes": "TAGGED_OCM",
}
StandardKey = tuple[str, str]
LinkKey = tuple[str, str, RelationType]


@dataclass
class Link:
    source: str
    target: str
    type: RelationType
    origin: Literal["explicit", "mechanism", "standard"]
    weight: float = 1.0
    note: str | None = None
    status: ExplanationStatus | None = None
    is_fictional_quarantine: bool = False
    matched_codes: list[dict[str, str]] = field(default_factory=list)

    @property
    def key(self) -> LinkKey:
        return self.source, self.target, self.type


def validate_explicit_links(cards: dict[str, VaultCard]) -> dict[LinkKey, Link]:
    links: dict[LinkKey, Link] = {}
    errors = []

    for card in cards.values():
        node = card.metadata
        candidates = [
            Link(node.id, relation.target, relation.type, "explicit",
                 weight=relation.weight, note=relation.note, status=relation.status)
            for relation in node.relations
        ]
        candidates.extend(
            Link(node.id, mechanism.target_id, "EXPLAINED_BY", "mechanism",
                 note=mechanism.evidence_note, status=mechanism.status)
            for mechanism in node.mechanisms
        )
        for link in candidates:
            target = cards.get(link.target)
            if target is None:
                errors.append(f"{card.source_path} {link.type} 指向不存在的节点 {link.target}")
                continue
            if target is card:
                errors.append(f"{card.source_path} {link.type} 指向卡片自身")
                continue
            if link.type == "EXPLAINED_BY" and target.metadata.z_layer != 4:
                errors.append(f"{card.source_path} EXPLAINED_BY 须指向 L4 节点 {link.target}")
                continue
            if link.type in {"HAS_MOTIF", "TAGGED_OCM"} and target.metadata.z_layer != 3:
                errors.append(f"{card.source_path} {link.type} 须指向 L3 节点 {link.target}")
                continue
            if link.type == "ATTESTS_MOTIF" and (node.z_layer != 2 or target.metadata.z_layer != 3 or not link.note):
                errors.append(f"{card.source_path} ATTESTS_MOTIF 须连接 L2 地区资料与 L3 母题并注明依据")
                continue
            if link.key in links:
                errors.append(f"{card.source_path} 到 {link.target} 的 {link.type} 关系重复")
                continue
            link.is_fictional_quarantine = (
                node.is_fictional_quarantine or target.metadata.is_fictional_quarantine
            )
            links[link.key] = link

    if errors:
        raise VaultError("\n".join(errors))
    return links


def normalize_code(system: str, value: str) -> str:
    normalized = "".join(value.split()).casefold()
    prefix = {"atu_types": "atu", "ocm_codes": "ocm"}.get(system)
    if prefix and normalized != prefix:
        normalized = normalized.removeprefix(prefix)
    return normalized


def standard_codes(standards: Standards) -> dict[StandardKey, str]:
    codes: dict[StandardKey, str] = {}
    for system in STANDARD_RELATION_TYPES:
        for code in getattr(standards, system):
            codes.setdefault((system, normalize_code(system, code)), code)
    return codes


def infer_standard_links(
    cards: dict[str, VaultCard], links: dict[LinkKey, Link]
) -> list[dict[str, str]]:
    codes_by_node = {
        node_id: standard_codes(card.metadata.standards)
        for node_id, card in cards.items()
    }
    hubs: dict[tuple[bool, StandardKey], tuple[str, str]] = {}
    for card in cards.values():
        node = card.metadata
        if node.node_type != "motif_index":
            continue
        for key, code in codes_by_node[node.id].items():
            hub_key = node.is_fictional_quarantine, key
            if hub_key in hubs:
                other_id, _ = hubs[hub_key]
                raise VaultError(f"{card.source_path} 的 {key[0]} 编码 {code} 已由 {other_id} 登记")
            hubs[hub_key] = node.id, code

    unmatched = []
    for card in cards.values():
        node = card.metadata
        if node.node_type == "motif_index":
            continue
        for key, code in codes_by_node[node.id].items():
            system, _ = key
            hub = hubs.get((node.is_fictional_quarantine, key))
            if hub is None:
                unmatched.append({"node_id": node.id, "system": system, "code": code})
                continue
            hub_id, hub_code = hub
            link_type = STANDARD_RELATION_TYPES[system]
            link_key = node.id, hub_id, link_type
            if link_key not in links:
                links[link_key] = Link(
                    node.id, hub_id, link_type, "standard",
                    weight=CREDIBILITY_WEIGHT[node.credibility_tier],
                    is_fictional_quarantine=node.is_fictional_quarantine,
                )
            links[link_key].matched_codes.append({"system": system, "code": hub_code})
    return unmatched
