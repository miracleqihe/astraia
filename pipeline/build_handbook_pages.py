"""Render on-demand handbook page images and verify the source text with two PDF engines.

The page numbers are physical PDF pages, matching build_life_knowledge.py.
This command does not rewrite or redistribute a new PDF.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
import re
import subprocess
import tempfile
from pathlib import Path

import pypdfium2 as pdfium

_doc = None
HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0002fa1f]')


def init_worker(pdf: str) -> None:
    global _doc
    _doc = pdfium.PdfDocument(pdf)


def render_page(index: int) -> tuple[int, str, bytes, int, int]:
    page = _doc[index]
    textpage = page.get_textpage()
    text = textpage.get_text_range()
    textpage.close()
    bitmap = page.render(scale=1.8)
    image = bitmap.to_pil().convert('RGB')
    bitmap.close()
    page.close()
    output = BytesIO()
    image.save(output, format='WEBP', quality=86, method=4)
    return index + 1, text, output.getvalue(), image.width, image.height


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, default=Path('web/public/knowledge/handbook.pdf'))
    parser.add_argument('--book', type=Path, default=Path('web/public/knowledge/data.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise ValueError('Use between one and eight render workers.')
    if args.output.is_symlink():
        raise ValueError('The page output must not be a symbolic link.')
    pdf, book_path, output = args.pdf.resolve(), args.book.resolve(), args.output.resolve()
    book_bytes = book_path.read_bytes()
    book = json.loads(book_bytes)
    if not isinstance(book.get('entries'), list) or not book.get('source_sha256'):
        raise ValueError('Invalid handbook data.')
    fonts = subprocess.run(['pdffonts', str(pdf)], check=True, capture_output=True, text=True, encoding='utf-8').stdout.splitlines()[2:]
    if not fonts:
        raise ValueError('PDF has no fonts that can be checked for embedding and ToUnicode.')
    for line in fonts:
        match = re.search(r'\s(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$', line)
        if not match or match.group(1) != 'yes' or match.group(3) != 'yes':
            raise ValueError(f'PDF font lacks embedding or ToUnicode: {line}')
    with tempfile.TemporaryDirectory(prefix='astraia-pdf-text-') as tmp:
        text_path = Path(tmp) / 'handbook.txt'
        subprocess.run(['pdftotext', '-raw', '-enc', 'UTF-8', str(pdf), str(text_path)], check=True)
        poppler = text_path.read_text(encoding='utf-8').split('\f')
    pdf_doc = pdfium.PdfDocument(str(pdf))
    count = len(pdf_doc)
    pdf_doc.close()
    if len(poppler) == count + 1 and not poppler[-1].strip():
        poppler.pop()
    if len(poppler) != count:
        raise ValueError('Poppler and PDFium disagree about the page count.')
    expected: dict[int, list[str]] = {}
    for entry in book['entries']:
        page = entry['page']
        if not isinstance(page, int) or not 1 <= page <= count:
            raise ValueError(f'Invalid page for {entry["id"]}.')
        expected.setdefault(page, []).append(entry['id'])
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError('The page output must not be a symbolic link.')
    pages = []
    with ProcessPoolExecutor(max_workers=args.jobs, initializer=init_worker, initargs=(str(pdf),)) as pool:
        for number, text, data, width, height in pool.map(render_page, range(count), chunksize=4):
            # Both engines must decode the same Chinese glyphs on every page.
            poppler_han = set(HAN.findall(poppler[number - 1]))
            if not poppler_han or poppler_han != set(HAN.findall(text)):
                raise ValueError(f'Chinese extraction differs between PDF engines on page {number}.')
            compact = ''.join(text.split())
            for identifier in expected.get(number, []):
                if identifier not in compact:
                    raise ValueError(f'Entry {identifier} is not on PDF page {number}.')
            digest = sha256(data).hexdigest()
            filename = f'p{number:04d}-{digest[:16]}.webp'
            (output / filename).write_bytes(data)
            pages.append({'page': number, 'file': filename, 'sha256': digest, 'width': width, 'height': height})
    manifest = {'schema_version': 1, 'pdf_sha256': sha256(pdf.read_bytes()).hexdigest(),
                'book_sha256': sha256(book_bytes).hexdigest(), 'source_sha256': book['source_sha256'],
                'page_count': count, 'entry_count': len(book['entries']),
                'verification': {'fonts_embedded_and_unicode': True, 'chinese_text_engines': ['Poppler', 'PDFium'],
                                 'pages_compared': count, 'entry_pages_verified': len(book['entries'])},
                'pages': pages}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    print(f'Handbook: {count} page images; Chinese extraction and {len(book["entries"])} entry locations verified with Poppler and PDFium.')


if __name__ == '__main__':
    main()
