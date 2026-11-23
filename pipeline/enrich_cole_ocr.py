"""Attach page-exact OCR candidates to existing, unreviewed Cole drafts."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from pipeline.cole_ocr_segments import load
from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT, literal_block
from pipeline.intake_sources import IntakeError
from pipeline.node_model import Source
from pipeline.philippines_cole import BOOK_URL, TOC, _local, scan_url
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

MARKER = '<!-- astraia:cole-ocr-pages-v1 -->'


def note(segment: dict) -> str:
    lines = ['', MARKER, '## 扫描分页 OCR（待校）', '',
             '以下保留本地扫描 OCR 的原有文字、页眉、脚注、误字及换行；OCR 不等于校对后的原文。'
             '页面范围以目录项候选起始页和下一候选起始页截取，最后一项截至后续发音表候选页；'
             '这不能证明篇章边界，须逐页核对原扫描。', '']
    for page in segment['pages']:
        lines.extend([f"### 候选扫描页 {page['scan']}", '', f"[查看该页原扫描]({page['scan_url']})", '',
                      literal_block(page['text']), ''])
    return '\n'.join(lines)


def segment_sources(segment: dict, folder: Path) -> list[Source]:
    page_file = folder / (segment['id'] + '.json')
    manifest_file = folder / 'manifest.json'
    return [Source.model_validate({'citation': '项目根据本地原始 OCR 与分页索引截取的未校对候选页面。',
        'type': 'cole_ocr_segments', 'url': scan_url(segment['start_scan']),
        'locator': f"目录印刷页 {segment['printed_page']} / 候选扫描序号 {segment['start_scan']}–{segment['end_scan_exclusive'] - 1}",
        'local_path': _local(page_file), 'content_sha256': sha256(page_file.read_bytes()).hexdigest()}),
        Source.model_validate({'citation': '项目生成的 OCR 逐页候选范围清单；范围和文字均待人工核对。',
        'type': 'cole_ocr_segments_manifest', 'url': BOOK_URL, 'locator': 'OCR 逐页范围清单',
        'local_path': _local(manifest_file), 'content_sha256': sha256(manifest_file.read_bytes()).hexdigest()})]


def enrich(vault: Path, folder: Path, toc: Path, snapshots: Path, *, check: bool = False) -> dict:
    manifest, segments = load(folder, toc, snapshots)
    plans, already = [], 0
    with vault_writer(vault):
        for segment in segments:
            path = vault / '00_drafts/asia_ph_cole_1916' / (segment['id'] + '.md')
            if not path.is_file() or path.is_symlink():
                raise IntakeError(f'草稿不存在或是符号链接：{path}')
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            metadata, body = parse_card(text.replace('\r\n', '\n'))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                raise IntakeError(f'已复核或示例草稿不能自动修改：{path}')
            required = {'cole_toc_index': manifest['toc_sha256'], 'cole_ocr': manifest['ocr_sha256'],
                        'cole_page_index': manifest['page_index_sha256']}
            groups = {kind: [s for s in metadata.sources if s.type == kind] for kind in required}
            scans = [s for s in metadata.sources if s.type == 'cole_scan_link']
            if (metadata.id != segment['id'] or metadata.node_type != 'case'
                    or any(len(groups[k]) != 1 or groups[k][0].content_sha256 != digest for k, digest in required.items())
                    or len(scans) != 1 or str(scans[0].url) != scan_url(segment['start_scan'])):
                raise IntakeError(f'原草稿档号或来源不符：{path}')
            additions = segment_sources(segment, folder)
            previous = [s for s in metadata.sources if s.type in {'cole_ocr_segments', 'cole_ocr_segments_manifest'}]
            if MARKER in text or previous:
                if previous != additions or note(segment).strip() not in body:
                    raise IntakeError(f'草稿已有不同的 OCR 内容或来源；保留现有内容：{path}')
                already += 1
                continue
            revised = append_sources(text, additions) + note(segment)
            new_meta, new_body = parse_card(revised.replace('\r\n', '\n'))
            if (metadata.model_dump(exclude={'sources'}) != new_meta.model_dump(exclude={'sources'})
                    or new_meta.sources != metadata.sources + additions or not new_body.startswith(body)):
                raise IntakeError(f'补充 OCR 时原草稿字段或正文发生变化：{path}')
            encoded = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + revised.encode('utf-8')
            plans.append((path, raw, encoded))
        if not check:
            staged, changed = [], []
            try:
                for path, original, revised in plans:
                    with NamedTemporaryFile(dir=path.parent, prefix='.cole-ocr-', delete=False) as stream:
                        temporary = Path(stream.name)
                        staged.append(temporary)
                        stream.write(revised)
                if any(path.read_bytes() != original for path, original, _ in plans):
                    raise IntakeError('草稿在补充 OCR 时发生变化；未写入。')
                for (path, original, revised), temporary in zip(plans, staged, strict=True):
                    if path.read_bytes() != original:
                        raise IntakeError(f'草稿在补充 OCR 时发生变化：{path}')
                    temporary.replace(path)
                    changed.append((path, original, revised))
            except Exception:
                for path, original, revised in reversed(changed):
                    if path.read_bytes() != revised:
                        raise IntakeError(f'回滚时发现外部修改，保留该草稿：{path}')
                    with NamedTemporaryFile(dir=path.parent, prefix='.cole-rollback-', delete=False) as stream:
                        rollback = Path(stream.name)
                        stream.write(original)
                    try:
                        rollback.replace(path)
                    finally:
                        rollback.unlink(missing_ok=True)
                raise
            finally:
                for temporary in staged:
                    temporary.unlink(missing_ok=True)
    return {'cards_to_update': len(plans), 'already_enriched': already, 'check': check,
            'changes': [{'id': path.stem, 'before': sha256(raw).hexdigest(), 'after': sha256(revised).hexdigest()}
                        for path, raw, revised in plans]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--segments', type=Path, required=True)
    parser.add_argument('--toc', type=Path, default=TOC)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = enrich(args.vault.resolve(), args.segments.resolve(), args.toc.resolve(), args.snapshots.resolve(), check=args.check)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
