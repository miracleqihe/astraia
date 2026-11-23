from hashlib import sha256
import base64
from io import BytesIO
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from pipeline.build_life_knowledge import is_layout_wrapper, typst_body


ROOT = Path(__file__).resolve().parents[1]


class LifeFigureTests(unittest.TestCase):
    def test_figure_identity_survives_entry_boundary_whitespace(self):
        block = '```{=typst}\n#text[图中文字]\n```\n\n'
        digest = lambda text: sha256(typst_body(text).encode('utf-8')).hexdigest()
        self.assertEqual(digest(block), digest(block.strip()))
        self.assertTrue(is_layout_wrapper('```{=typst}\n#block(width: 100%)[\n```'))
        self.assertTrue(is_layout_wrapper('```{=typst}\n]\n```'))
        self.assertFalse(is_layout_wrapper(block))


    def test_all_handbook_figures_are_assigned_and_self_contained(self):
        folder = ROOT / 'web/public/knowledge/inline-figures'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        book = json.loads((folder.parent / 'data.json').read_text(encoding='utf-8'))
        source = (ROOT / 'knowledge/handbook.qmd').read_text(encoding='utf-8')
        self.assertEqual(manifest['source_sha256'], sha256(source.encode('utf-8')).hexdigest())
        self.assertEqual(manifest['block_count'], 750)
        self.assertEqual(manifest['figure_count'], 438)
        self.assertEqual(manifest['unique_count'], 438)
        assigned = [ref for entry in book['entries'] for ref in entry['figure_refs']]
        self.assertEqual(len(assigned), 438)
        self.assertEqual(set(assigned), set(book['figures']))
        self.assertEqual(set(assigned), {x['file'] for x in manifest['figures'].values()})
        for item in manifest['figures'].values():
            with self.subTest(figure=item['file']):
                self.assertEqual(Path(item['file']).name, item['file'])
                self.assertTrue(item['text'])
                self.assertTrue(all(urlsplit(link).scheme in {'http', 'https'} for link in item['links']))
                self.assertEqual(sha256((folder / item['file']).read_bytes()).hexdigest(), item['sha256'])
                self.assertEqual(book['figures'][item['file']], {'text': item['text'], 'links': item['links']})

    def test_original_svg_chinese_glyphs_are_self_contained(self):
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest('需要 figures 可选依赖来检查图中文字的字形')
        folder = ROOT / 'web/public/knowledge/figures'
        report = json.loads((folder / 'font-report.json').read_text(encoding='utf-8'))
        self.assertEqual(len(report), 285)

        def verify(raw):
            root = ET.fromstring(raw)
            labels = ''.join(''.join(element.itertext()) for element in root.iter()
                             if element.tag.rsplit('}', 1)[-1] == 'text')
            if not labels:
                return False
            self.assertIn(b'ASTRAIA_EMBEDDED_FIGURE_FONT', raw)
            match = re.search(rb'data:font/woff2;base64,([A-Za-z0-9+/=]+)', raw)
            self.assertIsNotNone(match)
            with TTFont(BytesIO(base64.b64decode(match[1], validate=True))) as font:
                cmap = font.getBestCmap()
                self.assertFalse({c for c in labels if not c.isspace() and ord(c) not in cmap})
            return True

        count = 0
        for item in report:
            with self.subTest(figure=item['file']):
                data = (folder / item['file']).read_bytes()
                self.assertEqual(sha256(data).hexdigest(), item['result_sha256'])
                count += verify(data)
        self.assertEqual(count, 283)
        nested_count = 0
        for path in (folder.parent / 'inline-figures').glob('*.svg'):
            for match in re.finditer(rb'data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)', path.read_bytes()):
                nested_count += verify(base64.b64decode(match[1], validate=True))
        self.assertEqual(nested_count, 18)


if __name__ == '__main__':
    unittest.main()
