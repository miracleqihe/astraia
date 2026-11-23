import csv
import html
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from urllib.error import HTTPError, URLError

from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.khmer_nitean import (CATALOGUE_URL, KHMER_DIGITS, canonical_url, fetch,
                                   load_snapshot, nitean_cards, parse_catalogue, request_with_transient_retry)
from pipeline.khmer_wikisource import fetch as fetch_wiki, parse_catalogue as parse_wiki
from pipeline.review_queue import export


COUNTS = (34, 24, 51, 12, 19, 20, 25, 29)


def catalogue_html():
    groups = ['<details><summary>Introduction 1</summary><ol><li>'
              '<a href="/nitean/folktales/introduction/"><span>·</span><span>អារម្ភកថា</span></a>'
              '</li></ol></details>']
    for volume, count in enumerate(COUNTS, 1):
        entries = []
        for position in range(1, count + 1):
            slug = 'រឿង-សាកល្បង' if (volume, position) == (1, 1) else f'v{volume}-p{position}'
            entries.append(f'<li><a href="/nitean/folktales/{slug}/"><span>{position}</span>'
                           f'<span>រឿងសាកល្បង {volume}-{position}</span></a></li>')
        groups.append(f'<details><summary><span>ប្រជុំរឿងព្រេងខ្មែរភាគ {KHMER_DIGITS[volume]}</span>'
                      f'<span>{count}</span></summary><ol>{"".join(entries)}</ol></details>')
    return ('<html><body><h1>ប្រជុំរឿងព្រេងនិទានខ្មែរ</h1><p>214 chapters 8 parts</p>'
            '<a href="https://khmertext.sourceforge.net/">KhmerText</a>'
            '<section aria-labelledby="toc"><div class="space-y-4">' + ''.join(groups) +
            '</div></section></body></html>').encode('utf-8')


def chapter_html(row):
    title = row['title'] + (' changed' if row['ordinal'] == 2 else '')
    return (f'<html><body><article><nav aria-label="Breadcrumb"><ol><li>Home</li><li>Stories</li>'
            f'<li>{html.escape(row["volume_title"])}</li></ol></nav><header><h1>{html.escape(title)}</h1>'
            f'<p>{row["ordinal"] + 1} / 215</p></header><div class="reader">'
            '<p>PRIVATE_PROTECTED_STORY_TEXT</p>'
            '<p>ប្រជុំ​រឿង​ព្រេង​ខ្មែរ​ភាគ ១ ទំព័រ​ទី ១-៣</p>'
            '<section class="footnotes"><ol><li id="user-content-fn-1">PRIVATE_NOTE_CONTENT</li>'
            '</ol></section></div></article></body></html>').encode('utf-8')


def wiki_html():
    khmer = str.maketrans('0123456789', KHMER_DIGITS)
    counts = (34, 23, 53, 12, 20, 20, 25, 29, 32)
    pages = (146, 158, 175, 140, 193, 159, 124, 218, 185)
    rows = ''.join(f'<tr><td>ភាគទី{KHMER_DIGITS[v]}</td><td>{str(counts[v-1]).translate(khmer)}</td>'
                   f'<td>{str(pages[v-1]).translate(khmer)}</td></tr>' for v in range(1, 10))
    return ('<html><head><script>var x={"wgRevisionId":783711};</script></head><body>'
            '<h1 id="firstHeading">ប្រជុំរឿងព្រេងខ្មែរ</h1><table class="wikitable">'
            '<tr><th>ចំណងជើង</th><th>ចំនួនរឿង</th><th>ចំនួនទំព័រ</th></tr>' + rows +
            '<tr><td>សរុប</td><td>២៤៨</td><td>១៤៩៨</td></tr></table>'
            '<p>PRIVATE_PROTECTED_STORY_TEXT</p></body></html>').encode('utf-8')


class KhmerNiteanTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / 'snapshots'
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.absent = self.root / 'absent'
        self.output = self.root / 'review'

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_catalogue_rejects_foreign_hosts_and_duplicate_links(self):
        parsed = parse_catalogue(catalogue_html())
        self.assertEqual(parsed['volume_counts'], list(COUNTS))
        self.assertEqual(len(parsed['records']), 214)
        self.assertIn('%E1%', parsed['records'][0]['url'])
        with self.assertRaises(IntakeError):
            canonical_url('https://example.com/nitean/folktales/example/')
        raw = catalogue_html().replace(b'/nitean/folktales/v1-p3/', b'/nitean/folktales/v1-p2/')
        with self.assertRaises(IntakeError):
            parse_catalogue(raw)

    def test_transient_retry_does_not_retry_http_rate_limits(self):
        failure = URLError('temporary TLS error')
        with patch('pipeline.khmer_nitean.time.sleep'), \
             patch('pipeline.khmer_nitean.request_html', side_effect=[failure, (b'ok', 'now')]) as request:
            self.assertEqual(request_with_transient_retry(CATALOGUE_URL, None, 2), (b'ok', 'now'))
            self.assertEqual(request.call_count, 2)
        limited = HTTPError(CATALOGUE_URL, 429, 'rate limit', None, None)
        with patch('pipeline.khmer_nitean.time.sleep'), \
             patch('pipeline.khmer_nitean.request_html', side_effect=limited) as request:
            with self.assertRaises(HTTPError):
                request_with_transient_retry(CATALOGUE_URL, None, 2)
            self.assertEqual(request.call_count, 1)

    def test_resume_review_and_tamper_detection(self):
        by_url = {row['url']: row for row in parse_catalogue(catalogue_html())['records']}
        def request(url, host, robots, delay):
            return (catalogue_html() if url == CATALOGUE_URL else chapter_html(by_url[url])), '2026-11-22T00:00:00+00:00'
        def interrupted(url, host, robots, delay):
            if url == list(by_url)[1]:
                raise URLError('temporary failure')
            return request(url, host, robots, delay)
        with patch('pipeline.khmer_nitean.robot_rules', return_value=(None, '404')), \
             patch('pipeline.khmer_nitean.request_html', side_effect=interrupted), \
             patch('pipeline.khmer_nitean.time.sleep'), patch('builtins.print'):
            with self.assertRaises(URLError):
                fetch(self.folder)
        selection = (self.folder / 'selection.json').read_bytes()
        first = (self.folder / 'chapter-001.json').read_bytes()
        self.assertFalse((self.folder / 'manifest.json').exists())
        with patch('pipeline.khmer_nitean.robot_rules', return_value=(None, '404')), \
             patch('pipeline.khmer_nitean.request_html', side_effect=request), patch('builtins.print'):
            fetch(self.folder)
            fetch(self.folder)
        self.assertEqual((self.folder / 'selection.json').read_bytes(), selection)
        self.assertEqual((self.folder / 'chapter-001.json').read_bytes(), first)
        selected, chapters = load_snapshot(self.folder)
        self.assertEqual((len(selected['records']), len(chapters)), (214, 214))
        for path in self.folder.glob('*.json'):
            content = path.read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE_PROTECTED_STORY_TEXT', content)
            self.assertNotIn('PRIVATE_NOTE_CONTENT', content)
        comparison = self.root / 'wikisource.json'
        with patch('pipeline.khmer_wikisource.robot_rules', return_value=(None, '200')), \
             patch('pipeline.khmer_wikisource.request_html', return_value=(wiki_html(), '2026-11-22T00:00:00+00:00')):
            fetch_wiki(comparison)
        self.assertNotIn('PRIVATE_PROTECTED_STORY_TEXT', comparison.read_text(encoding='utf-8'))
        manifest = stage_batch(self.vault, 'asia_kh_nitean_folktales', nitean_cards(self.folder, comparison), self.table, {})
        self.assertEqual(manifest['counts']['records'], 223)
        self.assertEqual(manifest['counts']['with_coordinates'], 0)
        self.assertEqual(manifest['counts']['indexed'], 0)
        summary = self.review()
        self.assertEqual(summary['flags']['nitean_title_mismatch'], 1)
        self.assertEqual(summary['flags']['nitean_volume_count_difference'], 97)
        self.assertNotIn('nitean_chapter_invalid', summary['flags'])
        self.assertNotIn('nitean_fields_changed', summary['flags'])
        self.assertNotIn('nitean_comparison_invalid', summary['flags'])
        with (self.output / 'khmer_nitean_chapter_review.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 214)
        self.assertEqual(rows[0]['单篇原文链接'], selected['records'][0]['url'])
        self.assertEqual(rows[0]['脚注锚点'], 'user-content-fn-1')
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核'] == '待复核' for row in rows))
        path = self.folder / 'chapter-001.json'
        path.write_text(path.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        with self.assertRaises(IntakeError):
            load_snapshot(self.folder)
        self.assertGreaterEqual(self.review()['flags']['source_hash_mismatch'], 1)

    def test_wikisource_counts_are_checked(self):
        result = parse_wiki(wiki_html())
        self.assertEqual(result['volume_counts'], [34, 23, 53, 12, 20, 20, 25, 29, 32])
        self.assertEqual((result['total_stories'], result['total_pages']), (248, 1498))
        with self.assertRaises(IntakeError):
            parse_wiki(wiki_html().replace('២៤៨'.encode('utf-8'), '២៤៩'.encode('utf-8')))


if __name__ == '__main__':
    unittest.main()
