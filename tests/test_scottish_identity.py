from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from pipeline.enrich_scottish_identity import enrich
from pipeline.enrich_scottish_snapshots import add_paths
from pipeline.ingest_agent import serialize_card
from pipeline.node_model import Audit, NodeMetadata, Source, Spatial, Standards
from pipeline.scottish_identity import ScottishIdentityIndex
from pipeline.scottish_witchcraft import DATASET_URL, RESIDENCES
from pipeline.vault import parse_card


class ScottishIdentityTests(unittest.TestCase):
    def test_id_link_flags_conflict_and_preserves_manual_coordinate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            folder = vault / "00_drafts/scottish_witchcraft"
            folder.mkdir(parents=True)
            schema = root / "schema.sql"
            schema.write_text("""CREATE TABLE WDB_Accused (
AccusedRef varchar,
Res_settlement varchar,
Res_county varchar,
Res_parish varchar
);
CREATE TABLE WDB_Ref_Parish (
Parishref varchar
);
""", encoding="utf-8")
            tables = root / "tables.zip"
            with ZipFile(tables, "w") as archive:
                archive.writestr("WDB_Accused.txt", 'A/EGD/1,Newton,Ayr,\nA/EGD/2,Newton,Ayr,\n')
                archive.writestr("WDB_Ref_Parish.txt", "")
            maps = root / "maps.zip"
            with ZipFile(maps, "w") as archive:
                archive.writestr(RESIDENCES,
                    "Wikidata Page,Name,Residence,Longitude,Latitude,Gender\n"
                    "http://www.wikidata.org/entity/Q1,Alice,Newton-on-Ayr,-4.625473,55.473285,Female\n"
                    "https://www.wikidata.org/wiki/Q2,Beth,Newton-on-Ayr,-4.625473,55.473285,Female\n"
                    "http://www.wikidata.org/entity/Q999,Other,Newton,-2.776134,55.873928,Female\n")
            snapshot = root / "wikidata.json"
            pairs = [("Q1", "A/EGD/1"), ("Q2", "A/EGD/2"), ("Q2", "A/EGD/3")]
            snapshot.write_text(json.dumps({"head": {"vars": ["item", "survey"]}, "results": {"bindings": [
                {"item": {"type": "uri", "value": f"http://www.wikidata.org/entity/{qid}"},
                 "survey": {"type": "literal", "value": ref}} for qid, ref in pairs]}}), encoding="utf-8")
            snapshot.with_suffix(".manifest.json").write_text(json.dumps({"property": "P4478",
                "sha256": sha256(snapshot.read_bytes()).hexdigest(), "retrieved_at": "2026-11-22T19:00:00+00:00"}), encoding="utf-8")
            identity = ScottishIdentityIndex(snapshot, maps)
            result = identity.lookup("A/EGD/1", (55.873928, -2.776134))
            self.assertTrue(result["coordinate_conflict"])
            self.assertGreater(result["map_candidates"][0]["distance_km"], 100)
            self.assertTrue(identity.lookup("A/EGD/2")["ambiguous_identity"])
            self.assertEqual(identity.lookup("A/EGD/2")["map_candidates"][0]["residence"], "Newton-on-Ayr")
            self.assertEqual(identity.lookup("A/EGD/9")["map_candidates"], [])

            source = Source(citation="测试调查库", type="scholarly_database", url=DATASET_URL,
                            content_sha256=sha256(tables.read_bytes()).hexdigest())
            for number, latitude, longitude in ((1, 55.873928, -2.776134), (2, 56.0, -2.0)):
                metadata = NodeMetadata(id=f"scot_a_egd_{number}", title="测试", node_type="case", z_layer=1,
                    genre="historical_archive", credibility_tier="A", is_fictional_quarantine=False,
                    spatial=Spatial(lat=latitude, lng=longitude, precision="city", location_name="Newton, Ayr",
                                    culture_region="Europe · Scotland"), temporal=None, standards=Standards(),
                    sources=[source], audit=Audit(created_at=date(2026, 1, 1), reviewed_by_human=False))
                (folder / f"{metadata.id}.md").write_bytes(serialize_card(metadata, "\n用户原有笔记。\n"))
            before = (folder / "scot_a_egd_1.md").read_bytes()
            checked = enrich(vault, tables, schema, maps, snapshot, check=True)
            self.assertEqual(checked["original_points_withheld"], 1)
            self.assertEqual((folder / "scot_a_egd_1.md").read_bytes(), before)
            changed = enrich(vault, tables, schema, maps, snapshot)
            self.assertEqual((changed["cards"], changed["coordinate_disagreements"], changed["original_points_withheld"],
                              changed["independently_edited_points_preserved"]), (2, 2, 1, 1))
            card1, body1 = parse_card((folder / "scot_a_egd_1.md").read_text(encoding="utf-8"))
            card2, _ = parse_card((folder / "scot_a_egd_2.md").read_text(encoding="utf-8"))
            self.assertIsNone(card1.spatial.lat)
            self.assertEqual(card2.spatial.lat, 56.0)
            self.assertIn("用户原有笔记。", body1)
            self.assertIn("55.873928", body1)
            self.assertIn("Newton-on-Ayr", body1)
            self.assertIn("Wikidata", card1.sources[-1].citation)
            self.assertEqual(card1.sources[-1].content_sha256, identity.snapshot_sha256)
            self.assertEqual(enrich(vault, tables, schema, maps, snapshot)["cards"], 0)

    def test_snapshot_path_enrichment_preserves_comments_and_existing_path(self):
        digest = "a" * 64
        spatial = Spatial(lat=None, lng=None, precision="culture_region", location_name="Scotland")
        metadata = NodeMetadata(id="scot_a_egd_1", title="测试", node_type="case", z_layer=1,
            genre="historical_archive", credibility_tier="A", is_fictional_quarantine=False,
            spatial=spatial, temporal=None, standards=Standards(),
            sources=[Source(citation="调查库", type="scholarly_database", url=DATASET_URL, content_sha256=digest)],
            audit=Audit(created_at=date(2026, 1, 1), reviewed_by_human=False))
        text = serialize_card(metadata, "\n人工正文。\n").decode().replace("  local_path: null", "  local_path: null # 自留注释")
        revised, count = add_paths(text, metadata, {("scholarly_database", DATASET_URL): (digest, "snapshots/source.zip")})
        self.assertEqual(count, 1)
        self.assertIn("# 自留注释", revised)
        self.assertIn("人工正文。", revised)
        parsed, _ = parse_card(revised)
        self.assertEqual(parsed.sources[0].local_path, "snapshots/source.zip")
        again, count = add_paths(revised, parsed, {("scholarly_database", DATASET_URL): (digest, "different.zip")})
        self.assertEqual((again, count), (revised, 0))


if __name__ == "__main__":
    unittest.main()
