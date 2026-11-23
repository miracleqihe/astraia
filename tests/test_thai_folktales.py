from argparse import Namespace
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.build_graph import compile_cards
from pipeline.import_datasets import stage_batch
from pipeline.ingest_agent import prepare_card, verify_local_sources
from pipeline.intake_sources import IntakeError
from pipeline.local_standards import load_code_table
from pipeline.review_queue import export
from pipeline.thai_folktales import original_text, read_dataset, thai_cards


def source_row(identifier, *, text="<p>เรื่องเล่าภาษาไทย</p>", creator="ผู้บันทึก", license_value="CC"):
    return {"title": f"นิทาน {identifier}", "type": "นิทานผี", "creator": creator,
            "description": text, "subject": "นิทานพื้นบ้าน", "spatial": "ไทย", "temporal": "",
            "language": "ไทย", "rights": "", "license": license_value,
            "source.uri": f"https://www.sac.or.th/databases/folktales/folktale-details.php?id={identifier}"}


class ThaiFolktaleTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "folktales.json"
        self.rows = [source_row(1, text="<p>เรื่องเล่าภาษาไทย</p><script>bad()</script>"),
                     source_row(2, text="", creator="", license_value="")]
        self.write_data(self.rows)
        self.catalogue = self.root / "catalogue.html"
        self.catalogue.write_text("<html>ข้อมูลนิทาน Creative Commons Attribution Non-Commercial</html>", encoding="utf-8")
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.vault = self.root / "vault"
        self.vault.mkdir()

    def write_data(self, rows):
        self.data.write_text(json.dumps({"status": 200, "row": len(rows), "result": rows}, ensure_ascii=False), encoding="utf-8")

    def test_dataset_integrity_and_original_text(self):
        self.assertEqual(set(read_dataset(self.data)), {1, 2})
        self.assertEqual(original_text(self.rows[0]["description"]), "เรื่องเล่าภาษาไทย")
        self.write_data([self.rows[0], self.rows[0]])
        with self.assertRaisesRegex(IntakeError, "记录号重复"):
            read_dataset(self.data)
        bad = source_row(2)
        bad["source.uri"] = "https://example.org/?id=2"
        self.write_data([bad])
        with self.assertRaisesRegex(IntakeError, "链接格式"):
            read_dataset(self.data)

    def test_pending_records_include_source_fields_and_missing_text_flags(self):
        manifest = stage_batch(self.vault, "asia_thai_sac", thai_cards(self.data, self.catalogue), self.table, {})
        self.assertEqual(manifest["counts"]["records"], 3)
        self.assertEqual(manifest["counts"]["indexed"], 0)
        self.assertEqual(manifest["counts"]["with_coordinates"], 0)
        absent = self.root / "absent"
        output = self.root / "review"
        summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        self.assertEqual(summary["collections"], {"asia": 3})
        script = (output / "data.js").read_text(encoding="utf-8")
        records = {record["id"]: record for record in json.loads(
            script.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
        first, second = records["case_thai_sac_1"], records["case_thai_sac_2"]
        self.assertIn("เรื่องเล่าภาษาไทย", first["markdown"])
        self.assertNotIn("bad()", first["markdown"])
        self.assertEqual(first["evidence"]["thai_catalogue_fields"]["type"], "นิทานผี")
        self.assertEqual(first["sources"][0]["content_sha256"], sha256(self.data.read_bytes()).hexdigest())
        issues = {entry["code"] for entry in second["issues"]}
        self.assertTrue({"thai_original_missing", "thai_creator_missing", "thai_record_license_missing",
                         "thai_record_page_unchecked", "thai_location_scope_unknown"}.issubset(issues))
        self.assertEqual(second["standards"]["atu_types"], [])
        table = load_code_table(self.table)
        paths = list((self.vault / "00_drafts/asia_thai_sac").glob("*.md"))
        candidates = [prepare_card(path, path.read_bytes(), Namespace(genre="folktale", tier=None), table) for path in paths]
        verify_local_sources(candidates)
        preview = compile_cards({card.metadata.id: card for card in candidates})
        self.assertEqual((len(preview["nodes"]), len(preview["links"])), (3, 2))
        changed_card = self.vault / "00_drafts/asia_thai_sac/case_thai_sac_1.md"
        changed_card.write_text(changed_card.read_text(encoding="utf-8").replace("เรื่องเล่าภาษาไทย", "ข้อความเปลี่ยน"), encoding="utf-8")
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        script = (output / "data.js").read_text(encoding="utf-8")
        changed = {record["id"]: record for record in json.loads(
            script.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
        self.assertTrue(any(flag["code"] == "thai_original_changed" for flag in changed["case_thai_sac_1"]["issues"]))
        self.data.write_text("{}", encoding="utf-8")
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        script = (output / "data.js").read_text(encoding="utf-8")
        changed = {record["id"]: record for record in json.loads(
            script.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
        self.assertTrue(any(flag["code"] == "source_hash_mismatch" for flag in changed["case_thai_sac_1"]["issues"]))


if __name__ == "__main__":
    unittest.main()
