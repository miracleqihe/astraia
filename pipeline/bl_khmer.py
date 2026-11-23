"""Snapshot and stage British Library Khmer folding-book catalogue records.

Each card represents one physical catalogue unit, which may contain several
works. Catalogue metadata is CC BY 4.0; manuscript images and text are not
downloaded or assumed to share that licence.
"""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError, _challenge_page
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

HOST = "searcharchives.bl.uk"
ROOT_ID = "corpus_kh_bl_or16131"
ROOT_URL = f"https://{HOST}/catalog/032-003779224"
CC_BY = "https://creativecommons.org/licenses/by/4.0/"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def soup_for(raw: bytes) -> BeautifulSoup:
    try:
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    except UnicodeError as error:
        raise IntakeError("大英图书馆目录编码无效。") from error
    if (soup.contains_replacement_characters or _challenge_page(soup) or not soup.title
            or "British Library Archives and Manuscripts Catalogue" not in soup.title.get_text(" ", strip=True)
            or not soup.find("a", href=CC_BY)):
        raise IntakeError("大英图书馆目录或文字许可说明不符。")
    return soup


def fields_for(soup: BeautifulSoup) -> dict[str, str]:
    result = {}
    for dt in soup.select("dt"):
        key = dt.get_text(" ", strip=True).removesuffix(":")
        dd = dt.find_next_sibling("dd")
        if key and dd:
            if key in result:
                raise IntakeError(f"馆方目录字段重复：{key}")
            result[key] = " ".join(dd.stripped_strings)
    return result


def parse_root(raw: bytes) -> tuple[dict, list[dict]]:
    soup = soup_for(raw)
    fields = fields_for(soup)
    if (fields.get("Record Id") != "032-003779224" or fields.get("Reference (shelfmark)") != "Or 16131/1-11"
            or fields.get("Extent") != "11 volumes" or fields.get("Languages") != "Central Khmer"
            or "11 folding books" not in fields.get("Scope & Content", "")):
        raise IntakeError("高棉折本馆藏组的档号、数量或语言不符。")
    label = next((dt for dt in soup.select("dt") if dt.get_text(" ", strip=True) == "Contains:"), None)
    dd = label.find_next_sibling("dd") if label else None
    children = []
    for anchor in dd.find_all("a", href=True) if dd else []:
        shelf = anchor.find("b")
        shelfmark = shelf.get_text(" ", strip=True) if shelf else ""
        match = re.fullmatch(r"Or 16131/(\d{1,2})", shelfmark)
        href = urljoin(ROOT_URL, anchor["href"])
        parsed = urlsplit(href)
        if (shelfmark == "Or 16131/1-11" and parsed.scheme == "https" and parsed.netloc == HOST
                and parsed.path == "/" and parse_qs(parsed.query).get("f[parent_reference_ssi][]") == [shelfmark]):
            continue  # The catalogue's "view full list" link is not a twelfth child.
        if not match or parsed.scheme != "https" or parsed.netloc != HOST or not re.fullmatch(r"/catalog/040-\d{9}", parsed.path) or parsed.query or parsed.fragment:
            raise IntakeError("高棉折本馆方目录子件链接无效。")
        children.append({"volume": int(match.group(1)), "record_id": parsed.path.rsplit("/", 1)[-1], "url": href})
    if sorted(item["volume"] for item in children) != list(range(1, 12)) or len({x["record_id"] for x in children}) != 11:
        raise IntakeError("高棉折本馆方子件不完整或重复。")
    return fields, children


def parse_volume(raw: bytes, child: dict) -> dict:
    soup = soup_for(raw)
    fields = fields_for(soup)
    number = child["volume"]
    if (fields.get("Record Id") != child["record_id"] or fields.get("Hierarchy Root Ancestor Record Id") != "032-003779224"
            or fields.get("Reference (shelfmark)") != f"Or 16131/{number}" or fields.get("Languages") != "Central Khmer"
            or not fields.get("Title") or not fields.get("Scope & Content") or not fields.get("Extent")):
        raise IntakeError(f"高棉折本子件档号、语言或内容字段不符：{number}")
    element = soup.select_one("dd.blacklight-url_tsi")
    links = []
    for anchor in element.find_all("a", href=True) if element else []:
        target = urljoin(child["url"], anchor["href"])
        parsed = urlsplit(target)
        if parsed.scheme == "https" and parsed.netloc:
            links.append(target)
    return {"馆方档号": fields["Reference (shelfmark)"], "馆方记录号": fields["Record Id"],
            "馆方题名": fields["Title"], "馆方内容说明": fields["Scope & Content"],
            "馆方册页数": fields["Extent"], "馆方语言": fields.get("Languages"), "馆方文字": fields.get("Scripts"),
            "馆方日期起始原字段": fields.get("Start Date"), "馆方日期结束原字段": fields.get("End Date"),
            "馆方日期范围原字段": fields.get("Date Range"), "馆方数字化字段": fields.get("Digitised Content"),
            "数字化字段链接": links, "馆方物理特征": fields.get("Physical Characteristics"),
            "来源与取得": fields.get("Source of Acquisition"), "馆方记录级别": fields.get("Record Type (Level)")}


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"馆方快照索引无法读取：{path}") from error
    if not isinstance(value, dict):
        raise IntakeError(f"馆方快照索引不是对象：{path}")
    return value


def load_snapshot(folder: Path) -> tuple[dict, dict, list[tuple[dict, Path, str, dict]]]:
    manifest = read_json(folder / "manifest.json")
    selection_path = folder / "selection.json"
    selection = read_json(selection_path)
    root_path = folder / "root.html"
    root_fields, children = parse_root(root_path.read_bytes())
    if (selection.get("version") != 1 or selection.get("source_url") != ROOT_URL
            or selection.get("root_sha256") != digest(root_path) or selection.get("children") != children
            or manifest.get("version") != 1 or manifest.get("selection_sha256") != digest(selection_path)
            or not isinstance(manifest.get("records"), list) or len(manifest["records"]) != len(children)):
        raise IntakeError("高棉折本来源清单或馆藏组快照不符。")
    result = []
    for child, entry in zip(children, manifest["records"], strict=True):
        number = child["volume"]
        name = f"record-{number:02d}.html"
        meta_name = f"record-{number:02d}.json"
        if not isinstance(entry, dict) or entry.get("volume") != number or entry.get("path") != name or entry.get("meta") != meta_name:
            raise IntakeError(f"高棉折本子件清单不符：{number}")
        path = folder / name
        metadata = read_json(folder / meta_name)
        checksum = digest(path)
        if (checksum != entry.get("sha256") or digest(folder / meta_name) != entry.get("meta_sha256")
                or metadata.get("url") != child["url"] or metadata.get("sha256") != checksum
                or not isinstance(metadata.get("observed_at"), str)):
            raise IntakeError(f"高棉折本子件快照哈希不符：{number}")
        result.append((child, path, checksum, parse_volume(path.read_bytes(), child)))
    return selection, root_fields, result


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError("馆藏页面请求间隔至少为 2 秒。")
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "manifest.json").exists():
        load_snapshot(folder)
        return read_json(folder / "manifest.json")
    robots, status = robot_rules(HOST, delay)
    root_path, selection_path = folder / "root.html", folder / "selection.json"
    if root_path.exists() or selection_path.exists():
        if not root_path.is_file() or not selection_path.is_file():
            raise IntakeError("馆藏组快照或选取清单不完整，须核对后续跑。")
        selection = read_json(selection_path)
        _, children = parse_root(root_path.read_bytes())
        if selection.get("source_url") != ROOT_URL or selection.get("root_sha256") != digest(root_path) or selection.get("children") != children:
            raise IntakeError("已保存的馆藏组与选取清单不符。")
    else:
        raw, observed = request_html(ROOT_URL, HOST, robots, delay)
        _, children = parse_root(raw)
        exclusive_write(root_path, raw)
        selection = {"version": 1, "source_url": ROOT_URL, "root_sha256": sha256(raw).hexdigest(),
                     "observed_at": observed, "children": children}
        exclusive_write(selection_path, json_bytes(selection))
    entries = []
    for child in children:
        number = child["volume"]
        path, meta_path = folder / f"record-{number:02d}.html", folder / f"record-{number:02d}.json"
        if path.exists() or meta_path.exists():
            if not path.is_file() or not meta_path.is_file():
                raise IntakeError(f"子件快照或指纹不完整：{number}")
            metadata = read_json(meta_path)
            if metadata.get("url") != child["url"] or metadata.get("sha256") != digest(path):
                raise IntakeError(f"子件快照或指纹不符：{number}")
            parse_volume(path.read_bytes(), child)
        else:
            raw, observed = request_html(child["url"], HOST, robots, delay)
            parse_volume(raw, child)
            metadata = {"url": child["url"], "sha256": sha256(raw).hexdigest(), "observed_at": observed}
            exclusive_write(path, raw)
            exclusive_write(meta_path, json_bytes(metadata))
        entries.append({"volume": number, "path": path.name, "sha256": digest(path),
                        "meta": meta_path.name, "meta_sha256": digest(meta_path)})
        print(f"已核验高棉折本 {len(entries)}/{len(children)} · Or 16131/{number}", flush=True)
    manifest = {"version": 1, "selection_sha256": digest(selection_path), "robots_status": status,
                "catalogue_text_license": CC_BY, "records": entries,
                "scope": "馆藏目录页面；不保存手稿图像或转写正文"}
    exclusive_write(folder / "manifest.json", json_bytes(manifest))
    load_snapshot(folder)
    return manifest


def bl_cards(folder: Path):
    selection, root_fields, records = load_snapshot(folder)
    root_path, root_hash = folder / "root.html", selection["root_sha256"]
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "spatial": {"precision": "culture_region", "location_name": "柬埔寨（馆方所列可能来源；具体地点待核）",
                          "culture_region": "Southeast Asia · Cambodia"},
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}

    def source(path: Path, checksum: str, url: str, locator: str) -> dict:
        return {"citation": "British Library Archives and Manuscripts Catalogue，Or 16131；目录文字 CC BY 4.0，手稿权利另核。",
                "type": "bl_khmer_catalogue", "url": url, "locator": locator,
                "local_path": display_path(path), "content_sha256": checksum}

    root_source = source(root_path, root_hash, ROOT_URL, "Or 16131/1-11 / 馆藏组")
    root = {**common, "id": ROOT_ID, "title": "柬埔寨高棉文折本 · Or 16131 馆藏组", "node_type": "myth_corpus",
            "z_layer": 2, "sources": [root_source]}
    body = ("\n## 馆方目录范围\n\n馆方登记 11 册折本，包含故事、传说及其他文字材料；"
            "册数不是故事数。馆方对来源地点保留疑问，馆藏目录所列日期不能直接作为故事年代。"
            "目录文字按 CC BY 4.0 署名，手稿影像与内容的访问及再利用另核；本地未保存手稿影像或转写正文。\n")
    yield NodeMetadata.model_validate(root), body
    for child, path, checksum, fields in records:
        number = child["volume"]
        model = {**common, "id": f"corpus_kh_bl_or16131_{number:02d}",
                 "title": f"柬埔寨高棉文折本 · Or 16131/{number}", "aliases": [fields["馆方题名"]],
                 "node_type": "myth_corpus", "z_layer": 2,
                 "relations": [{"type": "PART_OF_MACRO_TREND", "target": ROOT_ID,
                                "note": "同一馆方馆藏组的折本；每册可能包含多件作品。"}],
                 "sources": [source(path, checksum, child["url"], fields["馆方档号"]), root_source]}
        body = ("\n## 馆方目录原字段\n\n" + literal_block(json.dumps(fields, ensure_ascii=False, indent=2))
                + "\n\n## 复核说明\n\n这是一册手稿目录记录，不自动代表单篇故事。"
                  "馆方来源地、年代及作品组成可能带有疑问，须逐册查证；目录日期不自动作为叙事发生年代。"
                  "数字化字段为空不证明影像不存在；原件、影像、访问条件和内容权利请向馆方回查。"
                  "未下载手稿影像或正文；坐标、体裁和标准码暂不推定。\n")
        yield NodeMetadata.model_validate(model), body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        result = fetch(args.output, args.delay)
    except (ValueError, OSError, HTTPError, URLError) as error:
        print(f"高棉折本目录未完成；已有快照保留，可在同一目录续跑：{error}", file=sys.stderr)
        return 1
    print(f"馆藏组及 {len(result['records'])} 册折本目录已核验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
