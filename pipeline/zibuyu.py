"""Prepare individually traceable drafts from a pinned Wikisource transcription."""
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from pipeline.fetch_zibuyu import HOST, ROOT, VOLUMES, page_info, page_url
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_cn_zibuyu_wikisource'
VOLUME_PREFIX = 'corpus_cn_zibuyu_v'
CASE_PREFIX = 'case_cn_zibuyu_v'
EXISTING_ID = 'case_zibuyu_li_tongpan'
ORIGINAL_MARKER = 'zibuyu_revision_link'
LICENSE_URL = 'https://creativecommons.org/licenses/by-sa/4.0/'
TALK_URL = 'https://zh.wikisource.org/wiki/Talk:%E5%AD%90%E4%B8%8D%E8%AA%9E'


def volume_id(volume: int) -> str:
    return f'{VOLUME_PREFIX}{volume:02d}'


def node_id(row: dict) -> str:
    if row['volume'] == 1 and row['number'] == 1 and row['title'] == '李通判': return EXISTING_ID
    return f"{CASE_PREFIX}{row['volume']:02d}_s{row['number']:03d}"


def fixed_url(volume: int, revision: int, anchor: str = '') -> str:
    title = ROOT if volume == 0 else f'{ROOT}/卷{volume}'
    base = f'https://{HOST}/w/index.php?title={quote(title)}&oldid={revision}'
    return base + ('#' + quote(anchor, safe='') if anchor else '')


def parse_index(raw: bytes) -> list[list[dict]]:
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    root = soup.select_one('#mw-content-text > .mw-parser-output')
    headings = root.find_all('h3') if root else []
    if len(headings) != VOLUMES: raise IntakeError('子不语总目录卷数变化，须重新核对。')
    volumes = []
    for volume, heading in enumerate(headings, 1):
        link = heading.find('a', href=True)
        if not link or unquote(urlsplit(link['href']).path) != f'/wiki/{ROOT}/卷{volume}':
            raise IntakeError(f'子不语总目录卷次链接异常：{volume}')
        table = heading.parent.find_next_sibling('table')
        if not table: raise IntakeError(f'子不语目录缺少卷内篇目：{volume}')
        items = []
        for item in table.find_all('a', href=True):
            parsed = urlsplit(unquote(item['href']))
            if parsed.path == f'/wiki/{ROOT}/卷{volume}' and parsed.fragment:
                title = item.get_text('', strip=True)
                if not title: raise IntakeError(f'子不语目录篇名为空：{volume}')
                items.append({'number': len(items) + 1, 'title': title, 'anchor': parsed.fragment})
        if not items or len(items) > 200: raise IntakeError(f'子不语目录篇数异常：{volume}')
        volumes.append(items)
    return volumes


def parse_volume(raw: bytes, volume: int) -> list[dict]:
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    root = soup.select_one('#mw-content-text > .mw-parser-output')
    headings = root.find_all('h3') if root else []
    if not headings or len(headings) > 200: raise IntakeError(f'子不语分卷篇题数异常：{volume}')
    rows = []
    for heading in headings:
        label, anchor = heading.get_text('', strip=True), heading.get('id')
        if not label.startswith('○') or not isinstance(anchor, str) or not anchor:
            raise IntakeError(f'子不语分卷篇题或锚点异常：{volume}')
        paragraphs, annotations = [], []
        for element in heading.parent.next_siblings:
            if not getattr(element, 'name', None): continue
            if element.select_one('h3'): break
            if element.name == 'table' and 'ws-footer' in element.get('class', []): break
            if element.name != 'p':
                raise IntakeError(f'子不语正文结构须人工检查：卷 {volume} / {label} / {element.name}')
            for span in element.find_all('span', title=True):
                annotations.append({'可见文字': span.get_text('', strip=True), '原页提示': span['title']})
            # Keep explicit line breaks while stripping HTML; comments are not visible text.
            pieces = []
            for part in element.descendants:
                if isinstance(part, Comment): continue
                if isinstance(part, NavigableString): pieces.append(str(part))
                elif isinstance(part, Tag) and part.name == 'br': pieces.append('\n')
            value = ''.join(pieces).strip()
            if value: paragraphs.append(value)
        if not paragraphs: raise IntakeError(f'子不语正文为空：卷 {volume} / {label}')
        row = {'volume': volume, 'number': len(rows) + 1, 'title': label[1:], 'anchor': anchor,
               'paragraphs': paragraphs}
        if annotations: row['inline_annotations'] = annotations
        rows.append(row)
    if len({row['anchor'] for row in rows}) != len(rows):
        raise IntakeError(f'子不语分卷锚点重复：{volume}')
    return rows


def reconcile(items: list[dict], rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Only identical unique titles are candidates; same-position names remain tentative."""
    index_counts = Counter(item['title'] for item in items)
    page_counts = Counter(row['title'] for row in rows)
    index_by_title = {item['title']: item for item in items if index_counts[item['title']] == 1}
    result = []
    for row in rows:
        item = index_by_title.get(row['title']) if page_counts[row['title']] == 1 else None
        if item:
            kind = '同题候选'
        elif row['number'] <= len(items):
            item = items[row['number'] - 1]
            kind = '同序候选，身份待核'
        else:
            kind = '目录未找到候选'
        result.append({**row, 'index_candidate_kind': kind, 'index_candidate': item})
    missing = [item for item in items if index_counts[item['title']] != 1 or page_counts[item['title']] != 1]
    return result, missing


def load_snapshot(folder: Path) -> tuple[dict, list[list[dict]], list[list[dict]], list[list[dict]]]:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    pages = manifest.get('pages')
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or not isinstance(pages, list) or len(pages) != VOLUMES + 1):
        raise IntakeError('子不语网页快照清单不完整。')
    raw_pages = []
    for volume, page in enumerate(pages):
        name = 'index.html' if volume == 0 else f'volume-{volume:02d}.html'
        raw = (folder / name).read_bytes()
        info = page_info(raw, volume)
        if (page.get('volume') != volume or page.get('path') != name or page.get('url') != page_url(volume)
                or page.get('sha256') != sha256(raw).hexdigest() or page.get('bytes') != len(raw)
                or page.get('revision_id') != info['revision_id'] or page.get('title') != info['title']
                or not page.get('observed_at')):
            raise IntakeError(f'子不语快照哈希或来源不符：{name}')
        raw_pages.append(raw)
    check = manifest.get('index_recheck', {})
    if (check.get('url') != page_url(0) or check.get('revision_id') != pages[0]['revision_id']
            or not re.fullmatch(r'[a-f0-9]{64}', str(check.get('sha256', '')))
            or not isinstance(check.get('bytes'), int) or check['bytes'] <= 0 or not check.get('observed_at')):
        raise IntakeError('子不语总目录复查凭据异常。')
    index = parse_index(raw_pages[0])
    all_rows, missing = [], []
    for volume in range(1, VOLUMES + 1):
        rows, unmatched = reconcile(index[volume - 1], parse_volume(raw_pages[volume], volume))
        all_rows.append(rows); missing.append(unmatched)
    if not all_rows[0] or all_rows[0][0]['title'] != '李通判':
        raise IntakeError('既有《李通判》篇目与分卷首篇不符，不能自动对照。')
    return manifest, index, all_rows, missing


def load_talk(folder: Path) -> dict:
    receipt = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    raw = (folder / 'talk.html').read_bytes()
    text = BeautifulSoup(raw.decode('utf-8'), 'html.parser').get_text(' ', strip=True)
    revisions = set(re.findall(r'"wgRevisionId":(\d+)', raw.decode('utf-8')))
    if (receipt.get('version') != 1 or receipt.get('url') != TALK_URL or receipt.get('robots_status') not in ('200', '404')
            or receipt.get('sha256') != sha256(raw).hexdigest() or receipt.get('bytes') != len(raw)
            or not receipt.get('observed_at') or len(revisions) != 1
            or not all(value in text for value in ('User:arthursilva', '開放文學', '2011-12-24'))):
        raise IntakeError('子不语版本讨论网页或校对说明无法核验。')
    return {'修订号': int(next(iter(revisions))), '贡献者字段': 'User:arthursilva',
            '校对说明': '讨论页称依开放文学点校，最后校正 2011-12-24；讨论页未列明确古籍底本。',
            '篇序说明': '讨论页称目录中的阿拉伯数字为后加，方便编辑和阅读。'}


def evidence(row: dict, manifest: dict) -> dict:
    page = manifest['pages'][row['volume']]
    original = '\n\n'.join(row['paragraphs'])
    candidate = row['index_candidate']
    result = {'分卷': row['volume'], '分卷篇序': row['number'], '分卷篇名原文': row['title'],
            '分卷页面实际锚点': row['anchor'], '分卷修订号': page['revision_id'],
            '总目录候选方式': row['index_candidate_kind'], '总目录候选篇目': candidate,
            '锚点一致': candidate['anchor'] == row['anchor'] if candidate and row['index_candidate_kind'] == '同题候选' else None,
            '段落数': len(row['paragraphs']), '抽取纯文字 SHA256': sha256(original.encode('utf-8')).hexdigest(),
            '文字说明': '由分卷网页段落抽取纯文字；原页的版式与注标须回查，不等于已核对古籍底本。',
            '固定修订原文链接': fixed_url(row['volume'], page['revision_id'], row['anchor'])}
    if row.get('inline_annotations'): result['原页内嵌注标'] = row['inline_annotations']
    return result


def group_evidence(manifest: dict, index: list[list[dict]], volumes: list[list[dict]], missing: list[list[dict]]) -> dict:
    rows = [row for vol in volumes for row in vol]
    return {'总目录卷数': len(index), '总目录篇题数': sum(map(len, index)), '分卷标题数': len(rows),
            '同题候选数': sum(row['index_candidate_kind'] == '同题候选' for row in rows),
            '非同题候选数': sum(row['index_candidate_kind'] != '同题候选' for row in rows),
            '目录锚点与分卷不一致数': sum(row['index_candidate_kind'] == '同题候选' and row['index_candidate']['anchor'] != row['anchor'] for row in rows),
            '总目录未找到唯一同题的篇目数': sum(map(len, missing)), '目录修订号': manifest['pages'][0]['revision_id'],
            '范围说明': '一标题未必是一则独立叙事；相同题名或同序候选均须人工复核。只复查总目录修订号，分卷非原子快照。'}


def volume_evidence(volume: int, manifest: dict, index: list[list[dict]], volumes: list[list[dict]], missing: list[list[dict]]) -> dict:
    return {'卷次': volume, '总目录篇题数': len(index[volume - 1]), '分卷标题数': len(volumes[volume - 1]),
            '目录未找到唯一同题数': len(missing[volume - 1]), '分卷修订号': manifest['pages'][volume]['revision_id']}


def source_set(folder: Path, manifest: dict, row: dict | None = None, volume: int | None = None) -> list[dict]:
    page = manifest['pages'][volume if volume is not None else 0]
    if row is not None: page = manifest['pages'][row['volume']]
    vol = page['volume']; anchor = row['anchor'] if row else ''
    locator = f"卷 {vol} / {anchor}" if row else f'卷 {vol}' if vol else '总目录'
    original = {'citation': f'袁枚，《子不語》；维基文库贡献者转录修订 {page["revision_id"]}，底本与校勘待核。',
                'type': ORIGINAL_MARKER, 'url': fixed_url(vol, page['revision_id'], anchor), 'locator': locator + ' / 固定修订'}
    capture = {'citation': '维基文库对应页面的本地原网页快照；段落抽取不等于古籍底本校勘。',
               'type': 'zibuyu_snapshot', 'url': page['url'], 'locator': locator + ' / 本地网页快照',
               'local_path': display_path(folder / page['path']), 'content_sha256': page['sha256']}
    manifest_path = folder / 'manifest.json'
    receipt = {'citation': '本地总目录、分卷网页和修订号采集清单。', 'type': 'zibuyu_manifest',
               'url': page_url(0), 'locator': '总目录与分卷快照清单', 'local_path': display_path(manifest_path),
               'content_sha256': sha256(manifest_path.read_bytes()).hexdigest()}
    sources = [original, capture, receipt]
    if vol:
        index = manifest['pages'][0]
        sources.append({'citation': '维基文库总目录；同题或同序仅为待核对照。', 'type': 'zibuyu_index',
                        'url': index['url'], 'locator': f'总目录卷 {vol}', 'local_path': display_path(folder / index['path']),
                        'content_sha256': index['sha256']})
    return sources


def scope_note() -> str:
    return ('\n\n## 版本与复核\n\n本文是维基文库在线转录的段落纯文字，未对照纸本或影印底本；版式、注标及异文须回查原页。'
            '原作及数字转录版本的权利需分别核对；站点文字按 [CC BY-SA 4.0](' + LICENSE_URL + ') 提供，'
            '使用时应保留贡献者、修订版本和出处。志怪文本记述不等于已证实事件，故事发生地及年代、标准码均待核。\n')


def card_body(row: dict, manifest: dict) -> str:
    return ('\n## 来源字段\n\n' + literal_block(json.dumps(evidence(row, manifest), ensure_ascii=False, indent=2))
            + '\n\n## 在线转录原文（待校）\n\n' + literal_block('\n\n'.join(row['paragraphs'])) + scope_note())


def cards(folder: Path, talk: Path, *, include_existing: bool = False):
    manifest, index, volumes, missing = load_snapshot(folder)
    talk_data = load_talk(talk)
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False, 'spatial': {'precision': 'culture_region',
              'location_name': '中国志怪文献；各篇发生地与采录地待核', 'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    group = group_evidence(manifest, index, volumes, missing)
    talk_page, talk_manifest = talk / 'talk.html', talk / 'manifest.json'
    talk_sources = [{'citation': '维基文库《子不語》讨论页版本信息；仅是编辑者的校对说明。',
                     'type': 'zibuyu_talk', 'url': TALK_URL, 'locator': '版本信息 / 校对说明',
                     'local_path': display_path(talk_page), 'content_sha256': sha256(talk_page.read_bytes()).hexdigest()},
                    {'citation': '维基文库版本讨论网页快照清单。', 'type': 'zibuyu_talk_manifest', 'url': TALK_URL,
                     'locator': '版本讨论快照清单', 'local_path': display_path(talk_manifest),
                     'content_sha256': sha256(talk_manifest.read_bytes()).hexdigest()}]
    root = {**common, 'id': ROOT_ID, 'title': '《子不语》 · 维基文库二十四卷转录',
            'sources': [*source_set(folder, manifest), *talk_sources]}
    body = ('\n## 总目录与分卷对照\n\n' + literal_block(json.dumps(group, ensure_ascii=False, indent=2))
            + '\n\n## 站方版本讨论\n\n' + literal_block(json.dumps(talk_data, ensure_ascii=False, indent=2))
            + scope_note())
    yield NodeMetadata.model_validate(root), body
    for volume, rows in enumerate(volumes, 1):
        vol_data = volume_evidence(volume, manifest, index, volumes, missing)
        model = {**common, 'id': volume_id(volume), 'title': f'《子不语》卷 {volume:02d} · 在线转录',
                 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID, 'note': '维基文库所列卷次。'}],
                 'sources': source_set(folder, manifest, volume=volume)}
        yield NodeMetadata.model_validate(model), ('\n## 分卷对照\n\n' + literal_block(json.dumps(vol_data, ensure_ascii=False, indent=2)) + scope_note())
        for row in rows:
            if node_id(row) == EXISTING_ID and not include_existing: continue
            model = {**common, 'node_type': 'case', 'z_layer': 1, 'id': node_id(row),
                     'title': f"《子不语》卷 {volume:02d} · {row['title']}", 'aliases': [row['title']],
                     'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': volume_id(volume),
                                    'note': '所列分卷篇题；与目录同题或同序的对应仍需核查。'}],
                     'sources': source_set(folder, manifest, row=row)}
            yield NodeMetadata.model_validate(model), card_body(row, manifest)
