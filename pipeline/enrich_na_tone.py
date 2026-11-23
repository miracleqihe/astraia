"""Add published Na book cross-references to pending drafts without approving them."""

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from pipeline.ingest_agent import DEFAULT_CODE_TABLE, DEFAULT_VAULT, literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.na_tone_book import BOOK_DOI, BOOK_SHA, CORPUS_SHA, TEX_SHA
from pipeline.na_tone_crosswalk import load as load_index
from pipeline.node_model import NodeMetadata, Source
from pipeline.pangloss_na import CORPUS_URL, ROOT_ID, catalogue_rows
from pipeline.pangloss_na_catalogue import PREFIX, validate_selection as validate_na_selection
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

MARKER = '<!-- astraia:na-tone-book-v1 -->'
NEW_MARKER = 'na_tone_catalogue_candidate'
BOOK_PAGE = 'https://zenodo.org/records/15275071/files/513-Michaud-2025.pdf'
TABLE_SOURCE_URL = 'https://github.com/langsci/513/blob/5d1c2728bc2996ee663cf6a2b0c3e15530b8e1a5/indexed/abbreviations.tex'
FLAG_TEXT = {
    'book_table_doi_reused_across_topics': '专著目录将同一录音号列在多个不同题名下，须逐项核对。',
    'book_catalogue_version_label_differs': '专著目录的版本序号与馆方录音题名中的版本序号不同。',
    'rights_label_uri_differ': 'DataCite 权利名称与其许可链接的 ShareAlike 标记不一致，须查原资源许可。',
    'datacite_primary_disagrees': 'DataCite 注册目标与馆方目录主资源标识不同。',
    'datacite_record_type_disagrees': 'DataCite 注册类型与馆方目录录音类型不同。',
    'book_fragment_unclassified': '书中存在未说明形式的链接片段，不自动当作分句号。',
    'datacite_404': 'DataCite 本次未返回公开注册记录，不能据此认定资源不存在。',
    'datacite_missing': '未取得该 DOI 的公开登记元数据。',
    'primary_not_unique': '主资源标识在馆藏目录中并不唯一。',
    'primary_not_in_catalogue': '主资源标识未在现有目录快照找到。',
    'datacite_relation_unresolved': 'DataCite 的文本与录音关系未能按严格规则确认。',
}


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def summary(index: dict, number: str) -> dict:
    item = index['recordings'][number]
    ids = sorted({link['doi_id'] for link in item['links']})
    registry = []
    for identifier in ids:
        mapping = index['mappings'][identifier]
        if mapping['datacite_checked']:
            registry.append({'书中 DOI 编号': identifier, '登记类型': mapping['datacite_type'],
                             '登记题名原字段': mapping['datacite_titles'], '登记目标原字段': mapping['datacite_url'],
                             '登记权利原字段': mapping['datacite_rights'], '对应依据': mapping['basis'],
                             '登记疑点': mapping['flags']})
    return {'馆方录音号': number, '馆方目录题名': item['catalogue_title'],
            '专著叙事目录': item['table_mentions'], '专著中链接': item['links'],
            'DataCite 登记对照': registry, '待核标记': item['flags']}


def note(index: dict, number: str) -> str:
    item = index['recordings'][number]
    data = summary(index, number)
    lines = ['', MARKER, '## 出版专著的录音与分句引用（待核）', '',
             literal_block(json.dumps(data, ensure_ascii=False, indent=2)), '',
             '这是 2025 年专著 PDF 中实际存在的链接及公开 DOI 登记对照；不代表已读取或校对对应录音和转写。'
             '音频与文本可能是不同 DOI：只有主资源标识及 Requires 关系均唯一对应时，才列为待核关联。'
             '书中未说明的片段不自动解释为分句号。专著 CC BY 4.0 不决定音频、转写或社群资料的许可。']
    for flag in item['flags']:
        lines.append(f"- 待核：{FLAG_TEXT.get(flag, flag)}")
    for link in item['links']:
        fragment = f"#{link['fragment']}" if link['fragment'] else ''
        lines.append(f"- [书中 PDF 第 {link['pdf_page']} 页]({BOOK_PAGE}#page={link['pdf_page']}) · "
                     f"[DOI {link['doi_id']}{fragment}]({link['url']})")
    return '\n'.join(lines) + '\n'


def sources(index: dict, number: str, book: Path, tex: Path, index_path: Path, datacite: Path) -> list[Source]:
    pages = sorted({link['pdf_page'] for link in index['recordings'][number]['links']})
    manifest = datacite / 'manifest.json'
    values = [
        {'citation': 'Alexis Michaud, Tone in Yongning Na, 2nd ed., Language Science Press, 2025, CC BY 4.0.',
         'type': 'na_tone_book', 'url': BOOK_PAGE, 'doi': BOOK_DOI,
         'locator': '出版 PDF 页：' + '、'.join(map(str, pages)), 'local_path': display_path(book), 'content_sha256': BOOK_SHA},
        {'citation': 'Language Science Press 公开的专著目录 TeX 源码；与出版 PDF 页和链接对照。',
         'type': 'na_tone_table_source', 'url': TABLE_SOURCE_URL, 'locator': 'indexed/abbreviations.tex / 叙事目录',
         'local_path': display_path(tex), 'content_sha256': TEX_SHA},
        {'citation': '项目据出版 PDF、馆方目录及 DataCite 公共登记生成的可复核链接对照索引。',
         'type': 'na_tone_crosswalk', 'url': 'https://doi.org/' + BOOK_DOI, 'locator': f'录音 {number} / PDF 引用对照',
         'local_path': display_path(index_path), 'content_sha256': digest(index_path)},
        {'citation': 'DataCite 公共 DOI 登记元数据快照清单；元数据 CC0，资源许可单独核对。',
         'type': 'na_tone_datacite_manifest', 'url': 'https://support.datacite.org/docs/harvesting-datacite-doi-metadata',
         'locator': '公开 DOI 登记回执与原始响应哈希', 'local_path': display_path(manifest), 'content_sha256': digest(manifest)},
    ]
    return [Source.model_validate(value) for value in values]


def new_selection(index: dict, index_path: Path, corpus: Path, first: Path, context: Path, prior: Path) -> dict:
    catalog, selected, previous = validate_na_selection(corpus, first, context, prior)
    previous |= {item['id'] for item in selected['choices']}
    mentioned = {mention['doi_id'] for row in index['table'] for mention in row['mentions']}
    identifiers = sorted(number for number in mentioned if number in catalog and number not in previous)
    if not identifiers or any(number not in index['recordings'] for number in identifiers):
        raise IntakeError('专著目录新增候选与已保存目录无法对应。')
    return {'version': 1, 'crosswalk_sha256': digest(index_path), 'catalogue_sha256': digest(corpus),
            'first_sha256': digest(first), 'context_sha256': digest(context), 'prior_sha256': digest(prior),
            'first_path': display_path(first), 'context_path': display_path(context), 'prior_path': display_path(prior),
            'ids': identifiers, 'method': '专著叙事目录明确列出、馆方录音目录存在且此前三次未选取的录音。',
            'limits': '本批包含生产生活背景，不自动判为民间故事；录音详情、原文、许可及社区要求待核。'}


def new_evidence(row: dict) -> dict:
    return {'馆方录音号': row['id'], '馆方目录题名': row['title'], '馆方目录研究者': row['researchers'],
            '馆方目录讲述者': row['speakers'], '馆方目录录音日期': row['recorded'], '馆方时长': row['duration'],
            '馆方媒介图标': row['formats'], '馆方转写图标': row['transcription_icon'],
            '选取依据': '2025 年专著叙事与背景文本目录明确列出；此前三批未选取。'}


def new_cards(index: dict, index_path: Path, book: Path, tex: Path, corpus: Path, datacite: Path,
              first: Path, context: Path, prior: Path, selection_path: Path):
    selected = json.loads(selection_path.read_text(encoding='utf-8'))
    if selected != new_selection(index, index_path, corpus, first, context, prior):
        raise IntakeError('专著新增候选选择范围或哈希不符。')
    catalog = catalogue_rows(corpus.read_bytes())
    for number in selected['ids']:
        row = catalog[number]
        original = {'citation': 'CNRS-LACITO，Pangloss 单条录音页面；详情和许可尚未取得。',
                    'type': NEW_MARKER, 'url': row['url'], 'doi': row['doi'].removeprefix('https://doi.org/'),
                    'locator': f'录音 {number} / 馆方单条详情待核'}
        source_catalogue = {'citation': 'CNRS-LACITO，Pangloss 永宁纳语馆藏目录快照。',
                            'type': 'na_tone_catalogue', 'url': CORPUS_URL, 'locator': f'目录录音 {number}',
                            'local_path': display_path(corpus), 'content_sha256': CORPUS_SHA}
        source_selection = {'citation': '项目依据专著目录及前三批选取生成的新增候选清单。',
                            'type': 'na_tone_new_selection', 'url': 'https://doi.org/' + BOOK_DOI,
                            'locator': f'录音 {number} / 新增候选', 'local_path': display_path(selection_path),
                            'content_sha256': digest(selection_path)}
        related = [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                    'note': '同一馆藏目录的录音资源，不表示同一故事、演述或采录地点。'}]
        if number == '0004549' and '0004448' in selected['ids']:
            related.append({'type': 'COMPARED_WITH', 'target': PREFIX + '0004448',
                            'note': '专著目录并列建房题名，仅为待核对照，不证明同一次演述或传播。'})
        model = {'id': PREFIX + number, 'title': f"永宁纳语录音 · {row['title']}", 'aliases': [row['title']],
                 'node_type': 'case', 'z_layer': 1, 'genre': 'unclassified', 'credibility_tier': 'B',
                 'is_fictional_quarantine': False, 'spatial': {'precision': 'culture_region',
                 'location_name': '永宁纳语馆藏范围；单条录音地点尚未核实', 'culture_region': 'East Asia · China'},
                 'temporal': None, 'standards': {}, 'relations': related,
                 'sources': [original, source_catalogue, source_selection,
                             *[s.model_dump(mode='json') for s in sources(index, number, book, tex, index_path, datacite)]],
                 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
        data = new_evidence(row)
        body = ('\n## 馆方目录字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n此卡为录音资源的背景候选，不自动判为故事；馆方单条详情、'
                  '音频和转写尚未取得。研究者、讲述者、录音时间、采录地点和叙事地点须分别核对；'
                  '录音日期不是叙事年代，坐标和标准码留空。具体许可与社区要求须逐条回查。\n'
                + note(index, number))
        yield NodeMetadata.model_validate(model), body


def enrich(vault: Path, index: dict, book: Path, tex: Path, index_path: Path, datacite: Path, *, check: bool = False) -> dict:
    plans, already, skipped = [], 0, []
    with vault_writer(vault):
        for number in sorted(index['recordings']):
            name = PREFIX + number + '.md'
            paths = [path for batch in ('asia_cn_pangloss_na', 'asia_cn_pangloss_na_context', 'asia_cn_pangloss_na_catalogue')
                     if (path := vault / '00_drafts' / batch / name).is_file()]
            if not paths:
                continue
            if len(paths) != 1 or paths[0].is_symlink():
                raise IntakeError(f'待审录音草稿重复或是符号链接：{number}')
            path = paths[0]
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            metadata, body = parse_card(text.replace('\r\n', '\n'))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                skipped.append({'id': number, 'reason': '草稿已复核或为示例'})
                continue
            catalogues = [s for s in metadata.sources if s.type in ('pangloss_na_catalogue', 'pangloss_na_candidate_catalogue')]
            if metadata.id != PREFIX + number or len(catalogues) != 1 or catalogues[0].content_sha256 != CORPUS_SHA:
                raise IntakeError(f'草稿与馆方目录来源不符：{number}')
            additions = sources(index, number, book, tex, index_path, datacite)
            previous = [s for s in metadata.sources if s.type in {s.type for s in additions}]
            if previous or MARKER in text:
                if previous != additions or note(index, number).strip() not in body:
                    raise IntakeError(f'草稿已有不同版本的专著补充，保留原内容：{number}')
                already += 1
                continue
            revised = append_sources(text, additions) + note(index, number)
            new_meta, new_body = parse_card(revised.replace('\r\n', '\n'))
            if (metadata.model_dump(exclude={'sources'}) != new_meta.model_dump(exclude={'sources'})
                    or new_meta.sources != metadata.sources + additions or not new_body.startswith(body)):
                raise IntakeError(f'补充时草稿原字段或正文发生变化：{number}')
            encoded = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + revised.encode('utf-8')
            plans.append((path, raw, encoded))
        if not check:
            staged, changed = [], []
            try:
                for path, original, revised in plans:
                    with NamedTemporaryFile(dir=path.parent, prefix='.na-tone-', delete=False) as stream:
                        temporary = Path(stream.name)
                        staged.append(temporary)
                        stream.write(revised)
                if any(path.read_bytes() != original for path, original, _ in plans):
                    raise IntakeError('草稿在补充期间发生变化；未写入。')
                for (path, original, revised), temporary in zip(plans, staged, strict=True):
                    if path.read_bytes() != original:
                        raise IntakeError(f'草稿在补充期间发生变化：{path}')
                    temporary.replace(path)
                    changed.append((path, original, revised))
            except Exception:
                for path, original, revised in reversed(changed):
                    if path.read_bytes() != revised:
                        raise IntakeError(f'回滚时发现外部修改，保留该草稿：{path}')
                    with NamedTemporaryFile(dir=path.parent, prefix='.na-tone-rollback-', delete=False) as stream:
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
    return {'cards_to_update': len(plans), 'already_enriched': already, 'skipped': skipped, 'check': check,
            'changes': [{'id': path.stem, 'before': sha256(raw).hexdigest(), 'after': sha256(revised).hexdigest()}
                        for path, raw, revised in plans]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('select', 'stage', 'enrich'))
    parser.add_argument('--book', type=Path, required=True)
    parser.add_argument('--tex', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--datacite', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--first', type=Path, default=Path('reference/pangloss_na_selection_v1.json'))
    parser.add_argument('--context', type=Path, default=Path('reference/pangloss_na_context_selection_v1.json'))
    parser.add_argument('--prior', type=Path, default=Path('reference/pangloss_na_catalogue_selection_v1.json'))
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--code-table', type=Path, default=DEFAULT_CODE_TABLE)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    index = load_index(args.index, args.book, args.tex, args.corpus, args.datacite)
    if args.action == 'select':
        from pipeline.archive_fetch import json_bytes
        from pipeline.fetch_lao_dllm import exclusive_write
        selected = new_selection(index, args.index, args.corpus, args.first, args.context, args.prior)
        if not args.check:
            exclusive_write(args.selection, json_bytes(selected))
        result = {'new_candidate_ids': selected['ids'], 'check': args.check}
    elif args.action == 'stage':
        cards = list(new_cards(index, args.index, args.book, args.tex, args.corpus, args.datacite,
                               args.first, args.context, args.prior, args.selection))
        if args.check:
            from pipeline.local_standards import load_code_table, verify_codes
            from pipeline.vault import load_vault
            existing = set(load_vault(args.vault)) | {path.stem for path in (args.vault / '00_drafts').rglob('*.md')}
            table = load_code_table(args.code_table)
            for metadata, _ in cards:
                if metadata.id in existing:
                    raise IntakeError(f'已存在卡片，不能建立新批次：{metadata.id}')
                verify_codes(metadata.standards, table)
            result = {'new_candidate_ids': [m.id for m, _ in cards], 'check': True}
        else:
            from pipeline.import_datasets import stage_batch
            result = stage_batch(args.vault, 'asia_cn_pangloss_na_tone', cards, args.code_table,
                                 {'book_doi': BOOK_DOI, 'book_sha256': BOOK_SHA,
                                  'crosswalk_sha256': digest(args.index), 'selection_sha256': digest(args.selection),
                                  'scope': '专著目录中的此前未选背景录音；未取得单条详情、音频或转写，人工复核前不入图。'})
    else:
        result = enrich(args.vault, index, args.book, args.tex, args.index, args.datacite, check=args.check)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
