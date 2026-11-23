import csv
from hashlib import sha256
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from pipeline.hmml_makassar import (DATASET_PAGE, PURL, REPOSITORY, extract_selection,
                                   hmml_cards, load_legacy, load_selection)
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export


class HMMLMakassarTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.legacy = self.root / "legacy.json"
        copyfile(Path(__file__).resolve().parents[1] / "reference/hmml_makassar_legacy_candidates_v1.json", self.legacy)
        self.source = self.root / "source"
        self.source.mkdir()
        self.selection = self.root / "selection"
        self.output = self.root / "review"
        self.absent = self.root / "absent"
        entries = load_legacy(self.legacy)["entries"]
        rows = [self.record(e["project"], 833975 + i) for i, e in enumerate(entries)]
        rows += [self.record("DS 0045 00001", 536311), {"id": 1, "hmmlProjectNumber": "DS 9999 00001"}]
        payload = b"[" + b",\n".join(json.dumps(row, ensure_ascii=False).encode("utf-8") for row in rows) + b"]"
        archive = self.source / "vhmml_rr_fulldata.zip"
        with ZipFile(archive, "w") as zipped:
            zipped.writestr("vhmml_rr_fulldata.json", payload)
        manifest = {"version": 1, "dataset_page": DATASET_PAGE, "metadata_license": "CC BY 4.0",
                    "archive": archive.name, "sha256": sha256(archive.read_bytes()).hexdigest()}
        (self.source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    @staticmethod
    def record(project, identifier):
        return {"id": identifier, "PURL": PURL + str(identifier), "hmmlProjectNumber": project,
                "country": {"name": "Indonesia"}, "city": {"name": "Makassar (Sulawesi Selatan)"},
                "repository": {"name": REPOSITORY}, "objectType": "MANUSCRIPT", "parts": [],
                "notes": "This is an uncataloged stub record with provisional metadata.",
                "viewableOnline": False, "accessRestriction": "Unregistered or order a digital copy",
                "captureDateDisplay": "2023/10/11"}

    def prepare(self):
        extract_selection(self.source, self.selection)
        return stage_batch(self.vault, "asia_hmml_makassar", hmml_cards(self.selection, self.legacy), self.table, {})

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_inventory_and_candidates_are_distinct_and_unreviewed(self):
        self.assertEqual(self.prepare()["counts"],
                         {"records": 13, "with_coordinates": 0, "with_years": 0, "fiction": 0, "indexed": 0})
        manifest, items = load_selection(self.selection)
        self.assertEqual((manifest["count"], len(items)), (13, 13))
        result = self.review()
        self.assertEqual(result["collections"], {"asia": 13})
        self.assertEqual(result["flags"]["hmml_legacy_uncached"], 13)
        self.assertEqual(result["flags"]["hmml_stub_catalogue"], 13)
        self.assertNotIn("hmml_fields_changed", result["flags"])
        self.assertNotIn("hmml_selection_invalid", result["flags"])
        with (self.output / "hmml_makassar_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            candidates = list(csv.DictReader(stream))
        with (self.output / "hmml_makassar_inventory.csv").open(encoding="utf-8-sig", newline="") as stream:
            inventory = list(csv.DictReader(stream))
        self.assertEqual((len(candidates), len(inventory)), (12, 13))
        first = next(row for row in candidates if row["馆方档号"] == "DS 0045 00541")
        self.assertEqual(first["旧目录原文字题名候选"], "ᨕᨚᨄᨙᨌᨚᨕ - ᨔᨙᨑᨙᨊ")
        self.assertEqual(first["馆方记录链接"], PURL + "833975")
        self.assertEqual(first["旧目录公历抄写日期候选"], "1932 July 08")
        self.assertTrue(all(not row["坐标"] and not row["标准码"] and not row["采录时间"]
                            and row["人工复核"] == "待复核" for row in candidates))
        self.assertEqual(sum(bool(row["待审卡片ID"]) for row in inventory), 12)
        self.assertTrue(all(row["馆方单条元数据SHA256"] and not row["坐标"] and not row["标准码"] for row in inventory))

    def test_tampering_and_reusing_existing_output_fail_closed(self):
        self.prepare()
        with self.assertRaises(IntakeError):
            extract_selection(self.source, self.selection)
        card = self.vault / "00_drafts/asia_hmml_makassar/corpus_hmml_makassar_00541.md"
        text = card.read_text(encoding="utf-8")
        card.write_text(text.replace('"旧目录署名候选": "Liem Kheng Yong"', '"旧目录署名候选": "changed"'), encoding="utf-8")
        self.assertEqual(self.review()["flags"]["hmml_fields_changed"], 1)
        with (self.selection / "records.jsonl").open("ab") as stream:
            stream.write(b"tampered\n")
        self.assertGreaterEqual(self.review()["flags"]["source_hash_mismatch"], 13)
        with (self.output / "hmml_makassar_inventory.csv").open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])

    def test_legacy_duplicate_project_is_rejected(self):
        legacy = load_legacy(self.legacy)
        legacy["entries"][1]["project"] = legacy["entries"][0]["project"]
        self.legacy.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(IntakeError):
            load_legacy(self.legacy)


if __name__ == "__main__":
    unittest.main()
