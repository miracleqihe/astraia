"""Render the handbook's original Typst figures as self-contained inline SVGs.

The corresponding QMD and original figure assets are needed only to regenerate
these files. The output includes searchable text and original image-credit links.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import pypdfium2 as pdfium
import typst

from pipeline.build_life_knowledge import TYPST, is_layout_wrapper, typst_body
from pipeline.embed_handbook_svg_fonts import embed_nested_svgs
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'web/public/knowledge/inline-figures'
PREAMBLE = '''#set page(width: 182mm, height: auto, margin: 4mm, fill: rgb("#FDFBF7"))
#let sans-font = ("DengXian", "Noto Sans SC", "Microsoft YaHei", "Cambria", "Segoe UI Symbol", "Segoe UI Emoji")
#let serif-font = ("霞鶩文楷", "SimSun", "Noto Serif SC", "Cambria", "Segoe UI Symbol", "Segoe UI Emoji")
#set text(font: serif-font, weight: 400, size: 10.5pt, fill: rgb("#1E2430"), lang: "zh", region: "cn", fallback: false)
#set par(justify: true, leading: 0.68em, spacing: 0.60em, first-line-indent: 0pt)
'''


def svg_links(data: bytes) -> list[str]:
    root = ET.fromstring(data)
    if not root.tag.endswith('svg'):
        raise ValueError('图表不是 SVG。')
    links = []
    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1]
        if tag in {'script', 'foreignObject'}:
            raise ValueError(f'SVG 包含不支持的元素：{tag}')
        for key, value in element.attrib.items():
            if key.rsplit('}', 1)[-1] != 'href':
                continue
            if tag == 'image' and not (value.startswith('data:') or value.startswith('#')):
                raise ValueError('图表包含未内嵌的外部图片。')
            if tag == 'a' and urlsplit(value).scheme in {'http', 'https'} and value not in links:
                links.append(value)
    return links


def render(source: Path, assets_root: Path, output: Path, *, reuse_svg: bool = False,
           noto: Path | None = None, noto_license: Path | None = None) -> dict:
    source_text = source.read_text(encoding='utf-8')
    blocks = [match.group(0) for match in TYPST.finditer(source_text)]
    figures = [block for block in blocks if not is_layout_wrapper(block)]
    # Entry slicing removes surrounding whitespace, so key figures by their
    # Typst body rather than by whitespace outside the fenced block.
    unique = {sha256(typst_body(block).encode('utf-8')).hexdigest(): block for block in figures}
    if len(blocks) != 750:
        raise ValueError(f'原书图表数量发生变化：{len(blocks)}，请核对版次。')
    font_dir = assets_root / 'fonts'
    if not (font_dir / 'LXGWWenKai-Regular.ttf').is_file() or not (font_dir / 'OFL.txt').is_file():
        raise ValueError('缺少原书字体 LXGWWenKai-Regular.ttf，无法核验中文显示。')
    fallback = font_dir / 'LXGWWenKai-Regular.ttf'
    if noto and (not noto_license or not noto_license.is_file()):
        raise ValueError('使用额外的 Noto 字体时须提供其 SIL OFL 许可文件。')
    noto = noto or fallback
    with TTFont(noto, lazy=True) as font:
        noto_cmap = set(font.getBestCmap())
    font_cache = {}
    output.mkdir(parents=True, exist_ok=True)
    manifest, failures, warnings = {}, [], []
    for i, (digest, raw) in enumerate(unique.items(), 1):
        body = typst_body(raw)
        source_bytes = (PREAMBLE + body).encode('utf-8')
        try:
            filename = digest[:24] + '.svg'
            cached = output / filename
            if reuse_svg and cached.is_file():
                svg, svg_warnings = cached.read_bytes(), []
            else:
                svg, svg_warnings = typst.compile_with_warnings(source_bytes, root=str(assets_root),
                    font_paths=[str(font_dir)], format='svg')
            svg, _ = embed_nested_svgs(svg, noto, fallback, noto_cmap, font_cache)
            pdf, pdf_warnings = typst.compile_with_warnings(source_bytes, root=str(assets_root),
                font_paths=[str(font_dir)], format='pdf')
            if svg_warnings or pdf_warnings:
                warnings.append({'figure': digest, 'messages': [str(item) for item in svg_warnings + pdf_warnings]})
            links = svg_links(svg)
            document = pdfium.PdfDocument(pdf)
            if len(document) != 1:
                raise ValueError('图表输出超过一页。')
            page = document[0]
            textpage = page.get_textpage()
            transcript = re.sub(r'\s+', ' ', textpage.get_text_range()).strip()
            textpage.close(); page.close(); document.close()
            (output / filename).write_bytes(svg)
            manifest[digest] = {'file': filename, 'sha256': sha256(svg).hexdigest(),
                                'text': transcript, 'links': links}
        except Exception as exc:
            failures.append({'figure': digest, 'error': str(exc)})
        if i % 50 == 0 or i == len(unique):
            print(f'图表 {i}/{len(unique)}；失败 {len(failures)}；警告 {len(warnings)}', flush=True)
    if failures or warnings:
        (output / 'render-errors.json').write_text(json.dumps({'failures': failures, 'warnings': warnings},
            ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        raise ValueError(f'图表生成有 {len(failures)} 项失败、{len(warnings)} 项警告，未更新清单。')
    shutil.copy2(font_dir / 'OFL.txt', output / 'FONT_LICENSE.txt')
    if noto_license:
        shutil.copy2(noto_license, output / 'FONT_LICENSE_Noto.txt')
    result = {'version': 1, 'source_sha256': sha256(source_text.encode('utf-8')).hexdigest(),
              'block_count': len(blocks), 'figure_count': len(figures), 'unique_count': len(unique), 'figures': manifest}
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    return {'blocks': len(blocks), 'figures': len(figures), 'layout_wrappers': len(blocks)-len(figures),
            'unique': len(unique), 'with_text': sum(bool(v['text']) for v in manifest.values()),
            'with_links': sum(bool(v['links']) for v in manifest.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'knowledge/handbook.qmd')
    parser.add_argument('--assets-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--noto', type=Path, help='可选的 Noto Sans SC 字体文件，用于内嵌原书 SVG 图中文字')
    parser.add_argument('--noto-license', type=Path, help='Noto 字体的 SIL OFL 许可文件')
    parser.add_argument('--reuse-svg', action='store_true', help='复用同目录下已成功生成的 SVG')
    args = parser.parse_args()
    try:
        print(json.dumps(render(args.source.resolve(), args.assets_root.resolve(), args.output.resolve(),
                                reuse_svg=args.reuse_svg, noto=args.noto.resolve() if args.noto else None,
                                noto_license=args.noto_license.resolve() if args.noto_license else None), ensure_ascii=False))
    except (OSError, ValueError, typst.TypstError) as error:
        print(f'图表未生成：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
