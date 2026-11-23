"""Build public reading notes from cited editorial text and selected catalogue fields."""

from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
from typing import Annotated, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field
import yaml

from pipeline.graph_output import graph_json
from pipeline.node_model import NonBlank, Source, StrictModel
from pipeline.vault import FrontmatterLoader, VaultCard

DEFAULT_NOTES = Path(__file__).resolve().parents[1] / "reference/reading_notes.yaml"


class EditorialNote(StrictModel):
    kind: Literal["story", "legend", "report", "history", "research"]
    paragraphs: list[NonBlank] = Field(min_length=1, max_length=4)
    source_numbers: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    additional_sources: list[Source] = Field(default_factory=list)
    map_label: NonBlank | None = None
    location_note: NonBlank | None = None


def load_notes(path: Path, cards: dict[str, VaultCard]) -> dict[str, EditorialNote]:
    raw = yaml.load(path.read_text(encoding="utf-8"), Loader=FrontmatterLoader)
    if not isinstance(raw, dict):
        raise ValueError("阅读提要应按卡片 ID 编目。")
    notes = {}
    for node_id, data in raw.items():
        card = cards.get(node_id)
        if card is None:
            raise ValueError(f"阅读提要指向不存在的卡片：{node_id}")
        note = EditorialNote.model_validate(data)
        if any(not source.url or source.local_path or source.content_sha256 for source in note.additional_sources):
            raise ValueError(f"补充出处须是公开链接：{node_id}")
        if max(note.source_numbers) > len(card.metadata.sources) + len(note.additional_sources):
            raise ValueError(f"阅读提要引用了不存在的出处：{node_id}")
        if len(note.source_numbers) != len(set(note.source_numbers)):
            raise ValueError(f"阅读提要重复引用同一出处：{node_id}")
        notes[node_id] = note
    return notes


def zibuyu_edition(card: VaultCard) -> dict | None:
    """Publish only the public-domain passage indexed to a fixed Wikisource revision."""
    if not (card.source_path.startswith("00_drafts/asia_cn_zibuyu_wikisource/")
            or card.metadata.id == "case_zibuyu_li_tongpan"):
        return None
    passage = re.search(r"^## 在线转录原文（待校）\n\n```\n(.+?)\n```$", card.markdown, re.M | re.S)
    if not passage:
        return None
    digest = re.search(r'"抽取纯文字 SHA256": "([0-9a-f]{64})"', card.markdown)
    text = passage[1]
    if not digest or digest[1] != sha256(text.encode("utf-8")).hexdigest():
        raise ValueError(f"《子不语》转录正文与原记录哈希不一致：{card.metadata.id}")
    for position, source in enumerate(card.metadata.sources, start=1):
        if source.type != "zibuyu_revision_link" or not source.url:
            continue
        url = urlsplit(str(source.url))
        fields = parse_qs(url.query)
        if (url.scheme == "https" and url.netloc == "zh.wikisource.org"
                and fields.get("title", [""])[0].startswith("子不語/卷")
                and fields.get("oldid", [""])[0].isdigit() and url.fragment):
            return {"text": text, "source_number": position}
    raise ValueError(f"《子不语》转录正文缺少可核对的固定修订链接：{card.metadata.id}")


def accused_archive_note(card: VaultCard) -> dict | None:
    """Use public facts from the Edinburgh survey rather than implying a story."""
    if not card.source_path.startswith("00_drafts/scottish_witchcraft/") or card.metadata.z_layer != 1:
        return None
    entries = []
    for match in re.finditer(r"^- (调查|审判) `([^\n`]+)`(?:　([^\n]+))?$", card.markdown, re.M):
        label, archive_id, details = match.groups()
        entries.append(" ".join(part for part in (label, archive_id, details) if part))
    number = re.search(r"^- 原表中登记的涉案人数　(\d+)$", card.markdown, re.M)
    sentences = []
    if number:
        sentences.append(f"案卷登记涉案人数为 {number[1]}。")
    if entries:
        sentences.append("关联档案列有" + "；".join(entries[:8]) + "。")
    if not sentences:
        return None
    return {"kind": "archive", "paragraphs": ["".join(sentences)], "source_numbers": [1]}


def attach_reading(graph: dict, cards: dict[str, VaultCard], notes_path: Path | None) -> dict:
    notes = load_notes(notes_path, cards) if notes_path else {}
    motif_regions = Counter(link["target"] for link in graph["links"] if link["type"] == "ATTESTS_MOTIF")
    for node in graph["nodes"]:
        card = cards[node["id"]]
        editorial = notes.get(node["id"])
        if editorial:
            reading = editorial.model_dump(mode="json", exclude={"additional_sources"}, exclude_none=True)
            node["sources"].extend(source.model_dump(mode="json") for source in editorial.additional_sources)
        else:
            reading = accused_archive_note(card)
            if card.source_path.startswith("00_drafts/berezkin_distribution/") and motif_regions[node["id"]]:
                count = motif_regions[node["id"]]
                reading = {"kind": "archive", "source_numbers": [1], "paragraphs": [
                    f"研究数据为此母题标引了 {count} 个文化分析区。点开关联可以逐个查看这些研究区及其参考地点。"
                ]}
        edition = zibuyu_edition(card)
        if edition and reading is None:
            reading = {"kind": "edition", "paragraphs": [], "source_numbers": [edition["source_number"]]}
        if reading is not None:
            if edition:
                reading["edition"] = edition
            node["reading"] = reading
    graph.pop("snapshot_id")
    graph["snapshot_id"] = sha256(graph_json(graph).encode("utf-8")).hexdigest()
    return graph
