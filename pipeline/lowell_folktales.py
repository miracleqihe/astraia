"""Index Lowell's Southeast Asian community folktale project at item level.

Only catalogue metadata is retained. Full pages, meeting transcripts, books,
images and audio are not saved; HTTP response hashes cannot be recomputed from
the metadata index alone.
"""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError, _challenge_page
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

HOST = "umlseada.omeka.net"
COLLECTION_URL = f"https://{HOST}/collections/show/19"
ROOT_ID = "corpus_us_lowell_sea_folktales"
COLLECTION_TITLE = "Southeast Asian Folktales Book Project Collection, 2018-2019"
ITEMS = re.compile(r"/items/show/([1-9]\d*)")
ALLOWED_FIELDS = ("title", "date", "creator", "subject", "publisher", "format", "language", "type", "identifier", "coverage")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def soup_for(raw: bytes) -> BeautifulSoup:
    try:
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    except UnicodeError as error:
        raise IntakeError("洛厄尔馆藏页面编码无效。") from error
    if (soup.contains_replacement_characters or _challenge_page(soup) or not soup.title
            or "Southeast Asian Digital Archive" not in soup.title.get_text(" ", strip=True)):
        raise IntakeError("洛厄尔馆藏页面标题或编码不符。")
    return soup


def element(soup: BeautifulSoup, key: str) -> list[str]:
    node = soup.select_one(f"#dublin-core-{key}")
    return [" ".join(value.stripped_strings) for value in node.select(".element-text") if value.get_text(" ", strip=True)] if node else []


def parse_collection(raw: bytes) -> list[dict]:
    soup = soup_for(raw)
    description = " ".join(element(soup, "description"))
    if (element(soup, "title") != [COLLECTION_TITLE]
            or not all(value in description for value in ("Burmese", "Cambodian", "Laotian", "Vietnamese", "Lowell"))):
        raise IntakeError("洛厄尔馆藏组标题或社群范围不符。")
    records, seen = [], set()
    for anchor in soup.select("#collection-items .item h2 a.permalink[href]"):
        url = urljoin(COLLECTION_URL, anchor["href"])
        parts = urlsplit(url)
        match = ITEMS.fullmatch(parts.path)
        title = " ".join(anchor.stripped_strings)
        if (parts.scheme != "https" or parts.netloc != HOST or parts.query or parts.fragment
                or not match or not title or int(match.group(1)) in seen):
            raise IntakeError("洛厄尔馆藏目录包含无效或重复的条目链接。")
        identifier = int(match.group(1))
        seen.add(identifier)
        records.append({"id": identifier, "title": title, "url": url})
    if not records or len(records) > 200:
        raise IntakeError("洛厄尔馆藏目录数量为空或异常。")
    all_items = soup.select_one("#collection-items a[href*='/items/browse?collection=19']")
    if not all_items:
        raise IntakeError("洛厄尔馆藏目录缺少总数链接。")
    match = re.search(r"View all\s+(\d+)\s+items", all_items.get_text(" ", strip=True), re.I)
    if not match or int(match.group(1)) != len(records):
        raise IntakeError("洛厄尔馆藏组展示的条目数量不完整。")
    return records


def parse_item(raw: bytes, row: dict) -> dict:
    soup = soup_for(raw)
    fields = {key: element(soup, key) for key in ALLOWED_FIELDS}
    rights = " ".join(element(soup, "rights"))
    collections = [urljoin(row["url"], a["href"]) for a in soup.select("#collection a[href]")]
    if (fields["title"] != [row["title"]] or COLLECTION_URL not in collections
            or "private, educational, and research use" not in rights
            or "secure any needed permissions" not in rights
            or not fields["format"] or not fields["type"]):
        raise IntakeError(f"洛厄尔单件 {row['id']} 的标题、馆藏归属或使用说明不符。")
    attachments = soup.select("#itemfiles a[href], #item-files a[href], .item-file a[href], a[href^='/files/']")
    return {"fields": fields, "rights_status": "private_educational_research_permissions_needed",
            "rights_statement_sha256": sha256(rights.encode("utf-8")).hexdigest(),
            "visible_file_link_count": len(attachments)}


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"洛厄尔馆藏研究索引无法读取：{path}") from error
    if not isinstance(value, dict):
        raise IntakeError(f"洛厄尔馆藏研究索引不是对象：{path}")
    return value


def validate_selection(selection: dict) -> list[dict]:
    rows = selection.get("records")
    if (selection.get("version") != 1 or selection.get("source_url") != COLLECTION_URL
            or not re.fullmatch(r"[0-9a-f]{64}", str(selection.get("raw_sha256", "")))
            or not isinstance(selection.get("observed_at"), str)
            or not isinstance(rows, list) or not rows or len(rows) > 200):
        raise IntakeError("洛厄尔馆藏组选取索引无效。")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"id", "title", "url"} or type(row.get("id")) is not int
                or row["id"] < 1 or row["id"] in seen or not isinstance(row.get("title"), str) or not row["title"].strip()
                or row.get("url") != f"https://{HOST}/items/show/{row['id']}"):
            raise IntakeError("洛厄尔馆藏组选取条目无效或重复。")
        seen.add(row["id"])
    return rows


def validate_item(document: dict, row: dict) -> dict:
    fields = document.get("fields")
    allowed = {"version", "id", "url", "raw_sha256", "raw_bytes", "observed_at", "fields", "rights_status",
               "rights_statement_sha256", "visible_file_link_count"}
    if (set(document) != allowed or document.get("version") != 1 or document.get("id") != row["id"] or document.get("url") != row["url"]
            or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("raw_sha256", "")))
            or not isinstance(document.get("observed_at"), str) or type(document.get("raw_bytes")) is not int or document["raw_bytes"] < 1
            or not isinstance(fields, dict) or set(fields) != set(ALLOWED_FIELDS)
            or any(not isinstance(value, list) or any(not isinstance(x, str) or "\ufffd" in x for x in value) for value in fields.values())
            or fields["title"] != [row["title"]] or not fields["format"] or not fields["type"]
            or document.get("rights_status") != "private_educational_research_permissions_needed"
            or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("rights_statement_sha256", "")))
            or type(document.get("visible_file_link_count")) is not int or document["visible_file_link_count"] < 0):
        raise IntakeError(f"洛厄尔单件研究索引无效：{row['id']}")
    return document


def load_snapshot(folder: Path) -> tuple[dict, list[tuple[dict, Path, str, dict]]]:
    selection_path = folder / "selection.json"
    selection = read_json(selection_path)
    rows = validate_selection(selection)
    manifest = read_json(folder / "manifest.json")
    if (manifest.get("version") != 1 or manifest.get("selection_sha256") != digest(selection_path)
            or not isinstance(manifest.get("records"), list) or len(manifest["records"]) != len(rows)):
        raise IntakeError("洛厄尔馆藏研究索引清单不完整。")
    result = []
    for row, entry in zip(rows, manifest["records"], strict=True):
        name = f"record-{row['id']}.json"
        if not isinstance(entry, dict) or entry.get("id") != row["id"] or entry.get("path") != name:
            raise IntakeError(f"洛厄尔馆藏研究索引路径不符：{row['id']}")
        path = folder / name
        checksum = digest(path)
        if checksum != entry.get("sha256"):
            raise IntakeError(f"洛厄尔馆藏研究索引哈希不符：{row['id']}")
        result.append((row, path, checksum, validate_item(read_json(path), row)))
    return selection, result


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError("馆藏页面请求间隔至少为 2 秒。")
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "manifest.json").exists():
        load_snapshot(folder)
        return read_json(folder / "manifest.json")
    robots, status = robot_rules(HOST, delay)
    selection_path = folder / "selection.json"
    if selection_path.exists():
        selection = read_json(selection_path)
        rows = validate_selection(selection)
    else:
        raw, observed = request_html(COLLECTION_URL, HOST, robots, delay)
        rows = parse_collection(raw)
        selection = {"version": 1, "source_url": COLLECTION_URL, "raw_sha256": sha256(raw).hexdigest(),
                     "observed_at": observed, "records": rows,
                     "scope": "馆藏组题名及条目链接；网页原响应未保存，响应哈希无法离线重算"}
        exclusive_write(selection_path, json_bytes(selection))
    entries = []
    for row in rows:
        identifier = row["id"]
        path = folder / f"record-{identifier}.json"
        if path.exists():
            validate_item(read_json(path), row)
        else:
            raw, observed = request_html(row["url"], HOST, robots, delay)
            metadata = parse_item(raw, row)
            document = {"version": 1, "id": identifier, "url": row["url"],
                        "raw_sha256": sha256(raw).hexdigest(), "raw_bytes": len(raw),
                        "observed_at": observed, **metadata}
            validate_item(document, row)
            exclusive_write(path, json_bytes(document))
            del raw
        entries.append({"id": identifier, "path": path.name, "sha256": digest(path)})
        print(f"已核验洛厄尔项目资料 {len(entries)}/{len(rows)} · {identifier}", flush=True)
    manifest = {"version": 1, "selection_sha256": digest(selection_path), "robots_status": status,
                "records": entries, "scope": "仅目录字段；不保存网页原响应、叙事正文、音视频或影像"}
    exclusive_write(folder / "manifest.json", json_bytes(manifest))
    load_snapshot(folder)
    return manifest


def is_poster(row: dict) -> bool:
    return "book launch" in row["title"].casefold() and "poster" in row["title"].casefold()


def evidence(document: dict) -> dict:
    fields = document["fields"]
    return {"馆方题名": fields["title"], "馆方日期原字段": fields["date"], "馆方署名": fields["creator"],
            "馆方主题": fields["subject"], "馆方出版者": fields["publisher"], "馆方格式": fields["format"],
            "馆方语言": fields["language"], "馆方类型": fields["type"], "馆方标识": fields["identifier"],
            "馆方覆盖范围": fields["coverage"], "可见文件链接数": document["visible_file_link_count"],
            "馆方使用范围": "私人、教育与研究用途；所需权利许可须由使用者取得",
            "网页原响应 SHA256": document["raw_sha256"], "网页观察时间": document["observed_at"],
            "原始响应": "未保存；指纹不能仅凭字段索引离线重算"}


def lowell_cards(folder: Path):
    selection, records = load_snapshot(folder)
    selection_path, selection_hash = folder / "selection.json", digest(folder / "selection.json")
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "spatial": {"precision": "culture_region", "location_name": "美国马萨诸塞州洛厄尔（项目与馆藏范围；故事地点待核）",
                          "culture_region": "Southeast Asian diaspora · United States"},
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}

    def source(path: Path, checksum: str, url: str, locator: str) -> dict:
        return {"citation": "University of Massachusetts Lowell，Southeast Asian Digital Archive，目录字段研究索引；原网页未保存。",
                "type": "lowell_sea_catalogue", "url": url, "locator": locator,
                "local_path": display_path(path), "content_sha256": checksum}

    root_source = source(selection_path, selection_hash, COLLECTION_URL, "UML 24 / 项目馆藏组")
    root = {**common, "id": ROOT_ID, "title": "洛厄尔东南亚社群故事项目 · 2018–2019", "node_type": "myth_corpus",
            "z_layer": 2, "sources": [root_source]}
    body = (f"\n## 馆方目录范围\n\n馆方项目由洛厄尔地区大学与社群组织合作，涉及缅甸、柬埔寨、老挝和越南社群。"
            f"馆藏组列出 {len(records)} 项项目资料，包括书籍、会议记录、故事文档和活动海报；"
            "资料件数不是故事数。海报保留在筛查清单，不作为叙事文献卡导入。"
            "项目覆盖范围与每篇故事的采录、流传或发生地点须分开核查。"
            "本地仅保存目录字段，不保存网页原响应、故事正文、音视频或图像；"
            "馆方允许私人、教育和研究用途，其他使用所需许可须另核。\n")
    yield NodeMetadata.model_validate(root), body
    for row, path, checksum, document in records:
        if is_poster(row):
            continue
        model = {**common, "id": f"corpus_us_lowell_sea_{row['id']}",
                 "title": f"洛厄尔东南亚社群项目 · {row['title']}", "aliases": [row["title"]],
                 "node_type": "myth_corpus", "z_layer": 2,
                 "relations": [{"type": "PART_OF_MACRO_TREND", "target": ROOT_ID,
                                "note": "同一社区故事项目的馆藏资料，不表示各故事同源或发生于洛厄尔。"}],
                 "sources": [source(path, checksum, row["url"], f"馆方记录 {row['id']} / 描述字段"), root_source]}
        body = ("\n## 馆方目录字段\n\n" + literal_block(json.dumps(evidence(document), ensure_ascii=False, indent=2))
                + "\n\n## 复核说明\n\n这是一件项目文档、会议记录或书籍的馆方目录项，可能包含多篇故事；"
                  "目录语言不自动等于故事最早使用的语言。馆方覆盖范围为洛厄尔，不能自动当作故事发生地或原始采录地。"
                  "项目日期不是叙事年代；未保存原网页响应、文档正文或音视频，响应指纹不能离线重算。"
                  "单件文件是否可访问、讲述人、版本、社区要求及再利用许可须回查；坐标和标准码暂留空。\n")
        yield NodeMetadata.model_validate(model), body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        result = fetch(args.output, args.delay)
    except (ValueError, OSError, HTTPError, URLError) as error:
        print(f"洛厄尔馆藏索引未完成；已有字段保留，可在同一目录续跑：{error}", file=sys.stderr)
        return 1
    print(f"洛厄尔馆藏组 {len(result['records'])} 项资料已核验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
