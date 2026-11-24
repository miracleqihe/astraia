"""The published story batch keeps readable text, attribution and honest map precision."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml

from pipeline.reading_notes import EditorialNote
from pipeline.vault import FrontmatterLoader, parse_card, read_card
from pipeline import import_modern_stories


ROOT = Path(__file__).resolve().parents[1]


class ModernAsianStoriesTests(unittest.TestCase):
    def test_fiction_import_keeps_tier_and_quarantine_together(self):
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
                'id': 'case_test_fiction', 'title': '虚构故事', 'genre': 'creepypasta_ostension',
                'credibility_tier': 'F', 'theme': 'motif_existing',
                'location': {'lat': 1.0, 'lng': 2.0, 'precision': 'city', 'location_name': '传播地'},
                'location_note': '传播地参考点。', 'paragraphs': ['虚构故事。', '传播记录。'],
                'sources': [{'citation': '采访', 'url': 'https://example.com/story', 'locator': '正文'}],
            }]}, allow_unicode=True), encoding='utf-8')
            with patch.object(import_modern_stories, 'ROOT', root), patch.object(import_modern_stories, 'VAULT', vault), \
                    patch.object(import_modern_stories, 'NOTES', notes):
                import_modern_stories.run(collection, root / 'out/manifest.json')
            card = read_card(vault, vault / '05_quarantine_fiction/case_test_fiction.md')
            self.assertEqual(card.metadata.credibility_tier, 'F')
            self.assertTrue(card.metadata.is_fictional_quarantine)

    def test_import_with_custom_manifest_and_repeat_is_safe(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / 'vault'
            (vault / '01_cases').mkdir(parents=True)
            (root / 'web/public/data').mkdir(parents=True)
            (root / 'web/public/data/graph_data.json').write_text(
                '{"nodes":[{"id":"motif_existing","title":"已有母题","sources":[]},'
                '{"id":"mech_existing","title":"已有机制","sources":[]}]}', encoding='utf-8')
            notes = root / 'notes.yaml'
            notes.write_text('{}\n', encoding='utf-8')
            collection = root / 'batch.yaml'
            collection.write_text(yaml.safe_dump({'themes': [], 'existing_notes': {}, 'records': [{
                'id': 'case_test', 'title': '测试故事', 'genre': 'memorate', 'reading_kind': 'report', 'theme': 'motif_existing',
                'peers': ['mech_existing', 'motif_existing'],
                'location': {'lat': 1.0, 'lng': 2.0, 'precision': 'city', 'location_name': '参考点'},
                'location_note': '参考坐标。', 'map_label': '短地名', 'paragraphs': ['故事一。', '故事二。'],
                'sources': [{'citation': '资料', 'url': 'https://example.com/story', 'locator': '正文'}],
            }]}, allow_unicode=True), encoding='utf-8')
            manifest = root / 'out/manifest.json'
            with patch.object(import_modern_stories, 'ROOT', root), patch.object(import_modern_stories, 'VAULT', vault), \
                    patch.object(import_modern_stories, 'NOTES', notes):
                valid_collection = collection.read_text(encoding='utf-8')
                collection.write_text(valid_collection.replace('mech_existing', 'mech_missing'), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, '关联目标不存在'):
                    import_modern_stories.run(collection, manifest)
                self.assertFalse((vault / '01_cases/case_test.md').exists())
                self.assertEqual(notes.read_text(encoding='utf-8'), '{}\n')
                collection.write_text(valid_collection, encoding='utf-8')
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
                card = read_card(vault, vault / '01_cases/case_test.md')
                self.assertEqual({relation.target for relation in card.metadata.relations},
                                 {'motif_existing', 'mech_existing'})
                self.assertEqual(len(card.metadata.relations), 2)
                self.assertIn('case_test', manifest.read_text(encoding='utf-8'))
                self.assertEqual(yaml.safe_load(notes.read_text(encoding='utf-8'))['case_test']['kind'], 'report')
                self.assertEqual(yaml.safe_load(notes.read_text(encoding='utf-8'))['case_test']['map_label'], '短地名')
                before = notes.read_bytes()
                with self.assertRaisesRegex(ValueError, '阅读提要已存在'):
                    import_modern_stories.run(collection, manifest)
                self.assertEqual(before, notes.read_bytes())

    def test_collection_cards_and_reading_notes_remain_in_step(self):
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'),
                          Loader=FrontmatterLoader)
        records = []
        revisions = {}
        for filename in ('modern_asian_stories_20261123.yaml', 'modern_asian_stories_second_20261123.yaml',
                         'modern_asian_stories_third_20261123.yaml', 'modern_asian_stories_fourth_20261123.yaml',
                         'modern_asian_stories_fifth_20261123.yaml', 'modern_asian_stories_sixth_20261123.yaml',
                         'modern_asian_stories_seventh_20261123.yaml', 'modern_asian_stories_eighth_20261123.yaml',
                         'modern_asian_stories_ninth_20261123.yaml', 'modern_asian_stories_tenth_20261123.yaml',
                         'modern_asian_stories_eleventh_20261123.yaml'):
            collection = yaml.load((ROOT / 'reference' / filename).read_text(encoding='utf-8'), Loader=FrontmatterLoader)
            records.extend(collection['records'])
            revisions.update(collection.get('revisions', {}))
        self.assertEqual(len(records), len({item['id'] for item in records}))
        self.assertGreaterEqual(len(records), 30)
        for item in records:
            with self.subTest(id=item['id']):
                directory = '05_quarantine_fiction' if item.get('credibility_tier', 'A') == 'F' else '01_cases'
                path = ROOT / 'vault' / directory / (item['id'] + '.md')
                card = read_card(ROOT / 'vault', path)
                note = EditorialNote.model_validate(notes[item['id']])
                self.assertEqual(note.paragraphs, revisions.get(item['id'], item)['paragraphs'])
                self.assertTrue(all(paragraph in card.markdown for paragraph in note.paragraphs))
                self.assertGreaterEqual(len(note.paragraphs), 2)
                self.assertTrue(card.metadata.sources)
                self.assertTrue(all(source.url and source.locator for source in card.metadata.sources))
                self.assertEqual(note.source_numbers, list(range(1, len(card.metadata.sources) + 1)))
                self.assertIsNotNone(card.metadata.spatial.lat)
                self.assertIsNotNone(card.metadata.spatial.lng)
                self.assertIn(card.metadata.spatial.precision, ('city', 'province', 'culture_region'))
                self.assertEqual(card.metadata.spatial.precision, item['location']['precision'])
                self.assertEqual(card.metadata.genre, item['genre'])
                self.assertTrue(set(item.get('peers', [])).issubset({relation.target for relation in card.metadata.relations}))
                if item.get('reading_kind'):
                    self.assertEqual(note.kind, item['reading_kind'])
                self.assertTrue(note.location_note)
                if item.get('map_label'):
                    self.assertEqual(note.map_label, item['map_label'])
                self.assertFalse(card.metadata.audit.reviewed_by_human)
                self.assertEqual(card.metadata.is_fictional_quarantine, item.get('credibility_tier', 'A') == 'F')
                self.assertFalse(card.metadata.standards.atu_types)
                self.assertFalse(card.metadata.standards.ocm_codes)

    def test_nichibun_readings_keep_catalogue_provenance_and_location(self):
        additions = yaml.load((ROOT / 'reference/nichibun_readings_20261123.yaml').read_text(encoding='utf-8'),
                              Loader=FrontmatterLoader)['records']
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'),
                          Loader=FrontmatterLoader)
        self.assertEqual(len(additions), 15)
        self.assertEqual(len({item['id'] for item in additions}), len(additions))
        for item in additions:
            with self.subTest(id=item['id']):
                metadata, body = parse_card((ROOT / item['path']).read_text(encoding='utf-8'))
                self.assertEqual(metadata.id, item['id'])
                self.assertEqual(metadata.title, item['title'])
                self.assertIn(item['former_title'], metadata.aliases)
                self.assertEqual(metadata.sources[0].content_sha256, item['snapshot_sha256'])
                self.assertEqual(notes[item['id']], item['note'])
                self.assertTrue(all(paragraph in body for paragraph in item['note']['paragraphs']))
                self.assertTrue(metadata.spatial and metadata.spatial.lat is not None and metadata.spatial.lng is not None)
                self.assertFalse(metadata.audit.reviewed_by_human)

    def test_ubin_revision_preserves_its_source_and_reading_note(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_seventh_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        node_id = 'case_sg_ubin_german_girl_shrine'
        revision = collection['revisions'][node_id]
        card = read_card(ROOT / 'vault', ROOT / 'vault/01_cases' / (node_id + '.md'))
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        note = EditorialNote.model_validate(notes[node_id])
        self.assertEqual(note.paragraphs, revision['paragraphs'])
        self.assertEqual(note.source_numbers, [1, 2, 3])
        self.assertEqual(str(card.metadata.sources[2].url), revision['source']['url'])
        self.assertTrue(all(paragraph in card.markdown for paragraph in note.paragraphs))
        self.assertFalse(card.metadata.audit.reviewed_by_human)

    def test_qingdao_followup_extends_the_original_record(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_eighth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        node_id = 'case_cn_qingdao_jiangxi_road_red_dress'
        revision = collection['revisions'][node_id]
        card = read_card(ROOT / 'vault', ROOT / 'vault/01_cases' / (node_id + '.md'))
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        note = EditorialNote.model_validate(notes[node_id])
        self.assertEqual(note.paragraphs, revision['paragraphs'])
        self.assertEqual(note.source_numbers, [1, 2])
        self.assertEqual(str(card.metadata.sources[1].url), revision['source']['url'])
        self.assertTrue(all(paragraph in card.markdown for paragraph in note.paragraphs))
        self.assertFalse(card.metadata.audit.reviewed_by_human)

    def test_ninth_batch_revisions_preserve_original_cards(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_ninth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        for node_id, revision in collection['revisions'].items():
            with self.subTest(id=node_id):
                metadata, body = parse_card((ROOT / revision['path']).read_text(encoding='utf-8'))
                note = EditorialNote.model_validate(notes[node_id])
                self.assertEqual(note.paragraphs, revision['paragraphs'])
                self.assertEqual(note.source_numbers, revision['source_numbers'])
                self.assertEqual(str(metadata.sources[-1].url), revision['source']['url'])
                self.assertTrue(all(paragraph in body for paragraph in note.paragraphs))
                self.assertFalse(metadata.audit.reviewed_by_human)

    def test_tenth_batch_adds_versions_to_existing_cards(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_tenth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        for node_id, revision in collection['revisions'].items():
            with self.subTest(id=node_id):
                metadata, body = parse_card((ROOT / revision['path']).read_text(encoding='utf-8'))
                note = EditorialNote.model_validate(notes[node_id])
                self.assertEqual(note.paragraphs, revision['paragraphs'])
                self.assertEqual(note.source_numbers, revision['source_numbers'])
                self.assertEqual(str(metadata.sources[-1].url), revision['source']['url'])
                self.assertTrue(all(paragraph in body for paragraph in note.paragraphs))
                self.assertFalse(metadata.audit.reviewed_by_human)


if __name__ == '__main__':
    unittest.main()
