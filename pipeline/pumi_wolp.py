"""Stage the Wangjiagou Pumi recording directory as attributed review drafts."""
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.fetch_minyag_wolp import TERMS_URL
from pipeline.fetch_pumi_current import ITEM_URL as CURRENT_ITEM_URL
from pipeline.fetch_pumi_wolp import CATALOGUE_URL
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_cn_pumi_wolp'
PREFIX = 'case_cn_pumi_wolp_'
MARKER = 'pumi_wolp_archive_link'
AUDIO_MARKER = 'pumi_wolp_audio_link'
COMPARISONS = {27: 15}
KIND_NAMES = {'song': '歌曲题名', 'interview': '访谈题名', 'ritual': '仪式题名',
              'speech': '演说题名', 'story': '故事题名'}


def classify_title(title: str) -> str:
    if re.match(r'^Interview \d+,', title): return 'interview'
    if re.match(r'^Ritual \d+,', title): return 'ritual'
    if re.match(r'^Speech \d+,', title): return 'speech'
    if re.match(r'^Story \d+,', title): return 'story'
    if re.match(r'^(?:(?:Drinking|Folk|Love|Religious|Wedding) )?Song \d+,', title): return 'song'
    raise IntakeError(f'普米语目录题名无法按原标签筛查：{title}')


def catalogue_rows(raw: bytes) -> list[dict]:
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    text = soup.get_text(' ', strip=True)
    if not all(value in text for value in ('Hu Qianma', 'Wangjiagou', 'forty-five audio files', 'Pumi', 'Premi',
                                            'February 2008', 'February 2011')):
        raise IntakeError('普米语馆藏总述发生变化，须核对。')
    rows = []
    for paragraph in soup.find_all('p'):
        content = paragraph.get_text(' ', strip=True)
        match = re.match(r'^(\d+)\.\s', content)
        if not match: continue
        number, strong = int(match.group(1)), paragraph.find('strong')
        archive = [a['href'].strip() for a in paragraph.find_all('a', href=True) if a.get_text(strip=True) == '[Archive]']
        audio = [a['href'].strip() for a in paragraph.find_all('a', href=True) if a.get_text(strip=True) == '[Listen to audio]']
        if (strong is None or len(archive) != 1 or len(audio) != 1
                or not re.fullmatch(r'http://www\.dspace\.cam\.ac\.uk/handle/1810/\d+', archive[0])
                or not re.fullmatch(r'https?://sms\.cam\.ac\.uk/media/\d+', audio[0])):
            raise IntakeError(f'普米语目录题名、旧档案或试听入口异常：{number}')
        title = strong.get_text(' ', strip=True)
        rows.append({'number': number, 'title': title, 'title_kind': classify_title(title),
                     'archive_url': archive[0], 'audio_url': audio[0]})
    if ([r['number'] for r in rows] != list(range(1, 46))
            or len({r['archive_url'] for r in rows}) != 45 or len({r['audio_url'] for r in rows}) != 45):
        raise IntakeError('普米语目录编号、档案或试听入口缺失或重复。')
    counts = Counter(row['title_kind'] for row in rows)
    if counts != {'song': 25, 'interview': 12, 'ritual': 3, 'speech': 1, 'story': 4}:
        raise IntakeError('普米语目录题名分类或数量变化，须重新筛查。')
    if not all('madami' in rows[n-1]['title'].casefold() for n in (15, 27)):
        raise IntakeError('普米语同名歌曲对照线索变化，须复核。')
    return rows


def load_snapshot(folder: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404'):
        raise IntakeError('普米语目录快照清单版本或 robots 状态异常。')
    entries = manifest.get('pages')
    if not isinstance(entries, list) or len(entries) != 2:
        raise IntakeError('普米语目录快照清单不完整。')
    for entry, (name, url) in zip(entries, [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)], strict=True):
        raw = (folder / name).read_bytes()
        if (entry.get('path') != name or entry.get('url') != url or entry.get('sha256') != sha256(raw).hexdigest()
                or entry.get('bytes') != len(raw) or not entry.get('observed_at')):
            raise IntakeError(f'普米语目录快照来源或哈希不符：{name}')
    terms = BeautifulSoup((folder / 'terms.html').read_bytes().decode('utf-8'), 'html.parser').get_text(' ', strip=True)
    if not all(value in terms for value in ('personal non-commercial use', 'internal non-commercial circulation',
                                            'prior written permission', 'proprietary notices')):
        raise IntakeError('网站条款变化，须重新确认。')
    return manifest, catalogue_rows((folder / 'catalogue.html').read_bytes())


def load_current(folder: Path, rows: list[dict]) -> dict:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    raw = (folder / 'item.html').read_bytes()
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or manifest.get('url') != CURRENT_ITEM_URL or manifest.get('path') != 'item.html'
            or manifest.get('sha256') != sha256(raw).hexdigest() or manifest.get('bytes') != len(raw)
            or not manifest.get('observed_at')):
        raise IntakeError('剑桥普米语单件网页快照或清单不符。')
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    old = [a for a in soup.find_all('a', href=True) if a['href'].strip() == rows[40]['archive_url']]
    authors = [a for a in soup.find_all('a', href=True) if a.get_text(' ', strip=True) == 'Hu Qianma'
               and a['href'].startswith('/browse/author?')]
    wrapper = authors[0].find_parent('ds-metadata-field-wrapper') if len(authors) == 1 else None
    label = wrapper.find('h2').get_text(' ', strip=True) if wrapper and wrapper.find('h2') else ''
    rights = soup.find('a', id='cc-name', href=True)
    visible = soup.get_text(' ', strip=True)
    right_text = 'Attribution-NonCommercial-NoDerivs 2.0 UK: England & Wales'
    if (title != rows[40]['title'] or len(old) != 1 or label != 'Authors' or 'forty-six audio files' not in visible
            or not rights or rights.get_text(' ', strip=True) != right_text
            or rights['href'] != 'http://creativecommons.org/licenses/by-nc-nd/2.0/uk/'):
        raise IntakeError('剑桥普米语单件的题名、档号、作者、文件数或许可变化，须复核。')
    return {'旧档案链接': rows[40]['archive_url'], '现行单件题名': title, '现行单件 Authors 字段': 'Hu Qianma',
            '旧目录馆藏总述音频文件数': 45, '现行单件馆藏总述音频文件数': 46,
            '数量说明': '两处原值不同；统计口径与目录编号对应关系须核，不推定缺失或增补。',
            '现行单件许可原字段': right_text, '现行单件许可链接': rights['href'],
            '现行单件链接': CURRENT_ITEM_URL,
            '角色说明': 'Authors 字段与旧目录馆藏采录者字段分开保留；演述者尚未核实。'}


def group_evidence(rows: list[dict], current: dict | None) -> dict:
    return {'馆藏名称原字段': 'Wangjiagou Pumi Collection', '馆藏总体采录者字段': 'Hu Qianma',
            '馆藏总体语言字段': 'Pumi, Premi', '馆藏总体地点字段': 'Wangjiagou, Jinmian Township, Ninglang County, Yunnan',
            '馆藏总体采录时间': 'February 2008 – February 2011', '旧目录总述音频文件数': 45,
            '页面有序编号条目数': len(rows), '现行单件所载馆藏文件数': current['现行单件馆藏总述音频文件数'] if current else None,
            '题名标签计数': {KIND_NAMES[key]: sum(row['title_kind'] == key for row in rows) for key in KIND_NAMES},
            '数量说明': '文件数、编号条目与作品数的对应关系尚未核实。'}


def evidence(row: dict) -> dict:
    number = row['number']
    return {'目录序号': number, '目录题名': row['title'], '目录题名标签': KIND_NAMES[row['title_kind']],
            '旧档案链接': row['archive_url'], '目录所列试听入口': row['audio_url'],
            '试听入口状态': '仅保留旧链接，未请求或核验', '对照目录序号': COMPARISONS.get(number)}


def cards(folder: Path, current: Path | None = None):
    _, rows = load_snapshot(folder)
    current_data = load_current(current, rows) if current else None
    catalogue, receipt = folder / 'catalogue.html', folder / 'manifest.json'
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False,
              'spatial': {'precision': 'culture_region', 'location_name': '云南王家沟普米语馆藏总体范围；单条地点待核',
                          'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    parent = {'citation': 'World Oral Literature Project, Hu Qianma 普米语馆藏目录；网站保留权利，单件权利另核。',
              'type': 'pumi_wolp_catalogue', 'url': CATALOGUE_URL, 'locator': '馆藏总述与编号目录',
              'local_path': display_path(catalogue), 'content_sha256': sha256(catalogue.read_bytes()).hexdigest()}
    receipt_source = {'citation': '本地原网页快照与网站条款清单；仅供个人或内部非商业研究。',
                      'type': 'pumi_wolp_manifest', 'url': TERMS_URL, 'locator': '目录与网站条款快照清单',
                      'local_path': display_path(receipt), 'content_sha256': sha256(receipt.read_bytes()).hexdigest()}
    current_sources = []
    if current_data is not None:
        page, current_receipt = current / 'item.html', current / 'manifest.json'
        current_sources = [{'citation': '剑桥大学 Apollo 第 41 条单件目录；所标许可仅适用于该单件。',
                            'type': 'pumi_wolp_current', 'url': CURRENT_ITEM_URL, 'locator': '单件目录 / 旧档案标识、馆藏数量与许可',
                            'local_path': display_path(page), 'content_sha256': sha256(page.read_bytes()).hexdigest()},
                           {'citation': '本地剑桥单件网页快照清单；未下载音频及附件。', 'type': 'pumi_wolp_current_manifest',
                            'url': CURRENT_ITEM_URL, 'locator': '单件目录网页快照清单', 'local_path': display_path(current_receipt),
                            'content_sha256': sha256(current_receipt.read_bytes()).hexdigest()}]
    group = group_evidence(rows, current_data)
    root = {**common, 'id': ROOT_ID, 'title': '云南王家沟普米语口述资料 · 项目目录',
            'sources': [parent, receipt_source, *current_sources]}
    body = ('\n## 馆藏总述核对字段\n\n' + literal_block(json.dumps(group, ensure_ascii=False, indent=2))
            + '\n\n## 复核范围\n\n音频文件、目录条目及独立作品是不同的计数单位。馆藏总体语言、采录时间与地点'
              '不自动确定每条演述及其发生地。目录题名标签仅供筛查；历史叙事及地方观念应作为具体讲述复核，'
              '不能直接当作已证实历史或群体共同观点。网站材料仅用于本地个人或内部非商业研究；'
              '单件和相关社区的使用条件另核，未获取音频、转写或附件。\n')
    if current_data:
        body += ('\n## 现行单件目录对照\n\n' + literal_block(json.dumps(current_data, ensure_ascii=False, indent=2))
                 + '\n\n此处单件许可不自动适用于其他录音。\n')
    yield NodeMetadata.model_validate(root), body
    for row in rows:
        number = row['number']
        related = [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                    'note': '同一馆藏目录条目，不证明同一演述、故事或采录地点。'}]
        if number in COMPARISONS:
            related.append({'type': 'COMPARED_WITH', 'target': f'{PREFIX}{COMPARISONS[number]:02d}',
                            'note': '两条目录题名均含 Madami；仅供比较，不证明同一演述、版本或传播。'})
        original = {'citation': '项目目录中的旧剑桥档案入口；单条详情待核。', 'type': MARKER,
                    'url': row['archive_url'], 'locator': f'目录第 {number} 条 / 旧档案入口待核'}
        audio = {'citation': '项目目录所列试听入口；未请求音频，权限待核。', 'type': AUDIO_MARKER,
                 'url': row['audio_url'], 'locator': f'目录第 {number} 条 / 旧试听入口待核'}
        sources = [original, audio, parent, receipt_source, *(current_sources if number == 41 else [])]
        model = {**common, 'node_type': 'case', 'z_layer': 1, 'id': f'{PREFIX}{number:02d}',
                 'title': f"云南普米语目录 · {row['title']}", 'aliases': [row['title']],
                 'relations': related, 'sources': sources}
        text = ('\n## 目录字段与筛查线索\n\n' + literal_block(json.dumps(evidence(row), ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n目录题名标签不能替代对音频、转写和语境的核查；一条录音不等于一篇独立故事。'
                  '馆藏总体地点、语言与采录时间不自动赋给本条；采录者与演述者的角色须区分。'
                  '历史叙事和地方观念应作为具体演述核实，不能直接当作历史事实或群体共同观点。'
                  '旧档案及试听入口、单件许可和社区要求待核；本地未下载音频或附件。'
                  '坐标、叙事年代与标准码留空。\n')
        if number in COMPARISONS:
            text += '\nMadami 只是两条目录题名的对照线索，不证明同一演述、版本或传播。\n'
        if number == 41 and current_data:
            text += ('\n## 现行剑桥单件目录对照\n\n' + literal_block(json.dumps(current_data, ensure_ascii=False, indent=2))
                     + '\n\n单件许可仅见于此页面，不能自动套用到其他资源。\n')
        yield NodeMetadata.model_validate(model), text
