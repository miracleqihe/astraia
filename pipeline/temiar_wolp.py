"""Stage Temiar recording leads and contextual archive descriptions for review."""
from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.fetch_minyag_wolp import TERMS_URL
from pipeline.fetch_temiar_current import ITEM_URL as CURRENT_ITEM_URL
from pipeline.fetch_temiar_wolp import CATALOGUE_URL, catalogue_rows
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_my_temiar_wolp'
SONG_PREFIX = 'case_my_temiar_wolp_'
CONTEXT_PREFIX = 'corpus_my_temiar_wolp_'
MARKER = 'temiar_wolp_archive_link'
AUDIO_MARKER = 'temiar_wolp_audio_link'
SONGS = set(range(33, 42))
CONTEXT = {1, 2, 23, 27, 28, 29, 30, 31, 32, 42, 43}
SELECTED = SONGS | CONTEXT
COMPARISONS = {30: 29, 41: 40}


def node_id(number: int) -> str:
    return f'{SONG_PREFIX if number in SONGS else CONTEXT_PREFIX}{number:02d}'


def category(number: int) -> str:
    if number in SONGS: return '叙事歌曲音轨线索'
    if number in {4, 5}: return '后期器乐录音'
    if number in {6, 7, 8}: return '后期英语歌曲录音'
    if number in {10, *range(42, 51)}: return '照片或底片'
    if number in {29, 30}: return '历史研究评论'
    if number == 31: return '录音背景说明'
    if number == 32: return '歌曲说明文件'
    if number in {1, 2, 21, 23, 28}: return '笔记或回忆'
    if number == 24: return '履历'
    return '信件或其他文书'


def load_snapshot(folder: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404'):
        raise IntakeError('Temiar 馆藏快照清单版本或 robots 状态异常。')
    pages = manifest.get('pages')
    if not isinstance(pages, list) or len(pages) != 2:
        raise IntakeError('Temiar 馆藏快照清单不完整。')
    for entry, (name, url) in zip(pages, [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)], strict=True):
        raw = (folder / name).read_bytes()
        if (entry.get('path') != name or entry.get('url') != url or entry.get('sha256') != sha256(raw).hexdigest()
                or entry.get('bytes') != len(raw) or not entry.get('observed_at')):
            raise IntakeError(f'Temiar 馆藏快照来源或哈希不符：{name}')
    terms = BeautifulSoup((folder / 'terms.html').read_bytes().decode('utf-8'), 'html.parser').get_text(' ', strip=True)
    if not all(value in terms for value in ('personal non-commercial use', 'internal non-commercial circulation',
                                            'prior written permission', 'proprietary notices')):
        raise IntakeError('网站条款变化，须重新确认。')
    raw = (folder / 'catalogue.html').read_bytes()
    rows = catalogue_rows(raw)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['archive_url']].append(row['number'])
    if sorted(group for group in grouped.values() if len(group) > 1) != [[10, 45]]:
        raise IntakeError('Temiar 目录旧档案链接重复情况变化，须复核。')
    if {r['number'] for r in rows if r['audio_url']} != SONGS | set(range(4, 9)):
        raise IntakeError('Temiar 目录所列音频入口范围变化，须复核。')
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    texts = {}
    for paragraph in soup.find_all('p'):
        content = paragraph.get_text(' ', strip=True)
        match = re.match(r'^(\d+)\.\s', content)
        if match: texts[int(match.group(1))] = content
    required = {1: ('Aileen Margaret Robertson',), 23: ('Peggy Robertson',),
                29: ('H.D. Noone', 'nine Dream Music tracks'), 30: ('H.D. Noone',),
                32: ('nine Dream Music tracks', 'December of 1941'),
                42: ('8th December, 1941', 'Bersei, Upper Perak'),
                43: ('Carvill, recording engineer', 'Sahwi, Sumatran driver')}
    if any(any(part not in texts.get(number, '') for part in parts) for number, parts in required.items()):
        raise IntakeError('Temiar 目录署名、日期或照片说明变化，须复核。')
    return manifest, rows


def group_evidence(rows: list[dict]) -> dict:
    return {'馆藏名原字段': 'Senoi Collection', '馆方总体收藏者字段': 'Aileen Margaret (Peggy) Robertson',
            '馆藏总体语言字段': '(Ple-)Temiar', '馆藏总体日期字段': '1941',
            '总述音轨数': 10, '总述另列后期音轨数': 5, '歌曲说明文件所称音轨数': 9,
            '网页编号条目数': len(rows), '数量说明': '总述、歌曲说明与编号目录的统计单位和对应关系未核。',
            '共用旧档案链接的目录序号': [10, 45]}


def evidence(row: dict) -> dict:
    number = row['number']
    name = {1: 'Aileen Margaret Robertson', 23: 'Peggy Robertson', 29: 'H.D. Noone', 30: 'H.D. Noone'}.get(number)
    role = {1: '目录称笔记记录者', 23: '目录称回忆撰写者', 29: '目录称评论撰写者', 30: '目录称评论撰写者'}.get(number)
    return {'目录序号': number, '目录题名': row['title'], '本项目筛查类别': category(number),
            '目录明确署名': name, '目录中署名的角色': role,
            '照片说明的日期线索': '8 December 1941' if number == 42 else None,
            '照片说明的地点线索': 'Bersei, Upper Perak' if number == 42 else None,
            '照片说明的角色线索': {'Carvill': 'recording engineer', 'Sahwi': 'Sumatran driver'} if number == 43 else None,
            '旧档案链接': row['archive_url'], '目录所列试听入口': row['audio_url'],
            '试听入口状态': '仅保留旧链接，未请求或核验' if row['audio_url'] else None,
            '对照目录序号': COMPARISONS.get(number)}


def load_current(folder: Path, rows: list[dict]) -> dict:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    raw = (folder / 'item.html').read_bytes()
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or manifest.get('url') != CURRENT_ITEM_URL or manifest.get('path') != 'item.html'
            or manifest.get('sha256') != sha256(raw).hexdigest() or manifest.get('bytes') != len(raw)
            or not manifest.get('observed_at')):
        raise IntakeError('剑桥 Temiar 单件网页快照或清单不符。')
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    archive = [a for a in soup.find_all('a', href=True) if a['href'].strip() == rows[32]['archive_url']]
    author = [a for a in soup.find_all('a', href=True) if a['href'] == '/browse/author?startsWith=Carvill'
              and a.get_text(' ', strip=True) == 'Carvill']
    wrapper = author[0].find_parent('ds-metadata-field-wrapper') if len(author) == 1 else None
    header = wrapper.find('h2').get_text(' ', strip=True) if wrapper and wrapper.find('h2') else ''
    rights = [a for a in soup.find_all('a', id='cc-name') if a.get_text(' ', strip=True) == 'All Rights Reserved']
    if title != rows[32]['title'] or len(archive) != 1 or header != 'Authors' or len(rights) != 1:
        raise IntakeError('剑桥 Temiar 单件题名、旧档案标识、作者字段或权利标记变化，须复核。')
    return {'对应旧档案链接': rows[32]['archive_url'], '现行单件题名': title, '现行单件 Authors 字段': 'Carvill',
            '同目录照片第 43 条角色线索': 'Carvill, recording engineer', '姓名与角色说明': '同名是否同一人及其在本条录音中的角色须核；不能直接视作演唱者。',
            '现行单件权利标记': 'All Rights Reserved', '现行单件链接': CURRENT_ITEM_URL}


def cards(folder: Path, current: Path | None = None):
    _, rows = load_snapshot(folder)
    current_data = load_current(current, rows) if current else None
    catalogue, receipt = folder / 'catalogue.html', folder / 'manifest.json'
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False,
              'spatial': {'precision': 'culture_region', 'location_name': 'Temiar 馆藏总体范围；单件地点待核',
                          'culture_region': 'Southeast Asia · Malaysia'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    parent = {'citation': 'World Oral Literature Project, Robertson 馆藏目录；网站保留权利，单件权利另核。',
              'type': 'temiar_wolp_catalogue', 'url': CATALOGUE_URL, 'locator': '馆藏总述与编号目录',
              'local_path': display_path(catalogue), 'content_sha256': sha256(catalogue.read_bytes()).hexdigest()}
    receipt_source = {'citation': '本地原网页快照与网站条款清单；仅供个人或内部非商业研究。',
                      'type': 'temiar_wolp_manifest', 'url': TERMS_URL, 'locator': '目录与网站条款快照清单',
                      'local_path': display_path(receipt), 'content_sha256': sha256(receipt.read_bytes()).hexdigest()}
    root = {**common, 'id': ROOT_ID, 'title': '马来西亚 Temiar 叙事歌曲 · Robertson 馆藏目录',
            'sources': [parent, receipt_source]}
    body = ('\n## 馆藏总述核对字段\n\n' + literal_block(json.dumps(group_evidence(rows), ensure_ascii=False, indent=2))
            + '\n\n## 复核范围\n\n音轨、照片、书信及目录条目是不同单位；不能作为独立故事数量。'
              'Senoi 是目录历史名称，需按社区与语言自称分别核对；录音、转写与附件未下载。'
              '照片地点和日期不能直接赋给每条歌曲。网站材料仅用于本地个人或内部非商业研究，'
              '单件权利与社区要求另核。\n')
    yield NodeMetadata.model_validate(root), body
    for row in rows:
        number = row['number']
        if number not in SELECTED: continue
        related = [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                    'note': '同一馆藏的目录条目，不表示同一故事、演述或采录地点。'}]
        if number in COMPARISONS:
            related.append({'type': 'COMPARED_WITH', 'target': node_id(COMPARISONS[number]),
                            'note': '目录题名或作者相近，仅作待核对照，不证明同一版本、同源或连续演述。'})
        old = {'citation': '项目目录中的旧剑桥档案入口；单件详情待核。', 'type': MARKER,
               'url': row['archive_url'], 'locator': f'目录第 {number} 条 / 旧档案入口待核'}
        sources = [old]
        if row['audio_url']:
            sources.append({'citation': '项目目录列出的试听入口；本地未请求音频及核验许可。', 'type': AUDIO_MARKER,
                            'url': row['audio_url'], 'locator': f'目录第 {number} 条 / 旧试听入口待核'})
        sources += [parent, receipt_source]
        if number == 33 and current_data is not None:
            page, current_receipt = current / 'item.html', current / 'manifest.json'
            sources += [{'citation': '剑桥大学 Apollo 单件目录；单件标注 All Rights Reserved。',
                         'type': 'temiar_wolp_current', 'url': CURRENT_ITEM_URL, 'locator': '单件目录 / 旧档案标识及 Authors',
                         'local_path': display_path(page), 'content_sha256': sha256(page.read_bytes()).hexdigest()},
                        {'citation': '本地剑桥单件网页快照清单；未下载音频。', 'type': 'temiar_wolp_current_manifest',
                         'url': CURRENT_ITEM_URL, 'locator': '单件目录网页快照清单', 'local_path': display_path(current_receipt),
                         'content_sha256': sha256(current_receipt.read_bytes()).hexdigest()}]
        song = number in SONGS
        model = {**common, 'node_type': 'case' if song else 'myth_corpus', 'z_layer': 1 if song else 2,
                 'id': node_id(number), 'title': f"Temiar 馆藏目录 · {row['title']}", 'aliases': [row['title']],
                 'relations': related, 'sources': sources}
        body = ('\n## 目录字段与筛查线索\n\n' + literal_block(json.dumps(evidence(row), ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n本卡为目录条目，音轨不是已经核实的一篇独立故事；'
                  '背景文书或照片也不是演述。馆藏总体语言、年代与地点不能直接赋给单件；'
                  '旧档案及试听入口、演述者、单件许可、社区要求均待核，音频和附件未下载。'
                  '历史研究评论不自动代表 Temiar 社区观点。坐标、叙事年代与标准码留空。\n')
        if number in COMPARISONS:
            body += '\n本卡的对照仅基于题名或目录署名，不证明连续、同版、同源或传播。\n'
        if number == 33 and current_data is not None:
            body += ('\n## 现行剑桥单件目录对照\n\n' + literal_block(json.dumps(current_data, ensure_ascii=False, indent=2))
                     + '\n\n目录作者字段与照片角色线索分开保留，身份及演述角色须核；单件标注 All Rights Reserved。\n')
        yield NodeMetadata.model_validate(model), body
