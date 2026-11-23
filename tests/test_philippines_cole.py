import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline import philippines_cole as cole
from pipeline import cole_ocr_segments as ocr_segments
from pipeline import enrich_cole_ocr
from pipeline.vault import parse_card
from pipeline.review_queue import export


class PhilippineColeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshots = self.root / 'snapshots'
        self.snapshots.mkdir()
        self.toc = self.root / 'toc.tsv'
        self.toc.write_bytes(cole.TOC.read_bytes())
        with self.toc.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        pages = ['' for _ in range(259)]
        for row in rows:
            page = int(row['printed_page'])
            pages[page + 19] = f"{row['title'].upper()}\n{row['subgroup']}\n[{page}]\n"
        pages[237] = 'PRONUNCIATION OF PHILIPPINE NAMES\n'
        text = ''.join(pages)
        offsets = []
        cursor = 0
        for page in pages:
            offsets.append([cursor, cursor + len(page), 0, 0])
            cursor += len(page)
        ocr = gzip.compress(text.encode('utf-8'), mtime=0)
        index = gzip.compress(json.dumps(offsets).encode('utf-8'), mtime=0)
        (self.snapshots / cole.OCR_NAME).write_bytes(ocr)
        (self.snapshots / cole.PAGE_INDEX_NAME).write_bytes(index)
        for name, value in [('OCR_SHA', sha256(ocr).hexdigest()), ('PAGE_INDEX_SHA', sha256(index).hexdigest())]:
            for module in (cole, ocr_segments):
                mock = patch.object(module, name, value)
                mock.start()
                self.addCleanup(mock.stop)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')

    def test_candidates_keep_homonyms_and_reject_changed_sources(self):
        rows = cole.load_catalogue(self.toc, self.snapshots)
        same_title = [row for row in rows if row['title'] == 'The Sun and the Moon']
        self.assertEqual(len(same_title), 3)
        self.assertEqual(len({cole.node_id(row) for row in same_title}), 3)
        self.assertEqual([row['scan'] for row in same_title], [85, 165, 221])
        self.assertTrue(all(row['footer_match'] for row in rows))
        (self.snapshots / cole.OCR_NAME).write_bytes(b'changed')
        with self.assertRaisesRegex(IntakeError, '哈希'):
            cole.load_catalogue(self.toc, self.snapshots)

    def test_pending_export_links_and_flags(self):
        manifest = stage_batch(self.vault, 'asia_ph_cole_1916', cole.cole_cards(self.toc, self.snapshots), self.table, {})
        self.assertEqual(manifest['counts']['records'], 62)
        self.assertEqual(manifest['counts']['indexed'], 0)
        self.assertEqual(manifest['counts']['with_coordinates'], 0)
        parent = self.vault / '00_drafts/asia_ph_cole_1916/corpus_ph_cole_1916.md'
        self.assertIn('资料组卡本身不含正文或影像；各子卡是否附 OCR 请以其草稿为准。', parent.read_text(encoding='utf-8'))
        absent, output = self.root / 'absent', self.root / 'review'
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        js = (output / 'data.js').read_text(encoding='utf-8')
        records = {record['id']: record for record in json.loads(js.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])['records']}
        sayen = records['case_ph_cole_1916_p060']
        self.assertTrue(any(issue['code'] == 'cole_auto_toc_sayen' for issue in sayen['issues']))
        self.assertEqual(sayen['evidence']['cole_1916']['目录题名'], 'The Story of Sayen')
        self.assertTrue(sayen['sources'][0]['url'].endswith('/page/n79/mode/1up'))
        self.assertIsNone(sayen['spatial']['lat'])
        self.assertFalse(any(sayen['standards'].values()))
        context = records[cole.SPECIAL_ID]
        self.assertTrue(any(issue['code'] == 'cole_chapter_boundary' for issue in context['issues']))
        with (output / 'philippines_cole_1916_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            entries = list(csv.DictReader(stream))
        self.assertEqual(len(entries), 61)
        self.assertTrue(all(row['人工复核'] == '待复核' for row in entries))
        (self.snapshots / cole.OCR_NAME).write_bytes(b'changed')
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        changed = (output / 'data.js').read_text(encoding='utf-8')
        self.assertIn('source_hash_mismatch', changed)

    def test_ocr_enrichment_preserves_page_bytes_and_review_gate(self):
        stage_batch(self.vault, 'asia_ph_cole_1916', cole.cole_cards(self.toc, self.snapshots), self.table, {})
        folder = self.root / 'segments'
        manifest = ocr_segments.create(folder, self.toc, self.snapshots)
        self.assertEqual(len(manifest['entries']), 61)
        _, segments = ocr_segments.load(folder, self.toc, self.snapshots)
        self.assertEqual(segments[-1]['end_scan_exclusive'], 238)
        self.assertNotIn('PRONUNCIATION', ''.join(p['text'] for p in segments[-1]['pages']))
        target = self.vault / '00_drafts/asia_ph_cole_1916/case_ph_cole_1916_p006.md'
        before = target.read_bytes()
        plan = enrich_cole_ocr.enrich(self.vault, folder, self.toc, self.snapshots, check=True)
        self.assertEqual(plan['cards_to_update'], 61)
        self.assertEqual(target.read_bytes(), before)
        result = enrich_cole_ocr.enrich(self.vault, folder, self.toc, self.snapshots)
        self.assertEqual(result['cards_to_update'], 61)
        old_meta, old_body = parse_card(before.decode('utf-8'))
        new_meta, new_body = parse_card(target.read_text(encoding='utf-8'))
        self.assertEqual(old_meta.model_dump(exclude={'sources'}), new_meta.model_dump(exclude={'sources'}))
        self.assertTrue(new_body.startswith(old_body))
        self.assertIn(enrich_cole_ocr.note(segments[0]).strip(), new_body)
        self.assertEqual(enrich_cole_ocr.enrich(self.vault, folder, self.toc, self.snapshots, check=True)['already_enriched'], 61)
        absent, output = self.root / 'absent', self.root / 'review'
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        data = (output / 'data.js').read_text(encoding='utf-8')
        records = {r['id']: r for r in json.loads(data.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])['records']}
        first = records[segments[0]['id']]
        self.assertEqual(first['evidence']['cole_ocr_pages'], segments[0]['pages'])
        self.assertTrue(any(i['code'] == 'cole_ocr_uncorrected' for i in first['issues']))
        with (output / 'philippines_cole_1916_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            entries = list(csv.DictReader(stream))
        self.assertEqual(entries[0]['OCR候选页数'], str(len(segments[0]['pages'])))
        original = target.read_text(encoding='utf-8')
        target.write_text(original.replace(enrich_cole_ocr.MARKER, enrich_cole_ocr.MARKER + '\n文字被修改', 1), encoding='utf-8')
        export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        changed = (output / 'data.js').read_text(encoding='utf-8')
        changed_records = {r['id']: r for r in json.loads(changed.removeprefix('window.ASTRAIA_REVIEW_DATA=').rstrip()[:-1])['records']}
        changed_first = changed_records[segments[0]['id']]
        self.assertTrue(any(i['code'] == 'cole_ocr_segments_changed' for i in changed_first['issues']))
        self.assertNotIn('cole_ocr_pages', changed_first['evidence'])
        reviewed = original.replace('reviewed_by_human: false', 'reviewed_by_human: true')
        target.write_text(reviewed.replace('genre: unclassified', 'genre: folktale'), encoding='utf-8')
        with self.assertRaisesRegex(IntakeError, '已复核'):
            enrich_cole_ocr.enrich(self.vault, folder, self.toc, self.snapshots)
        fragment = folder / (segments[0]['id'] + '.json')
        fragment_original = fragment.read_bytes()
        fragment.write_bytes(fragment_original + b' ')
        with self.assertRaisesRegex(IntakeError, '不符'):
            ocr_segments.load(folder, self.toc, self.snapshots)
        fragment.write_bytes(fragment_original)
        manifest_path = folder / 'manifest.json'
        malformed = json.loads(manifest_path.read_text(encoding='utf-8'))
        malformed['entries'][0] = 'invalid'
        manifest_path.write_text(json.dumps(malformed), encoding='utf-8')
        with self.assertRaisesRegex(IntakeError, '条目格式无效'):
            ocr_segments.load(folder, self.toc, self.snapshots)

    def test_ocr_segments_reject_bad_offsets_and_ambiguous_end(self):
        text = 'A\nPRONUNCIATION OF PHILIPPINE NAMES\nPRONUNCIATION OF PHILIPPINE NAMES\n'
        first = len('A\n')
        second = first + len('PRONUNCIATION OF PHILIPPINE NAMES\n')
        rows = [{'printed_page': 1, 'title': 'A', 'scan': 1}]
        offsets = [[0, first, 0, 0], [first, second, 0, 0], [second, len(text), 0, 0]]
        with self.assertRaisesRegex(IntakeError, '唯一识别'):
            ocr_segments.derive_segments(text, offsets, rows)
        offsets[1][0] += 1
        with self.assertRaisesRegex(IntakeError, '不连续'):
            ocr_segments.derive_segments(text, offsets, rows)


if __name__ == '__main__':
    unittest.main()
