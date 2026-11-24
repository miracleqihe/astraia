"""The published story batch keeps readable text, attribution and honest map precision."""

from pathlib import Path
import unittest

import yaml

from pipeline.reading_notes import EditorialNote
from pipeline.vault import FrontmatterLoader, read_card


ROOT = Path(__file__).resolve().parents[1]


class ModernAsianStoriesTests(unittest.TestCase):
    def test_collection_cards_and_reading_notes_remain_in_step(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'),
                          Loader=FrontmatterLoader)
        records = collection['records']
        self.assertEqual(len(records), len({item['id'] for item in records}))
        self.assertGreaterEqual(len(records), 20)
        for item in records:
            with self.subTest(id=item['id']):
                path = ROOT / 'vault/01_cases' / (item['id'] + '.md')
                card = read_card(ROOT / 'vault', path)
                note = EditorialNote.model_validate(notes[item['id']])
                self.assertEqual(note.paragraphs, item['paragraphs'])
                self.assertTrue(all(paragraph in card.markdown for paragraph in note.paragraphs))
                self.assertGreaterEqual(len(note.paragraphs), 2)
                self.assertTrue(card.metadata.sources)
                self.assertTrue(all(source.url and source.locator for source in card.metadata.sources))
                self.assertEqual(note.source_numbers, list(range(1, len(card.metadata.sources) + 1)))
                self.assertIsNotNone(card.metadata.spatial.lat)
                self.assertIsNotNone(card.metadata.spatial.lng)
                self.assertEqual(card.metadata.spatial.precision, 'city')
                self.assertTrue(note.location_note)
                self.assertFalse(card.metadata.audit.reviewed_by_human)
                self.assertFalse(card.metadata.standards.atu_types)
                self.assertFalse(card.metadata.standards.ocm_codes)


if __name__ == '__main__':
    unittest.main()
