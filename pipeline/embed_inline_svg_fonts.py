"""Embed CJK fonts in SVG images nested inside previously rendered handbook figures."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil

from fontTools.ttLib import TTFont

from pipeline.embed_handbook_svg_fonts import embed_nested_svgs


def prepare(source: Path, output: Path, noto: Path, noto_license: Path, fallback: Path) -> dict:
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError('输出目录不能位于图表源目录中。')
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    with TTFont(noto, lazy=True) as font:
        cmap = set(font.getBestCmap())
    output.mkdir(parents=True, exist_ok=True)
    cache, changed, count = {}, [], 0
    for item in manifest['figures'].values():
        name = item['file']
        if Path(name).name != name:
            raise ValueError(f'不安全的图表文件名：{name}')
        raw = (source / name).read_bytes()
        if sha256(raw).hexdigest() != item['sha256']:
            raise ValueError(f'源图与清单不符：{name}')
        processed, nested = embed_nested_svgs(raw, noto, fallback, cmap, cache)
        (output / name).write_bytes(processed)
        item['sha256'] = sha256(processed).hexdigest()
        count += nested
        if nested:
            changed.append({'file': name, 'nested_svgs': nested})
    shutil.copy2(noto_license, output / 'FONT_LICENSE_Noto.txt')
    shutil.copy2(fallback.parent / 'OFL.txt', output / 'FONT_LICENSE.txt')
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    (output / 'nested-font-report.json').write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'figures': len(manifest['figures']), 'changed_figures': len(changed), 'nested_svgs': count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--noto', type=Path, required=True)
    parser.add_argument('--noto-license', type=Path, required=True)
    parser.add_argument('--fallback', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.noto, args.noto_license, args.fallback), ensure_ascii=False))


if __name__ == '__main__':
    main()
