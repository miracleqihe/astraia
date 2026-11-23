"""Attach text-free sentence indexes to unchanged, pending Pangloss drafts."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

from pipeline.ingest_agent import DEFAULT_VAULT, literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import Source
from pipeline.pangloss_annotations import (digest, json_object, read_index,
                                           validate_selection, viewer_url)
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

MARKER = "<!-- astraia:pangloss-sentence-index-v1 -->"


def card_summary(index: dict) -> dict:
    annotations = []
    for resource in index["resources"]:
        for annotation in resource["annotations"]:
            segments = annotation.get("segments", [])
            positions = sorted({1, (len(segments) + 1) // 2, len(segments)}) if segments else []
            annotations.append({"对应音视频资源": resource["oai"], "主资源许可原字段": resource["primary_license"],
                                "关联资源编号": annotation["oai"], "关联资源 DOI": annotation["doi"],
                                "资源类型": annotation["type"], "关联资源单独许可": annotation["license"],
                                "分句数": len(segments), "有有效时间范围的分句数": sum(s["time_status"] == "valid" for s in segments),
                                "原语文字形式": sorted({form for s in segments for form in s["forms"]}),
                                "译文语言标记": sorted({lang for s in segments for lang in s["translation_languages"]}),
                                "原站资源链接": annotation["viewer_url"],
                                "原站示例段落": [{"段号": n, "链接": viewer_url(resource["oai"], annotation["oai"], n)} for n in positions]})
    return {"馆方目录转写图标": index["catalogue_transcription_icon"], "馆方音视频资源数": len(index["resources"]),
            "关联转写或附件": annotations, "主资源接口响应 SHA256": index["primary_response_sha256"],
            "关联资源接口响应 SHA256": [entry["sha256"] for entry in index["responses"]],
            "原始响应和转写正文": "未保存；响应指纹不能仅凭结构索引离线重算"}


def read_supplement(folder: Path, corpus: Path, chosen: Path, details: Path) -> list[tuple[dict, Path, str, dict]]:
    selection_path, manifest_path = folder / "selection.json", folder / "manifest.json"
    selection, manifest = json_object(selection_path), json_object(manifest_path)
    rows = validate_selection(selection, corpus, chosen, details)
    if (manifest.get("version") != 1 or manifest.get("selection_sha256") != digest(selection_path)
            or not isinstance(manifest.get("records"), list) or len(manifest["records"]) != len(rows)):
        raise IntakeError("Pangloss 分句索引清单不完整或与选取范围不符。")
    result = []
    for row, entry in zip(rows, manifest["records"], strict=True):
        number = row["id"]
        if not isinstance(entry, dict) or entry.get("id") != number or entry.get("path") != f"record-{number}.json":
            raise IntakeError(f"Pangloss 分句索引路径不符：{number}")
        path = folder / entry["path"]
        snapshot_hash = digest(path)
        if snapshot_hash != entry.get("sha256"):
            raise IntakeError(f"Pangloss 分句索引哈希不符：{number}")
        result.append((row, path, snapshot_hash, read_index(path, row)))
    return result


def enrich(vault: Path, corpus: Path, chosen: Path, details: Path, folder: Path, *, check: bool = False) -> dict:
    records = read_supplement(folder, corpus, chosen, details)
    cards = vault / "00_drafts/asia_cn_pangloss_na"
    plans, skipped, already = [], [], 0
    with vault_writer(vault):
        for row, index_path, index_hash, index in records:
            number = row["id"]
            path = cards / f"{row['node_id']}.md"
            if not path.is_file() or path.is_symlink():
                skipped.append({"id": number, "reason": "待审草稿缺失或为符号链接"})
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, _ = parse_card(text.replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                skipped.append({"id": number, "reason": "草稿已签核或为示例"})
                continue
            prior = [source for source in metadata.sources if source.type == "pangloss_annotation_index"]
            if prior:
                if len(prior) == 1 and prior[0].content_sha256 == index_hash and MARKER in text:
                    already += 1
                else:
                    skipped.append({"id": number, "reason": "已有不同的分句来源或人工修改"})
                continue
            if MARKER in text or sha256(raw).hexdigest() != row["card_sha256"]:
                skipped.append({"id": number, "reason": "选取后草稿发生变化；保留现有修改"})
                continue
            detail = next((source for source in metadata.sources if source.type == "pangloss_na_detail"), None)
            if (metadata.id != row["node_id"] or not detail or not detail.url or str(detail.url) != row["detail_url"]
                    or detail.content_sha256 != row["detail_sha256"]):
                skipped.append({"id": number, "reason": "草稿的馆方详情来源已变化"})
                continue
            source = Source.model_validate({"citation": "Pangloss 馆方接口的本地分句结构索引；不含音视频或转写正文。",
                    "type": "pangloss_annotation_index", "url": row["detail_url"], "locator": f"录音 {number} / 关联资源与分句",
                    "local_path": display_path(index_path), "content_sha256": index_hash})
            revised = append_sources(text, [source])
            summary = card_summary(index)
            note = ("\n\n" + MARKER + "\n## 原站分句检索（待复核）\n\n"
                    + literal_block(json.dumps(summary, ensure_ascii=False, indent=2))
                    + "\n\n分句序号及起止时间来自馆方接口；本地不保存原语、翻译、音视频或完整接口响应。"
                      "指纹只能在重新取得相同响应后核验。关联资源的单独许可与社区要求须另查，"
                      "音视频资源许可不能自动套用到转写文本或附件。原站分句序号供定位，不能把其中叙事视作历史事实。\n")
            for annotation in summary["关联转写或附件"]:
                for segment in annotation["原站示例段落"]:
                    note += f"\n- [在原站查看第 {segment['段号']} 段]({segment['链接']})"
            if not summary["关联转写或附件"]:
                note += "\n本次接口未返回关联转写或附件；这不证明馆方不存在其他版本。\n"
            linebreak = "\r\n" if "\r\n" in text else "\n"
            revised += note.replace("\n", linebreak)
            encoded = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + revised.encode("utf-8")
            checked, _ = parse_card(encoded.decode("utf-8-sig").replace("\r\n", "\n"))
            if checked.id != metadata.id or checked.audit.reviewed_by_human:
                raise IntakeError(f"补充后草稿无效：{path}")
            plans.append((path, raw, encoded))
        if not check:
            for path, original, revised in plans:
                with NamedTemporaryFile(dir=path.parent, prefix=".pangloss-index-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise IntakeError(f"草稿在补充时发生变化：{path}")
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
    return {"cards_to_update": len(plans), "already_enriched": already, "skipped": skipped, "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--chosen", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        result = enrich(args.vault.resolve(), args.corpus, args.chosen, args.details, args.supplement, check=args.check)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"分句索引补充未完成，现有草稿保留：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
