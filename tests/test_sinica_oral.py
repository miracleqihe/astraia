import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pipeline.fetch_sinica_oral import detail_url, fetch, list_url, parse_detail, parse_listing
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from pipeline.sinica_oral import load_snapshot, sinica_cards


GROUPS = {1: "阿美族：馬太安 Unak Tafong"}
PAGE = ("""<!doctype html><html><head><meta charset="utf-8"><title>阿美族、雅美族口語傳說採錄翻譯</title></head>
<body><a href="https://aya.ioe.sinica.edu.tw/index.php/Frontend/loreDetail/21">花蓮馬太安01 ‧ 阿美語題名（中文題名）</a>
<a href="https://other.example/index.php/Frontend/loreDetail/999">非館方</a></body></html>""").encode("utf-8")
DETAIL_PAGE = ("""<!doctype html><html><head><meta charset="utf-8"><title>阿美族、雅美族口語傳說採錄翻譯</title></head>
<body><table id="Table1"><tr><th>檔案名稱：</th><td>1-01</td><th>採集日期：</th><td>1958-06-10</td></tr>
<tr><th>族別：</th><td>雅美族</td><th>記音者：</th><td>記音者甲</td></tr>
<tr><th>報導人：</th><td>報導人乙</td><th>翻譯者：</th><td>翻譯者丙</td></tr>
<tr><th>採集地點：</th><td>馬太安</td></tr><tr><th>說明：</th><td>阿美語題名（中文題名）</td></tr>
<tr><th colspan="4">中譯全文</th></tr><tr><td>【版權聲明】本網站刊載之所有內容供非營利性教育與學術目的瀏覽使用，
非經同意不得以任何形式擷取內容出版。這段受保護的譯文不可存入研究索引。</td></tr></table></body></html>""").encode("utf-8")


class SinicaOralTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / "snapshots"
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")

    def make_snapshot(self):
        def response(url, delay):
            return {list_url(1): PAGE, detail_url(21): DETAIL_PAGE}[url]
        parser = SimpleNamespace(can_fetch=lambda agent, url: True)
        with patch("pipeline.fetch_sinica_oral.GROUPS", GROUPS), \
             patch("pipeline.fetch_sinica_oral._request", side_effect=response), \
             patch("pipeline.fetch_sinica_oral._robots", return_value=(parser, "404")):
            return fetch(self.folder, details_per_group=1)

    def test_field_extraction_excludes_translation_and_untrusted_domain(self):
        listing = parse_listing(PAGE, 1, 1)
        self.assertEqual([row["id"] for row in listing["entries"]], [21])
        detail = parse_detail(DETAIL_PAGE, 21)
        self.assertEqual(detail["fields"]["報導人"], "報導人乙")
        self.assertEqual(detail["rights_notice_variant"], "original")
        self.assertNotIn("受保護的譯文", json.dumps(detail, ensure_ascii=False))
        variant = DETAIL_PAGE.replace("學術目的瀏覽使用".encode(), "學術目的的瀏覽使用".encode())
        self.assertEqual(parse_detail(variant, 21)["rights_notice_variant"], "extra_de")
        with self.assertRaisesRegex(IntakeError, "使用声明"):
            parse_detail(variant.replace("不得以任何形式擷取內容出版".encode(), "請洽館方".encode()), 21)
        with self.assertRaisesRegex(IntakeError, "使用声明"):
            parse_detail(DETAIL_PAGE.replace("不得以任何形式擷取內容出版".encode(), "請洽館方".encode()), 21)

    def test_review_preserves_conflicts_and_blocks_inferred_data(self):
        self.make_snapshot()
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), patch("pipeline.review_queue.SINICA_GROUPS", GROUPS):
            manifest, entries = load_snapshot(self.folder)
            self.assertEqual((manifest["total_records"], len(entries)), (1, 1))
            for path in self.folder.glob("*.json"):
                self.assertNotIn("受保護的譯文", path.read_text(encoding="utf-8"))
            cards = list(sinica_cards(self.folder))
            self.assertEqual(len(cards), 2)
            item, body = cards[1]
            self.assertIsNone(item.spatial.lat)
            self.assertIsNone(item.temporal)
            self.assertFalse(any(item.standards.model_dump().values()))
            self.assertFalse(item.audit.reviewed_by_human)
            self.assertIn("報導人乙", body)
            stage_batch(self.vault, "asia_tw_sinica_oral", iter(cards), self.table, {})
            output = self.root / "review"
            absent = self.root / "absent"
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertEqual(summary["collections"], {"asia": 2})
            data = (output / "data.js").read_text(encoding="utf-8")
            records = {r["id"]: r for r in json.loads(data.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
            record = records["case_tw_sinica_oral_21"]
            flags = {flag["code"] for flag in record["issues"]}
            self.assertTrue({"sinica_tribe_conflict", "sinica_rights_restricted", "sinica_collection_scope",
                             "sinica_original_remote", "coordinate_missing"} <= flags)
            self.assertNotIn("source_hash_missing", flags)
            self.assertEqual(record["evidence"]["sinica_detail_fields"]["報導人"], "報導人乙")
            with (output / "sinica_oral_review.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual((row["详情族别"], row["目录组"], row["人工复核"]),
                             ("雅美族", GROUPS[1], "待复核"))
            self.assertFalse(row["坐标"] or row["标准码"])
            self.assertEqual(row["原站详情"], detail_url(21))
            (self.folder / "detail-21.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(IntakeError, "哈希不符"):
                load_snapshot(self.folder)

    def test_group_overview_and_detail_credits_remain_separate(self):
        groups = {2: "阿美族：諸部落"}
        parser = SimpleNamespace(can_fetch=lambda agent, url: True)
        def response(url, delay):
            return {list_url(2): PAGE, detail_url(21): DETAIL_PAGE}[url]
        with patch("pipeline.fetch_sinica_oral.GROUPS", groups), \
             patch("pipeline.fetch_sinica_oral._request", side_effect=response), \
             patch("pipeline.fetch_sinica_oral._robots", return_value=(parser, "404")):
            fetch(self.folder, details_per_group=1)
        with patch("pipeline.sinica_oral.GROUPS", groups), patch("pipeline.review_queue.SINICA_GROUPS", groups):
            stage_batch(self.vault, "asia_tw_sinica_oral", sinica_cards(self.folder), self.table, {})
            absent, output = self.root / "absent", self.root / "review"
            export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            text = (output / "data.js").read_text(encoding="utf-8")
            records = json.loads(text.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]
            record = next(r for r in records if r["id"] == "case_tw_sinica_oral_21")
            flags = {flag["code"] for flag in record["issues"]}
            self.assertTrue({"sinica_group_audit", "sinica_tribe_conflict", "sinica_credit_scope_conflict",
                             "sinica_project_date_scope"} <= flags)
            self.assertEqual(record["evidence"]["sinica_detail_fields"]["記音者"], "記音者甲")

    def test_verified_notice_variant_is_recorded_in_review(self):
        variant = DETAIL_PAGE.replace("學術目的瀏覽使用".encode(), "學術目的的瀏覽使用".encode())
        parser = SimpleNamespace(can_fetch=lambda agent, url: True)
        def response(url, delay):
            return {list_url(1): PAGE, detail_url(21): variant}[url]
        with patch("pipeline.fetch_sinica_oral.GROUPS", GROUPS), \
             patch("pipeline.fetch_sinica_oral._request", side_effect=response), \
             patch("pipeline.fetch_sinica_oral._robots", return_value=(parser, "404")):
            fetch(self.folder, details_per_group=1)
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), patch("pipeline.review_queue.SINICA_GROUPS", GROUPS):
            stage_batch(self.vault, "asia_tw_sinica_oral", sinica_cards(self.folder), self.table, {})
            absent, output = self.root / "absent", self.root / "review"
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertEqual(summary["flags"]["sinica_rights_notice_variant"], 1)
            self.assertIn("目的’后多一‘的", (output / "data.js").read_text(encoding="utf-8"))

    def test_linked_directory_pages_cannot_be_silently_omitted(self):
        self.make_snapshot()
        path = self.folder / "group-1-page-001.json"
        page = json.loads(path.read_text(encoding="utf-8"))
        page["linked_pages"] = [2]
        path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
        manifest_path = self.folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pages"][0]["sha256"] = sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), self.assertRaisesRegex(IntakeError, "计数或详情来源不符"):
            load_snapshot(self.folder)


if __name__ == "__main__":
    unittest.main()
