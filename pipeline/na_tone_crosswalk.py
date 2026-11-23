"""Cross-check a published Na book's links against catalogue and DOI metadata."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from pipeline.archive_fetch import json_bytes
from pipeline.fetch_datacite_na_tone import load as load_datacite
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError
from pipeline.na_tone_book import BOOK_DOI, BOOK_SHA, CORPUS_SHA, TEX_SHA, checked, extract_links, extract_narrative_table
from pipeline.pangloss_na import catalogue_rows

UUID_PATTERN = r'cocoon-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


def primary_from_url(url: str | None) -> tuple[str | None, bool]:
    if not isinstance(url, str):
        return None, False
    try:
        parts = urlsplit(url)
        query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None, False
    primary = query.get('oai_primary', [])
    secondary = query.get('oai_secondary', [])
    if (parts.scheme != 'https' or parts.netloc != 'pangloss.cnrs.fr' or parts.path != '/corpus/show' or parts.fragment
            or len(primary) != 1 or not re.fullmatch(UUID_PATTERN, primary[0])
            or (secondary and (len(secondary) != 1 or not re.fullmatch(UUID_PATTERN, secondary[0])))):
        return None, False
    return primary[0], len(secondary) == 1


def requires_primary(attrs: dict, primary: str) -> bool:
    links = attrs.get('relatedIdentifiers')
    if not isinstance(links, list):
        return False
    for entry in links:
        if not isinstance(entry, dict) or entry.get('relationType') != 'Requires' or entry.get('relatedIdentifierType') != 'PURL':
            continue
        url = entry.get('relatedIdentifier')
        if not isinstance(url, str):
            continue
        try:
            parts = urlsplit(url)
        except ValueError:
            continue
        if (parts.scheme in ('http', 'https') and parts.netloc == 'purl.org'
                and parts.path == '/poi/crdo.vjf.cnrs.fr/' + primary and not parts.query and not parts.fragment):
            return True
    return False


def rights_conflict(rights: object) -> bool:
    if not isinstance(rights, list):
        return False
    for item in rights:
        if not isinstance(item, dict):
            continue
        label, uri = item.get('rights'), item.get('rightsUri')
        if (isinstance(label, str) and isinstance(uri, str) and '/by-nc-sa/' in uri.lower()
                and re.search(r'Attribution[- ]NonCommercial', label, re.I)
                and not re.search(r'Share[ -]?Alike|\bSA\b', label, re.I)):
            return True  # The string omits SA while its linked licence has SA.
    return False


def catalog_version(title: str) -> str | None:
    match = re.search(r'\bversion\s+(\d+)\b', title, re.I)
    return match.group(1) if match else None


def build(book: Path, tex: Path, corpus: Path, datacite: Path) -> dict:
    links = extract_links(book)
    table = extract_narrative_table(tex, links)
    catalogue = catalogue_rows(checked(corpus, CORPUS_SHA))
    selected, manifest, registered = load_datacite(datacite, book, tex, corpus)
    primary_index = defaultdict(list)
    for identifier, row in catalogue.items():
        primary, secondary = primary_from_url(row['url'])
        if not primary or secondary:
            raise IntakeError(f'馆方录音目录缺少唯一主资源标识：{identifier}')
        primary_index[primary].append(identifier)
    book_ids = sorted({link['doi_id'] for link in links})
    mappings = {}
    for number in book_ids:
        attrs = registered.get(number)
        found = number in registered
        target = number if number in catalogue else None
        basis = '书中 DOI 与馆方录音目录 DOI 完全一致' if target else None
        warnings = []
        rec_type = None
        rights = []
        titles = []
        registered_url = None
        primary = None
        if found and attrs is None:
            warnings.append('datacite_404')
        elif attrs:
            registered_url = attrs.get('url')
            primary, secondary = primary_from_url(registered_url)
            type_info = attrs.get('types') if isinstance(attrs.get('types'), dict) else {}
            rec_type = type_info.get('resourceTypeGeneral')
            rights = attrs.get('rightsList') if isinstance(attrs.get('rightsList'), list) else []
            titles = attrs.get('titles') if isinstance(attrs.get('titles'), list) else []
            if rights_conflict(rights):
                warnings.append('rights_label_uri_differ')
            if target:
                expected_primary, _ = primary_from_url(catalogue[target]['url'])
                if not primary or primary != expected_primary:
                    warnings.append('datacite_primary_disagrees')
                if rec_type != 'Sound' or secondary:
                    warnings.append('datacite_record_type_disagrees')
            elif primary and secondary and rec_type == 'Text' and requires_primary(attrs, primary):
                candidates = primary_index.get(primary, [])
                if len(candidates) == 1:
                    target = candidates[0]
                    basis = 'DataCite 的文本目标和 Requires 主资源标识均与馆方录音目录唯一对应'
                elif len(candidates) > 1:
                    warnings.append('primary_not_unique')
                else:
                    warnings.append('primary_not_in_catalogue')
            else:
                warnings.append('datacite_relation_unresolved')
        elif not target:
            warnings.append('datacite_missing')
        mappings[number] = {'doi_id': number, 'catalogue_recording_id': target, 'basis': basis,
                            'datacite_checked': found, 'datacite_type': rec_type, 'datacite_url': registered_url,
                            'datacite_titles': titles, 'datacite_rights': rights, 'flags': warnings}
    table_count = Counter(mention['doi_id'] for row in table for mention in row['mentions'])
    by_sound = {}
    for link in links:
        mapping = mappings[link['doi_id']]
        item = {**link, 'catalogue_recording_id': mapping['catalogue_recording_id'], 'basis': mapping['basis']}
        target = mapping['catalogue_recording_id']
        if target:
            by_sound.setdefault(target, {'recording_id': target, 'links': [], 'table_mentions': [], 'flags': []})['links'].append(item)
    for position, row in enumerate(table):
        page = 29 if position < 10 else 30
        for mention in row['mentions']:
            number = mention['doi_id']
            target = mappings[number]['catalogue_recording_id']
            if not target:
                continue
            card = by_sound[target]
            item = {'topic': row['topic'], 'title': row['title'], 'book_version_label': mention['version_label'],
                    'book_doi_id': number, 'pdf_page': page, 'printed_page': 'xxiii' if page == 29 else 'xxiv'}
            card['table_mentions'].append(item)
            if table_count[number] > 1:
                card['flags'].append('book_table_doi_reused_across_topics')
            version = catalog_version(catalogue[target]['title'])
            if version and mention['version_label'] and version != mention['version_label']:
                card['flags'].append('book_catalogue_version_label_differs')
    for target, card in by_sound.items():
        referenced_ids = {link['doi_id'] for link in card['links']}
        for number in referenced_ids:
            card['flags'].extend(mappings[number]['flags'])
        if any(link['fragment_kind'] == 'unknown_fragment' for link in card['links']):
            card['flags'].append('book_fragment_unclassified')
        card['flags'] = sorted(set(card['flags']))
        card['catalogue_title'] = catalogue[target]['title']
        card['catalogue_url'] = catalogue[target]['url']
    return {'version': 1, 'book_doi': BOOK_DOI, 'book_sha256': BOOK_SHA, 'source_tex_sha256': TEX_SHA,
            'catalogue_sha256': CORPUS_SHA, 'datacite_manifest_sha256': sha256((datacite / 'manifest.json').read_bytes()).hexdigest(),
            'mapping_rule': '仅按完全相同的录音 DOI，或 DataCite 文本链接及 Requires 中的唯一主资源标识对应；不按编号相邻、题名或日期匹配。',
            'limits': '书中页码和链接是已发表引文线索；无法验证录音、转写内容、片段可用性或源资源权利。',
            'links': links, 'table': table, 'mappings': mappings, 'recordings': dict(sorted(by_sound.items()))}


def create(output: Path, book: Path, tex: Path, corpus: Path, datacite: Path) -> dict:
    index = build(book, tex, corpus, datacite)
    exclusive_write(output, json_bytes(index))
    return index


def load(path: Path, book: Path, tex: Path, corpus: Path, datacite: Path) -> dict:
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f'纳语书目对照索引无法读取：{error}') from error
    if result != build(book, tex, corpus, datacite):
        raise IntakeError('纳语书目对照索引与原书、目录或 DataCite 快照不符。')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book', type=Path, required=True)
    parser.add_argument('--tex', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--datacite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    index = create(args.output, args.book, args.tex, args.corpus, args.datacite)
    print(f"已核对 {len(index['links'])} 条书中链接，关联 {len(index['recordings'])} 条馆方目录录音；均待人工复核。")
    return 0


if __name__ == '__main__': raise SystemExit(main())
