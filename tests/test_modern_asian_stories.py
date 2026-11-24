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
                         'modern_asian_stories_eleventh_20261123.yaml', 'modern_asian_stories_twelfth_20261123.yaml',
                         'modern_asian_stories_thirteenth_20261123.yaml', 'modern_asian_stories_fourteenth_20261123.yaml',
                         'modern_asian_stories_fifteenth_20261123.yaml', 'modern_asian_stories_sixteenth_20261123.yaml',
                         'modern_asian_stories_seventeenth_20261123.yaml', 'modern_asian_stories_eighteenth_20261123.yaml',
                         'modern_asian_stories_nineteenth_20261123.yaml'):
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
                if item.get('temporal'):
                    self.assertEqual(card.metadata.temporal.year_start, item['temporal']['year_start'])
                    self.assertEqual(card.metadata.temporal.era_label, item['temporal']['era_label'])
                    self.assertEqual(card.metadata.temporal.uncertainty_note, item['temporal']['uncertainty_note'])
                self.assertEqual(card.metadata.genre, item['genre'])
                self.assertTrue(set(item.get('peers', [])).issubset({relation.target for relation in card.metadata.relations}))
                if item.get('reading_kind'):
                    self.assertEqual(note.kind, item['reading_kind'])
                self.assertTrue(note.location_note)
                if item.get('map_label'):
                    self.assertEqual(note.map_label, revisions.get(item['id'], item).get('map_label', item['map_label']))
                self.assertFalse(card.metadata.audit.reviewed_by_human)
                self.assertEqual(card.metadata.is_fictional_quarantine, item.get('credibility_tier', 'A') == 'F')
                self.assertFalse(card.metadata.standards.atu_types)
                self.assertFalse(card.metadata.standards.ocm_codes)

    def test_latest_urban_stories_are_in_modern_reading_scope(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_nineteenth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'),
                          Loader=FrontmatterLoader)
        for item in collection['records']:
            with self.subTest(id=item['id']):
                # The frontend's modern directory includes legends and reports.
                self.assertIn(notes[item['id']]['kind'], ('legend', 'report'))

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

    def test_cole_readings_preserve_existing_cards_and_cite_the_edition(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_eighteenth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        for node_id, addition in collection['existing_notes'].items():
            with self.subTest(id=node_id):
                path = ROOT / 'vault/00_drafts/asia_ph_cole_1916' / (node_id + '.md')
                metadata, body = parse_card(path.read_text(encoding='utf-8'))
                note = EditorialNote.model_validate(notes[node_id])
                self.assertEqual(note.paragraphs, addition['paragraphs'])
                self.assertEqual(note.source_numbers, [len(metadata.sources) + 1])
                self.assertEqual(str(note.additional_sources[0].url), addition['source']['url'])
                self.assertIn('扫描分页 OCR（待校）', body)
                self.assertFalse(metadata.audit.reviewed_by_human)
                self.assertIsNone(metadata.spatial.lat)
                self.assertIsNone(metadata.spatial.lng)

    def test_twelfth_batch_adds_sources_and_distinguishes_campus_versions(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_twelfth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        hub = collection['themes'][0]['id']
        for item in collection['records']:
            self.assertEqual(item['temporal']['era_label'], '资料发表')
            self.assertIn('并非故事中事件发生时间', item['temporal']['uncertainty_note'])
        for node_id, revision in collection['revisions'].items():
            with self.subTest(id=node_id):
                metadata, body = parse_card((ROOT / revision['path']).read_text(encoding='utf-8'))
                note = EditorialNote.model_validate(notes[node_id])
                self.assertEqual(note.paragraphs, revision['paragraphs'])
                self.assertEqual(note.source_numbers, revision['source_numbers'])
                self.assertEqual(note.map_label, revision['map_label'])
                self.assertEqual(str(metadata.sources[-1].url), revision['source']['url'])
                self.assertIn(hub, {relation.target for relation in metadata.relations})
                self.assertTrue(all(paragraph in body for paragraph in note.paragraphs))
                self.assertFalse(metadata.audit.reviewed_by_human)

    def test_bear_granny_versions_preserve_each_ending_and_are_linked(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_thirteenth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        old_id = 'case_cn_chongqing_grandfather_bear_granny_2019'
        new_id = 'case_cn_sichuan_jinhua_bear_grandma_2024'
        revision = collection['revisions'][old_id]
        old_card = read_card(ROOT / 'vault', ROOT / revision['path'])
        new_card = read_card(ROOT / 'vault', ROOT / 'vault/01_cases' / (new_id + '.md'))
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        self.assertEqual(notes[old_id]['paragraphs'], revision['paragraphs'])
        self.assertEqual(notes[old_id]['source_numbers'], [1, 2])
        self.assertIn('制服了熊家婆', old_card.markdown)
        self.assertNotIn('没有在这次访谈中讲出后续', old_card.markdown)
        self.assertIn('先把弟弟带进房间', new_card.markdown)
        self.assertIn(new_id, {relation.target for relation in old_card.metadata.relations})
        self.assertIn(old_id, {relation.target for relation in new_card.metadata.relations})
        self.assertEqual(new_card.metadata.spatial.precision, 'province')
        self.assertFalse(old_card.metadata.audit.reviewed_by_human)

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
                self.assertTrue(set(revision['source_numbers']).issubset(note.source_numbers))
                self.assertIn(revision['source']['url'], {str(source.url) for source in metadata.sources})
                self.assertTrue(all(paragraph in body for paragraph in note.paragraphs))
                self.assertFalse(metadata.audit.reviewed_by_human)

    def test_new_oral_versions_preserve_earlier_sources_and_short_map_labels(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_fourteenth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        for node_id, revision in collection['revisions'].items():
            with self.subTest(id=node_id):
                card = read_card(ROOT / 'vault', ROOT / revision['path'])
                note = EditorialNote.model_validate(notes[node_id])
                self.assertEqual(note.paragraphs, revision['paragraphs'])
                self.assertEqual(note.source_numbers, revision['source_numbers'])
                self.assertEqual(note.map_label, revision['map_label'])
                self.assertEqual(str(card.metadata.sources[-1].url), revision['source']['url'])
                self.assertTrue(set(revision['peers']).issubset({r.target for r in card.metadata.relations}))
                self.assertTrue(all(paragraph in card.markdown for paragraph in note.paragraphs))
                self.assertFalse(card.metadata.audit.reviewed_by_human)

    def test_mill_versions_are_distinct_and_white_shadow_links_back(self):
        collection = yaml.load((ROOT / 'reference/modern_asian_stories_sixteenth_20261123.yaml').read_text(encoding='utf-8'),
                               Loader=FrontmatterLoader)
        old_id = 'case_cn_shenyang_village_white_mill_2023'
        new_id = 'case_cn_northeast_big_white_shadow_2021'
        revision = collection['revisions'][old_id]
        old = read_card(ROOT / 'vault', ROOT / revision['path'])
        new = read_card(ROOT / 'vault', ROOT / 'vault/01_cases' / (new_id + '.md'))
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        self.assertEqual(notes[old_id]['paragraphs'], revision['paragraphs'])
        self.assertEqual(notes[old_id]['source_numbers'], [1, 2])
        self.assertIn('红带沟', old.markdown)
        self.assertIn('不能证明两次采录来自同一村庄', old.markdown)
        self.assertIn(new_id, {relation.target for relation in old.metadata.relations})
        self.assertIn(old_id, {relation.target for relation in new.metadata.relations})
        self.assertEqual(new.metadata.spatial.precision, 'culture_region')
        self.assertFalse(old.metadata.audit.reviewed_by_human)

    def test_neighborhood_accounts_preserve_source_and_geographic_limits(self):
        notes = yaml.load((ROOT / 'reference/reading_notes.yaml').read_text(encoding='utf-8'), Loader=FrontmatterLoader)
        dream = read_card(ROOT / 'vault', ROOT / 'vault/01_cases/case_cn_beijing_teller_faceless_dream_2017.md')
        self.assertIn('童年经历的城市未指明', notes[dream.metadata.id]['location_note'])
        self.assertIn('并不是祖父', dream.markdown)
        delivery = read_card(ROOT / 'vault', ROOT / 'vault/01_cases/case_sg_bukit_merah_empty_delivery_2026.md')
        self.assertIn('餐费与配送费都已经支付', delivery.markdown)
        self.assertIn('没有得到确定答案', delivery.markdown)
        river = read_card(ROOT / 'vault', ROOT / 'vault/01_cases/case_vn_saigon_river_binh_loi_fisherman_2016.md')
        self.assertAlmostEqual(river.metadata.spatial.lat, 10.82473)
        self.assertAlmostEqual(river.metadata.spatial.lng, 106.70924)
        self.assertIn('不定位个人住处', notes[river.metadata.id]['location_note'])
        self.assertIn('一对渔民夫妇', river.markdown)
        self.assertTrue(any('e.vnexpress.net' in str(source.url) for source in river.metadata.sources))
        hotel = read_card(ROOT / 'vault', ROOT / 'vault/01_cases/case_cn_shanghai_dahu_hotel_newspaper_ghost_2017.md')
        self.assertIn('不能因此证明故事里的事件', hotel.markdown)
        self.assertEqual(len(hotel.metadata.sources), 2)

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
