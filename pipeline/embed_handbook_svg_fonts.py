"""Make original SVG diagrams self-contained by embedding licensed glyph subsets.

Run into a separate directory, inspect the result, then copy the verified files
to web/public/knowledge/figures. Original SVG text remains selectable in SVG
viewers; no system CJK font is needed to display the result as an image.
"""

import argparse
import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'ASTRAIA_EMBEDDED_FIGURE_FONT'
NESTED_SVG = re.compile(rb'data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)')


def text_in_svg(raw: bytes) -> str:
    root = ET.fromstring(raw)
    return ''.join(''.join(element.itertext()) for element in root.iter()
                   if element.tag.rsplit('}', 1)[-1] == 'text')


def font_subset(path: Path, text: str) -> bytes:
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        missing = sorted({character for character in text if not character.isspace() and ord(character) not in cmap})
        if missing:
            raise ValueError(f'{path.name} 缺少字形：{"".join(missing)}')
        options = subset.Options()
        options.flavor = 'woff2'
        options.name_IDs = ['*']; options.name_legacy = True; options.name_languages = ['*']
        worker = subset.Subsetter(options=options)
        worker.populate(text=text)
        worker.subset(font)
        family, ps = 'Astraia Figure', 'AstraiaFigure-Regular'
        names = {1: family, 2: 'Regular', 3: family, 4: family, 6: ps,
                 16: family, 17: 'Regular', 18: family, 21: family, 22: 'Regular', 25: 'AstraiaFigure'}
        for record in font['name'].names:
            if record.nameID in names:
                record.string = names[record.nameID].encode(record.getEncoding())
        if 'CFF ' in font:
            cff = font['CFF '].cff
            cff.fontNames = [ps]
            cff.topDictIndex[0].FullName = family
            cff.topDictIndex[0].FamilyName = family
        font.flavor = 'woff2'
        buffer = BytesIO()
        font.save(buffer)
    result = buffer.getvalue()
    with TTFont(BytesIO(result)) as verify:
        cmap = verify.getBestCmap()
        if any(ord(character) not in cmap for character in text if not character.isspace()):
            raise ValueError('嵌入字体的字形校验失败。')
    return result


def embed_svg(raw: bytes, noto: Path, fallback: Path, noto_cmap: set[int], cache: dict) -> tuple[bytes, Path | None]:
    if MARKER.encode() in raw:
        raise ValueError('源图已内嵌过字体，请使用原始 SVG。')
    text = text_in_svg(raw)
    if not text:
        return raw, None
    chosen = fallback if any(ord(c) not in noto_cmap for c in text if not c.isspace()) else noto
    key = (str(chosen), ''.join(sorted(set(text))))
    if key not in cache:
        cache[key] = font_subset(chosen, key[1])
    encoded = base64.b64encode(cache[key]).decode('ascii')
    style = (f'<!-- {MARKER}: SIL OFL 1.1, see FONT_LICENSE files -->'
             f'<style>@font-face{{font-family:"Astraia Figure";src:url(data:font/woff2;base64,{encoded}) '
             f'format("woff2");font-style:normal;font-weight:400}}'
             f'text,tspan{{font-family:"Astraia Figure" !important}}</style>')
    xml = raw.decode('utf-8')
    match = re.search(r'<svg\b[^>]*>', xml)
    if not match:
        raise ValueError('没有找到 SVG 根元素。')
    result = (xml[:match.end()] + style + xml[match.end():]).encode('utf-8')
    if text_in_svg(result) != text:
        raise ValueError('嵌入字体时改变了图中文字。')
    return result, chosen


def embed_nested_svgs(raw: bytes, noto: Path, fallback: Path, noto_cmap: set[int], cache: dict) -> tuple[bytes, int]:
    """Embed fonts in SVG images nested in Typst's self-contained outer SVG."""
    changed = 0
    def replace(match: re.Match) -> bytes:
        nonlocal changed
        nested = base64.b64decode(match[1], validate=True)
        if not text_in_svg(nested) or MARKER.encode() in nested:
            return match[0]
        embedded, _ = embed_svg(nested, noto, fallback, noto_cmap, cache)
        changed += 1
        return b'data:image/svg+xml;base64,' + base64.b64encode(embedded)
    result = NESTED_SVG.sub(replace, raw)
    ET.fromstring(result)
    return result, changed


def prepare(source: Path, output: Path, noto: Path, fallback: Path, limit: int | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with TTFont(noto, lazy=True) as font:
        noto_cmap = set(font.getBestCmap())
    cache, report = {}, []
    paths = sorted(source.rglob('*.svg'))
    if limit is not None:
        paths = paths[:limit]
    for index, path in enumerate(paths, 1):
        raw = path.read_bytes()
        text = text_in_svg(raw)
        target = output / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        result, chosen = embed_svg(raw, noto, fallback, noto_cmap, cache)
        target.write_bytes(result)
        report.append({'file': path.relative_to(source).as_posix(), 'source_sha256': sha256(raw).hexdigest(),
                       'result_sha256': sha256(result).hexdigest(), 'characters': len(set(text)),
                       'font': chosen.name if chosen else None})
        if index % 50 == 0 or index == len(paths):
            print(f'SVG 字体 {index}/{len(paths)}', flush=True)
    shutil.copy2(ROOT / 'web/node_modules/@fontsource/noto-sans-sc/LICENSE', output / 'FONT_LICENSE_Noto.txt')
    shutil.copy2(fallback.parent / 'OFL.txt', output / 'FONT_LICENSE_LXGW.txt')
    (output / 'font-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'files': len(report), 'with_text': sum(bool(item['font']) for item in report),
            'fallback': sum(item['font'] == fallback.name for item in report)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'web/public/knowledge/figures')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--noto', type=Path, required=True)
    parser.add_argument('--fallback', type=Path, required=True)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.source.resolve()):
        raise ValueError('输出目录不能位于原始图表目录中。')
    print(json.dumps(prepare(args.source, args.output, args.noto, args.fallback, args.limit), ensure_ascii=False))


if __name__ == '__main__':
    main()
