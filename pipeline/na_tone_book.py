"""Index published Pangloss DOI links, without fetching recordings or transcriptions."""

from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import urlsplit

from pypdf import PdfReader

from pipeline.intake_sources import IntakeError
from pipeline.pangloss_na import catalogue_rows

BOOK_SHA = '824730384cb88091754c3918601414dd40c8b08b2c6d504dc4f8e15241a5da77'
TEX_SHA = '69d81c8c14ce426b6d0c776526da869c9621d88aa28a67ba65883efa7fec3024'
CORPUS_SHA = '85f6c91212d4ca5d7ae29bc1e3caa6a35d248911d0173811055f38409295dbaf'
BOOK_DOI = '10.5281/zenodo.15275071'
BOOK_URL = 'https://zenodo.org/records/15275071/files/513-Michaud-2025.pdf?download=1'
BOOK_GIT = 'https://github.com/langsci/513/commit/5d1c2728bc2996ee663cf6a2b0c3e15530b8e1a5'
DATACITE_API = 'https://api.datacite.org/dois/10.24397/pangloss-'


def checked(path: Path, expected: str) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise IntakeError(f'来源文件无法读取：{path}：{error}') from error
    if sha256(raw).hexdigest() != expected:
        raise IntakeError(f'来源哈希不符：{path}')
    return raw


def parse_doi_uri(uri: str) -> tuple[str, str] | None:
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return None
    match = re.fullmatch(r'/10\.24397/pangloss-(\d{7})', parsed.path, flags=re.I)
    if parsed.scheme != 'https' or parsed.netloc.lower() != 'doi.org' or parsed.query or not match:
        return None
    if parsed.fragment and not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', parsed.fragment):
        raise IntakeError('书中 Pangloss DOI 的片段标识无效。')
    return match.group(1), parsed.fragment


def extract_links(book: Path) -> list[dict]:
    checked(book, BOOK_SHA)
    try:
        pdf = PdfReader(book)
        labels = pdf.page_labels
        if len(pdf.pages) != 661 or len(labels) != 661:
            raise IntakeError('专著 PDF 页数或页码标签与登记版本不符。')
        rows = []
        for index, page in enumerate(pdf.pages):
            for ordinal, reference in enumerate(page.get('/Annots', []), 1):
                annotation = reference.get_object()
                action = annotation.get('/A', {})
                uri = action.get('/URI') if action else None
                if not isinstance(uri, str):
                    continue
                parsed = parse_doi_uri(uri)
                if not parsed:
                    continue
                number, fragment = parsed
                kind = ('sentence' if re.fullmatch(r'S\d+', fragment) else
                        'word' if re.fullmatch(r'W\d+', fragment) else 'resource' if not fragment else 'unknown_fragment')
                rows.append({'pdf_page': index + 1, 'printed_page': labels[index], 'annotation': ordinal,
                             'doi_id': number, 'fragment': fragment, 'fragment_kind': kind, 'url': uri})
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise IntakeError(f'专著 DOI 链接无法读取：{error}') from error
    if len(rows) != 321 or len({item['doi_id'] for item in rows}) != 90:
        raise IntakeError('专著中的 DOI 链接数量与登记版本不符。')
    return rows


def extract_narrative_table(tex: Path, links: list[dict]) -> list[dict]:
    text = checked(tex, TEX_SHA).decode('utf-8')
    try:
        portion = text.split('Here is a list of texts', 1)[1].split('For elicited phonological', 1)[0]
    except IndexError as error:
        raise IntakeError('专著叙事目录的起止标记缺失。') from error
    table = []
    for topic, title, references in re.findall(r'\\textit\{([^{}]+)\}\s*&\s*(.*?)\s*&\s*(.*?)\\\\', portion, re.S):
        mentions = [{'doi_id': m.group(2), 'version_label': m.group(1)}
                    for m in re.finditer(r'(?:(\d+)\s*:\s*)?\\pandoi\{(\d{7})\}', references)]
        if not mentions:
            raise IntakeError(f'专著叙事目录缺少 DOI：{topic}')
        table.append({'topic': topic, 'title': ' '.join(title.split()), 'mentions': mentions})
    if len(table) != 20 or len({item['topic'] for item in table}) != 20:
        raise IntakeError('专著叙事目录题名数不符。')
    tex_ids = [mention['doi_id'] for row in table for mention in row['mentions']]
    # The two narrative tables are printed on PDF pages 29 and 30. Page 30
    # continues with two phonology rows, so compare the exact ordered prefix.
    rendered_ids = [item['doi_id'] for item in links if item['pdf_page'] in (29, 30) and not item['fragment']]
    if rendered_ids[:len(tex_ids)] != tex_ids:
        raise IntakeError('专著排版目录的 DOI 顺序与出版 PDF 链接不一致。')
    return table


def selection(book: Path, tex: Path, corpus: Path) -> dict:
    links = extract_links(book)
    table = extract_narrative_table(tex, links)
    catalogue = catalogue_rows(checked(corpus, CORPUS_SHA))
    identifiers = {item['doi_id'] for item in links}
    table_ids = {mention['doi_id'] for row in table for mention in row['mentions']}
    missing_from_catalogue = identifiers - set(catalogue)
    return {'version': 1, 'book_sha256': BOOK_SHA, 'source_tex_sha256': TEX_SHA, 'catalogue_sha256': CORPUS_SHA,
            'book_doi': BOOK_DOI, 'book_git_revision': '5d1c2728bc2996ee663cf6a2b0c3e15530b8e1a5',
            'book_link_count': len(links), 'book_doi_count': len(identifiers), 'table_topic_count': len(table),
            'fetch_ids': sorted(missing_from_catalogue | table_ids),
            'absent_from_audio_catalogue': sorted(missing_from_catalogue),
            'table_duplicate_dois': {number: count for number, count in Counter(
                mention['doi_id'] for row in table for mention in row['mentions']).items() if count > 1},
            'scope': 'DataCite 公开 DOI 登记字段仅用于原书链接与既有馆藏目录的候选对应，不获取录音、转写或馆方受限页面。'}
