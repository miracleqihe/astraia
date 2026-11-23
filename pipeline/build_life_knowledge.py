"""Index the supplied handbook without changing its original text or citations.

Example: python -m pipeline.build_life_knowledge --source handbook.qmd --pdf handbook.pdf
The PDF is indexed with Poppler; the original PDF remains the authority for figures.
"""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTRY = re.compile(r'^###\s+`([^`]+)`\s*[—–-]\s*(.+)$', re.M)
HEADINGS = re.compile(r'^(#|##|###)\s+(.+)$', re.M)
PDF_HEAD = re.compile(r'(?m)^([A-Z]{2,4}-(?:[A-Z0-9]+-)*[0-9]{3,4})\s*[—–-]\s*')
FIGURES = re.compile(r'!\[[^\]]*\]\((figures/[^)]+)\)')
TYPST = re.compile(r'^```\{=typst\}\s*\n[\s\S]*?^```\s*$', re.M)
ENTRY_LINK = re.compile(r'\]\(#entry-([a-z0-9-]+)\)')


def build(source: Path, pdf: Path, pdftotext: str) -> dict:
    text = source.read_text(encoding='utf-8')
    entries = list(ENTRY.finditer(text))
    ids = [m[1] for m in entries]
    if len(ids) != 2266 or len(set(ids)) != len(ids):
        raise ValueError('手册条目数量或编号不符合预期，未生成。')
    # Poppler performs text extraction; retain the PDF itself for exact diagrams and layout.
    with tempfile.TemporaryDirectory() as tmp:
        extracted = Path(tmp) / 'book.txt'
        subprocess.run([pdftotext, '-raw', '-enc', 'UTF-8', str(pdf), str(extracted)], check=True)
        pages = extracted.read_text(encoding='utf-8').split('\f')
    candidates = {}
    for page_no, page in enumerate(pages, 1):
        for match in PDF_HEAD.finditer(page):
            if match[1] in ids:
                candidates.setdefault(match[1], []).append(page_no)
    pages_by_id = {}
    previous = 1
    for node_id in ids:
        possible = [p for p in candidates.get(node_id, []) if p >= previous]
        if not possible:
            raise ValueError(f'PDF 缺少按正文顺序排列的条目：{node_id}')
        previous = min(possible)
        pages_by_id[node_id] = previous

    headings = list(HEADINGS.finditer(text))
    volumes, subjects, rows = [], {}, []
    anchor_owners, raw_by_id = {}, {}
    volume = subject = None
    entry_by_start = {m.start(): m for m in entries}
    for i, heading in enumerate(headings):
        level, value = heading.groups()
        if level == '#':
            volume = re.sub(r'\s*\{#[^}]+\}\s*$', '', value)
            if volume not in volumes:
                volumes.append(volume)
        elif level == '##':
            m = re.match(r'([A-Z]{2,4})\s+(.+?)\s*\{#[^}]+\}\s*$', value)
            subject = m[1] if m else None
            if m:
                subjects[subject] = {'id': subject, 'title': m[2], 'volume': volume}
        elif heading.start() in entry_by_start:
            m = entry_by_start[heading.start()]
            if not subject or not volume:
                raise ValueError(f'条目缺少学科：{m[1]}')
            title = re.sub(r'\s*\{#[^}]+\}\s*$', '', m[2])
            topic_match = re.search(r'\s*〔([^〕]+)〕\s*$', title)
            topic = topic_match[1] if topic_match else ''
            title = re.sub(r'\s*〔[^〕]+〕\s*$', '', title)
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            raw = text[m.end():end].strip()
            raw_by_id[m[1]] = raw
            for anchor in re.findall(r'\{#([a-z0-9-]+)\}', raw):
                if anchor in anchor_owners and anchor_owners[anchor] != m[1]:
                    raise ValueError(f'手册锚点重复：{anchor}')
                anchor_owners[anchor] = m[1]
            links = list(dict.fromkeys(ref.upper() for ref in ENTRY_LINK.findall(raw)))
            if any(ref not in ids for ref in links):
                raise ValueError(f'手册交叉链接缺少目标：{m[1]}')
            readable = TYPST.sub('\n\n**原书图表及其说明**：请打开下方的原书图文。\n\n', raw)
            readable = re.sub(r'(?m)^(#{4,6}\s+.*?)\s*\{#([a-z0-9-]+)\}\s*$',
                              lambda h: f'{h[1]} ⟦anchor:{h[2]}⟧', readable)
            readable = re.sub(r'(?m)^\[\]\{#([a-z0-9-]+)\}\s*$',
                              lambda a: f'⟦anchor:{a[1]}⟧', readable)
            readable = re.sub(r'\s*\{(?:#[^}]+|width=[^}]+)\}', '', readable)
            rows.append({'id': m[1], 'title': title, 'topic': topic, 'subject': subject,
                         'volume': volume, 'page': pages_by_id[m[1]], 'links': links, 'body': readable})

    if len(rows) != 2266 or len(subjects) != 20:
        raise ValueError('提取后的条目或学科数量不正确。')
    for row in rows:
        for anchor in re.findall(r'\]\(#(?!entry-)([a-z0-9-]+)\)', row['body']):
            target = anchor_owners.get(anchor)
            if not target:
                raise ValueError(f'手册内部锚点缺少目标：{anchor}')
            if target != row['id'] and target not in row['links']:
                row['links'].append(target)
        # Separate UTF-8 drafts keep original text and the same resolved cross-references.
        path = ROOT / 'knowledge/entries' / row['subject'] / (row['id'] + '.md')
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {k: row[k] for k in ('id', 'title', 'topic', 'subject', 'volume', 'page', 'links')}
        metadata['source'] = '格物识微_全书增绘_20261121.pdf'
        path.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
                        + '---\n\n' + raw_by_id[row['id']] + '\n', encoding='utf-8', newline='\n')
    counts = Counter(row['subject'] for row in rows)
    for key, value in subjects.items():
        value['count'] = counts[key]

    public = ROOT / 'web/public/knowledge'
    public.mkdir(parents=True, exist_ok=True)
    for ref in set(FIGURES.findall(text)):
        if '..' in Path(ref).parts:
            raise ValueError(f'图像路径不正确：{ref}')
        original = source.parent / ref
        if not original.is_file():
            original = public / ref
        if not original.is_file():
            raise ValueError(f'原书图像缺失：{ref}')
        target = public / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        if original.resolve() != target.resolve():
            shutil.copy2(original, target)
    target_pdf = public / 'handbook.pdf'
    if pdf.resolve() != target_pdf.resolve():
        shutil.copy2(pdf, target_pdf)
    saved_source = ROOT / 'knowledge/handbook.qmd'
    saved_source.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != saved_source.resolve():
        shutil.copy2(source, saved_source)
    data = {'title': '格物识微', 'edition': '全书增绘版 · 2026-11-21',
            'source_sha256': sha256(pdf.read_bytes()).hexdigest(), 'subjects': list(subjects.values()),
            'anchors': anchor_owners, 'entries': rows}
    (public / 'data.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    return {'entries': len(rows), 'subjects': len(subjects), 'volumes': len({r['volume'] for r in rows}),
            'explicit_links': sum(len(r['links']) for r in rows), 'figures': len(set(FIGURES.findall(text))),
            'pdf_sha256': data['source_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--pdftotext', default=shutil.which('pdftotext') or 'pdftotext')
    args = parser.parse_args()
    print(json.dumps(build(args.source.resolve(), args.pdf.resolve(), args.pdftotext), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
