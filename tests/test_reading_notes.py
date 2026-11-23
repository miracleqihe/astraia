from dataclasses import replace
from pathlib import Path
import unittest

from pipeline.build_graph import PROJECT_ROOT
from pipeline.reading_notes import zibuyu_edition
from pipeline.vault import VaultCard, parse_card


class PublicTranscriptionTests(unittest.TestCase):
    def test_only_the_fixed_revision_passage_is_exposed(self):
        path = Path("00_drafts/asia_cn_zibuyu_wikisource/case_cn_zibuyu_v01_s002.md")
        metadata, markdown = parse_card((PROJECT_ROOT / "vault" / path).read_text(encoding="utf-8"))
        card = VaultCard(metadata, path.as_posix(), markdown)
        edition = zibuyu_edition(card)

        self.assertIn("杭州北關門外有一屋", edition["text"])
        self.assertNotIn("版本与复核", edition["text"])
        citation = metadata.sources[edition["source_number"] - 1]
        self.assertIn("oldid=2632979", str(citation.url))
        self.assertFalse(metadata.audit.reviewed_by_human)
        self.assertIsNone(zibuyu_edition(replace(card, source_path="00_drafts/other/case.md")))
        with self.assertRaisesRegex(ValueError, "哈希不一致"):
            zibuyu_edition(replace(card, markdown=markdown.replace("杭州北關", "杭州南關")))


if __name__ == "__main__":
    unittest.main()
