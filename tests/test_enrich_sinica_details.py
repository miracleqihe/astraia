import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

from pipeline.enrich_sinica_details import MARKER, enrich
from pipeline.fetch_sinica_details import fetch as fetch_details
from pipeline.fetch_sinica_oral import detail_url, fetch as fetch_catalogue, list_url
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export, sinica_fields_preserved, sinica_titles_match
from pipeline.sinica_oral import sinica_cards
from pipeline.vault import parse_card
from tests.test_sinica_oral import DETAIL_PAGE, GROUPS, PAGE


PAGE_TWO = PAGE.replace(b"</body>",
    b'<a href="https://aya.ioe.sinica.edu.tw/index.php/Frontend/loreDetail/22">second</a></body>')


class SinicaDetailEnrichmentTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base = self.root / "base"
        self.folder = self.root / "supplement"
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.parser = SimpleNamespace(can_fetch=lambda agent, url: True)
        with patch("pipeline.fetch_sinica_oral.GROUPS", GROUPS), \
             patch("pipeline.fetch_sinica_oral._request", return_value=PAGE_TWO), \
             patch("pipeline.fetch_sinica_oral._robots", return_value=(self.parser, "404")):
            fetch_catalogue(self.base, details_per_group=0)
        with patch("pipeline.sinica_oral.GROUPS", GROUPS):
            stage_batch(self.vault, "asia_tw_sinica_oral", sinica_cards(self.base), self.table, {})
        self.card = self.vault / "00_drafts/asia_tw_sinica_oral/case_tw_sinica_oral_21.md"

    def fetch(self, *, request=None):
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), \
             patch("pipeline.fetch_sinica_details._robots", return_value=(self.parser, "404")), \
             patch("pipeline.fetch_sinica_oral._request", side_effect=request or (lambda url, delay: DETAIL_PAGE)):
            return fetch_details(self.vault, self.base, self.folder, limit=2, delay=2)

    def test_detail_fields_preserve_notes_and_update_review(self):
        self.card.write_text(self.card.read_text(encoding="utf-8") + "\n已有的人工备注。\n", encoding="utf-8")
        self.fetch()
        for path in self.folder.glob("*.json"):
            self.assertNotIn("受保護的譯文", path.read_text(encoding="utf-8"))
        original = self.card.read_bytes()
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), patch("pipeline.review_queue.SINICA_GROUPS", GROUPS):
            plan = enrich(self.vault, self.base, self.folder, check=True)
            self.assertEqual(plan["cards_to_update"], 2)
            self.assertEqual(self.card.read_bytes(), original)
            result = enrich(self.vault, self.base, self.folder)
            self.assertEqual((result["cards_to_update"], len(result["skipped"])), (2, 0))
            text = self.card.read_text(encoding="utf-8")
            self.assertIn("已有的人工备注。", text)
            self.assertIn(MARKER, text)
            self.assertIn("報導人乙", text)
            self.assertNotEqual(self.card.read_bytes(), original)
            metadata, body = parse_card(text)
            self.assertFalse(metadata.audit.reviewed_by_human)
            self.assertIsNone(metadata.spatial.lat)
            self.assertFalse(any(metadata.standards.model_dump().values()))
            self.assertEqual(sum(source.type == "sinica_detail_metadata" for source in metadata.sources), 1)
            self.assertEqual(enrich(self.vault, self.base, self.folder, check=True)["already_enriched"], 2)
            absent, output = self.root / "absent", self.root / "review"
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertNotIn("sinica_detail_unchecked", summary["flags"])
            self.assertNotIn("sinica_fields_changed", summary["flags"])
            self.assertEqual(summary["flags"]["sinica_tribe_conflict"], 2)
            with (output / "sinica_oral_review.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["报道人"], "報導人乙")
            self.assertEqual(rows[0]["详情族别"], "雅美族")

    def test_edited_after_selection_is_skipped_and_corruption_aborts(self):
        self.fetch()
        edited = self.card.read_text(encoding="utf-8") + "\n获取期间的新备注。\n"
        self.card.write_text(edited, encoding="utf-8")
        with patch("pipeline.sinica_oral.GROUPS", GROUPS):
            plan = enrich(self.vault, self.base, self.folder, check=True)
            self.assertEqual(plan["cards_to_update"], 1)
            self.assertEqual(plan["skipped"][0]["id"], 21)
            enrich(self.vault, self.base, self.folder)
            self.assertEqual(self.card.read_text(encoding="utf-8"), edited)
            before = self.card.read_bytes()
            (self.folder / "detail-21.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(IntakeError, "哈希不符"):
                enrich(self.vault, self.base, self.folder)
            self.assertEqual(self.card.read_bytes(), before)

    def test_interrupted_fetch_resumes_same_selection_without_overwriting(self):
        def interrupted(url, delay):
            if url == detail_url(22):
                raise URLError("test interruption")
            return DETAIL_PAGE
        with self.assertRaises(URLError):
            self.fetch(request=interrupted)
        self.assertTrue((self.folder / "selection.json").is_file())
        self.assertTrue((self.folder / "detail-21.json").is_file())
        self.assertFalse((self.folder / "manifest.json").exists())
        before = (self.folder / "detail-21.json").read_bytes()
        calls = []
        def resumed(url, delay):
            calls.append(url)
            return DETAIL_PAGE
        self.fetch(request=resumed)
        self.assertEqual(calls, [detail_url(22)])
        self.assertEqual((self.folder / "detail-21.json").read_bytes(), before)
        with self.assertRaisesRegex(IntakeError, "已有完整详情"):
            self.fetch()

    def test_field_comparison_checks_json_values_not_substrings(self):
        fields = {"說明": '原题 "A" \\ B', "報導人": "記錄者"}
        body = "```\n" + json.dumps({"详情描述字段": fields}, ensure_ascii=False, indent=2) + "\n```"
        self.assertTrue(sinica_fields_preserved(body, fields))
        changed = {"說明": fields["說明"], "報導人": "另一人"}
        self.assertFalse(sinica_fields_preserved(body + "\n另一人", changed))
        self.assertTrue(sinica_titles_match("花蓮馬太安01 ‧ Story（原題）", "01. Story （原題）"))
        self.assertFalse(sinica_titles_match("花蓮馬太安01 ‧ Story（原題）", "Different（另一題）"))
        self.assertTrue(sinica_titles_match("蘭嶼朗島65 ‧ tolowalowas a cinedkeran（自動出海的大船）",
            "tolowalowas a cinedkeran kavavattanen da no inapo 自動出海的大船﹝朗島祖先的故事﹞"))
        self.assertFalse(sinica_titles_match("台東宜灣08 ‧ Tosaay ko kamay a mianip a Lamdaw（雙手插秧的人）",
            "Tosaay ko kamay a mianip a Lamdaw （雙手補秧的人）"))

    def test_missing_archive_or_ethnicity_is_flagged_not_inferred(self):
        incomplete = DETAIL_PAGE.replace(b"<td>1-01</td>", b"<td></td>").replace(
            "<td>雅美族</td>".encode("utf-8"), b"<td></td>").replace(b"1958-06-10", b"1958-02-30")
        self.fetch(request=lambda url, delay: incomplete)
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), patch("pipeline.review_queue.SINICA_GROUPS", GROUPS):
            enrich(self.vault, self.base, self.folder)
            absent, output = self.root / "absent", self.root / "review"
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertEqual(summary["flags"]["sinica_archive_id_missing"], 2)
            self.assertEqual(summary["flags"]["sinica_ethnicity_missing"], 2)
            self.assertEqual(summary["flags"]["sinica_collection_date_invalid"], 2)
            self.assertNotIn("sinica_tribe_conflict", summary["flags"])
            with (output / "sinica_oral_review.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertTrue(all(not row["详情档案名称"] and not row["详情族别"] for row in rows))
            self.assertTrue(all(row["采集日期"] == "1958-02-30" for row in rows))


if __name__ == "__main__":
    unittest.main()
