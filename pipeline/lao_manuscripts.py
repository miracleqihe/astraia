"""Create reviewable DLLM manuscript records from verified search snapshots."""
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from collections import defaultdict
import json
from pathlib import Path
import re

from pipeline.build_graph import PROJECT_ROOT
from pipeline.fetch_lao_dllm import IDENTIFIER, PAYLOAD, SEARCH_URL, metadata_values, parse_page
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

COLLECTION = "corpus_lao_dllm_folktales"
VIEWER = "https://iiif.crossasia.org/s/dllm/manifests/{}"
SELECTED_FIELDS = ("title", "dc:identifier", "otherIdentifier.code_number", "dc:language", "script",
                   "dc:subject", "material", "dc:extent", "date_original", "full_location_name",
                   "schema:latitude", "schema:longitude", "is_complete", "has_colophon", "legibilities", "conditions")


@dataclass(frozen=True)
class Manuscript:
    identifier: int
    page: int
    snapshot: Path
    digest: str
    record: dict


def display_path(path: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def load_snapshot(folder: Path) -> tuple[dict, list[Manuscript]]:
    folder = folder.resolve(strict=True)
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"老挝馆藏批次清单无法读取。{error}") from error
    if (not isinstance(manifest, dict) or manifest.get("version") != 1 or manifest.get("search_url") != SEARCH_URL
            or manifest.get("payload") != PAYLOAD or not isinstance(manifest.get("pages"), list)
            or type(manifest.get("total_results")) is not int or type(manifest.get("total_pages")) is not int
            or type(manifest.get("page_size")) is not int or len(manifest["pages"]) != manifest["total_pages"]):
        raise IntakeError("老挝馆藏批次清单的检索条件或分页信息不符。")
    records, seen = [], set()
    for number, entry in enumerate(manifest["pages"], 1):
        if not isinstance(entry, dict) or entry.get("page") != number or entry.get("path") != f"page-{number:03d}.json":
            raise IntakeError("老挝馆藏分页路径或顺序不符。")
        path = folder / entry["path"]
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != entry.get("sha256"):
            raise IntakeError(f"老挝馆藏第 {number} 页与登记哈希不符。")
        document = parse_page(raw, number)
        page = document["pagination"]
        if (page["totalResults"], page["totalPages"], page["pageSize"]) != (
                manifest["total_results"], manifest["total_pages"], manifest["page_size"]):
            raise IntakeError("老挝馆藏分页与清单统计不符。")
        if entry.get("records") != len(document["results"]):
            raise IntakeError("老挝馆藏分页记录数与清单不符。")
        for item in document["results"]:
            identifier = int(IDENTIFIER.fullmatch(item["resource_id"]).group(1))
            if identifier in seen:
                raise IntakeError(f"老挝馆藏编号重复。{identifier}")
            seen.add(identifier)
            records.append(Manuscript(identifier, number, path, digest, item))
    if len(records) != manifest["total_results"]:
        raise IntakeError("老挝馆藏唯一记录数与清单不符。")
    return manifest, records


def selected_fields(item: dict) -> dict[str, dict[str, list[str]]]:
    return {key: value for key in SELECTED_FIELDS if (value := metadata_values(item, key))}


def plmp_index(records: list[Manuscript]) -> dict[str, list[Manuscript]]:
    groups: dict[str, list[Manuscript]] = defaultdict(list)
    for item in records:
        codes = selected_fields(item.record).get("otherIdentifier.code_number", {}).get("none", [])
        for code in dict.fromkeys(value.strip() for value in codes if value.strip()):
            groups[code].append(item)
    return dict(groups)


def attribution(item: dict) -> str:
    statement = item.get("requiredStatement")
    if not isinstance(statement, dict) or not isinstance(statement.get("value"), dict):
        return ""
    values = [value.strip() for group in statement["value"].values() if isinstance(group, list)
              for value in group if isinstance(value, str) and value.strip()]
    return " / ".join(values)


def _values(fields: dict, name: str, language: str) -> list[str]:
    return [value.strip() for value in fields.get(name, {}).get(language, []) if value.strip()]


def lao_cards(folder: Path):
    manifest, records = load_snapshot(folder)
    code_groups = plmp_index(records)
    manifest_path = folder / "manifest.json"
    manifest_digest = sha256(manifest_path.read_bytes()).hexdigest()
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}
    corpus = {**common, "id": COLLECTION, "title": "老挝数字手稿馆 · 民间故事类手稿",
              "node_type": "myth_corpus", "z_layer": 2,
              "spatial": {"precision": "culture_region", "location_name": "老挝（馆藏范围，非单篇采录地）",
                          "culture_region": "Southeast Asia · Laos"},
              "sources": [{"citation": "Digital Library of Lao Manuscripts, Folk Tale 分类检索快照。",
                           "type": "lao_dllm_manifest", "url": SEARCH_URL,
                           "locator": f"Folk Tale / {manifest['total_results']} 件 / {manifest['total_pages']} 页",
                           "local_path": display_path(manifest_path), "content_sha256": manifest_digest}]}
    yield NodeMetadata.model_validate(corpus), (
        "\n## 馆藏范围\n\n此批为老挝数字手稿馆检索分类 Folk Tale 的馆藏元数据。每件对应一份馆藏手稿或文本，"
        "并非独立采录事件。馆藏地点与坐标是保管地信息，不能直接当作传说发生地或采录地点。"
        "原手稿通过各条馆藏链接查看；本批没有下载影像，也没有假称完成文字转录。"
        "馆方逐件署名及许可声明保存在卡片和快照中；抄写年代不等于叙事发生年代。\n")

    for item in records:
        fields = selected_fields(item.record)
        roman = _values(fields, "title", "en")
        lao = _values(fields, "title", "lo")
        label = item.record.get("label", {})
        candidates = [value.strip() for values in label.values() if isinstance(values, list)
                      for value in values if isinstance(value, str) and value.strip()] if isinstance(label, dict) else []
        title = candidates[0] if candidates else " / ".join([*roman, *lao]) or f"馆藏 {item.identifier}"
        places = _values(fields, "full_location_name", "en") + _values(fields, "full_location_name", "lo")
        location = " / ".join(places) or "馆藏地点未登记"
        identifiers = _values(fields, "dc:identifier", "none") + _values(fields, "otherIdentifier.code_number", "none")
        aliases = list(dict.fromkeys([*roman, *lao, *identifiers]))
        codes = _values(fields, "otherIdentifier.code_number", "none")
        duplicates = {other.identifier: (code, other) for code in codes for other in code_groups.get(code, [])
                      if other.identifier != item.identifier}
        credit = attribution(item.record)
        citation = credit or "Digital Library of Lao Manuscripts，单件许可及署名说明待核。"
        metadata = {**common, "id": f"corpus_lao_dllm_{item.identifier}", "title": f"老挝馆藏手稿 · {title}",
                    "aliases": aliases, "node_type": "myth_corpus", "z_layer": 2,
                    "spatial": {"precision": "culture_region", "location_name": f"馆藏地（非采录地或故事发生地）：{location}",
                                "culture_region": "Southeast Asia · Laos"},
                    "relations": [{"type": "PART_OF_MACRO_TREND", "target": COLLECTION,
                                   "note": "属于同一馆藏检索集合，不表示叙事之间存在传播关系。"}],
                    "sources": [{"citation": citation, "type": "lao_dllm_search", "url": SEARCH_URL,
                                 "locator": f"Folk Tale / 第 {item.page} 页 / 馆藏 manifest {item.identifier}",
                                 "local_path": display_path(item.snapshot), "content_sha256": item.digest},
                                {"citation": "老挝数字手稿馆单件页面与原始影像（未下载；点击原馆藏查看）。",
                                 "type": "lao_dllm_viewer", "url": VIEWER.format(item.identifier),
                                 "locator": f"manifest {item.identifier} / 手稿影像"}]}
        compared_pages = set()
        for code, other in duplicates.values():
            if other.snapshot == item.snapshot or other.snapshot in compared_pages:
                continue
            compared_pages.add(other.snapshot)
            metadata["sources"].append({"citation": "老挝数字手稿馆相同 PLMP 档号的跨页对照。",
                "type": "lao_dllm_crosscheck", "url": SEARCH_URL,
                "locator": f"PLMP {code} / 第 {other.page} 页 / manifest {other.identifier}",
                "local_path": display_path(other.snapshot), "content_sha256": other.digest})
        formatted = json.dumps({"馆藏字段": fields, "署名与许可": credit or "未提供"}, ensure_ascii=False, indent=2)
        comparison = ""
        if duplicates:
            comparison = "\n## PLMP 档号对照待核\n\n同一档号对应不同馆藏记录，可能存在重号或其他编目关系，不能自动合并：\n\n"
            for other_id, (code, other) in sorted(duplicates.items()):
                other_fields = selected_fields(other.record)
                other_names = _values(other_fields, "title", "en") + _values(other_fields, "dc:identifier", "none")
                comparison += f"- PLMP {code} · manifest {other_id} · {' / '.join(other_names)} · [查看馆藏]({VIEWER.format(other_id)})\n"
        body = ("\n## 原始馆藏字段\n\n" + literal_block(formatted) + comparison
                + "\n\n## 原图与复核\n\n这是馆藏手稿的元数据，未下载手稿图像，也未生成文字转录；"
                  "可通过出处中的馆藏页面查看原图。馆藏地点及其候选坐标不代表故事发生地或采录地；"
                  "馆藏日期属于手稿登记，不能直接推定叙事年代。体裁和标准码留待人工核对。\n")
        yield NodeMetadata.model_validate(metadata), body
