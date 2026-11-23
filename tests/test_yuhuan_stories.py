from argparse import Namespace
from hashlib import sha256
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfWriter

from pipeline.build_graph import compile_cards
from pipeline.import_datasets import stage_batch
from pipeline.ingest_agent import prepare_card, verify_local_sources
from pipeline.intake_sources import IntakeError
from pipeline.local_standards import load_code_table
from pipeline.review_queue import export
from pipeline.yuhuan_stories import PDF_URL, pdf_page, read_index, yuhuan_cards


class YuhuanStoryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pdf = self.root / "source.pdf"
        writer = PdfWriter()
        for _ in range(124):
            writer.add_blank_page(width=841, height=595)
        with self.pdf.open("wb") as output:
            writer.write(output)
        self.index = self.root / "index.json"
        self.document = {"version": 1, "pdf_sha256": sha256(self.pdf.read_bytes()).hexdigest(), "entries": [
            {"page": 1, "title": "狗桔城", "category": "史事传说", "credit_page": 5,
             "credits": ["讲述者：某某", "流传区域：本县陈屿"]},
            {"page": 94, "title": "下一世怎么报答", "category": "生活故事和笑话",
             "title_note": "字形待核"},
        ]}
        self.write_index()
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")

    def write_index(self):
        self.index.write_text(json.dumps(self.document, ensure_ascii=False), encoding="utf-8")

    def test_print_pages_and_integrity(self):
        self.assertEqual([pdf_page(n) for n in (1, 2, 3, 5, 94)], [9, 10, 10, 11, 56])
        for invalid in (0, 95, True, "1"):
            with self.assertRaises(IntakeError):
                pdf_page(invalid)
        self.document["entries"][1]["page"] = 1
        self.write_index()
        with self.assertRaisesRegex(IntakeError, "递增"):
            read_index(self.index)
        self.document["entries"][1]["page"] = 94
        self.document["pdf_sha256"] = "0" * 64
        self.write_index()
        with self.assertRaisesRegex(IntakeError, "哈希不匹配"):
            list(yuhuan_cards(self.pdf, self.index))

    def test_pending_cards_review_and_isolated_compile(self):
        manifest = stage_batch(self.vault, "asia_yuhuan_2008", yuhuan_cards(self.pdf, self.index), self.table, {})
        self.assertEqual(manifest["counts"]["records"], 3)
        self.assertEqual(manifest["counts"]["with_coordinates"], 0)
        self.assertEqual(manifest["counts"]["indexed"], 0)
        absent = self.root / "absent"
        output = self.root / "review"
        summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        self.assertEqual(summary["collections"], {"asia": 3})
        script = (output / "data.js").read_text(encoding="utf-8")
        records = {record["id"]: record for record in json.loads(
            script.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
        first = records["case_cn_yuhuan_2008_p001"]
        last = records["case_cn_yuhuan_2008_p094"]
        self.assertEqual(first["sources"][0]["url"], f"{PDF_URL}#page=9")
        self.assertEqual(first["evidence"]["yuhuan_index"]["credit_page"], 5)
        self.assertIn("讲述者：某某", first["markdown"])
        self.assertIn("没有正文转录", first["markdown"])
        self.assertIsNone(first["spatial"]["lat"])
        self.assertEqual(first["standards"]["atu_types"], [])
        codes = {issue["code"] for issue in last["issues"]}
        self.assertTrue({"yuhuan_scan_only", "yuhuan_credit_missing", "yuhuan_rights_unverified",
                         "yuhuan_title_uncertain", "yuhuan_collection_scope"}.issubset(codes))
        with (output / "yuhuan_story_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["起始印刷页"], rows[0]["起始PDF页"]), ("1", "9"))
        self.assertEqual(rows[0]["原页链接"], f"{PDF_URL}#page=9")
        table = load_code_table(self.table)
        paths = list((self.vault / "00_drafts/asia_yuhuan_2008").glob("*.md"))
        candidates = [prepare_card(path, path.read_bytes(), Namespace(genre="folktale", tier=None), table) for path in paths]
        verify_local_sources(candidates)
        preview = compile_cards({card.metadata.id: card for card in candidates})
        self.assertEqual((len(preview["nodes"]), len(preview["links"])), (3, 2))
        self.pdf.write_bytes(b"changed")
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        script = (output / "data.js").read_text(encoding="utf-8")
        changed = {record["id"]: record for record in json.loads(
            script.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
        self.assertTrue(any(issue["code"] == "source_hash_mismatch" for issue in changed[first["id"]]["issues"]))

    def test_online_version_is_bound_to_title_and_snapshot(self):
        online = self.root / "version.html"
        online.write_text("<html><head><title>狗桔城</title></head><body>网页版本</body></html>", encoding="utf-8")
        self.document["entries"][0]["online_source"] = {
            "url": "https://yhsz.yuhuan.gov.cn/art/2013/example.html", "local_path": str(online),
            "sha256": sha256(online.read_bytes()).hexdigest(), "date": "2013-09-29"}
        self.write_index()
        cards = list(yuhuan_cards(self.pdf, self.index))
        self.assertEqual(cards[1][0].sources[-1].type, "yuhuan_web_version")
        self.assertIn("文字差异", cards[1][1])
        online.write_text("<title>内容已变</title>", encoding="utf-8")
        with self.assertRaisesRegex(IntakeError, "网页版本快照哈希不符"):
            list(yuhuan_cards(self.pdf, self.index))


if __name__ == "__main__":
    unittest.main()
