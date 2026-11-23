from hashlib import sha256
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfWriter

from pipeline.enrich_yuhuan_credits import MARKER, enrich, read_supplement
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export
from pipeline.vault import parse_card
from pipeline.yuhuan_stories import yuhuan_cards


class EnrichYuhuanCreditsTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.pdf = self.root / "source.pdf"
        writer = PdfWriter()
        for _ in range(124):
            writer.add_blank_page(width=841, height=595)
        with self.pdf.open("wb") as stream:
            writer.write(stream)
        self.pdf_hash = sha256(self.pdf.read_bytes()).hexdigest()
        self.base = self.root / "index.json"
        self.base.write_text(json.dumps({"version": 1, "pdf_sha256": self.pdf_hash, "entries": [
            {"page": 41, "title": "石蜂山", "category": "地方传说"},
            {"page": 94, "title": "下一世怎么报答", "category": "生活故事和笑话", "credit_page": 94,
             "credits": ["讲述者：支存祥"]}]}, ensure_ascii=False), encoding="utf-8")
        self.online = self.root / "version.html"
        self.online.write_text("<html><title>网页版本</title><body>正文</body></html>", encoding="utf-8")
        self.supplement = self.root / "credits.json"
        self.data = {"version": 1, "base_index_sha256": sha256(self.base.read_bytes()).hexdigest(),
                     "pdf_sha256": self.pdf_hash, "entries": [
            {"page": 41, "title": "石蜂山", "credit_pages": [42, 43], "credits": ["讲述者：陈光进"],
             "prior_publication": "原书旁注称载某书；未核对原版。", "online_source": {
                "title": "网页版本", "url": "https://yhsz.yuhuan.gov.cn/art/2013/example.html",
                "local_path": str(self.online), "sha256": sha256(self.online.read_bytes()).hexdigest(),
                "date": "2013-11-21", "note": "版本关系待核。"}},
            {"page": 94, "title": "下一世怎么报答", "credit_pages": [94], "credits": ["讲述者候选：支存样"],
             "conflict": "原登记为支存祥，新读法疑为支存样，待核。"}]}
        self.write_supplement()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        stage_batch(self.vault, "asia_yuhuan_2008", yuhuan_cards(self.pdf, self.base), self.table, {})
        self.card = self.vault / "00_drafts/asia_yuhuan_2008/case_cn_yuhuan_2008_p041.md"

    def write_supplement(self):
        self.supplement.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def test_check_is_nonmutating_and_updates_preserve_notes(self):
        self.card.write_text(self.card.read_text(encoding="utf-8") + "\n用户的原有备注。\n", encoding="utf-8")
        before = self.card.read_bytes()
        plan = enrich(self.vault, self.supplement, self.base, self.pdf, check=True)
        self.assertEqual(plan["cards_to_update"], 2)
        self.assertEqual(self.card.read_bytes(), before)
        result = enrich(self.vault, self.supplement, self.base, self.pdf)
        self.assertEqual(result["cards_to_update"], 2)
        text = self.card.read_text(encoding="utf-8")
        self.assertIn("用户的原有备注。", text)
        self.assertIn("印刷第 42、43 页", text)
        self.assertIn("未核对该版原件", text)
        self.assertIn(MARKER, text)
        metadata, _ = parse_card(text)
        self.assertFalse(metadata.audit.reviewed_by_human)
        self.assertIsNone(metadata.spatial.lat)
        self.assertEqual(metadata.standards.atu_types, [])
        self.assertEqual(sum(source.type == "yuhuan_credit_supplement" for source in metadata.sources), 1)
        self.assertEqual(sum(source.type == "yuhuan_web_candidate" for source in metadata.sources), 1)
        last = (self.card.parent / "case_cn_yuhuan_2008_p094.md").read_text(encoding="utf-8")
        self.assertIn("支存祥", last)
        self.assertIn("支存样", last)
        rerun = enrich(self.vault, self.supplement, self.base, self.pdf, check=True)
        self.assertEqual((rerun["cards_to_update"], rerun["already_enriched"]), (0, 2))
        output = self.root / "review"
        absent = self.root / "absent"
        summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        self.assertEqual(summary["flags"].get("yuhuan_credit_unverified"), 2)
        self.assertEqual(summary["flags"].get("yuhuan_credit_conflict"), 1)
        self.assertEqual(summary["flags"].get("yuhuan_prior_version_unchecked"), 1)
        self.assertNotIn("yuhuan_credit_missing", summary["flags"])
        with (output / "yuhuan_story_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = {row["卡片ID"]: row for row in csv.DictReader(stream)}
        first = rows["case_cn_yuhuan_2008_p041"]
        self.assertEqual(first["旁注印刷页"], "42、43")
        self.assertIn("陈光进", first["采录旁注候选"])
        self.assertIn("未核对原版", first["早期刊载候选"])
        self.assertIn("example.html", first["网页版本"])
        last = rows["case_cn_yuhuan_2008_p094"]
        self.assertIn("支存祥", last["采录旁注候选"])
        self.assertIn("支存样", last["采录旁注候选"])
        changed = self.card.read_text(encoding="utf-8").replace("原书旁注称载某书；未核对原版。", "另一条刊载记录。")
        changed = changed.replace("https://yhsz.yuhuan.gov.cn/art/2013/example.html", "https://yhsz.yuhuan.gov.cn/art/2013/other.html")
        self.card.write_text(changed, encoding="utf-8")
        summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        self.assertEqual(summary["flags"].get("yuhuan_supplement_changed"), 1)
        self.assertEqual(summary["flags"].get("yuhuan_web_source_missing"), 1)

    def test_changed_sources_or_out_of_range_pages_abort(self):
        self.data["entries"][0]["credit_pages"] = [40]
        self.write_supplement()
        with self.assertRaisesRegex(IntakeError, "旁注页码"):
            read_supplement(self.supplement, self.base, self.pdf)
        self.data["entries"][0]["credit_pages"] = [42, 43]
        self.write_supplement()
        self.online.write_text("<title>不同内容</title>", encoding="utf-8")
        before = self.card.read_bytes()
        with self.assertRaisesRegex(IntakeError, "网页版本快照"):
            enrich(self.vault, self.supplement, self.base, self.pdf)
        self.assertEqual(self.card.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
