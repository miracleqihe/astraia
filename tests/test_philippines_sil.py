import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.philippines_sil import ENTRIES, ilianen_cards, parse_catalogue
from pipeline.review_queue import export


def catalogue_html():
    content = ['<html><title>Ilianen Manobo Oral Narrative Recordings</title><body>',
               '<p>samples from two of the narratives of Ampatuan Ampalid</p>',
               '<p>complete digitized recordings onsite</p>']
    for number, (_, title, english, book, credit) in enumerate(ENTRIES, 1):
        content.append(f'<ul><li><em>{title}</em> <a href="https://philippines.sil.org/sample{number}.mp3">mp3</a></li>'
                       f'<li>{english}<ul><li>by Ampatuan Ampalid. Recorded: August 2, 1976<br>'
                       f'Oral transcription published in <a href="https://philippines.sil.org/book{number}">{book}</a>'
                       f' by {credit}</li></ul></li></ul>')
    return ''.join(content) + '</body></html>'


class PhilippinesSILTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.source = self.root / "catalogue.html"
        self.source.write_text(catalogue_html(), encoding="utf-8")
        self.output = self.root / "review"
        self.absent = self.root / "absent"

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_two_samples_remain_separate_from_full_recordings_and_publication(self):
        result = stage_batch(self.vault, "asia_ph_ilianen_sil", ilianen_cards(self.source), self.table, {})
        self.assertEqual(result["counts"], {"records": 3, "with_coordinates": 0, "with_years": 0, "fiction": 0, "indexed": 0})
        summary = self.review()
        self.assertEqual(summary["collections"], {"asia": 3})
        self.assertEqual(summary["flags"]["sil_sample_not_complete"], 3)
        self.assertEqual(summary["flags"]["sil_rights_community_unverified"], 3)
        self.assertEqual(summary["flags"]["sil_transcription_unchecked"], 2)
        self.assertNotIn("sil_fields_changed", summary["flags"])
        with (self.output / "philippines_ilianen_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["讲述人"] == "Ampatuan Ampalid" and row["录音日期（非故事年代）"] == "1976-08-02"
                            and not row["具体录音地点"] and not row["坐标"] and not row["标准码"]
                            and row["人工复核"] == "待复核" for row in rows))
        self.assertIn("2008", rows[1]["书目署名及年份（原字段）"])

    def test_untrusted_source_and_changed_draft_are_flagged(self):
        self.source.write_text(catalogue_html().replace("https://philippines.sil.org/sample1.mp3", "https://example.org/sample.mp3"), encoding="utf-8")
        with self.assertRaises(IntakeError):
            parse_catalogue(self.source)
        self.source.write_text(catalogue_html(), encoding="utf-8")
        stage_batch(self.vault, "asia_ph_ilianen_sil", ilianen_cards(self.source), self.table, {})
        card = self.vault / "00_drafts/asia_ph_ilianen_sil/case_ph_ilianen_pilanduk.md"
        text = card.read_text(encoding="utf-8")
        card.write_text(text.replace('"馆方录音日期": "1976-08-02"', '"馆方录音日期": "1975-08-02"'), encoding="utf-8")
        self.assertEqual(self.review()["flags"]["sil_fields_changed"], 1)


if __name__ == "__main__":
    unittest.main()
