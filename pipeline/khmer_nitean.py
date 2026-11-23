"""Index Khmer folktale chapters and source locators without copying text.

The site is a modern transcription of an earlier collection. Its edition,
individual attribution, text rights, and relationship to other editions remain
review questions; no codes or locations are inferred from the catalogue.
"""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
import unicodedata

from bs4 import BeautifulSoup

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError, _challenge_page
from pipeline.khmer_wikisource import URL as WIKISOURCE_URL, load_snapshot as load_wikisource
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

HOST = "seuksa.com"
CATALOGUE_URL = f"https://{HOST}/nitean/folktales/"
ROOT_ID = "corpus_kh_nitean_folktales"
PROJECT = "https://khmertext.sourceforge.net/"
KHMER_DIGITS = "០១២៣៤៥៦៧៨៩"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def canonical_url(href: str) -> str:
    parsed = urlsplit(urljoin(CATALOGUE_URL, href))
    if parsed.scheme != "https" or parsed.netloc != HOST or parsed.query or parsed.fragment:
        raise IntakeError("高棉故事链接的域名或参数不符。")
    try:
        path = unquote(parsed.path, encoding="utf-8", errors="strict")
    except UnicodeError as error:
        raise IntakeError("高棉故事链接编码无效。") from error
    prefix = "/nitean/folktales/"
    if not path.startswith(prefix) or not path.endswith("/"):
        raise IntakeError("高棉故事链接路径不符。")
    slug = path[len(prefix):-1]
    if (not slug or len(slug) > 250 or any(c not in "-_" and unicodedata.category(c)[0] not in "LMN" for c in slug)):
        raise IntakeError("高棉故事链接包含无效字符。")
    return urlunsplit(("https", HOST, quote(path, safe="/-._~"), "", ""))


def parse_catalogue(raw: bytes) -> dict:
    try:
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    except UnicodeError as error:
        raise IntakeError("高棉故事目录编码无效。") from error
    heading = soup.find("h1")
    toc = soup.select_one('section[aria-labelledby="toc"]')
    text = soup.get_text(" ", strip=True)
    if (soup.contains_replacement_characters or _challenge_page(soup) or not heading
            or heading.get_text(" ", strip=True) != "ប្រជុំរឿងព្រេងនិទានខ្មែរ"
            or "214 chapters" not in text or "8 parts" not in text or not toc
            or not any("khmertext.sourceforge" in a.get("href", "") for a in soup.find_all("a", href=True))):
        raise IntakeError("高棉故事目录题名、规模或转录来源说明不符。")
    groups = toc.select("div.space-y-4 > details")
    if len(groups) != 9 or groups[0].find("summary").get_text(" ", strip=True) != "Introduction 1":
        raise IntakeError("高棉故事目录卷次或序言结构不符。")
    intro = groups[0].select("ol > li > a[href]")
    if len(intro) != 1:
        raise IntakeError("高棉故事目录序言链接不唯一。")
    introduction = canonical_url(intro[0]["href"])
    rows, seen, counts = [], set(), []
    for volume, group in enumerate(groups[1:], 1):
        summary = group.find("summary")
        labels = summary.find_all("span", recursive=False) if summary else []
        expected = f"ប្រជុំរឿងព្រេងខ្មែរភាគ {KHMER_DIGITS[volume]}"
        if len(labels) != 2 or labels[0].get_text(" ", strip=True) != expected:
            raise IntakeError(f"高棉故事目录第 {volume} 卷名称不符。")
        count_text = labels[1].get_text(" ", strip=True)
        links = group.select("ol > li > a[href]")
        if not count_text.isdigit() or int(count_text) != len(links) or not links:
            raise IntakeError(f"高棉故事目录第 {volume} 卷数量不符。")
        counts.append(len(links))
        for position, anchor in enumerate(links, 1):
            spans = anchor.find_all("span", recursive=False)
            if len(spans) != 2 or spans[0].get_text(" ", strip=True) != str(position):
                raise IntakeError(f"高棉故事目录第 {volume} 卷序号不连续。")
            title = spans[1].get_text(" ", strip=True)
            url = canonical_url(anchor["href"])
            if not title or "\ufffd" in title or url in seen:
                raise IntakeError("高棉故事目录题名为空或链接重复。")
            seen.add(url)
            rows.append({"volume": volume, "position": position, "ordinal": len(rows) + 1,
                         "title": title, "url": url, "volume_title": expected})
    if len(rows) != 214:
        raise IntakeError("高棉故事目录与展示的 214 章不符。")
    return {"introduction_url": introduction, "volume_counts": counts, "records": rows}


def parse_chapter(raw: bytes, row: dict) -> dict:
    try:
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    except UnicodeError as error:
        raise IntakeError(f"高棉故事页面编码无效：{row['ordinal']}") from error
    article = soup.select_one("article")
    header = article.select_one("header h1") if article else None
    reader = article.select_one("div.reader") if article else None
    breadcrumb = article.select("nav[aria-label='Breadcrumb'] li") if article else []
    if (soup.contains_replacement_characters or _challenge_page(soup) or not header or not reader
            or not header.get_text(" ", strip=True) or len(breadcrumb) < 3):
        raise IntakeError(f"高棉故事页面结构不符：{row['ordinal']}")
    title = header.get_text(" ", strip=True)
    volume_title = breadcrumb[-1].get_text(" ", strip=True)
    paragraphs = reader.find_all("p", recursive=False)
    locators = []
    for paragraph in paragraphs:
        text = paragraph.get_text(" ", strip=True)
        clean = text.replace("\u200b", "")
        if len(text) <= 250 and "ទំព័រ" in clean and ("ភាគ" in clean or "ប្រជុំ" in clean):
            locators.append(text)
    note_ids = []
    for note in reader.select("section.footnotes li[id]"):
        identifier = note.get("id", "")
        if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier) and identifier not in note_ids:
            note_ids.append(identifier)
    displayed = None
    for item in article.select("header p"):
        match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", item.get_text(" ", strip=True))
        if match:
            displayed = {"position": int(match.group(1)), "total": int(match.group(2))}
            break
    return {"detail_title": title, "volume_title": volume_title, "title_matches_catalogue": title == row["title"],
            "volume_matches_catalogue": volume_title == row["volume_title"], "visible_paragraphs": len(paragraphs),
            "printed_locators": locators, "footnote_count": len(reader.select("section.footnotes li")),
            "footnote_anchors": note_ids, "displayed_sequence": displayed}


def read_json(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"高棉故事索引无法读取：{path}") from error
    if not isinstance(document, dict):
        raise IntakeError(f"高棉故事索引不是对象：{path}")
    return document


def validate_selection(selection: dict) -> list[dict]:
    rows, counts = selection.get("records"), selection.get("volume_counts")
    if (selection.get("version") != 1 or selection.get("source_url") != CATALOGUE_URL
            or not re.fullmatch(r"[0-9a-f]{64}", str(selection.get("raw_sha256", "")))
            or not isinstance(selection.get("observed_at"), str) or not isinstance(counts, list) or len(counts) != 8
            or any(type(count) is not int or count <= 0 for count in counts) or sum(counts) != 214
            or not isinstance(rows, list) or len(rows) != 214
            or canonical_url(selection.get("introduction_url", "")) != selection.get("introduction_url")):
        raise IntakeError("高棉故事目录研究索引无效。")
    seen, ordinal = set(), 0
    for volume, count in enumerate(counts, 1):
        expected = f"ប្រជុំរឿងព្រេងខ្មែរភាគ {KHMER_DIGITS[volume]}"
        for position in range(1, count + 1):
            row = rows[ordinal]
            ordinal += 1
            if (not isinstance(row, dict) or set(row) != {"volume", "position", "ordinal", "title", "url", "volume_title"}
                    or (row.get("volume"), row.get("position"), row.get("ordinal"), row.get("volume_title")) != (volume, position, ordinal, expected)
                    or not isinstance(row.get("title"), str) or not row["title"].strip() or "\ufffd" in row["title"]
                    or canonical_url(row.get("url", "")) != row.get("url") or row["url"] in seen):
                raise IntakeError(f"高棉故事目录条目无效：{volume}/{position}")
            seen.add(row["url"])
    return rows


def validate_chapter(document: dict, row: dict) -> dict:
    allowed = {"version", "ordinal", "url", "raw_sha256", "raw_bytes", "observed_at", "detail_title", "volume_title",
               "title_matches_catalogue", "volume_matches_catalogue", "visible_paragraphs", "printed_locators",
               "footnote_count", "footnote_anchors", "displayed_sequence"}
    if (set(document) != allowed or document.get("version") != 1 or document.get("ordinal") != row["ordinal"]
            or document.get("url") != row["url"] or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("raw_sha256", "")))
            or type(document.get("raw_bytes")) is not int or document["raw_bytes"] < 1
            or not isinstance(document.get("observed_at"), str)
            or not isinstance(document.get("detail_title"), str) or not document["detail_title"]
            or not isinstance(document.get("volume_title"), str) or not document["volume_title"]
            or type(document.get("title_matches_catalogue")) is not bool
            or document["title_matches_catalogue"] != (document["detail_title"] == row["title"])
            or type(document.get("volume_matches_catalogue")) is not bool
            or document["volume_matches_catalogue"] != (document["volume_title"] == row["volume_title"])
            or type(document.get("visible_paragraphs")) is not int or document["visible_paragraphs"] < 0
            or not isinstance(document.get("printed_locators"), list)
            or any(not isinstance(x, str) or len(x) > 250 for x in document["printed_locators"])
            or type(document.get("footnote_count")) is not int or document["footnote_count"] < 0
            or not isinstance(document.get("footnote_anchors"), list)
            or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", x) for x in document["footnote_anchors"])
            or len(set(document["footnote_anchors"])) != len(document["footnote_anchors"])
            or len(document["footnote_anchors"]) > document["footnote_count"]):
        raise IntakeError(f"高棉故事单篇字段索引无效：{row['ordinal']}")
    displayed = document.get("displayed_sequence")
    if displayed is not None and (not isinstance(displayed, dict) or set(displayed) != {"position", "total"}
            or any(type(displayed.get(key)) is not int or displayed[key] < 1 for key in ("position", "total"))):
        raise IntakeError(f"高棉故事页面序号无效：{row['ordinal']}")
    return document


def load_snapshot(folder: Path) -> tuple[dict, list[tuple[dict, Path, str, dict]]]:
    selection_path = folder / "selection.json"
    selection = read_json(selection_path)
    rows = validate_selection(selection)
    manifest = read_json(folder / "manifest.json")
    if (manifest.get("version") != 1 or manifest.get("selection_sha256") != digest(selection_path)
            or not isinstance(manifest.get("records"), list) or len(manifest["records"]) != len(rows)):
        raise IntakeError("高棉故事单篇索引清单不完整。")
    result = []
    for row, entry in zip(rows, manifest["records"], strict=True):
        name = f"chapter-{row['ordinal']:03d}.json"
        if not isinstance(entry, dict) or entry.get("ordinal") != row["ordinal"] or entry.get("path") != name:
            raise IntakeError(f"高棉故事单篇索引路径不符：{row['ordinal']}")
        path = folder / name
        checksum = digest(path)
        if checksum != entry.get("sha256"):
            raise IntakeError(f"高棉故事单篇索引哈希不符：{row['ordinal']}")
        result.append((row, path, checksum, validate_chapter(read_json(path), row)))
    return selection, result


def request_with_transient_retry(url: str, robots, delay: float):
    # Retry connection failures only. HTTP errors, including rate limits, stop the
    # run; every attempt still passes through the same robots and delay checks.
    for attempt in range(3):
        try:
            return request_html(url, HOST, robots, delay)
        except HTTPError:
            raise
        except URLError:
            if attempt == 2:
                raise
            time.sleep(delay * (attempt + 1))


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError("高棉故事页面请求间隔至少为 2 秒。")
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
        raw, observed = request_with_transient_retry(CATALOGUE_URL, robots, delay)
        catalogue = parse_catalogue(raw)
        selection = {"version": 1, "source_url": CATALOGUE_URL, "raw_sha256": sha256(raw).hexdigest(),
                     "observed_at": observed, **catalogue,
                     "scope": "仅目录题名、卷次与链接；网页原响应未保存，响应指纹无法离线重算"}
        rows = validate_selection(selection)
        exclusive_write(selection_path, json_bytes(selection))
        del raw
    entries = []
    for row in rows:
        path = folder / f"chapter-{row['ordinal']:03d}.json"
        if path.exists():
            validate_chapter(read_json(path), row)
        else:
            raw, observed = request_with_transient_retry(row["url"], robots, delay)
            fields = parse_chapter(raw, row)
            document = {"version": 1, "ordinal": row["ordinal"], "url": row["url"],
                        "raw_sha256": sha256(raw).hexdigest(), "raw_bytes": len(raw), "observed_at": observed, **fields}
            validate_chapter(document, row)
            exclusive_write(path, json_bytes(document))
            del raw
        entries.append({"ordinal": row["ordinal"], "path": path.name, "sha256": digest(path)})
        print(f"已核验高棉故事 {len(entries)}/{len(rows)} · 第 {row['volume']} 卷第 {row['position']} 篇", flush=True)
    manifest = {"version": 1, "selection_sha256": digest(selection_path), "robots_status": status,
                "records": entries, "scope": "仅目录与单篇结构和出处字段；不保存网页原响应或故事正文"}
    exclusive_write(folder / "manifest.json", json_bytes(manifest))
    load_snapshot(folder)
    return manifest


def chapter_id(row: dict) -> str:
    return f"case_kh_nitean_v{row['volume']:02d}_{row['position']:03d}"


def chapter_evidence(row: dict, document: dict) -> dict:
    return {"目录卷次": row["volume"], "目录卷内序号": row["position"], "目录总序号": row["ordinal"],
            "目录高棉文题名": row["title"], "详情高棉文题名": document["detail_title"],
            "目录与详情题名一致": document["title_matches_catalogue"], "目录卷名": row["volume_title"],
            "详情卷名": document["volume_title"], "目录与详情卷名一致": document["volume_matches_catalogue"],
            "页面段落数（含注记）": document["visible_paragraphs"], "页面所列卷册页码原文": document["printed_locators"],
            "页面脚注数": document["footnote_count"], "可定位脚注": document["footnote_anchors"],
            "页面显示次序": document["displayed_sequence"], "网页原响应 SHA256": document["raw_sha256"],
            "网页观察时间": document["observed_at"], "原始响应": "未保存；指纹不能仅凭字段索引离线重算"}


def nitean_cards(folder: Path, comparison: Path | None = None):
    selection, chapters = load_snapshot(folder)
    selection_path, selection_hash = folder / "selection.json", digest(folder / "selection.json")
    wiki = load_wikisource(comparison) if comparison else None
    common = {"genre": "unclassified", "credibility_tier": "C", "is_fictional_quarantine": False,
              "spatial": {"precision": "culture_region", "location_name": "柬埔寨（选集范围；采录和叙事地点待核）",
                          "culture_region": "Southeast Asia · Cambodia"},
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}

    def source(path: Path, checksum: str, url: str, locator: str, kind: str) -> dict:
        return {"citation": "Nitean 高棉文故事转录网站，目录及单篇字段研究索引；原网页和正文未保存，原版及权利待核。",
                "type": kind, "url": url, "locator": locator,
                "local_path": display_path(path), "content_sha256": checksum}

    root_source = source(selection_path, selection_hash, CATALOGUE_URL, "选集目录 / 8 卷 214 章", "nitean_catalogue")
    wiki_source = ({"citation": "Wikisource 高棉文选集目录，卷册数量对照；不是单篇身份或版本相同的证明。",
                    "type": "wikisource_catalogue", "url": WIKISOURCE_URL,
                    "locator": f"目录修订版本 {wiki['revision_id']} / 九卷卷册数量",
                    "local_path": display_path(comparison), "content_sha256": digest(comparison)} if wiki else None)
    comparison_sources = [wiki_source] if wiki_source else []
    root = {**common, "id": ROOT_ID, "title": "柬埔寨高棉文故事选集 · Nitean 转录目录", "node_type": "myth_corpus",
            "z_layer": 2, "sources": [root_source, *comparison_sources]}
    body = ("\n## 来源与版本范围\n\nNitean 目录列出八卷 214 篇及一篇独立序言，网站称文字来自 KhmerText。"
            "这是一份数字转录目录，不证明每篇是同一次口述或未经编辑的采录。"
            "来源项目的许可标签不能自动覆盖所有文本；原版、编者和再利用条件须逐篇查证。"
            "本地不保存原网页或故事正文，原响应指纹无法仅凭字段索引离线重算。\n")
    if wiki:
        body += (f"\n另一份 [Wikisource 目录]({WIKISOURCE_URL})的修订版本 {wiki['revision_id']} "
                 f"列出 {len(wiki['volume_counts'])} 卷、{wiki['total_stories']} 篇。"
                 "版本与章节边界尚待核，不能据题名自动合并。\n")
    yield NodeMetadata.model_validate(root), body
    for volume, count in enumerate(selection["volume_counts"], 1):
        model = {**common, "id": f"corpus_kh_nitean_v{volume:02d}",
                 "title": f"高棉文故事选集 · 第 {volume} 卷", "node_type": "myth_corpus", "z_layer": 2,
                 "relations": [{"type": "PART_OF_MACRO_TREND", "target": ROOT_ID, "note": "Nitean 目录中的卷次；与其他版本的对应须核对。"}],
                 "sources": [source(selection_path, selection_hash, CATALOGUE_URL, f"目录第 {volume} 卷 / {count} 篇", "nitean_catalogue"), *comparison_sources]}
        volume_body = f"\n## 目录范围\n\n转录网站第 {volume} 卷列出 {count} 篇；版本与原版页码须逐条核对。\n"
        if wiki:
            volume_body += f"\nWikisource 目录同序卷列出 {wiki['volume_counts'][volume - 1]} 篇；卷名相近不证明逐篇对应。\n"
        yield NodeMetadata.model_validate(model), volume_body
    for row, path, checksum, document in chapters:
        model = {**common, "id": chapter_id(row), "title": row["title"], "aliases": [document["detail_title"]],
                 "node_type": "case", "z_layer": 1,
                 "relations": [{"type": "PART_OF_MACRO_TREND", "target": f"corpus_kh_nitean_v{row['volume']:02d}",
                                "note": "所属转录目录卷次，不表示故事的采录点或传播路线。"}],
                 "sources": [source(path, checksum, row["url"], f"第 {row['volume']} 卷 / 第 {row['position']} 篇", "nitean_chapter"),
                             source(selection_path, selection_hash, CATALOGUE_URL, f"目录第 {row['volume']} 卷 / 第 {row['position']} 篇", "nitean_catalogue"),
                             *comparison_sources]}
        data = chapter_evidence(row, document)
        body = ("\n## 目录与单篇字段\n\n" + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + f"\n\n[在转录站查看高棉文原文]({row['url']})\n"
                + "\n## 复核说明\n\n网站为数字转录版本；原印本、采录者、讲述者、语言背景、文本权利及社区要求须回查。"
                  "页面卷册页码和脚注是转录站所列的线索，不等于已核验原版。"
                  "本地未保存原网页或故事正文，原响应指纹无法仅凭字段索引离线重算。"
                  "目录所涉地区不自动成为故事采录地或发生地；坐标、体裁、年代和标准码留空。\n")
        if wiki:
            body += (f"\n两个目录同序第 {row['volume']} 卷分别列出 {selection['volume_counts'][row['volume'] - 1]} "
                     f"和 {wiki['volume_counts'][row['volume'] - 1]} 篇；这项卷次对照不表示单篇已匹配。\n")
        for anchor in document["footnote_anchors"]:
            body += f"\n- [查看转录站脚注]({row['url']}#{anchor})"
        yield NodeMetadata.model_validate(model), body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        result = fetch(args.output, args.delay)
    except (ValueError, OSError, HTTPError, URLError) as error:
        print(f"高棉故事索引未完成；已有字段保留，可在同一目录续跑：{error}", file=sys.stderr)
        return 1
    print(f"已核验 {len(result['records'])} 篇高棉故事目录和单篇字段。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
