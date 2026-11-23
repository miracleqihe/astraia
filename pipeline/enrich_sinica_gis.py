"""Attach attributable community-landmark candidates without setting graph coordinates."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

from pipeline.fetch_sinica_oral import FIELDS as DETAIL_FIELDS, detail_url
from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT, literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import Source
from pipeline.review_queue import sinica_fields_preserved
from pipeline.sinica_gis import DATA_URL, candidates, load_gis, locator
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

DEFAULT_GIS = PROJECT_ROOT / ".local/import-sources/cip-tribal-gis-2026-11-22.json"
MARKER = "<!-- astraia:sinica-community-gis-v1 -->"


def enrich(vault: Path, data: Path, *, check: bool = False) -> dict:
    rows = load_gis(data)
    data_path, data_digest = display_path(data), sha256(data.read_bytes()).hexdigest()
    folder = vault / "00_drafts/asia_tw_sinica_oral"
    plans, skipped, without, already = [], [], [], 0
    with vault_writer(vault):
        for path in sorted(folder.glob("case_tw_sinica_oral_*.md")):
            if path.is_symlink():
                skipped.append({"id": path.stem, "reason": "草稿是符号链接"})
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, body = parse_card(text.replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                skipped.append({"id": path.stem, "reason": "已签核或为示例"})
                continue
            previous = [source for source in metadata.sources if source.type == "sinica_community_gis"]
            if previous or MARKER in text:
                if len(previous) == 1 and previous[0].content_sha256 == data_digest and MARKER in text:
                    already += 1
                else:
                    skipped.append({"id": path.stem, "reason": "已有不同或不完整的 GIS 对照"})
                continue
            details = [source for source in metadata.sources if source.type == "sinica_detail_metadata"]
            if not details:
                continue
            if len(details) != 1 or not details[0].local_path or not details[0].content_sha256:
                skipped.append({"id": path.stem, "reason": "详情字段来源不唯一或缺少哈希"})
                continue
            detail_path = Path(details[0].local_path)
            if not detail_path.is_absolute():
                detail_path = PROJECT_ROOT / detail_path
            if not detail_path.is_file() or sha256(detail_path.read_bytes()).hexdigest() != details[0].content_sha256:
                raise IntakeError(f"详情来源快照不存在或哈希不符：{path}")
            document = json.loads(detail_path.read_text(encoding="utf-8"))
            fields = document.get("fields")
            identifier = int(path.stem.rsplit("_", 1)[-1])
            if (metadata.id != path.stem or document.get("id") != identifier
                    or document.get("source_url") != detail_url(identifier) or not details[0].url
                    or str(details[0].url) != detail_url(identifier)
                    or document.get("rights_notice_present") is not True or not isinstance(fields, dict)
                    or any(key not in DETAIL_FIELDS or not isinstance(value, str) for key, value in fields.items())
                    or not sinica_fields_preserved(body, fields)):
                skipped.append({"id": path.stem, "reason": "草稿详情字段已变化或无法验证"})
                continue
            location = fields.get("採集地點", "")
            matches = candidates(location, rows)
            if not matches:
                without.append({"id": path.stem, "location": location})
                continue
            source = Source.model_validate({"citation": "原住民族委员会部落 GIS 点位表，政府资料开放授权第 1 版；地标不是采录点。",
                "type": "sinica_community_gis", "url": DATA_URL, "locator": locator(matches),
                "local_path": data_path, "content_sha256": data_digest})
            revised = append_sources(text, [source])
            note = ("\n\n" + MARKER + "\n## 采集地点的社区地标候选（待复核）\n\n"
                    + literal_block(json.dumps({"館方採集地點": location, "社区地标候选": matches}, ensure_ascii=False, indent=2))
                    + "\n\n这些点由政府数据集指定为学校、道路等地标，只用于对照社区范围，"
                      "不代表实际录音地点、故事发生地点或个人族属；坐标参考系、名称和时间适用性均待复核。\n")
            revised += note.replace("\n", "\r\n" if "\r\n" in text else "\n")
            encoded = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + revised.encode("utf-8")
            updated, _ = parse_card(encoded.decode("utf-8-sig").replace("\r\n", "\n"))
            if updated.id != metadata.id or updated.spatial != metadata.spatial or updated.audit.reviewed_by_human:
                raise IntakeError(f"社区地标补充改变了草稿标识、坐标或复核状态：{path}")
            plans.append((path, raw, encoded))
        if not check:
            for path, original, revised in plans:
                with NamedTemporaryFile(dir=path.parent, prefix=".sinica-gis-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise IntakeError(f"草稿在补充地标时发生变化：{path}")
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
    return {"cards_to_update": len(plans), "without_candidate": without,
            "already_enriched": already, "skipped": skipped, "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--data", type=Path, default=DEFAULT_GIS)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        result = enrich(args.vault.resolve(), args.data.resolve(), check=args.check)
    except (ValueError, OSError) as error:
        print(f"社区地标补充未完成；现有草稿已保留。{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
