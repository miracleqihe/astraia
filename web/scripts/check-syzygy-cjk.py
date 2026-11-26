"""Audit CJK glyph coverage for the published graph, book, and Syzygy UI.

Run from the repository root with the project's ``figures`` dependencies
installed, after ``npm install`` in ``web``. Both font weights must pass.
"""

import json
from pathlib import Path
import sys

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
DATA = (ROOT / 'web/public/data/graph_data.json', ROOT / 'web/public/knowledge/data.json',
        ROOT / 'web/src/syzygy/bridges.json', ROOT / 'web/src/syzygy/matching-rules.json',
        ROOT / 'web/src/syzygy/matching-concepts.json', ROOT / 'web/src/syzygy/matching-relays.json',
        ROOT / 'web/src/syzygy/reading-paths.json')
UI = (list((ROOT / 'web/src/syzygy').glob('*.js')) + list((ROOT / 'web/src').glob('*.tsx'))
      + [ROOT / 'web/syzygy/index.html', ROOT / 'web/src/portalNavigation.ts',
         ROOT / 'web/src/engraving.ts'])
texts = [json.dumps(json.loads(path.read_text(encoding='utf-8')), ensure_ascii=False) for path in DATA]
texts.extend(path.read_text(encoding='utf-8') for path in UI)
used = {ord(char) for text in texts for char in text
        if 0x3400 <= ord(char) <= 0x9fff or 0x20000 <= ord(char) <= 0x2fa1f}
report = {}
for weight in ('400', '600'):
    fonts = list((ROOT / 'web/node_modules/@fontsource/noto-serif-sc/files').glob(f'noto-serif-sc-*-{weight}-normal.woff2'))
    if not fonts:
        raise SystemExit('Noto Serif SC is missing. Install the web dependencies first.')
    fonts += [ROOT / f'web/public/fonts/astraia-cjk-supplement-{weight}.woff2',
              ROOT / f'web/public/fonts/astraia-handbook-{weight}.woff2']
    covered = set()
    for path in fonts:
        with TTFont(path) as font:
            covered.update(font.getBestCmap() or {})
    missing = sorted(used - covered)
    report[weight] = {'characters': len(used), 'font_files': len(fonts),
                      'missing_count': len(missing), 'missing': ''.join(map(chr, missing))}
print(json.dumps(report, ensure_ascii=False, indent=2))
if any(item['missing_count'] for item in report.values()):
    sys.exit(1)
