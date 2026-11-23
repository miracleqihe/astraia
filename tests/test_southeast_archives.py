import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from urllib.error import URLError

from pipeline.bl_khmer import ROOT_URL as BL_URL, bl_cards, fetch as fetch_bl, load_snapshot as load_bl, parse_root
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.lowell_folktales import (COLLECTION_TITLE, COLLECTION_URL, fetch as fetch_lowell,
                                       load_snapshot as load_lowell, lowell_cards)
from pipeline.review_queue import export


def definition(label, value):
    return f'<dt>{label}:</dt><dd>{value}</dd>'


def bl_html(volume=None):
    common = '<html><head><title>British Library Archives and Manuscripts Catalogue</title></head><body>'
    common += '<a href="https://creativecommons.org/licenses/by/4.0/">CC-BY</a><dl>'
    if volume is None:
        fields = {'Record Id': '032-003779224', 'Reference (shelfmark)': 'Or 16131/1-11',
                  'Title': 'Ṭāv rīöṅ', 'Extent': '11 volumes', 'Languages': 'Central Khmer',
                  'Scope & Content': 'Collection of Cambodian folk stories and legends in 11 folding books.',
                  'Start Date': '1890', 'End Date': '1925'}
        for key, value in fields.items():
            common += definition(key, value)
        children = ''.join(f'<a href="/catalog/040-{n:09d}"><b>Or 16131/{n}</b> : Title {n}</a>' for n in range(1, 12))
        children += '<a href="/?f%5Bparent_reference_ssi%5D%5B%5D=Or+16131%2F1-11"><b>Or 16131/1-11</b></a>'
        common += definition('Contains', children)
    else:
        fields = {'Record Id': f'040-{volume:09d}', 'Hierarchy Root Ancestor Record Id': '032-003779224',
                  'Reference (shelfmark)': f'Or 16131/{volume}', 'Title': f'Khmer work {volume}',
                  'Scope & Content': 'Two texts. Origin: Cambodia (Phnom Penh?)', 'Extent': '76 folios',
                  'Languages': 'Central Khmer', 'Scripts': 'Khmer', 'Start Date': '1859' if volume == 5 else '1890',
                  'End Date': '1925', 'Date Range': '1859-1925' if volume == 5 else '1890-1925',
                  'Digitised Content': '', 'Record Type (Level)': 'File'}
        for key, value in fields.items():
            common += definition(key, value)
    return (common + '</dl></body></html>').encode('utf-8')


LOWELL_ROWS = [(1241, 'A Long Long Time Ago in Southeast Asia book, 2018'),
               (1256, 'The document with four Khmer stories, [2018]'),
               (1321, 'A Long Long Time Ago in Southeast Asia book launch and signing event poster, 2019')]


def element(key, value):
    return f'<div id="dublin-core-{key}"><div class="element-text">{value}</div></div>'


def lowell_collection():
    body = element('title', COLLECTION_TITLE)
    body += element('description', 'Burmese Cambodian Laotian Vietnamese communities in Lowell')
    rows = ''.join(f'<div class="item"><h2><a class="permalink" href="/items/show/{identifier}">{title}</a></h2></div>'
                   for identifier, title in LOWELL_ROWS)
    body += '<div id="collection-items">' + rows + '<a href="/items/browse?collection=19">View all 3 items</a></div>'
    return ('<html><head><title>Southeast Asian Digital Archive</title></head><body>' + body + '</body></html>').encode('utf-8')


def lowell_item(identifier, title):
    body = element('title', title) + element('date', '[2018]') + element('language', 'English')
    body += element('format', 'application/pdf; 3 p.') + element('type', 'Text')
    body += element('coverage', 'Lowell, Massachusetts') + element('identifier', f'item-{identifier}')
    body += element('rights', 'Available for private, educational, and research use; users must secure any needed permissions.')
    body += element('description', 'PROTECTED NARRATIVE TEXT MUST NOT BE SAVED')
    body += '<div id="collection"><a href="/collections/show/19">Collection</a></div>'
    return ('<html><head><title>Southeast Asian Digital Archive</title></head><body>' + body + '</body></html>').encode('utf-8')


class SoutheastArchivesTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.bl = self.root / 'bl'
        self.lowell = self.root / 'lowell'
        self.output = self.root / 'review'
        self.absent = self.root / 'absent'

    def bl_fetch(self):
        def request(url, host, robots, delay):
            raw = bl_html() if url == BL_URL else bl_html(int(url.rsplit('-', 1)[1]))
            return raw, '2026-11-22T00:00:00+00:00'
        with patch('pipeline.bl_khmer.robot_rules', return_value=(None, '404')), \
             patch('pipeline.bl_khmer.request_html', side_effect=request):
            return fetch_bl(self.bl)

    def lowell_fetch(self):
        items = {f'https://umlseada.omeka.net/items/show/{identifier}': lowell_item(identifier, title)
                 for identifier, title in LOWELL_ROWS}
        def request(url, host, robots, delay):
            return (lowell_collection() if url == COLLECTION_URL else items[url]), '2026-11-22T00:00:00+00:00'
        with patch('pipeline.lowell_folktales.robot_rules', return_value=(None, '200')), \
             patch('pipeline.lowell_folktales.request_html', side_effect=request):
            return fetch_lowell(self.lowell)

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_folding_books_preserve_units_and_flag_parent_date_difference(self):
        self.bl_fetch()
        self.bl_fetch()  # A completed snapshot is verified, not overwritten.
        selection, _, items = load_bl(self.bl)
        self.assertEqual((len(selection['children']), len(items)), (11, 11))
        self.assertEqual(items[4][3]['馆方日期起始原字段'], '1859')
        manifest = stage_batch(self.vault, 'asia_kh_bl_folding_books', bl_cards(self.bl), self.table, {})
        self.assertEqual(manifest['counts']['records'], 12)
        self.assertEqual(manifest['counts']['with_coordinates'], 0)
        self.assertEqual(manifest['counts']['indexed'], 0)
        summary = self.review()
        self.assertEqual(summary['flags']['bl_khmer_date_parent_conflict'], 1)
        self.assertEqual(summary['flags']['bl_khmer_no_digital_link'], 11)
        with (self.output / 'bl_khmer_folding_books_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 11)
        fifth = next(row for row in rows if row['馆方档号'] == 'Or 16131/5')
        self.assertEqual((fifth['本册起始日期'], fifth['馆藏组起始日期']), ('1859', '1890'))
        self.assertFalse(fifth['坐标'] or fifth['标准码'])
        path = self.bl / 'record-05.html'
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaises(IntakeError):
            load_bl(self.bl)
        self.assertGreaterEqual(self.review()['flags']['source_hash_mismatch'], 1)

    def test_lowell_documents_preserve_diaspora_context_and_exclude_poster(self):
        self.lowell_fetch()
        self.lowell_fetch()
        selection, records = load_lowell(self.lowell)
        self.assertEqual((len(selection['records']), len(records)), (3, 3))
        for path in self.lowell.glob('*.json'):
            self.assertNotIn('PROTECTED NARRATIVE TEXT', path.read_text(encoding='utf-8'))
        manifest = stage_batch(self.vault, 'asia_us_lowell_sea', lowell_cards(self.lowell), self.table, {})
        self.assertEqual(manifest['counts']['records'], 3)
        self.assertEqual(manifest['counts']['with_coordinates'], 0)
        self.assertEqual(manifest['counts']['indexed'], 0)
        summary = self.review()
        self.assertEqual(summary['flags']['lowell_diaspora_scope'], 3)
        self.assertEqual(summary['flags']['lowell_no_visible_file_link'], 2)
        self.assertNotIn('lowell_fields_changed', summary['flags'])
        with (self.output / 'lowell_sea_folktales_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3)
        self.assertEqual(next(row for row in rows if row['馆方记录号'] == '1321')['待审卡片ID'], '')
        self.assertTrue(all(row['馆方覆盖范围'] == 'Lowell, Massachusetts' for row in rows))
        path = self.lowell / 'record-1256.json'
        path.write_text(path.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        with self.assertRaises(IntakeError):
            load_lowell(self.lowell)
        self.assertGreaterEqual(self.review()['flags']['source_hash_mismatch'], 1)

    def test_british_library_rejects_changed_child_links(self):
        raw = bl_html().replace(b'/catalog/040-000000001', b'https://example.org/040-000000001')
        with self.assertRaises(IntakeError):
            parse_root(raw)

    def test_interrupted_fetch_resumes_same_selection_without_overwrite(self):
        items = {f'https://umlseada.omeka.net/items/show/{identifier}': lowell_item(identifier, title)
                 for identifier, title in LOWELL_ROWS}
        def interrupted(url, host, robots, delay):
            if url.endswith('/1256'):
                raise URLError('temporary failure')
            return (lowell_collection() if url == COLLECTION_URL else items[url]), '2026-11-22T00:00:00+00:00'
        with patch('pipeline.lowell_folktales.robot_rules', return_value=(None, '200')), \
             patch('pipeline.lowell_folktales.request_html', side_effect=interrupted):
            with self.assertRaises(URLError):
                fetch_lowell(self.lowell)
        selected = (self.lowell / 'selection.json').read_bytes()
        first = (self.lowell / 'record-1241.json').read_bytes()
        self.lowell_fetch()
        self.assertEqual((self.lowell / 'selection.json').read_bytes(), selected)
        self.assertEqual((self.lowell / 'record-1241.json').read_bytes(), first)
        self.assertEqual(len(load_lowell(self.lowell)[1]), 3)

    def test_changed_rights_text_stops_before_item_is_saved(self):
        def request(url, host, robots, delay):
            if url == COLLECTION_URL:
                return lowell_collection(), '2026-11-22T00:00:00+00:00'
            return lowell_item(*LOWELL_ROWS[0]).replace(b'secure any needed permissions', b'no permission needed'), '2026-11-22T00:00:00+00:00'
        with patch('pipeline.lowell_folktales.robot_rules', return_value=(None, '200')), \
             patch('pipeline.lowell_folktales.request_html', side_effect=request):
            with self.assertRaisesRegex(IntakeError, '使用说明'):
                fetch_lowell(self.lowell)
        self.assertFalse((self.lowell / 'record-1241.json').exists())


if __name__ == '__main__':
    unittest.main()
