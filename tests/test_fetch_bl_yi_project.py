from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline import fetch_bl_yi_project as project
from pipeline.intake_sources import IntakeError
from tests.test_southeast_archives import definition


def page(number, total=201, duplicate=False, changed=False):
    first = (number - 1) * 100 + 1
    end = min(number * 100, total)
    docs = []
    for value in range(first, end + 1):
        shelf = f'EAP081/1/{value}'
        record = 1 if duplicate and value == 201 else value
        title = 'Changed' if changed and value == 1 else f'Title {value}'
        fields = {'Reference (shelfmark)': shelf, 'Title': title,
                  'Scope & Content': 'Book of oral literature.', 'Languages': 'Nuosu', 'Extent': '32 TIFF images'}
        definitions = ''.join(definition(key, val) for key, val in fields.items())
        docs.append(f'<div class="document"><h2><a href="/catalog/040-{record:09}">{shelf}</a></h2><dl>{definitions}</dl></div>')
    return ('<html><head><title>British Library Archives and Manuscripts Catalogue</title>'
            f'<meta name="totalResults" content="{total}"></head><body>'
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY</a>'
            '<div id="documents">' + ''.join(docs) + '</div></body></html>').encode()


def receipt(number, raw):
    return {'url': project.page_url(number), 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
            'observed_at': '2026-11-23T00:00:00+00:00'}


class YiProjectFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'snapshot'

    def test_complete_pages_and_boundary_checks_are_reconstructable(self):
        calls = []
        def request(number, robots, delay):
            calls.append(number); raw = page(number); return raw, receipt(number, raw)
        with redirect_stdout(StringIO()), patch('pipeline.fetch_bl_yi_project.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_yi_project.request_page', side_effect=request):
            manifest = project.fetch(self.folder)
            self.assertEqual(calls, [1, 2, 3, 1, 3])
            project.fetch(self.folder)
            self.assertEqual(calls, [1, 2, 3, 1, 3])
        loaded, rows = project.load_snapshot(self.folder)
        self.assertEqual(manifest['total'], 201); self.assertEqual(len(rows), 201)
        self.assertEqual([item['count'] for item in loaded['pages']], [100, 100, 1])
        self.assertEqual(rows[-1]['fields']['Scope & Content'], 'Book of oral literature.')
        with (self.folder / 'page-02.html').open('ab') as stream: stream.write(b' ')
        with self.assertRaises(IntakeError): project.load_snapshot(self.folder)

    def test_changed_boundary_refuses_to_publish_manifest(self):
        seen = []
        def request(number, robots, delay):
            seen.append(number)
            raw = page(number, changed=(number == 1 and seen.count(1) == 2))
            return raw, receipt(number, raw)
        with redirect_stdout(StringIO()), patch('pipeline.fetch_bl_yi_project.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_yi_project.request_page', side_effect=request):
            with self.assertRaisesRegex(IntakeError, '采集期间变化'): project.fetch(self.folder)
        self.assertFalse((self.folder / 'manifest.json').exists())

    def test_duplicate_ids_and_changed_total_are_rejected(self):
        def request(number, robots, delay):
            raw = page(number, duplicate=True); return raw, receipt(number, raw)
        with redirect_stdout(StringIO()), patch('pipeline.fetch_bl_yi_project.robot_rules', return_value=(None, '200')), \
             patch('pipeline.fetch_bl_yi_project.request_page', side_effect=request):
            with self.assertRaisesRegex(IntakeError, '重复'): project.fetch(self.folder)
        with self.assertRaises(IntakeError): project.parse_page(page(1, total=201), 1, expected_total=202)


if __name__ == '__main__': unittest.main()
