"""The published story batch keeps readable text, attribution and honest map precision."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml

from pipeline.reading_notes import EditorialNote
from pipeline.vault import FrontmatterLoader, read_card
from pipeline import import_modern_stories


ROOT = Path(__file__).resolve().parents[1]


class ModernAsianStoriesTests(unittest.TestCase):
    def test_import_with_custom_manifest_and_repeat_is_safe(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / 'vault'
            (vault / '01_cases').mkdir(parents=True)
            (root / 'web/public/data').mkdir(parents=True)
            (root / 'web/public/data/graph_data.json').write_text(
                '{"nodes":[{"id":"motif_existing","title":"已有母题","sources":[]}]}', encoding='utf-8')
            notes = root / 'notes.yaml'
            notes.write_text('{}\n', encoding='utf-8')
            collection = root / 'batch.yaml'
            collection.write_text(yaml.safe_dump({'themes': [], 'existing_notes': {}, 'records': [{
                'id': 'case_test', 'title': '测试故事', 'genre': 'memorate', 'reading_kind': 'report', 'theme': 'motif_existing',
                'location': {'lat': 1.0, 'lng': 2.0, 'precision': 'city', 'location_name': '参考点'},
                'location_note': '参考坐标。', 'paragraphs': ['故事一。', '故事二。'],
                'sources': [{'citation': '资料', 'url': 'https://example.com/story', 'locator': '正文'}],
            }]}, allow_unicode=True), encoding='utf-8')
            manifest = root / 'out/manifest.json'
            with patch.object(import_modern_stories, 'ROOT', root), patch.object(import_modern_stories, 'VAULT', vault), \
                    patch.object(import_modern_stories, 'NOTES', notes):
                real_replace = import_modern_stories.replace_card

                def fail_manifest(path, content):
                    if path == manifest:
                        raise OSError('manifest failed')
                    return real_replace(path, content)

                with patch.object(import_modern_stories, 'replace_card', side_effect=fail_manifest):
                    with self.assertRaisesRegex(OSError, 'manifest failed'):
                        import_modern_stories.run(collection, manifest)
                self.assertEqual(notes.read_text(encoding='utf-8'), '{}\n')
                self.assertFalse((vault / '01_cases/case_test.md').exists())
                import_modern_stories.run(collection, manifest)
                self.assertTrue((vault / '01_cases/case_test.md').exists())
                self.assertIn('case_test', manifest.read_text(encoding='utf-8'))
                self.assertEqual(yaml.safe_load(notes.read_text(encoding='utf-8'))['case_test']['kind'], 'report')
                before = notes.read_bytes()
                with self.assertRaisesRegex(ValueError, '阅读提要已存在'):
                    import_modern_stories.run(collection, manifest)
                self.assertEqual(before, notes.read_bytes())

    def test_collection_cards_and_reading_notes_remain_in_step(self):
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'),
                          Loader=FrontmatterLoader)
        records = []
        for filename in ('modern_asian_stories_20261123.yaml', 'modern_asian_stories_second_20261123.yaml',
                         'modern_asian_stories_third_20261123.yaml', 'modern_asian_stories_fourth_20261123.yaml',
                         'modern_asian_stories_fifth_20261123.yaml', 'modern_asian_stories_sixth_20261123.yaml'):
            collection = yaml.load((ROOT / 'reference' / filename).read_text(encoding='utf-8'), Loader=FrontmatterLoader)
            records.extend(collection['records'])
        self.assertEqual(len(records), len({item['id'] for item in records}))
        self.assertGreaterEqual(len(records), 30)
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
                self.assertIn(card.metadata.spatial.precision, ('city', 'province', 'culture_region'))
                if item.get('reading_kind'):
                    self.assertEqual(note.kind, item['reading_kind'])
                self.assertTrue(note.location_note)
                self.assertFalse(card.metadata.audit.reviewed_by_human)
                self.assertFalse(card.metadata.standards.atu_types)
                self.assertFalse(card.metadata.standards.ocm_codes)


if __name__ == '__main__':
    unittest.main()
