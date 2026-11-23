"""Stage a local research index of the Academia Sinica oral-tradition catalogue."""
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.fetch_sinica_oral import FIELDS, GROUPS, detail_url, list_url
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

COLLECTION = "corpus_tw_sinica_oral"
RIGHTS_URL = "https://ascdc.digitalarchives.tw/site_7132.html"


@dataclass(frozen=True)
class OralRecord:
    identifier: int
    group: int
    page: int
    label: str
    page_path: Path
    page_digest: str
    detail_path: Path | None
    detail_digest: str | None
    detail: dict | None


def _load_file(folder: Path, entry: dict, expected_name: str) -> dict:
    if not isinstance(entry, dict) or entry.get("path") != expected_name:
        raise IntakeError("馆藏索引的快照路径无效。")
    path = folder / expected_name
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != entry.get("sha256"):
        raise IntakeError(f"馆藏索引快照哈希不符：{path}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"馆藏索引快照无法读取：{path}") from error
    if not isinstance(value, dict) or not re.fullmatch(r"[a-f0-9]{64}", value.get("raw_sha256", "")):
        raise IntakeError(f"馆藏索引快照缺少原响应哈希：{path}")
    return value


def load_snapshot(folder: Path) -> tuple[dict, list[OralRecord]]:
    folder = folder.resolve(strict=True)
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"馆藏批次清单无法读取：{error}") from error
    if (not isinstance(manifest, dict) or manifest.get("version") != 1
            or manifest.get("groups") != {str(key): value for key, value in GROUPS.items()}
            or not isinstance(manifest.get("pages"), list) or not isinstance(manifest.get("details"), list)
            or type(manifest.get("total_records")) is not int):
        raise IntakeError("馆藏批次清单结构不符。")
    details = {}
    for entry in manifest["details"]:
        identifier = entry.get("id") if isinstance(entry, dict) else None
        if type(identifier) is not int or identifier <= 0 or identifier in details:
            raise IntakeError("馆藏详情编号无效或重复。")
        name = f"detail-{identifier}.json"
        value = _load_file(folder, entry, name)
        fields = value.get("fields")
        if (value.get("id") != identifier or value.get("source_url") != detail_url(identifier)
                or value.get("rights_notice_present") is not True or not isinstance(fields, dict)
                or not fields or not any(isinstance(text, str) and text.strip() for text in fields.values())
                or any(key not in FIELDS or not isinstance(text, str) for key, text in fields.items())):
            raise IntakeError(f"详情字段快照无效：{name}")
        details[identifier] = (folder / name, entry["sha256"], fields)
    records, seen, counts, visited, linked = [], set(), {str(key): 0 for key in GROUPS}, set(), set()
    for entry in manifest["pages"]:
        group = entry.get("group") if isinstance(entry, dict) else None
        page = entry.get("page") if isinstance(entry, dict) else None
        if type(group) is not int or group not in GROUPS or type(page) is not int or page < 1 or (group, page) in visited:
            raise IntakeError("馆藏目录组或分页无效、重复。")
        visited.add((group, page))
        name = f"group-{group}-page-{page:03d}.json"
        value = _load_file(folder, entry, name)
        entries = value.get("entries")
        if (value.get("group") != group or value.get("page") != page or value.get("source_url") != list_url(group, page)
                or not isinstance(entries, list) or not entries or entry.get("records") != len(entries)):
            raise IntakeError(f"馆藏目录分页内容无效：{name}")
        page_links = value.get("linked_pages")
        if not isinstance(page_links, list) or any(type(num) is not int or not 1 <= num <= 100 for num in page_links):
            raise IntakeError(f"馆藏目录分页链接无效：{name}")
        linked.update((group, num) for num in page_links)
        for row in entries:
            identifier = row.get("id") if isinstance(row, dict) else None
            label = row.get("label") if isinstance(row, dict) else None
            if (type(identifier) is not int or identifier <= 0 or identifier in seen
                    or not isinstance(label, str) or not label.strip() or "\ufffd" in label):
                raise IntakeError(f"馆藏目录编号重复或标题无效：{name}")
            seen.add(identifier)
            counts[str(group)] += 1
            detail_path, detail_digest, fields = details.get(identifier, (None, None, None))
            records.append(OralRecord(identifier, group, page, label, folder / name, entry["sha256"],
                                      detail_path, detail_digest, fields))
    if (len(records) != manifest["total_records"] or counts != manifest.get("group_counts") or set(details) - seen
            or linked - visited or any((group, 1) not in visited for group in GROUPS)):
        raise IntakeError("馆藏目录计数或详情来源不符。")
    return manifest, records


def sinica_cards(folder: Path):
    manifest, records = load_snapshot(folder)
    manifest_path = folder / "manifest.json"
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False},
              "spatial": {"precision": "culture_region", "location_name": "台湾（馆藏范围；不代表叙事地点）",
                          "culture_region": "East Asia · Taiwan"}}
    corpus = {**common, "id": COLLECTION, "title": "中研院 · 阿美族与雅美族口语资料目录",
              "node_type": "myth_corpus", "z_layer": 2,
              "sources": [{"citation": "中央研究院民族学研究所口语传说数位典藏目录的本地研究索引。",
                           "type": "sinica_manifest", "url": "https://aya.ioe.sinica.edu.tw/",
                           "locator": f"8 个目录组 / {manifest['total_records']} 条",
                           "local_path": display_path(manifest_path),
                           "content_sha256": sha256(manifest_path.read_bytes()).hexdigest()}]}
    yield NodeMetadata.model_validate(corpus), (
        "\n## 馆藏与使用范围\n\n本批为目录索引，包含口传故事、个人经历、生活习俗、歌谣等，"
        "不是已分类神话，也不能据此推断历史事实或传播关系。目录组名与详情页族别冲突时两者均保留，"
        "须按原始文献及社区观点复核。网站仅供非营利教育和学术浏览，未经同意不得摘取内容出版；"
        "本地研究索引不保存译文、录音或整页 HTML，具体再利用及社区权益须另行确认。\n")
    for item in records:
        group = GROUPS[item.group]
        sources = [{"citation": "中央研究院民族学研究所：口语资料目录；快照只含所需目录字段。",
                    "type": "sinica_catalogue", "url": list_url(item.group, item.page),
                    "locator": f"目录组 {item.group} / 第 {item.page} 页 / 记录 {item.identifier}",
                    "local_path": display_path(item.page_path), "content_sha256": item.page_digest},
                   {"citation": "馆方单条详情；译文及原音请在原站浏览，不在本地复制。",
                    "type": "sinica_original", "url": detail_url(item.identifier),
                    "locator": f"单条记录 {item.identifier}"}]
        if item.detail_path:
            sources.append({"citation": "馆方详情页的描述字段研究快照，不含正文和录音。",
                            "type": "sinica_detail_metadata", "url": detail_url(item.identifier),
                            "locator": f"单条记录 {item.identifier} / 描述字段",
                            "local_path": display_path(item.detail_path), "content_sha256": item.detail_digest})
        metadata = {**common, "id": f"case_tw_sinica_oral_{item.identifier}", "title": item.label,
                    "node_type": "case", "z_layer": 1, "sources": sources,
                    "relations": [{"type": "PART_OF_MACRO_TREND", "target": COLLECTION,
                                   "note": "同一馆藏目录，不表示叙事之间存在传播关系。"}]}
        evidence = {"原目录组": group, "原目录题名": item.label,
                    "详情描述字段": item.detail or "尚未采集；请查看原站单条详情"}
        body = ("\n## 馆方目录字段\n\n" + literal_block(json.dumps(evidence, ensure_ascii=False, indent=2))
                + "\n\n## 原文、录音与复核\n\n原站可能提供中文译文及原音，"
                  "请通过单条详情链接浏览；本研究索引未复制正文或录音。目录题名、族别、报告人和译者等"
                  "须对照原页及社区观点；目录组与详情字段若不一致，不自动改写。"
                  "采集地和采集日期不等于叙事发生地及发生年代。体裁、坐标与标准码待核，"
                  "未经同意不得摘取网站内容出版。\n")
        yield NodeMetadata.model_validate(metadata), body
