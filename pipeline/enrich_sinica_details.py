"""Add separately captured detail fields to unchanged, pending research cards."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile

from pipeline.fetch_sinica_details import BASE, validate_selection
from pipeline.fetch_sinica_oral import FIELDS, detail_url
from pipeline.ingest_agent import DEFAULT_VAULT, literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import Source
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

MARKER = "<!-- astraia:sinica-detail-fields-v1 -->"
PLACEHOLDER = "尚未采集；请查看原站单条详情"
REPLACEMENT = "原批次未采集；本次详情补充见下方，仍须复核"


def read_supplement(folder: Path, base: Path) -> list[tuple[dict, Path, str, dict]]:
    try:
        selection_path, manifest_path = folder / "selection.json", folder / "manifest.json"
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"详情补充清单无法读取：{error}") from error
    rows = validate_selection(selection, base)
    if (not isinstance(manifest, dict) or manifest.get("version") != 1
            or manifest.get("selection_sha256") != sha256(selection_path.read_bytes()).hexdigest()
            or manifest.get("base_manifest_sha256") != selection["base_manifest_sha256"]
            or not isinstance(manifest.get("records"), list) or len(manifest["records"]) != len(rows)):
        raise IntakeError("详情补充清单与选取清单不符。")
    result = []
    for row, entry in zip(rows, manifest["records"], strict=True):
        identifier = row["id"]
        if (not isinstance(entry, dict) or entry.get("id") != identifier
                or entry.get("path") != f"detail-{identifier}.json"):
            raise IntakeError(f"详情补充清单编号或路径不符：{identifier}")
        path = folder / entry["path"]
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != entry.get("sha256"):
            raise IntakeError(f"详情字段快照哈希不符：{identifier}")
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise IntakeError(f"详情字段快照无法读取：{identifier}") from error
        fields = document.get("fields") if isinstance(document, dict) else None
        if (not isinstance(fields, dict) or not fields or not any(isinstance(value, str) and value.strip() for value in fields.values())
                or any(key not in FIELDS or not isinstance(value, str) or "\ufffd" in value or "\0" in value
                       for key, value in fields.items())
                or document.get("source_url") != detail_url(identifier) or document.get("id") != identifier
                or document.get("rights_notice_present") is not True
                or document.get("rights_notice_variant") not in (None, "original", "extra_de")
                or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("raw_sha256", "")))):
            raise IntakeError(f"详情字段内容、来源或使用声明不符：{identifier}")
        result.append((row, path, digest, fields))
    return result


def enrich(vault: Path, base: Path, folder: Path, *, check: bool = False) -> dict:
    rows = read_supplement(folder, base)
    plans, skipped, already = [], [], 0
    cards = vault / "00_drafts/asia_tw_sinica_oral"
    with vault_writer(vault):
        for row, snapshot, digest, fields in rows:
            identifier = row["id"]
            path = cards / f"case_tw_sinica_oral_{identifier}.md"
            if not path.is_file() or path.is_symlink():
                skipped.append({"id": identifier, "reason": "待审草稿不存在或是符号链接"})
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, _ = parse_card(text.replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                skipped.append({"id": identifier, "reason": "已签核或为示例"})
                continue
            details = [source for source in metadata.sources if source.type == "sinica_detail_metadata"]
            if details:
                if len(details) == 1 and details[0].content_sha256 == digest and MARKER in text:
                    already += 1
                else:
                    skipped.append({"id": identifier, "reason": "已有不同或人工修改过的详情来源"})
                continue
            if MARKER in text:
                skipped.append({"id": identifier, "reason": "已有补充标记但缺少对应来源"})
                continue
            if sha256(raw).hexdigest() != row["card_sha256"]:
                skipped.append({"id": identifier, "reason": "选取后草稿发生变化；保留现有修改"})
                continue
            catalogue = next((source for source in metadata.sources if source.type == "sinica_catalogue"), None)
            original = next((source for source in metadata.sources if source.type == "sinica_original"), None)
            if (metadata.id != path.stem or not catalogue or catalogue.content_sha256 != row["catalogue_sha256"]
                    or not original or not original.url or str(original.url) != detail_url(identifier)):
                skipped.append({"id": identifier, "reason": "草稿的目录或详情链接已变化"})
                continue
            source = Source.model_validate({"citation": "馆方详情页的描述字段研究快照，不含正文和录音。",
                "type": "sinica_detail_metadata", "url": detail_url(identifier),
                "locator": f"单条记录 {identifier} / 描述字段", "local_path": display_path(snapshot), "content_sha256": digest})
            revised = append_sources(text, [source])
            if PLACEHOLDER in revised:
                revised = revised.replace(PLACEHOLDER, REPLACEMENT, 1)
            note = ("\n\n" + MARKER + "\n## 馆方详情描述字段补充（待复核）\n\n"
                    + literal_block(json.dumps({"详情描述字段": fields}, ensure_ascii=False, indent=2))
                    + "\n\n上述字段保留馆方原称谓和角色；采集日期、地点不等于叙事年代和发生地点。"
                      "原站译文及音频未复制，使用与社区权益须另行核对。\n")
            linebreak = "\r\n" if "\r\n" in text else "\n"
            revised += note.replace("\n", linebreak)
            encoded = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + revised.encode("utf-8")
            # Validate the full result before touching any card.
            validated, _ = parse_card(encoded.decode("utf-8-sig").replace("\r\n", "\n"))
            if validated.id != metadata.id or validated.audit.reviewed_by_human:
                raise IntakeError(f"补充后草稿无效：{path}")
            plans.append((path, raw, encoded))
        if not check:
            for path, original, revised in plans:
                with NamedTemporaryFile(dir=path.parent, prefix=".sinica-details-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise IntakeError(f"草稿在补充详情时发生变化：{path}")
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
    return {"cards_to_update": len(plans), "already_enriched": already, "skipped": skipped, "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        result = enrich(args.vault.resolve(), args.base.resolve(), args.supplement.resolve(), check=args.check)
    except (ValueError, OSError) as error:
        print(f"详情补充未完成；现有草稿已保留。{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
