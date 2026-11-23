"""Import the Sirindhorn Anthropology Centre's Thai folktale dataset for review."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.build_graph import PROJECT_ROOT
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

DATASET_URL = ("https://sac.gdcatalog.go.th/dataset/a19af6d7-bea9-4d66-ad43-460d017fbca8/"
               "resource/9bef7577-c1cf-4e28-a57d-82e65ff46db7/download/folktales.json")
CATALOGUE_URL = "https://sac.gdcatalog.go.th/dataset/folktales"
COLLECTION = "corpus_thai_sac_folktales"
FIELDS = ("title", "type", "creator", "description", "subject", "spatial", "temporal",
          "language", "rights", "license", "source.uri")
URI = re.compile(r"https://www\.sac\.or\.th/databases/folktales/folktale-details\.php\?id=([1-9]\d*)")


def read_dataset(path: Path) -> dict[int, dict[str, str]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"泰国馆藏快照不是有效的 UTF-8 JSON。{error}") from error
    if not isinstance(document, dict) or document.get("status") != 200 or not isinstance(document.get("result"), list):
        raise IntakeError("泰国馆藏快照缺少成功状态或记录列表。")
    records = document["result"]
    if document.get("row") != len(records) or not records:
        raise IntakeError("泰国馆藏快照中的记录数不一致。")
    indexed = {}
    for record in records:
        if (not isinstance(record, dict) or any(not isinstance(record.get(field), str) for field in FIELDS)
                or not record["title"].strip() or any("\ufffd" in record[field] or "\0" in record[field] for field in FIELDS)):
            raise IntakeError("泰国馆藏记录缺字段、名称或有效文字。")
        match = URI.fullmatch(record["source.uri"])
        if not match:
            raise IntakeError(f"泰国馆藏原记录链接格式不符。{record['source.uri']}")
        identifier = int(match.group(1))
        if identifier in indexed:
            raise IntakeError(f"泰国馆藏记录号重复。{identifier}")
        indexed[identifier] = {field: record[field] for field in FIELDS}
    return indexed


def original_text(description: str) -> str:
    soup = BeautifulSoup(description, "html.parser")
    for element in soup.select("script, style, template, noscript"):
        element.decompose()
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def _snapshot(path: Path) -> tuple[str, str]:
    resolved = path.resolve(strict=True)
    digest = sha256(resolved.read_bytes()).hexdigest()
    try:
        name = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        name = str(resolved)
    return name, digest


def thai_cards(dataset: Path, catalogue: Path):
    records = read_dataset(dataset)
    snapshot, digest = _snapshot(dataset)
    catalogue_path, catalogue_digest = _snapshot(catalogue)
    catalogue_text = BeautifulSoup(catalogue.read_bytes(), "html.parser").get_text(" ", strip=True)
    if "Creative Commons Attribution Non-Commercial" not in catalogue_text or "ข้อมูลนิทาน" not in catalogue_text:
        raise IntakeError("泰国馆藏目录快照缺少数据集名称或非商业署名许可说明。")
    citation = ("Sirindhorn Anthropology Centre, ข้อมูลนิทาน ตำนาน เรื่องเล่าพื้นบ้าน, "
                "公开数据目录（标注 Creative Commons Attribution Non-Commercial；版本待核）。")

    def dataset_source(locator: str) -> dict:
        return {"citation": citation, "type": "thai_sac_dataset", "url": DATASET_URL, "locator": locator,
                "local_path": snapshot, "content_sha256": digest}

    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}
    corpus = {**common, "id": COLLECTION, "title": "泰国诗琳通人类学中心 · 民间叙事资料集",
              "node_type": "myth_corpus", "z_layer": 2,
              "spatial": {"precision": "culture_region", "location_name": "泰国（资料集范围，非单篇采录地点）",
                          "culture_region": "Southeast Asia · Thailand"},
              "sources": [dataset_source(f"JSON / result / {len(records)} 条"),
                          {"citation": "Sirindhorn Anthropology Centre, 数据目录的许可与来源说明。",
                           "type": "dataset_catalogue", "url": CATALOGUE_URL, "locator": "ข้อมูลเพิ่มเติม / 许可字段",
                           "local_path": catalogue_path, "content_sha256": catalogue_digest}]}
    yield NodeMetadata.model_validate(corpus), (
        "\n## 资料集与范围\n\n本批读取泰国诗琳通人类学中心公开数据目录中的泰语故事记录。"
        "馆藏资料来自研究报告、书籍及文章；原字段 creator 的具体角色需回查，不自动解释为讲述人。"
        "数据目录标注 Creative Commons Attribution Non-Commercial，具体许可版本及个别记录权限待核；"
        "原记录页受其 robots.txt 限制，本项目未自动抓取。各条目保留可供人工回查的原链接及数据快照。"
        "资料库地点字段的性质未经确定，不能直接当作采录点或故事发生地。\n")

    for identifier, row in sorted(records.items()):
        text = original_text(row["description"])
        spatial = row["spatial"].strip() or "未登记"
        metadata = {**common, "id": f"case_thai_sac_{identifier}",
                    "title": f"泰国民间叙事 · {row['title'].strip()}",
                    "aliases": [row["title"].strip(), f"SAC {identifier}"],
                    "node_type": "case", "z_layer": 1,
                    "spatial": {"precision": "culture_region", "location_name": f"馆藏原地点字段（性质待核）：{spatial}",
                                "culture_region": "Southeast Asia · Thailand"},
                    "relations": [{"type": "PART_OF_MACRO_TREND", "target": COLLECTION,
                                   "note": "出自同一馆藏数据集；不表示共同采录地点或传播关系。"}],
                    "sources": [dataset_source(f"JSON / result / 原记录 id={identifier}"),
                                {"citation": "诗琳通人类学中心原记录页（未自动下载，请人工回查）。",
                                 "type": "thai_sac_record_link", "url": row["source.uri"],
                                 "locator": f"folktale id={identifier}"}]}
        fields = [f"- 泰语原题：{row['title'].strip()}", f"- 馆藏原类别 type：{row['type'] or '未登记'}",
                  f"- 馆藏原字段 creator：{row['creator'] or '未登记'}", f"- 馆藏原地点 spatial：{spatial}",
                  f"- 馆藏原语言 language：{row['language'] or '未登记'}",
                  f"- 馆藏原许可字段 license：{row['license'] or '未登记'}"]
        excerpt = literal_block(text) if text else "数据快照的 description 字段为空，未取得该条正文。"
        body = ("\n## 馆藏原字段\n\n" + "\n".join(fields) + "\n\n## 泰语原文\n\n" + excerpt
                + "\n\n## 来源与复核\n\n原文来自诗琳通人类学中心的公开数据快照。目录声明署名、非商业用途；"
                  "具体版本与单条权利仍需核对。原记录网页未自动抓取，可循出处链接人工查阅。"
                  "creator 的含义、地点字段的性质、体裁和标准码均需人工复核；未自动填入坐标或类型码。\n")
        yield NodeMetadata.model_validate(metadata), body
