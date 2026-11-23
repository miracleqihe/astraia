import csv
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
import unittest

from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from pipeline.shandong_mirrors import load_index, mirror_cards


class ShandongMirrorTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.index = self.root / "index.json"
        copyfile(Path(__file__).resolve().parents[1] / "reference/shandong_mirror_index_v1.json", self.index)
        self.output = self.root / "review"
        self.absent = self.root / "absent"

    def stage(self):
        return stage_batch(self.vault, "asia_shandong_mirrors", mirror_cards(self.index), self.table, {})

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_roles_citations_and_review_gates(self):
        result = self.stage()
        self.assertEqual(result["counts"], {"records": 21, "with_coordinates": 0, "with_years": 0, "fiction": 0, "indexed": 0})
        summary = self.review()
        self.assertEqual(summary["collections"], {"asia": 21})
        self.assertEqual(summary["flags"]["shandong_mirror_unverified"], 21)
        self.assertEqual(summary["flags"]["shandong_rights_unverified"], 21)
        self.assertEqual(summary["flags"]["shandong_narrator_missing"], 16)
        self.assertEqual(summary["flags"]["shandong_narrator_candidate"], 1)
        self.assertEqual(summary["flags"]["shandong_author_role"], 1)
        self.assertEqual(summary["flags"]["shandong_edited_version"], 1)
        self.assertEqual(summary["flags"]["shandong_related_bibliography"], 1)
        self.assertNotIn("shandong_fields_changed", summary["flags"])
        with (self.output / "shandong_mirror_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = {row["卡片ID"]: row for row in csv.DictReader(stream)}
        self.assertEqual(len(rows), 17)
        self.assertEqual(len({row["镜像章节链接"] for row in rows.values()}), 4)
        self.assertTrue(all(not row["坐标"] and not row["标准码"] and not row["采录时间"]
                            and not row["网页原响应SHA256"] and row["人工复核"] == "待复核" for row in rows.values()))
        author = rows["case_cn_sd_pingyin_rose_01"]
        narrator = rows["case_cn_sd_pingyin_rose_02"]
        self.assertEqual(author["作者候选"], "韩子奎")
        self.assertEqual(author["讲述人候选"], "")
        self.assertEqual((narrator["讲述人候选"], narrator["讲述人页面字形"], narrator["整理人候选"]),
                         ("张厚武", "张 厚武", "李中"))
        self.assertIn("1988", narrator["相关书目对照"])
        self.assertIn("sdu.edu.cn", narrator["相关书目出处"])
        self.assertIn("删改", rows["case_cn_sd_qingzhou_02"]["早期刊载线索"])
        self.assertTrue(all(row["研究字段索引SHA256"] for row in rows.values()))

    def test_corrupt_index_and_changed_draft_are_flagged(self):
        self.stage()
        card = self.vault / "00_drafts/asia_shandong_mirrors/case_cn_sd_pingyin_rose_01.md"
        text = card.read_text(encoding="utf-8")
        self.assertIn('"作者候选": "韩子奎"', text)
        card.write_text(text.replace('"作者候选": "韩子奎"', '"作者候选": "另一个名字"'), encoding="utf-8")
        self.assertEqual(self.review()["flags"]["shandong_fields_changed"], 1)
        self.index.write_text("{}", encoding="utf-8")
        summary = self.review()
        self.assertGreaterEqual(summary["flags"]["source_hash_mismatch"], 21)
        raw = (self.output / "data.js").read_text(encoding="utf-8")
        records = json.loads(raw.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]
        self.assertTrue(all(any(issue["code"] == "source_hash_mismatch" for issue in record["issues"]) for record in records))

    def test_duplicate_titles_and_untrusted_urls_rejected(self):
        data = load_index(self.index)
        data["pages"][0]["stories"][1]["id"] = data["pages"][0]["stories"][0]["id"]
        self.index.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(IntakeError):
            load_index(self.index)
        copyfile(Path(__file__).resolve().parents[1] / "reference/shandong_mirror_index_v1.json", self.index)
        data = load_index(self.index)
        data["pages"][0]["url"] = "https://example.com/database/c17/section/5/article/34/"
        self.index.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(IntakeError):
            load_index(self.index)


if __name__ == "__main__":
    unittest.main()
