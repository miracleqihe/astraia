import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from pipeline import early_asia_editions as editions
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export


class EarlyAsiaEditionTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshots = self.root / 'snapshots'
        self.toc = self.root / 'toc.tsv'
        self.toc.write_bytes(editions.JADE_TOC.read_bytes())
        with self.toc.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        fake_files = {}
        for identifier, count in ((editions.JADE, 394), (editions.SALEEBY, 175)):
            folder = self.snapshots / identifier
            folder.mkdir(parents=True)
            pages = ['' for _ in range(count)]
            if identifier == editions.JADE:
                for row in rows:
                    printed = int(row['printed_page'])
                    heading = row['title'].upper()
                    if printed == 23:
                        heading += ' OF EGYPT AND BAGDAD'
                    pages[printed + 16] = f'{heading}\nSome text.\n{printed}\n'
            else:
                pages[22] = 'THE MYTHOLOGY OF MINDANAO\nMagindanao\n16\n'
            cursor, offsets = 0, []
            for page in pages:
                offsets.append([cursor, cursor + len(page), 0, 0])
                cursor += len(page)
            root = ET.Element('book')
            bookdata = ET.SubElement(root, 'bookData')
            ET.SubElement(bookdata, 'leafCount').text = str(count)
            pagedata = ET.SubElement(root, 'pageData')
            for position in range(count):
                leaf = position if identifier == editions.JADE else position + 1
                page = ET.SubElement(pagedata, 'page', leafNum=str(leaf))
                ET.SubElement(page, 'addToAccessFormats').text = (
                    'false' if identifier == editions.JADE and position in (0, count - 1) else 'true')
            data = {
                'ocr': ('hocr_searchtext.txt.gz', gzip.compress(''.join(pages).encode('utf-8'), mtime=0)),
                'index': ('hocr_pageindex.json.gz', gzip.compress(json.dumps(offsets).encode('utf-8'), mtime=0)),
                'scandata': ('scandata.xml', ET.tostring(root, encoding='utf-8')),
            }
            fake_files[identifier] = {}
            for kind, (suffix, raw) in data.items():
                (folder / f'{identifier}_{suffix}').write_bytes(raw)
                fake_files[identifier][kind] = sha256(raw).hexdigest()
        files_patch = patch.object(editions, 'FILES', fake_files)
        files_patch.start()
        self.addCleanup(files_patch.stop)
        self.andersen = self.root / 'andersen'
        self.andersen.mkdir()
        sources = {'register.html': '<h1>Nattergalen</h1><p>11. november 1843</p>',
                   'translation.html': '<h1>The Nightingale</h1><p>Emperor of China</p>'}
        andersen_hashes = {}
        for name, content in sources.items():
            raw = content.encode('utf-8')
            (self.andersen / name).write_bytes(raw)
            andersen_hashes[name] = sha256(raw).hexdigest()
        andersen_patch = patch.object(editions, 'ANDERSEN_SHA', andersen_hashes)
        andersen_patch.start()
        self.addCleanup(andersen_patch.stop)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')

    def test_scan_index_skips_inaccessible_leaves_and_detects_tampering(self):
        rows = editions.load_jade(self.toc, self.snapshots)
        self.assertEqual(len(rows), 33)
        by_page = {row['printed_page']: row for row in rows}
        self.assertEqual((by_page[3]['scan'], by_page[3]['leaf'], by_page[3]['viewer']), (20, 19, 18))
        self.assertEqual((by_page[23]['scan'], by_page[23]['leaf'], by_page[23]['viewer']), (40, 39, 38))
        self.assertTrue(by_page[23]['heading_extended'])
        self.assertEqual(editions.scan_mapping(self.snapshots, editions.SALEEBY)[22], {'leaf': 23, 'viewer': 22})
        mapping = self.snapshots / editions.JADE / f'{editions.JADE}_scandata.xml'
        mapping.write_bytes(mapping.read_bytes() + b'changed')
        with self.assertRaisesRegex(IntakeError, '哈希'):
            editions.load_jade(self.toc, self.snapshots)

    def test_pending_review_export_preserves_versions_and_unmatched_fields(self):
        cards = list(editions.early_edition_cards(self.toc, self.snapshots, self.andersen))
        self.assertEqual(len(cards), 35)
        self.assertNotIn(editions.LUMAWIG_EXISTING, [metadata.id for metadata, _ in cards])
        self.assertTrue(all(metadata.genre == 'unclassified' and not metadata.audit.reviewed_by_human for metadata, _ in cards))
        self.assertTrue(all(metadata.spatial.lat is None and metadata.spatial.lng is None and not any(metadata.standards.model_dump().values()) for metadata, _ in cards))
        manifest = stage_batch(self.vault, 'asia_early_editions', iter(cards), self.table, {})
        self.assertEqual(manifest['counts']['records'], 35)
        self.assertEqual(manifest['counts']['indexed'], 0)
        self.assertEqual(manifest['counts']['with_coordinates'], 0)
        absent, output = self.root / 'absent', self.root / 'review'
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        js = (output / 'data.js').read_text(encoding='utf-8')
        records = {record['id']: record for record in json.loads(js.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])['records']}
        nightingale = records['case_asia_jade_1922_p003']
        flags = {flag['code'] for flag in nightingale['issues']}
        self.assertIn('jade_andersen_candidate', flags)
        self.assertNotIn('jade_andersen_reference_invalid', flags)
        self.assertNotIn('jade_snapshot_invalid', flags)
        self.assertEqual(nightingale['evidence']['jade_1922']['查看器索引'], 18)
        self.assertTrue(nightingale['sources'][0]['url'].endswith('/page/n18/mode/1up'))
        self.assertIn('jade_heading_difference', {flag['code'] for flag in records['case_asia_jade_1922_p023']['issues']})
        self.assertEqual(records[editions.SALEEBY_CASE]['evidence']['saleeby_1905']['查看器索引'], 22)
        with (output / 'jade_1922_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            inventory = list(csv.DictReader(stream))
        self.assertEqual(len(inventory), 33)
        self.assertTrue(all(row['人工复核'] == '待复核' for row in inventory))
        self.assertEqual(inventory[0]['原扫描候选链接'], editions.scan_url(editions.JADE, 18))
        (self.snapshots / editions.JADE / f'{editions.JADE}_scandata.xml').write_bytes(b'changed')
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        self.assertIn('source_hash_mismatch', (output / 'data.js').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
