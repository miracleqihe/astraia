"""Build text-free, sentence-level links to Pangloss's synchronized annotations.

Only identifiers, timing and language/format availability are retained. The
recorded utterances, translations, media, and full XML are not stored.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlencode, urlsplit
from xml.etree import ElementTree as ET

from pipeline.intake_sources import IntakeError
from pipeline.pangloss_na import DETAIL_BASE, json_object, load_snapshots
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

API = "https://pangloss.cnrs.fr/api/api.php"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
OAI = re.compile(r"cocoon-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
ANNOTATION_DOI = re.compile(r"https://doi\.org/10\.24397/pangloss-\d{7}")
DTD = re.compile(r'<!DOCTYPE\s+TEXT\s+SYSTEM\s+["\']https://cocoon\.huma-num\.fr/schemas/Archive\.dtd["\']\s*>', re.I)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def viewer_url(primary: str, secondary: str | None = None, position: int | None = None) -> str:
    if not OAI.fullmatch(primary) or (secondary is not None and not OAI.fullmatch(secondary)):
        raise IntakeError("Pangloss 资源标识符无效。")
    query = {"oai_primary": primary, "corpus": "Yongning Na"}
    if secondary is not None:
        query["oai_secondary"] = secondary
    if position is not None and (secondary is None or type(position) is not int or position < 1):
        raise IntakeError("Pangloss 段落定位无效。")
    return DETAIL_BASE + "?" + urlencode(query) + (f"#S{position}" if position is not None else "")


def primary_oai(url: str) -> str:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, strict_parsing=True)
    if (parsed.scheme != "https" or parsed.netloc != "pangloss.cnrs.fr" or parsed.path != "/corpus/show"
            or query.get("corpus") != ["Yongning Na"] or len(query.get("oai_primary", [])) != 1
            or not OAI.fullmatch(query["oai_primary"][0])):
        raise IntakeError("Pangloss 原站录音链接无效。")
    return query["oai_primary"][0]


def timing_status(start: str | None, end: str | None) -> str:
    if start is None or end is None:
        return "missing"
    try:
        a, b = Decimal(start), Decimal(end)
        return "valid" if a.is_finite() and b.is_finite() and 0 <= a <= b else "invalid"
    except (InvalidOperation, ValueError):
        return "invalid"


def capture_selection(vault: Path, corpus: Path, chosen: Path, details: Path) -> dict:
    catalogue, selected, _ = load_snapshots(details, corpus, chosen)
    ids = [number for group in selected["groups"] for number in group["ids"]]
    cards = vault / "00_drafts/asia_cn_pangloss_na"
    rows = []
    with vault_writer(vault):
        for number in ids:
            path = cards / f"case_cn_yongning_na_{number}.md"
            if not path.is_file() or path.is_symlink():
                raise IntakeError(f"待审录音草稿缺失或为符号链接：{number}")
            raw = path.read_bytes()
            metadata, _ = parse_card(raw.decode("utf-8-sig").replace("\r\n", "\n"))
            source = next((item for item in metadata.sources if item.type == "pangloss_na_detail"), None)
            if (metadata.id != path.stem or metadata.audit.reviewed_by_human or metadata.audit.is_sample
                    or not source or not source.url or str(source.url) != catalogue[number]["url"]
                    or source.content_sha256 != digest(details / "records" / number / "page.html")):
                raise IntakeError(f"录音草稿不是预期的待审版本：{number}")
            rows.append({"id": number, "node_id": metadata.id, "primary_oai": primary_oai(catalogue[number]["url"]),
                         "detail_url": catalogue[number]["url"], "detail_sha256": source.content_sha256,
                         "card_sha256": sha256(raw).hexdigest(), "catalogue_transcription_icon": catalogue[number]["transcription_icon"]})
    return {"version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "corpus_sha256": digest(corpus), "chosen_sha256": digest(chosen),
            "details_manifest_sha256": digest(details / "manifest.json"), "records": rows,
            "scope": "只记录原站资源、分句编号、时间和文字类型；不保存音视频或转写正文"}


def validate_selection(selection: dict, corpus: Path, chosen: Path, details: Path) -> list[dict]:
    catalogue, selected, _ = load_snapshots(details, corpus, chosen)
    ids = [number for group in selected["groups"] for number in group["ids"]]
    rows = selection.get("records")
    if (selection.get("version") != 1 or selection.get("corpus_sha256") != digest(corpus)
            or selection.get("chosen_sha256") != digest(chosen)
            or selection.get("details_manifest_sha256") != digest(details / "manifest.json")
            or not isinstance(rows, list) or len(rows) != len(ids)):
        raise IntakeError("Pangloss 分句选取清单与原批次不符。")
    for number, row in zip(ids, rows, strict=True):
        if (not isinstance(row, dict) or row.get("id") != number or row.get("node_id") != f"case_cn_yongning_na_{number}"
                or row.get("detail_url") != catalogue[number]["url"] or row.get("primary_oai") != primary_oai(catalogue[number]["url"])
                or row.get("detail_sha256") != digest(details / "records" / number / "page.html")
                or row.get("catalogue_transcription_icon") != catalogue[number]["transcription_icon"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("card_sha256", "")))):
            raise IntakeError(f"Pangloss 分句选取项无效：{number}")
    return rows


def parse_primary(raw: bytes, expected_oai: str) -> list[dict]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError("Pangloss 资源接口不是有效 UTF-8 JSON。") from error
    items = data.get("object") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("success") is not True or not isinstance(items, list) or not items or len(items) > 20:
        raise IntakeError("Pangloss 资源接口返回无效或过多资源。")
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or not OAI.fullmatch(str(item.get("oai", ""))) or item["oai"] in seen:
            raise IntakeError("Pangloss 资源标识无效或重复。")
        seen.add(item["oai"])
        try:
            links = json.loads(item.get("related_resources") or "{}")
        except (TypeError, json.JSONDecodeError) as error:
            raise IntakeError("Pangloss 关联资源字段无效。") from error
        if not isinstance(links, dict):
            raise IntakeError("Pangloss 关联资源不是对象。")
        primary, secondary = [], []
        for key, output in (("primary", primary), ("secondary", secondary)):
            values = links.get(key, [])
            if not isinstance(values, list) or len(values) > 50:
                raise IntakeError("Pangloss 关联资源列表无效。")
            for value in values:
                if not isinstance(value, str) or not value.startswith("oai:crdo.vjf.cnrs.fr:"):
                    raise IntakeError("Pangloss 关联资源的原始编号无效。")
                oai = value.removeprefix("oai:crdo.vjf.cnrs.fr:")
                if not OAI.fullmatch(oai) or oai in output:
                    raise IntakeError("Pangloss 关联资源编号无效或重复。")
                output.append(oai)
        licence = item.get("licence")
        if licence is not None and (not isinstance(licence, str) or len(licence) > 1000):
            raise IntakeError("Pangloss 主资源许可字段无效。")
        result.append({"oai": item["oai"], "format": str(item.get("format") or ""),
                       "primary": primary, "secondary": secondary, "primary_license": licence})
    origin = next((row for row in result if row["oai"] == expected_oai), None)
    if not origin or set(seen) != {expected_oai, *origin["primary"]}:
        raise IntakeError("Pangloss 资源组与所选录音及其关联不符。")
    return result


def parse_xml(xml: str) -> dict:
    if not isinstance(xml, str) or len(xml.encode("utf-8")) > 8 * 1024 * 1024 or "\ufffd" in xml or "\0" in xml:
        raise IntakeError("Pangloss 转写 XML 太大或编码不可靠。")
    if re.search(r"<!ENTITY", xml, re.I) or re.search(r"<!DOCTYPE[^>]*\[", xml, re.I):
        raise IntakeError("Pangloss 转写 XML 含不安全的实体定义。")
    clean = DTD.sub("", xml)
    if re.search(r"<!DOCTYPE", clean, re.I):
        raise IntakeError("Pangloss 转写 XML 使用了未经核对的 DTD。")
    try:
        root = ET.fromstring(clean)
    except ET.ParseError as error:
        raise IntakeError(f"Pangloss 转写 XML 解析失败：{error}") from error
    if root.tag != "TEXT":
        raise IntakeError("Pangloss 转写根元素不是 TEXT。")
    notes = Counter((item.get(XML_LANG) or "未标注") for item in root.findall("NOTE"))
    sentences = root.findall("S")
    if len(sentences) > 10000:
        raise IntakeError("Pangloss 转写段落数量异常。")
    segments = []
    for position, sentence in enumerate(sentences, 1):
        audio = sentence.find("AUDIO")
        start = audio.get("start") if audio is not None else None
        end = audio.get("end") if audio is not None else None
        time_status = timing_status(start, end)
        forms = sorted({item.get("kindOf") or "未标注" for item in sentence.findall("FORM") if "".join(item.itertext()).strip()})
        languages = sorted({item.get(XML_LANG) or "未标注" for item in sentence.findall("TRANSL") if "".join(item.itertext()).strip()})
        segments.append({"position": position, "xml_id": sentence.get("id"), "start": start, "end": end,
                         "time_status": time_status, "forms": forms, "translation_languages": languages})
    return {"xml_id": root.get("id"), "language": root.get(XML_LANG),
            "root_forms": sorted({item.get("kindOf") or "未标注" for item in root.findall("FORM") if "".join(item.itertext()).strip()}),
            "root_translation_languages": sorted({item.get(XML_LANG) or "未标注" for item in root.findall("TRANSL") if "".join(item.itertext()).strip()}),
            "global_note_languages": dict(notes), "segments": segments}


def parse_annotations(raw: bytes, expected: list[str], resource_oai: str) -> list[dict]:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError("Pangloss 转写接口不是有效 UTF-8 JSON。") from error
    if not isinstance(document, list) or len(document) != len(expected):
        raise IntakeError("Pangloss 转写接口结果数与关联资源不符。")
    by_id = {}
    for item in document:
        if (not isinstance(item, dict) or item.get("oai") not in expected or item["oai"] in by_id
                or not isinstance(item.get("type"), str)):
            raise IntakeError("Pangloss 转写接口资源标识无效或重复。")
        doi = item.get("doi")
        if doi is not None and (not isinstance(doi, str) or not ANNOTATION_DOI.fullmatch(doi)):
            raise IntakeError("Pangloss 转写 DOI 格式无效。")
        entry = {"oai": item["oai"], "type": item["type"], "doi": doi,
                 "viewer_url": viewer_url(resource_oai, item["oai"]), "license": None}
        if item["type"] == "xml":
            text = item.get("content")
            entry["content_sha256"] = sha256(text.encode("utf-8")).hexdigest() if isinstance(text, str) else None
            entry.update(parse_xml(text))
        by_id[item["oai"]] = entry
    return [by_id[value] for value in expected]


def read_index(path: Path, row: dict) -> dict:
    index = json_object(path)
    expected_keys = {"version", "id", "primary_oai", "detail_sha256", "catalogue_transcription_icon", "primary_url",
                     "primary_response_sha256", "primary_response_bytes", "responses", "resources", "observed_at", "scope"}
    primary_url = API + "?" + urlencode({"action": "getresourcesByOAI", "oai": row["primary_oai"]})
    if (set(index) != expected_keys or index.get("version") != 1 or index.get("id") != row["id"]
            or index.get("primary_oai") != row["primary_oai"] or index.get("detail_sha256") != row["detail_sha256"]
            or index.get("catalogue_transcription_icon") != row["catalogue_transcription_icon"]
            or index.get("primary_url") != primary_url or type(index.get("primary_response_bytes")) is not int
            or index["primary_response_bytes"] < 1 or not isinstance(index.get("scope"), str)
            or not isinstance(index.get("resources"), list) or not isinstance(index.get("responses"), list)
            or not re.fullmatch(r"[0-9a-f]{64}", str(index.get("primary_response_sha256", "")))):
        raise IntakeError(f"Pangloss 分句索引无效：{row['id']}")
    try:
        if datetime.fromisoformat(index["observed_at"]).utcoffset() is None:
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise IntakeError(f"Pangloss 分句索引时间无效：{row['id']}") from error
    seen, response_resources = set(), set()
    for resource in index["resources"]:
        if (not isinstance(resource, dict) or set(resource) != {"oai", "format", "primary", "secondary", "primary_license", "annotations"}
                or not OAI.fullmatch(str(resource.get("oai", ""))) or resource["oai"] in seen
                or not isinstance(resource.get("format"), str) or len(resource["format"]) > 100
                or not isinstance(resource.get("primary"), list) or not isinstance(resource.get("secondary"), list)
                or any(not isinstance(value, str) or not OAI.fullmatch(value) for value in resource["primary"] + resource["secondary"])
                or len(set(resource["primary"])) != len(resource["primary"]) or len(set(resource["secondary"])) != len(resource["secondary"])
                or (resource.get("primary_license") is not None and (not isinstance(resource["primary_license"], str) or len(resource["primary_license"]) > 1000))
                or not isinstance(resource.get("annotations"), list)
                or [item.get("oai") if isinstance(item, dict) else None for item in resource["annotations"]] != resource["secondary"]):
            raise IntakeError(f"Pangloss 分句资源索引无效：{row['id']}")
        seen.add(resource["oai"])
        for annotation in resource["annotations"]:
            common = {"oai", "type", "doi", "viewer_url", "license"}
            xml_keys = {"content_sha256", "xml_id", "language", "root_forms", "root_translation_languages", "global_note_languages", "segments"}
            allowed = common | (xml_keys if annotation.get("type") == "xml" else set()) if isinstance(annotation, dict) else set()
            if (not isinstance(annotation, dict) or set(annotation) != allowed or not OAI.fullmatch(str(annotation.get("oai", "")))
                    or not isinstance(annotation.get("type"), str) or len(annotation["type"]) > 100 or annotation.get("license") is not None
                    or (annotation.get("doi") is not None and not ANNOTATION_DOI.fullmatch(str(annotation["doi"])))
                    or annotation.get("viewer_url") != viewer_url(resource["oai"], annotation["oai"])
                    or (annotation.get("type") == "xml" and not isinstance(annotation.get("segments"), list))):
                raise IntakeError(f"Pangloss 转写索引标识无效：{row['id']}")
            if annotation["type"] == "xml":
                if (not re.fullmatch(r"[0-9a-f]{64}", str(annotation.get("content_sha256", "")))
                        or any(annotation.get(key) is not None and (not isinstance(annotation[key], str) or len(annotation[key]) > 300)
                               for key in ("xml_id", "language"))
                        or any(not isinstance(annotation.get(key), list) or any(not isinstance(x, str) or len(x) > 100 for x in annotation[key])
                               for key in ("root_forms", "root_translation_languages"))
                        or not isinstance(annotation.get("global_note_languages"), dict)
                        or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in annotation["global_note_languages"].items())
                        or len(annotation["segments"]) > 10000):
                    raise IntakeError(f"Pangloss XML 结构索引无效：{row['id']}")
            for position, segment in enumerate(annotation.get("segments", []), 1):
                if (not isinstance(segment, dict) or set(segment) != {"position", "xml_id", "start", "end", "time_status", "forms", "translation_languages"}
                        or type(segment.get("position")) is not int or segment.get("position") != position
                        or any(segment.get(key) is not None and (not isinstance(segment[key], str) or len(segment[key]) > 300) for key in ("xml_id", "start", "end"))
                        or segment.get("time_status") != timing_status(segment.get("start"), segment.get("end"))
                        or any(not isinstance(segment.get(key), list) or any(not isinstance(x, str) or len(x) > 100 for x in segment[key])
                               for key in ("forms", "translation_languages"))):
                    raise IntakeError(f"Pangloss 转写分句序号不连续：{row['id']}")
    origin = next((resource for resource in index["resources"] if resource["oai"] == row["primary_oai"]), None)
    if not origin or seen != {origin["oai"], *origin["primary"]}:
        raise IntakeError(f"Pangloss 分句索引资源组不符：{row['id']}")
    for response in index["responses"]:
        if (not isinstance(response, dict) or set(response) != {"resource_oai", "url", "sha256", "bytes"}
                or response.get("resource_oai") not in seen or response["resource_oai"] in response_resources
                or not re.fullmatch(r"[0-9a-f]{64}", str(response.get("sha256", "")))
                or type(response.get("bytes")) is not int or response["bytes"] < 1):
            raise IntakeError(f"Pangloss 分句接口响应索引无效：{row['id']}")
        resource = next(item for item in index["resources"] if item["oai"] == response["resource_oai"])
        expected = API + "?" + urlencode({"action": "getAnnotations", "oais": json.dumps(resource["secondary"], ensure_ascii=False, separators=(",", ":"))})
        if not resource["secondary"] or response["url"] != expected:
            raise IntakeError(f"Pangloss 分句接口请求与资源不符：{row['id']}")
        response_resources.add(response["resource_oai"])
    if response_resources != {resource["oai"] for resource in index["resources"] if resource["secondary"]}:
        raise IntakeError(f"Pangloss 分句接口响应不完整：{row['id']}")
    return index
