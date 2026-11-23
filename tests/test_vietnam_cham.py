import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

from pipeline.fetch_vietnam_cham import INTRO, RIGHTS, fetch, parse_intro, parse_story, story_url
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.prepare_vietnam_cham_revision import prepare as prepare_revision
from pipeline.review_queue import export
from pipeline.vietnam_cham import cham_cards, load_snapshot


def field(label, value):
    return f"<div><div>{label}<!-- -->:</div><div>{value}</div></div>"


def page(number=0, *, changed_title=False, empty=False, heading_note=False):
    buttons = "".join('<button' + (' aria-current="true"' if n == number else '')
                      + f'><span>{n}<!-- -->.</span>Truyện số {n}</button>' for n in range(1, 59))
    metadata = "".join((field("Authors", "Contributor: Center for Cham Studies, Ninh Thuan"),
                        field("Date Created", "2000"), field("Languages", "Vietnamese"),
                        field("Publisher", "Ethnic Culture Publishing House"), field("Access Condition", RIGHTS)))
    if number == 0:
        article = "<article><h2>Lời giới thiệu</h2><p>32 truyện, 26 truyện, Tuấn Dũng, 1997, TRƯƠNG HIẾN MAI</p></article>"
        next_link = f'<a href="{story_url(1)}">Next → 1</a>'
    else:
        heading = f"Truyện số {number}" + (" khác" if changed_title else "")
        if heading_note:
            heading += '<button aria-label="Footnote 1">1</button>'
        content = "" if empty else "<p>PRIVATE_FOLKTALE_TEXT_SHOULD_NOT_BE_RETAINED</p>"
        article = f"<article><h2>{number}. {heading}</h2>{content}</article>"
        next_link = f'<a href="{story_url(number + 1)}">Next → {number + 1}</a>' if number < 58 else ""
    html = f'<html><head><meta charset="utf-8"><title>Folktales of Cham People | Digitizing Việt Nam</title></head><body>{buttons}{article}{next_link}{metadata}</body></html>'
    return html.encode("utf-8")


class VietnamChamTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / "snapshot"
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.parser = SimpleNamespace(can_fetch=lambda agent, url: True)

    def response(self, url, parser, delay):
        if url == INTRO:
            return page()
        number = int(parse_qs(urlsplit(url).query)["muc"][0].removeprefix("truyen-"))
        return page(number, changed_title=number == 2, empty=number == 3)

    def capture(self, callback=None):
        with patch("pipeline.fetch_vietnam_cham._robots", return_value=self.parser), \
             patch("pipeline.fetch_vietnam_cham._request", side_effect=callback or self.response):
            return fetch(self.folder, delay=2)

    def test_individual_citations_rights_missing_and_unchanged_coordinates(self):
        self.capture()
        manifest, catalogue, stories = load_snapshot(self.folder)
        self.assertEqual(len(stories), 58)
        self.assertEqual(catalogue["catalogue_fields"]["Date Created"], "2000")
        self.assertEqual(catalogue["preface_date_as_written"], "Phan Rang, thu năm 1997")
        self.assertEqual(stories[9].number, 10)
        for path in self.folder.glob("*.json"):
            self.assertNotIn("PRIVATE_FOLKTALE_TEXT", path.read_text(encoding="utf-8"))
        staged = stage_batch(self.vault, "asia_vietnam_cham_folktales", cham_cards(self.folder), self.table, {})
        self.assertEqual(staged["counts"], {"records": 59, "with_coordinates": 0, "with_years": 0, "fiction": 0, "indexed": 0})
        absent, output = self.root / "absent", self.root / "review"
        summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        self.assertEqual(summary["collections"], {"asia": 59})
        self.assertEqual(summary["flags"]["vietnam_cham_rights_scope"], 59)
        self.assertEqual(summary["flags"]["vietnam_cham_heading_mismatch"], 1)
        self.assertEqual(summary["flags"]["vietnam_cham_text_unavailable"], 1)
        self.assertNotIn("vietnam_cham_fields_changed", summary["flags"])
        raw = (output / "data.js").read_text(encoding="utf-8")
        records = {item["id"]: item for item in json.loads(raw.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
        first = records["case_vietnam_cham_001"]
        self.assertEqual(first["sources"][1]["url"], story_url(1))
        self.assertEqual(first["evidence"]["vietnam_cham_book_fields"]["Languages"], "Vietnamese")
        self.assertIsNone(first["spatial"]["lat"])
        self.assertIsNone(first["temporal"])
        self.assertFalse(any(first["standards"].values()))
        with (output / "vietnam_cham_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 58)
        self.assertTrue(all(not row["坐标"] and not row["标准码"] and not row["单篇讲述者"] for row in rows))
        self.assertEqual(rows[0]["正文语言"], "Vietnamese")
        self.assertEqual(rows[0]["原站详情"], story_url(1))
        self.assertEqual(rows[0]["人工复核"], "待复核")
        (self.folder / "story-001.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(IntakeError, "哈希不符"):
            load_snapshot(self.folder)

    def test_interruption_resumes_without_replacing_previous_snapshot(self):
        def interrupted(url, parser, delay):
            if url == story_url(4):
                raise URLError("test interruption")
            return self.response(url, parser, delay)
        with self.assertRaises(URLError):
            self.capture(interrupted)
        path = self.folder / "story-001.json"
        before = path.read_bytes()
        self.assertFalse((self.folder / "manifest.json").exists())
        calls = []
        def resumed(url, parser, delay):
            calls.append(url)
            return self.response(url, parser, delay)
        self.capture(resumed)
        self.assertNotIn(INTRO, calls)
        self.assertNotIn(story_url(1), calls)
        self.assertIn(story_url(4), calls)
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaisesRegex(IntakeError, "已有完整批次"):
            self.capture()

    def test_rejects_changed_access_conditions_and_duplicate_numbers(self):
        with self.assertRaisesRegex(IntakeError, "访问条件"):
            parse_intro(page().replace(RIGHTS.encode(), b"All rights reserved"))
        altered = page().replace(b'<span>58<!-- -->.</span>', b'<span>57<!-- -->.</span>')
        with self.assertRaisesRegex(IntakeError, "重复编号"):
            parse_intro(altered)

    def test_heading_footnote_is_not_part_of_title(self):
        parsed = parse_story(page(5, heading_note=True), 5, "Truyện số 5")
        self.assertEqual(parsed["detail_title"], "Truyện số 5")
        self.assertTrue(parsed["title_matches"])
        self.assertEqual(parsed["heading_note_markers"], [{"label": "Footnote 1", "display": "1"}])
        self.assertEqual(parsed["heading_text_with_notes"], "5. Truyện số 5 1")

    def test_revision_reuses_verified_matching_pages_without_replacing_baseline(self):
        self.capture()
        prior = (self.folder / "manifest.json").read_bytes()
        revision = self.root / "revision"
        seed = prepare_revision(self.folder, revision)
        self.assertEqual(seed["refetch"], [2])
        self.assertEqual(len(seed["reused"]), 57)
        calls = []
        def response(url, parser, delay):
            calls.append(url)
            return self.response(url, parser, delay)
        with patch("pipeline.fetch_vietnam_cham._robots", return_value=self.parser), \
             patch("pipeline.fetch_vietnam_cham._request", side_effect=response):
            fetch(revision, delay=2)
        manifest, _, stories = load_snapshot(revision)
        self.assertEqual(calls, [story_url(2)])
        self.assertEqual(len(stories), 58)
        self.assertEqual(manifest["seed_path"], "seed.json")
        self.assertEqual((self.folder / "manifest.json").read_bytes(), prior)
        (revision / "story-001.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(IntakeError, "哈希不符"):
            load_snapshot(revision)


if __name__ == "__main__":
    unittest.main()
