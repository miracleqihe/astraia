"""Add Scottish P4478 links and quarantine large coordinate disagreements for review."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

from pyproj import Transformer

from pipeline.enrich_berezkin_coordinates import clear_original_coordinates
from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT
from pipeline.node_model import Source
from pipeline.scottish_identity import DISTANCE_REVIEW_KM, ScottishIdentityIndex
from pipeline.scottish_witchcraft import (
    _archive_table, _choose_location, _identifier, _residence_index, snapshot_path,
)
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

MARKER = "<!-- astraia:scottish-coordinate-crosscheck-v1 -->"


def identity_source(reference: str, qid: str, index: ScottishIdentityIndex, snapshot: Path) -> Source:
    return Source.model_validate({
        "citation": "Wikidata P4478 档号对照快照，CC0；爱丁堡地图导出亦来自 Wikidata，二者并非独立证据。",
        "type": "external_catalogue", "url": f"https://www.wikidata.org/wiki/{qid}",
        "locator": f"P4478 · {reference}", "local_path": snapshot_path(snapshot),
        "content_sha256": index.snapshot_sha256,
    })


def conflict_note(expected: dict, method: str, comparison: dict) -> str:
    lines = ["", MARKER, "## 地点坐标对照待复核", "",
             f"原草稿依据「{method}」所得坐标为纬度 {expected['lat']}、经度 {expected['lng']}。"
             f"同一被告档号通过 Wikidata P4478 连接到爱丁堡地图导出，下列地点与原坐标的距离均超过 {DISTANCE_REVIEW_KM:g} 公里：", ""]
    for candidate in comparison["map_candidates"]:
        lines.append(f"- {candidate['residence']}：纬度 {candidate['lat']}、经度 {candidate['lng']}，"
                     f"约 {candidate['distance_km']} 公里；[Wikidata {candidate['qid']}](https://www.wikidata.org/wiki/{candidate['qid']})。")
    lines += ["", "以上仅是同档号资料的地理对照；地图数据来自 Wikidata，不能作为独立证实。"
              "居住地、教区和调查或审判地点可能不同。10 公里只是提醒复核的阈值，不代表任一坐标已经证伪。"
              "原始生成坐标暂不作为地图点位；须结合原表格网、地名及史料进一步核对。", ""]
    return "\n".join(lines)


def enrich(vault: Path, tables: Path, schema: Path, maps: Path, snapshot: Path, *, check: bool = False) -> dict:
    index = ScottishIdentityIndex(snapshot, maps)
    archive_hash = sha256(tables.read_bytes()).hexdigest()
    with ZipFile(tables) as archive:
        source_schema = schema.read_text(encoding="utf-8-sig")
        accused = _archive_table(archive, source_schema, "Accused")
        parishes = {row["Parishref"]: row for row in _archive_table(archive, source_schema, "Ref_Parish")}
    residence_index = _residence_index(maps)
    transform = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True).transform
    folder = vault / "00_drafts/scottish_witchcraft"
    plans = []
    additions_count = conflicts = withheld = preserved = 0
    with vault_writer(vault):
        for row in accused:
            reference = row["AccusedRef"]
            path = folder / f"{_identifier(reference)}.md"
            if not path.exists():
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, _ = parse_card(text.replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                continue
            if metadata.id != path.stem or not metadata.sources or metadata.sources[0].content_sha256 != archive_hash:
                raise ValueError(f"待审草稿档号或调查库来源哈希不一致。{path}")
            expected, method = _choose_location(row, parishes.get(row.get("Res_parish"), {}), residence_index, transform)
            coordinates = (expected["lat"], expected["lng"]) if expected["lat"] is not None else None
            comparison = index.lookup(reference, coordinates)
            existing = {(str(source.url) if source.url else "", source.locator) for source in metadata.sources}
            additions = [identity_source(reference, entity["qid"], index, snapshot) for entity in comparison["entities"]
                         if (entity["url"], f"P4478 · {reference}") not in existing]
            revised = append_sources(text, additions)
            additions_count += len(additions)
            if comparison["coordinate_conflict"] and MARKER not in revised:
                conflicts += 1
                if metadata.spatial and metadata.spatial.model_dump(mode="json") == expected:
                    revised = clear_original_coordinates(revised)
                    withheld += 1
                elif metadata.spatial and metadata.spatial.lat is not None:
                    preserved += 1
                revised += conflict_note(expected, method or "原表", comparison)
            if revised != text:
                encoded = revised.encode("utf-8")
                if raw.startswith(b"\xef\xbb\xbf"):
                    encoded = b"\xef\xbb\xbf" + encoded
                plans.append((path, raw, encoded))
        if not check:
            for path, original, revised in plans:
                with NamedTemporaryFile(dir=path.parent, prefix=".identity-review-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise ValueError(f"草稿在补充身份线索时发生变化。{path}")
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
            manifest_path = folder / "manifest.json"
            if withheld and manifest_path.is_file():
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
                    if manifest_path.read_bytes() != old:
                        raise ValueError("批次清单在更新过程中发生变化。")
                    with NamedTemporaryFile(dir=folder, prefix=".identity-manifest-", delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                    try:
                        temporary.replace(manifest_path)
                    finally:
                        temporary.unlink(missing_ok=True)
    return {"cards": len(plans), "wikidata_sources_added": additions_count, "coordinate_disagreements": conflicts,
            "original_points_withheld": withheld, "independently_edited_points_preserved": preserved, "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--tables", type=Path, default=PROJECT_ROOT / ".local/import-sources/scottish-witches-tables.zip")
    parser.add_argument("--schema", type=Path, default=PROJECT_ROOT / ".local/import-sources/scottish-witches-schema.sql")
    parser.add_argument("--maps", type=Path, default=PROJECT_ROOT / ".local/import-sources/scottish-witches-maps.zip")
    parser.add_argument("--wikidata", type=Path, default=PROJECT_ROOT / ".local/import-sources/wikidata-scottish-p4478.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(enrich(args.vault.resolve(), args.tables.resolve(), args.schema.resolve(), args.maps.resolve(),
                            args.wikidata.resolve(), check=args.check), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
