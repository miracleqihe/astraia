"""Preserve HMML catalogue stubs and stage separately labelled legacy leads.

The current dataset supplies catalogue metadata, not a transcription.  Older
search-indexed fields are a researcher's provisional index, not a page capture.
"""
import argparse
from datetime import date
from hashlib import file_digest, sha256
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

DATASET_PAGE = "https://www.vhmml.org/dataPortal/dataset"
PURL = "https://w3id.org/vhmml/readingRoom/view/"
LEGACY = "https://www.hmmlcloud.org/dreamsea/detail.php?msid="
REPOSITORY = "Private Collection of Go Lan Ing"
ROOT_ID = "corpus_hmml_makassar_ouw_pe_coa"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"HMML 数据无法读取：{path}：{error}") from error
    if not isinstance(value, dict):
        raise IntakeError("HMML 数据应为 JSON 对象。")
    return value


def validate_record(record: dict) -> str:
    project = record.get("hmmlProjectNumber")
    number = record.get("id")
    if (not isinstance(project, str) or not re.fullmatch(r"DS 0045 \d{5}", project)
            or type(number) is not int or number < 1 or record.get("PURL") != PURL + str(number)
            or (record.get("repository") or {}).get("name") != REPOSITORY
            or (record.get("country") or {}).get("name") != "Indonesia"
            or (record.get("city") or {}).get("name") != "Makassar (Sulawesi Selatan)"
            or type(record.get("viewableOnline")) is not bool):
        raise IntakeError(f"HMML 馆藏条目的编号、馆藏地或链接无效：{project}")
    return project


def extract_selection(source: Path, output: Path) -> dict:
    """Filter one repository from a verified archive without extracting its ZIP."""
    manifest = read_json(source / "manifest.json")
    archive_name = manifest.get("archive")
    if (manifest.get("version") != 1 or manifest.get("dataset_page") != DATASET_PAGE
            or manifest.get("metadata_license") != "CC BY 4.0"
            or archive_name != "vhmml_rr_fulldata.zip"
            or not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("sha256", "")))):
        raise IntakeError("HMML 原始数据清单无效。")
    archive = source / archive_name
    if digest(archive) != manifest["sha256"]:
        raise IntakeError("HMML 原始数据压缩包哈希不符。")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise IntakeError("输出目录已存在，不覆盖先前的馆藏快照。")
    with TemporaryDirectory(prefix=".hmml-selection-", dir=output.parent) as temporary:
        stage = Path(temporary) / "selection"
        stage.mkdir()
        records_path = stage / "records.jsonl"
        selected, projects, numbers = [], set(), set()
        with ZipFile(archive) as zipped, records_path.open("wb") as destination:
            names = zipped.namelist()
            if names != ["vhmml_rr_fulldata.json"]:
                raise IntakeError("HMML 压缩包内容不符合已登记的数据格式。")
            with zipped.open(names[0]) as stream:
                for line_number, raw in enumerate(stream):
                    if b"DS 0045 " not in raw:
                        continue
                    clean = raw.strip()
                    if line_number == 0:
                        clean = clean.removeprefix(b"[")
                    clean = clean.removesuffix(b",")
                    if clean.endswith(b"}]"):
                        clean = clean[:-1]
                    record = json.loads(clean)
                    if not isinstance(record, dict) or not str(record.get("hmmlProjectNumber", "")).startswith("DS 0045 "):
                        continue
                    project = validate_record(record)
                    if project in projects or record["id"] in numbers:
                        raise IntakeError(f"HMML 馆藏编号重复：{project}")
                    projects.add(project)
                    numbers.add(record["id"])
                    destination.write(clean + b"\n")
                    selected.append({"project": project, "id": record["id"], "sha256": sha256(clean).hexdigest()})
        if not selected:
            raise IntakeError("原数据中没有找到目标馆藏。")
        result = {"version": 1, "source_dataset_page": DATASET_PAGE,
                  "source_archive": display_path(archive), "source_archive_sha256": manifest["sha256"],
                  "source_manifest": display_path(source / "manifest.json"),
                  "source_manifest_sha256": digest(source / "manifest.json"),
                  "metadata_license": "CC BY 4.0", "repository": REPOSITORY,
                  "scope": "DS 0045 馆藏元数据，原始单条 JSON；非故事或影像清单",
                  "records": "records.jsonl", "records_sha256": digest(records_path),
                  "count": len(selected), "entries": selected}
        (stage / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)
    return result


def load_selection(folder: Path) -> tuple[dict, dict[str, dict]]:
    manifest = read_json(folder / "manifest.json")
    path = folder / "records.jsonl"
    if (manifest.get("version") != 1 or manifest.get("source_dataset_page") != DATASET_PAGE
            or manifest.get("metadata_license") != "CC BY 4.0" or manifest.get("repository") != REPOSITORY
            or manifest.get("records") != "records.jsonl" or not isinstance(manifest.get("entries"), list)
            or digest(path) != manifest.get("records_sha256")):
        raise IntakeError("HMML 馆藏选取清单或数据哈希不符。")
    result, ids = {}, set()
    with path.open("rb") as stream:
        for line, index in zip(stream, manifest["entries"], strict=True):
            clean = line.rstrip(b"\r\n")
            record = json.loads(clean)
            if not isinstance(record, dict) or not isinstance(index, dict):
                raise IntakeError("HMML 馆藏行结构无效。")
            project = validate_record(record)
            if (index != {"project": project, "id": record["id"], "sha256": sha256(clean).hexdigest()}
                    or project in result or record["id"] in ids):
                raise IntakeError("HMML 馆藏行与索引不符或重复。")
            result[project] = record
            ids.add(record["id"])
    if len(result) != manifest.get("count") or not result:
        raise IntakeError("HMML 馆藏数量与清单不符。")
    return manifest, result


def load_legacy(path: Path) -> dict:
    data = read_json(path)
    entries = data.get("entries")
    if (data.get("version") != 1 or not isinstance(entries, list) or len(entries) != 12
            or not all(isinstance(data.get(key), str) and data[key].strip() for key in
                       ("method", "limitations", "attribution", "collection_title_candidate", "creator_candidate",
                        "language_candidate", "script_candidate", "context_note"))):
        raise IntakeError("HMML 旧目录候选索引结构不符。")
    projects, ids, volumes = set(), set(), set()
    for entry in entries:
        if (not isinstance(entry, dict) or type(entry.get("volume")) is not int
                or type(entry.get("legacy_id")) is not int or entry["legacy_id"] < 1
                or not re.fullmatch(r"DS 0045 \d{5}", str(entry.get("project", "")))
                or not all(isinstance(entry.get(key), str) and entry[key].strip() and "\ufffd" not in entry[key]
                           for key in ("native_title", "roman_title", "native_date", "gregorian_date"))
                or entry["project"] in projects or entry["legacy_id"] in ids or entry["volume"] in volumes):
            raise IntakeError("HMML 旧目录候选编号或字段有误。")
        projects.add(entry["project"])
        ids.add(entry["legacy_id"])
        volumes.add(entry["volume"])
    if volumes != set(range(1, 13)):
        raise IntakeError("HMML 旧目录候选卷次不完整。")
    return data


def evidence(record: dict, entry: dict, legacy: dict) -> dict:
    return {"当前馆方档号": record["hmmlProjectNumber"], "当前馆方记录号": record["id"],
            "当前编目说明": record.get("notes"), "馆方开放查看标志": record["viewableOnline"],
            "馆方访问限制原字段": record.get("accessRestriction"),
            "数字化日期原字段（非故事年代）": record.get("captureDateDisplay"),
            "旧目录题名候选（原文字）": entry["native_title"], "旧目录题名候选（罗马字）": entry["roman_title"],
            "旧目录卷次候选": entry["volume"], "旧目录署名候选": legacy["creator_candidate"],
            "旧目录语言候选": legacy["language_candidate"], "旧目录文字候选": legacy["script_candidate"],
            "旧目录原历抄写日期候选": entry["native_date"], "旧目录公历抄写日期候选": entry["gregorian_date"]}


def hmml_cards(folder: Path, legacy_path: Path):
    manifest, records = load_selection(folder)
    legacy = load_legacy(legacy_path)
    if any(item.get("objectType") != "MANUSCRIPT" or item.get("parts") != []
           or "uncataloged stub" not in str(item.get("notes", "")).lower()
           or item.get("commonName") or item.get("summary") for item in records.values()):
        raise IntakeError("馆方数据已出现新编目内容，不能继续按未编目清单导入；请重新核查。")
    selected_path = folder / "records.jsonl"
    selected_hash, legacy_hash = manifest["records_sha256"], digest(legacy_path)
    common = {"genre": "unclassified", "credibility_tier": "C", "is_fictional_quarantine": False,
              "spatial": {"precision": "culture_region", "location_name": "印度尼西亚望加锡（馆藏地，非采录或叙事地点）",
                          "culture_region": "Southeast Asia · Indonesia"},
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}

    def current_source(url: str, locator: str) -> dict:
        return {"citation": "HMML Reading Room 开放元数据导出，Private Collection of Go Lan Ing；元数据 CC BY 4.0。",
                "type": "hmml_makassar_metadata", "url": url, "locator": locator,
                "local_path": display_path(selected_path), "content_sha256": selected_hash}

    def legacy_source(entry: dict) -> dict:
        return {"citation": "DREAMSEA 旧目录搜索索引候选；旧站当次无法访问，本地索引不是原网页快照。",
                "type": "hmml_legacy_candidate", "url": LEGACY + str(entry["legacy_id"]),
                "locator": entry["project"], "local_path": display_path(legacy_path), "content_sha256": legacy_hash}

    for entry in legacy["entries"]:
        if entry["project"] not in records:
            raise IntakeError(f"旧目录候选档号在当前 HMML 数据中不存在：{entry['project']}")
    root = {**common, "id": ROOT_ID, "title": "望加锡手稿 · Ouw Pe Coa（旧目录候选）",
            "node_type": "myth_corpus", "z_layer": 2,
            "sources": [current_source(DATASET_PAGE, "DS 0045 馆藏元数据选取"), legacy_source(legacy["entries"][0])]}
    root_body = (f"\n## 馆藏与候选范围\n\n当前 HMML 开放元数据中该馆藏选出 {manifest['count']} 条手稿记录，"
                 "目前不能将它们直接视为故事条数。旧 DREAMSEA 目录的搜索索引将其中 12 个档号描述为一部作品的分卷；"
                 "旧站当次无法直接访问，这些只是题名及书目候选，必须回查馆方和原件。"
                 "旧目录所述中国传说改编关系尚待核验，不构成具体迁徙路线证据。"
                 "馆藏地、数字化时间与叙事发生地点、时间不能混同；没有自动添加坐标和标准码。"
                 "元数据按 CC BY 4.0 署名，手稿图像及内容的访问和再利用须另核。\n")
    yield NodeMetadata.model_validate(root), root_body
    for entry in legacy["entries"]:
        record = records[entry["project"]]
        number = entry["project"].split()[-1]
        model = {**common, "id": f"corpus_hmml_makassar_{number}",
                 "title": f"望加锡手稿 · {entry['project']}",
                 "aliases": [entry["native_title"], entry["roman_title"]], "node_type": "myth_corpus", "z_layer": 2,
                 "relations": [{"type": "PART_OF_MACRO_TREND", "target": ROOT_ID,
                                "note": "旧目录搜索索引称为同一作品的分卷；仍须核验，不表示传播路径。"}],
                 "sources": [current_source(record["PURL"], entry["project"]), legacy_source(entry)]}
        body = ("\n## 当前元数据与旧目录候选\n\n" + literal_block(json.dumps(evidence(record, entry, legacy), ensure_ascii=False, indent=2))
                + "\n\n## 复核说明\n\n当前数据为尚未完成编目的馆藏记录，未提供这些题名或内容。"
                  "旧目录候选来自搜索索引，不是网页原响应或手稿影像；分卷、署名、语言、日期均须回查。"
                  "抄写日期不是故事发生年代；馆藏位置不是单篇采录地点。"
                  "没有复制手稿图像和正文，查看条件与再利用权利须逐件核对；坐标及标准码留空。\n")
        yield NodeMetadata.model_validate(model), body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="下载的 HMML 数据目录")
    parser.add_argument("--output", type=Path, required=True, help="新的馆藏选取目录")
    args = parser.parse_args()
    try:
        manifest = extract_selection(args.source, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"馆藏选取未完成：{error}", file=sys.stderr)
        return 1
    print(f"已选取 {manifest['count']} 条馆藏元数据；SHA-256 {manifest['records_sha256']}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
