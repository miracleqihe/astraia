import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pipeline.enrich_sinica_details import enrich as enrich_details
from pipeline.enrich_sinica_gis import MARKER, enrich
from pipeline.fetch_sinica_details import fetch as fetch_details
from pipeline.fetch_sinica_oral import fetch as fetch_catalogue
from pipeline.import_datasets import stage_batch
from pipeline.review_queue import export
from pipeline.sinica_gis import RESOURCE_ID, candidates, load_gis
from pipeline.sinica_oral import sinica_cards
from pipeline.vault import parse_card
from tests.test_enrich_sinica_details import PAGE_TWO
from tests.test_sinica_oral import DETAIL_PAGE, GROUPS


def gis_row(seq, county="花蓮縣", town="光復鄉", name="馬太鞍部落", lat="23.671", lng="121.4252"):
    return {"Seq": seq, "DateListed": "20220725", "縣市": county, "鄉鎮市區": town, "村里": "大平村",
            "部落名稱": name, "部落傳統名制_羅馬拼音": "Fata’ an", "定位點": "光復國中", "緯度": lat,
            "經度": lng, "族別": "阿美族"}


class SinicaGisTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base, self.supplement, self.vault = self.root / "base", self.root / "supplement", self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.gis = self.root / "gis.json"
        self.write_gis([gis_row(410), gis_row(284, town="萬榮鄉")])
        parser = SimpleNamespace(can_fetch=lambda agent, url: True)
        with patch("pipeline.fetch_sinica_oral.GROUPS", GROUPS), \
             patch("pipeline.fetch_sinica_oral._request", return_value=PAGE_TWO), \
             patch("pipeline.fetch_sinica_oral._robots", return_value=(parser, "404")):
            fetch_catalogue(self.base, details_per_group=0)
        with patch("pipeline.sinica_oral.GROUPS", GROUPS):
            stage_batch(self.vault, "asia_tw_sinica_oral", sinica_cards(self.base), self.table, {})
        page = DETAIL_PAGE.replace("<td>馬太安</td>".encode(), "<td>花蓮-光復-馬太安</td>".encode())
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), \
             patch("pipeline.fetch_sinica_details._robots", return_value=(parser, "404")), \
             patch("pipeline.fetch_sinica_oral._request", return_value=page):
            fetch_details(self.vault, self.base, self.supplement, limit=2, delay=2)
            enrich_details(self.vault, self.base, self.supplement)
        self.card = self.vault / "00_drafts/asia_tw_sinica_oral/case_tw_sinica_oral_21.md"

    def write_gis(self, rows):
        data = [{"success": True, "result": {"resource_id": RESOURCE_ID, "records": rows}}]
        self.gis.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_requires_county_town_and_community_and_handles_alias(self):
        rows = load_gis(self.gis)
        result = candidates("花蓮-光復-馬太安", rows)
        self.assertEqual([row["seq"] for row in result], [410])
        self.assertTrue(result[0]["名称对照依据"].endswith("/73"))
        self.assertEqual([row["seq"] for row in candidates("花蓮-萬榮-馬太鞍", rows)], [284])
        self.assertEqual(candidates("花蓮-馬太安", rows), [])
        self.assertEqual(candidates("花蓮-光復", rows), [])
        same = [gis_row(20, county="臺東縣", town="臺東市", name="康樂部落")]
        self.assertEqual(candidates("台東-康樂", same), [])
        self.assertEqual(len(candidates("台東-台東-康樂", same)), 1)

    def test_landmark_is_review_candidate_only_and_tampering_is_flagged(self):
        self.card.write_text(self.card.read_text(encoding="utf-8") + "\n已有用户笔记。\n", encoding="utf-8")
        before = self.card.read_bytes()
        self.assertEqual(enrich(self.vault, self.gis, check=True)["cards_to_update"], 2)
        self.assertEqual(self.card.read_bytes(), before)
        self.assertEqual(enrich(self.vault, self.gis)["cards_to_update"], 2)
        text = self.card.read_text(encoding="utf-8")
        self.assertIn("已有用户笔记。", text)
        self.assertIn(MARKER, text)
        metadata, body = parse_card(text)
        self.assertIsNone(metadata.spatial.lat)
        self.assertFalse(metadata.audit.reviewed_by_human)
        self.assertEqual(enrich(self.vault, self.gis, check=True)["already_enriched"], 2)
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), patch("pipeline.review_queue.SINICA_GROUPS", GROUPS):
            output, absent = self.root / "review", self.root / "absent"
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertEqual(summary["flags"]["sinica_community_point_unverified"], 2)
            self.assertEqual(summary["flags"]["sinica_community_ethnicity_disagreement"], 2)
            self.assertNotIn("sinica_gis_note_changed", summary["flags"])
            with (output / "sinica_oral_review.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual((row["候选纬度"], row["候选经度"]), ("23.671", "121.4252"))
            self.assertFalse(row["坐标"])
            self.assertIn("光復國中", row["候选社区地标"])
            self.card.write_text(text.replace('"纬度": 23.671', '"纬度": 23.672'), encoding="utf-8")
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertEqual(summary["flags"]["sinica_gis_note_changed"], 1)
            self.write_gis([gis_row(410, lat="23.673"), gis_row(284, town="萬榮鄉")])
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertEqual(summary["flags"]["source_hash_mismatch"], 2)

    def test_ambiguous_candidates_are_both_preserved(self):
        self.write_gis([gis_row(410), gis_row(411, lat="23.672")])
        result = enrich(self.vault, self.gis)
        self.assertEqual(result["cards_to_update"], 2)
        with patch("pipeline.sinica_oral.GROUPS", GROUPS), patch("pipeline.review_queue.SINICA_GROUPS", GROUPS):
            output, absent = self.root / "review", self.root / "absent"
            summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
            self.assertEqual(summary["flags"]["sinica_community_point_ambiguous"], 2)
            with (output / "sinica_oral_review.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["候选纬度"], "23.671 | 23.672")
            self.assertFalse(row["坐标"])


if __name__ == "__main__":
    unittest.main()
