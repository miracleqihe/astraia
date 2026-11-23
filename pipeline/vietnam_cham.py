"""Stage individually sourced Vietnamese-language Cham folktale edition entries."""
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.build_graph import PROJECT_ROOT
from pipeline.fetch_vietnam_cham import INTRO, RIGHTS, story_url
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

COLLECTION = "corpus_vietnam_cham_folktales"


@dataclass(frozen=True)
class Story:
    number: int
    catalogue_title: str
    detail_title: str
    paragraph_count: int
    text_characters: int
    heading_note_markers: list[dict] | None
    snapshot: Path
    digest: str
    raw_sha256: str


def _read_json(path: Path) -> dict:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"越南选集研究快照无法读取：{path}") from error
    if not isinstance(result, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(result.get("raw_sha256", ""))):
        raise IntakeError(f"越南选集研究快照缺少原响应哈希：{path}")
    return result


def load_snapshot(folder: Path) -> tuple[dict, dict, list[Story]]:
    folder = folder.resolve(strict=True)
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"越南选集批次清单无法读取：{error}") from error
    if (not isinstance(manifest, dict) or manifest.get("version") != 1 or manifest.get("catalogue_url") != INTRO
            or manifest.get("catalogue_path") != "catalogue.json" or not isinstance(manifest.get("stories"), list)
            or len(manifest["stories"]) != 58):
        raise IntakeError("越南选集批次清单结构不符。")
    if manifest.get("seed_path") is not None:
        if manifest.get("seed_path") != "seed.json":
            raise IntakeError("越南选集修订基线路径无效。")
        seed_path = folder / "seed.json"
        seed_raw = seed_path.read_bytes()
        if sha256(seed_raw).hexdigest() != manifest.get("seed_sha256"):
            raise IntakeError("越南选集修订基线哈希不符。")
        seed = json.loads(seed_raw.decode("utf-8"))
        if (not isinstance(seed, dict) or seed.get("version") != 1 or not isinstance(seed.get("base_manifest_path"), str)
                or not isinstance(seed.get("reused"), list) or not isinstance(seed.get("refetch"), list)):
            raise IntakeError("越南选集修订基线结构无效。")
        original = Path(seed["base_manifest_path"])
        if not original.is_absolute():
            original = PROJECT_ROOT / original
        if original.resolve() == (folder / "manifest.json").resolve() or sha256(original.read_bytes()).hexdigest() != seed.get("base_manifest_sha256"):
            raise IntakeError("越南选集原批次清单不存在或哈希不符。")
        prior = json.loads(original.read_text(encoding="utf-8"))
        prior_hashes = {entry["number"]: entry["sha256"] for entry in prior.get("stories", [])}
        current_hashes = {entry.get("number"): entry.get("sha256") for entry in manifest["stories"] if isinstance(entry, dict)}
        reused = {}
        for entry in seed["reused"]:
            number = entry.get("number") if isinstance(entry, dict) else None
            if type(number) is not int or number in reused or entry.get("sha256") != prior_hashes.get(number):
                raise IntakeError("越南选集复用来源不符。")
            reused[number] = entry["sha256"]
            if current_hashes.get(number) != entry["sha256"]:
                raise IntakeError("越南选集复用后的快照哈希不符。")
        refetch = seed["refetch"]
        if (any(type(number) is not int for number in refetch) or len(set(refetch)) != len(refetch)
                or set(reused) & set(refetch) or set(reused) | set(refetch) != set(range(1, 59))
                or seed.get("catalogue_sha256") != manifest.get("catalogue_sha256")):
            raise IntakeError("越南选集修订范围不符。")
    catalogue_path = folder / "catalogue.json"
    if sha256(catalogue_path.read_bytes()).hexdigest() != manifest.get("catalogue_sha256"):
        raise IntakeError("越南选集目录快照哈希不符。")
    catalogue = _read_json(catalogue_path)
    entries, fields = catalogue.get("entries"), catalogue.get("catalogue_fields")
    if (catalogue.get("source_url") != INTRO or not isinstance(entries, list) or len(entries) != 58
            or [row.get("number") if isinstance(row, dict) else None for row in entries] != list(range(1, 59))
            or any(not isinstance(row.get("title"), str) or not row["title"].strip() or "\ufffd" in row["title"] for row in entries)
            or not isinstance(fields, dict) or fields.get("Access Condition") != RIGHTS or fields.get("Languages") != "Vietnamese"
            or not all(isinstance(fields.get(name), str) and fields[name].strip() for name in ("Authors", "Date Created", "Publisher"))):
        raise IntakeError("越南选集目录、语言或使用条件不符。")
    if catalogue.get("preface_signatory") != "TRƯƠNG HIẾN MAI" or catalogue.get("preface_date_as_written") != "Phan Rang, thu năm 1997":
        raise IntakeError("越南选集前言署名或日期线索不符。")
    stories = []
    for number, (entry, index) in enumerate(zip(entries, manifest["stories"], strict=True), 1):
        name = f"story-{number:03d}.json"
        if not isinstance(index, dict) or index.get("number") != number or index.get("path") != name:
            raise IntakeError(f"越南选集第 {number} 篇的索引路径不符。")
        path = folder / name
        digest = sha256(path.read_bytes()).hexdigest()
        if digest != index.get("sha256"):
            raise IntakeError(f"越南选集第 {number} 篇的字段快照哈希不符。")
        value = _read_json(path)
        expected_next = story_url(number + 1) if number < 58 else None
        title = value.get("detail_title")
        notes = value.get("heading_note_markers")
        if (value.get("number") != number or value.get("source_url") != story_url(number)
                or value.get("catalogue_title") != entry["title"] or not isinstance(title, str) or not title.strip()
                or "\ufffd" in title or type(value.get("title_matches")) is not bool
                or value["title_matches"] != (title == entry["title"]) or value.get("next_url") != expected_next
                or type(value.get("paragraph_count")) is not int or value["paragraph_count"] < 0
                or type(value.get("text_characters")) is not int or value["text_characters"] < 0
                or (notes is not None and (not isinstance(notes, list) or any(
                    not isinstance(note, dict) or not re.fullmatch(r"Footnote [1-9]\d*", str(note.get("label", "")))
                    or not isinstance(note.get("display"), str) for note in notes)))):
            raise IntakeError(f"越南选集第 {number} 篇的标题、链接或正文状态不符。")
        stories.append(Story(number, entry["title"], title, value["paragraph_count"], value["text_characters"],
                             notes, path, digest, value["raw_sha256"]))
    return manifest, catalogue, stories


def cham_cards(folder: Path):
    manifest, catalogue, stories = load_snapshot(folder)
    catalogue_path = folder / "catalogue.json"
    manifest_path = folder / "manifest.json"
    fields = catalogue["catalogue_fields"]
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False},
              "spatial": {"precision": "culture_region", "location_name": "越南（选集范围；不代表单篇采录或叙事地点）",
                          "culture_region": "Southeast Asia · Vietnam"}}
    corpus = {**common, "id": COLLECTION, "title": "越南占族故事选集 · Truyện cổ dân gian Chăm",
              "node_type": "myth_corpus", "z_layer": 2,
              "sources": [{"citation": "Digitizing Việt Nam，占族故事选集目录的本地研究索引。",
                           "type": "vietnam_cham_manifest", "url": INTRO,
                           "locator": "目录 / 58 篇 / 前言", "local_path": display_path(manifest_path),
                           "content_sha256": sha256(manifest_path.read_bytes()).hexdigest()}]}
    root_body = ("\n## 选集范围与来源\n\n这是越南文选集的逐篇检索索引；前言称 32 篇由馆藏及家庭材料整理翻译，"
                 "另 26 篇由 Tuấn Dũng 从书刊选录。前言没有在此索引中逐篇标出来源组，"
                 "不能推定每篇的讲述者、具体采集地或原始占语文本。"
                 "站点书目 Date Created 为 " + fields["Date Created"] + "，前言落款为 Phan Rang、1997 年秋；"
                 "两者分别保留，不能将任何一个直接当作故事发生年代。"
                 "馆方允许教育与研究用途，禁止商业使用；具体复制、再分发与社区权益仍须核对。"
                 "本地索引不保存选集正文或完整网页，单篇正文可在馆方链接浏览。\n")
    yield NodeMetadata.model_validate(corpus), root_body
    for story in stories:
        metadata = {**common, "id": f"case_vietnam_cham_{story.number:03d}",
                    "title": f"越南占族故事选集 · {story.catalogue_title}",
                    "aliases": [story.catalogue_title, f"Cham edition {story.number}"],
                    "node_type": "case", "z_layer": 1,
                    "relations": [{"type": "PART_OF_MACRO_TREND", "target": COLLECTION,
                                   "note": "同一越南文选集，不表示共同采录地点或传播关系。"}],
                    "sources": [{"citation": "Digitizing Việt Nam，占族故事选集的目录与访问条件。",
                                 "type": "vietnam_cham_catalogue", "url": INTRO,
                                 "locator": f"目录 / 第 {story.number} 篇", "local_path": display_path(catalogue_path),
                                 "content_sha256": manifest["catalogue_sha256"]},
                                {"citation": "Digitizing Việt Nam，越南文单篇详情；全文请在原站浏览。",
                                 "type": "vietnam_cham_story", "url": story_url(story.number),
                                 "locator": f"单篇 / 第 {story.number} 篇", "local_path": display_path(story.snapshot),
                                 "content_sha256": story.digest}]}
        evidence = {"目录序号": story.number, "目录越南文题名": story.catalogue_title,
                    "详情页题名": story.detail_title, "详情页可见段落数": story.paragraph_count,
                    "标题脚注标记": story.heading_note_markers if story.heading_note_markers is not None else "未单独提取",
                    "书目 Date Created": fields["Date Created"], "馆方贡献者字段": fields["Authors"],
                    "出版者字段": fields["Publisher"], "语言字段": fields["Languages"]}
        body = ("\n## 目录与书目原字段\n\n" + literal_block(json.dumps(evidence, ensure_ascii=False, indent=2))
                + "\n\n## 原文、来源与复核\n\n这是选集中的越南文版本，单篇正文未复制；"
                  "请通过单篇详情链接查看。前言所说的 32 篇馆藏／家庭材料与 26 篇书刊选录尚未逐篇对应，"
                  "讲述者、原始语言和采录时间地点须另查，不能以选集地域代替本条地点。"
                  "站点允许教育与研究用途、禁止商业使用；具体转载与社区权益待核。"
                  "体裁、坐标与标准码未自动推定。\n")
        yield NodeMetadata.model_validate(metadata), body
