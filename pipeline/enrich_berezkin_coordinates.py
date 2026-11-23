"""Attach sourced coordinate cautions to pending cards without changing source values."""

import argparse
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from pipeline.berezkin_distribution import (
    REGIONAL_HUBS, REGION_REVIEW_MARKER, read_study, region_crosschecks, region_review_section,
)
from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer


def clear_original_coordinates(text: str) -> str:
    """Edit only the two serialized spatial fields, preserving the rest of the card."""
    match = re.search(r"(?ms)^spatial:[ \t]*\r?\n(?P<fields>.*?)(?=^\S|\Z)", text)
    if not match:
        raise ValueError("找不到可保留其余内容的 spatial 区块。")
    fields = match.group("fields")
    for field in ("lat", "lng"):
        fields, count = re.subn(rf"(?m)^(  {field}:[ \t]*)[^\r\n]+", rf"\g<1>null", fields, count=1)
        if count != 1:
            raise ValueError(f"找不到唯一的 spatial.{field} 字段。")
    return text[:match.start("fields")] + fields + text[match.end("fields"):]


def replace_checked(path: Path, old: bytes, new: bytes) -> None:
    with NamedTemporaryFile(dir=path.parent, prefix=".coordinate-review-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(new)
    try:
        if path.read_bytes() != old:
            raise ValueError(f"草稿在补充复核说明时发生变化。{path}")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def enrich(vault: Path, study_path: Path) -> dict:
    study = read_study(study_path)
    notes = region_crosschecks(study)
    if not notes:
        raise ValueError("当前附件与已核查的附件哈希不一致，没有改动草稿。")
    folder = vault / "00_drafts" / "berezkin_distribution"
    targets = []
    for area in sorted(notes):
        targets.append((folder / f"corpus_berezkin_region_{area}.md", [area], True))
    for code, motif in study.motifs.items():
        areas = sorted(set(motif.areas) & notes.keys())
        if not areas:
            continue
        node_id = REGIONAL_HUBS.get(code, f"index_berezkin_{code}")
        parent = vault / "00_drafts" / "regional_sources" if code in REGIONAL_HUBS else folder
        targets.append((parent / f"{node_id}.md", areas, False))

    changed = withheld = skipped_existing = preserved_edits = 0
    with vault_writer(vault):
        plan = []
        for path, areas, is_region in targets:
            if not path.exists():  # A previously signed card is never rewritten.
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, _ = parse_card(text.replace("\r\n", "\n"))
            if metadata.id != path.stem or metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                raise ValueError(f"待审卡片 ID 或状态不正确。{path}")
            if REGION_REVIEW_MARKER in text:
                skipped_existing += 1
                continue
            if is_region:
                original = study.regions[areas[0]]
                if metadata.spatial == original:
                    text = clear_original_coordinates(text)
                    withheld += 1
                elif metadata.spatial and metadata.spatial.lat is not None:
                    # Preserve an independently edited coordinate for the reviewer.
                    preserved_edits += 1
            text += region_review_section(areas, notes, is_region=is_region)
            encoded = text.encode("utf-8")
            if raw.startswith(b"\xef\xbb\xbf"):
                encoded = b"\xef\xbb\xbf" + encoded
            plan.append((path, raw, encoded))
        for path, raw, encoded in plan:
            replace_checked(path, raw, encoded)
        changed = len(plan)

        manifest_path = folder / "manifest.json"
        if manifest_path.exists():
            old = manifest_path.read_bytes()
            manifest = json.loads(old.decode("utf-8-sig"))
            cards = list(folder.glob("*.md"))
            if (manifest.get("review_state") == "pending"
                    and manifest.get("counts", {}).get("records") == len(cards)):
                count = 0
                for path in cards:
                    metadata, _ = parse_card(path.read_text(encoding="utf-8-sig").replace("\r\n", "\n"))
                    count += bool(metadata.spatial and metadata.spatial.lat is not None)
                manifest["counts"]["with_coordinates"] = count
                replace_checked(manifest_path, old, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"cards_updated": changed, "original_points_withheld": withheld,
            "previously_annotated": skipped_existing, "independently_edited_points_preserved": preserved_edits}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--study", type=Path, default=PROJECT_ROOT / ".local/import-sources/liu-2022-supplement-3.zip")
    args = parser.parse_args()
    print(json.dumps(enrich(args.vault.resolve(), args.study.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
