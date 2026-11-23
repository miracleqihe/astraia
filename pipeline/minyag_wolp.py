"""Screen the Sichuan Mi nyag catalogue without copying recordings or narratives."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.fetch_minyag_wolp import CATALOGUE_URL, TERMS_URL
from pipeline.fetch_minyag_current import ITEM_URL as CURRENT_ITEM_URL
from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_cn_minyag_wolp_2009'
PREFIX = 'case_cn_minyag_wolp_'
MARKER = 'minyag_wolp_archive_link'
SELECTED = set(range(1, 21)) | {38, 39, 40} | set(range(43, 54))
COMPARISONS = {19: 16, 20: 7}
NAMES = {1: 'A lca', 2: 'A lca', 3: 'A lca', 4: 'Dbal bzang', 5: "Ste 'dzin",
         14: 'U rgyan dbang phyung', 15: 'U rgyan dbang phyung',
         19: 'U gyan dbang phyung', 38: 'U rgyan dbang phyung', 39: 'U rgyan dbang phyung',
         40: 'U rgyan dbang phyung', 43: 'U rgyan dbang phyung',
         **{n: "Tshe 'dzin" for n in (*range(44, 50), *range(51, 54))}, 50: 'Pad ma rgyal mtshan'}


def catalogue_rows(raw: bytes) -> list[dict]:
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    text = soup.get_text(' ', strip=True)
    for required in ('77 audio files', 'Bkra shis bzang po', 'Bang smad Village', 'Ri sne Village',
                     'Sichuan Province', 'October and November of 2009', 'Khams Tibetan'):
        if required not in text:
            raise IntakeError('木雅语馆藏总述字段变化，须重新核对。')
    rows = []
    for paragraph in soup.find_all('p'):
        content = paragraph.get_text(' ', strip=True)
        match = re.match(r'^(\d+)\.\s', content)
        if not match:
            continue
        number = int(match.group(1))
        strong, anchors = paragraph.find('strong'), paragraph.find_all('a', href=True)
        if not strong or len(anchors) != 1:
            raise IntakeError(f'木雅语目录条目题名或链接不唯一：{number}')
        title, url = strong.get_text(' ', strip=True), anchors[0]['href'].strip()
        if (not title or not re.fullmatch(r'http://www\.dspace\.cam\.ac\.uk/handle/1810/\d+', url)
                or anchors[0].get_text(strip=True) != '[Archive]'):
            raise IntakeError(f'木雅语目录条目题名或旧档案链接异常：{number}')
        name = NAMES.get(number)
        if name and not content.startswith(f'{number}. {title} {name} '):
            raise IntakeError(f'木雅语条目署名候选与目录不符：{number}')
        rows.append({'number': number, 'title': title, 'archive_url': url, 'named_in_description': name})
    if [row['number'] for row in rows] != list(range(1, 63)) or len({row['archive_url'] for row in rows}) != 62:
        raise IntakeError('木雅语目录编号或旧档案链接缺失或重复。')
    return rows


def load_snapshot(folder: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404'):
        raise IntakeError('木雅语目录快照清单版本或 robots 状态异常。')
    entries = manifest.get('pages')
    if not isinstance(entries, list) or len(entries) != 2:
        raise IntakeError('木雅语目录快照清单不完整。')
    for item, (name, url) in zip(entries, [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)], strict=True):
        raw = (folder / name).read_bytes()
        if (item.get('path') != name or item.get('url') != url or item.get('sha256') != sha256(raw).hexdigest()
                or item.get('bytes') != len(raw) or not item.get('observed_at')):
            raise IntakeError(f'木雅语目录快照来源或哈希不符：{name}')
    terms = BeautifulSoup((folder / 'terms.html').read_bytes().decode('utf-8'), 'html.parser').get_text(' ', strip=True)
    if not all(part in terms for part in ('personal non-commercial use', 'internal non-commercial circulation',
                                          'prior written permission', 'proprietary notices')):
        raise IntakeError('网站条款变化，暂停本地目录处理并复核。')
    return manifest, catalogue_rows((folder / 'catalogue.html').read_bytes())


def category(number: int) -> str:
    if number in {1, 2, 3}: return '仪式演说线索'
    if number == 5: return '节庆与地方史线索'
    if number == 9: return '谜语线索'
    if number in {14, 15}: return '狩猎口述线索'
    if number == 16: return '地方人物口述史线索'
    if number in {38, 39}: return '地方观念与口语线索'
    if number == 43: return '谚语线索'
    if number in SELECTED: return '目录称故事或故事题名线索'
    if number in set(range(21, 38)) | {41, 42}: return '歌曲；本轮未选'
    return '游戏；本轮未选'


def group_evidence(rows: list[dict]) -> dict:
    return {'项目': 'World Oral Literature Project', '采录者': 'Bkra shis bzang po',
            '馆藏语言原字段': 'Mi nyag, Minyak, Muya, Nyag skad, Khams Tibetan',
            '馆藏总体范围': 'Bang smad Village / Ri sne Village, Sichuan Province, China',
            '馆藏总体采录时间': 'October and November 2009', '总述所称音频文件数': 77,
            '页面有序编号条目数': len(rows), '数量说明': '文件数与编号条目数的对应关系未核；不推定缺失。'}


def load_current(folder: Path, rows: list[dict]) -> dict:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    raw = (folder / 'item.html').read_bytes()
    if (manifest.get('version') != 1 or manifest.get('robots_status') not in ('200', '404')
            or manifest.get('url') != CURRENT_ITEM_URL or manifest.get('path') != 'item.html'
            or manifest.get('sha256') != sha256(raw).hexdigest() or manifest.get('bytes') != len(raw)
            or not manifest.get('observed_at')):
        raise IntakeError('剑桥单件网页快照或清单不符。')
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    old_url = rows[18]['archive_url']
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    old_links = [anchor for anchor in soup.find_all('a', href=True) if anchor['href'].strip() == old_url]
    name = 'O rgyan dban phyugs'
    descriptions = [p for p in soup.find_all('p') if p.get_text(' ', strip=True).startswith(name + ' tells a story')]
    rights = [a for a in soup.find_all('a', id='cc-name') if a.get_text(' ', strip=True) == 'All Rights Reserved']
    if (title != 'A Story of Bu lung ma (Mgon po rnam rgyal)' or len(old_links) != 1
            or len(descriptions) != 1 or len(rights) != 1 or rows[18]['named_in_description'] != 'U gyan dbang phyung'):
        raise IntakeError('剑桥单件题名、旧档案标识、姓名或权利标记变化，须重新核对。')
    return {'对应旧档案链接': old_url, '旧目录段落署名候选': rows[18]['named_in_description'],
            '现行单件题名': title, '现行单件描述姓名原写法': name,
            '现行单件权利标记': 'All Rights Reserved', '现行单件链接': CURRENT_ITEM_URL,
            '姓名说明': '两处写法不同；是否为同一人物及角色须人工核对。'}


def evidence(row: dict) -> dict:
    number = row['number']
    return {'目录序号': number, '目录题名': row['title'], '目录段落署名候选': row['named_in_description'],
            '本项目筛查类别': category(number), '旧档案链接': row['archive_url'],
            '单条详情': '尚未取得；原始链接、角色、单条语言和许可须回查',
            '对照目录序号': COMPARISONS.get(number)}


def cards(folder: Path, current: Path | None = None):
    manifest, rows = load_snapshot(folder)
    current_data = load_current(current, rows) if current else None
    catalogue, receipt = folder / 'catalogue.html', folder / 'manifest.json'
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False,
              'spatial': {'precision': 'culture_region', 'location_name': '四川木雅语馆藏范围；单条录音地点待核',
                          'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    parent = {'citation': 'World Oral Literature Project, Bkra shis bzang po 馆藏目录；网站保留权利，单件权利另核。',
              'type': 'minyag_wolp_catalogue', 'url': CATALOGUE_URL, 'locator': '馆藏总述与编号目录',
              'local_path': display_path(catalogue), 'content_sha256': sha256(catalogue.read_bytes()).hexdigest()}
    receipt_source = {'citation': '本地原网页快照与网站条款清单；仅供本地个人或内部非商业研究。',
                      'type': 'minyag_wolp_manifest', 'url': TERMS_URL, 'locator': '目录与网站条款快照清单',
                      'local_path': display_path(receipt), 'content_sha256': sha256(receipt.read_bytes()).hexdigest()}
    root = {**common, 'id': ROOT_ID, 'title': '四川木雅语口述资料 · 剑桥世界口头文学计划',
            'sources': [parent, receipt_source]}
    body = ('\n## 馆藏总述核对字段\n\n' + literal_block(json.dumps(group_evidence(rows), ensure_ascii=False, indent=2))
            + '\n\n## 复核范围\n\n页面总述的文件数与编号目录的条目数口径不同，不能推定缺失或作品数。'
              '馆藏语言、时间和地域是总体字段，不自动对应单条。网站条款限定本地个人或内部非商业使用，'
              '更多使用与单件权利、相关社区要求须另核。未获取录音或转写。\n')
    yield NodeMetadata.model_validate(root), body
    for row in rows:
        number = row['number']
        if number not in SELECTED:
            continue
        related = [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                    'note': '同一馆藏目录条目，不证明采录地点、演述或故事相同。'}]
        if number in COMPARISONS:
            related.append({'type': 'COMPARED_WITH', 'target': f"{PREFIX}{COMPARISONS[number]:02d}",
                            'note': '目录题名中有共同人物线索；须回查内容，不证明同一故事、同源或传播。'})
        original = {'citation': '馆藏目录列出的旧剑桥档案链接；单条详情未核。', 'type': MARKER,
                    'url': row['archive_url'], 'locator': f'目录第 {number} 条 / 旧档案入口待核'}
        sources = [original, parent, receipt_source]
        if number == 19 and current_data is not None:
            current_page, current_receipt = current / 'item.html', current / 'manifest.json'
            sources += [{'citation': '剑桥大学 Apollo 单件目录；单件标注 All Rights Reserved。',
                         'type': 'minyag_wolp_current', 'url': CURRENT_ITEM_URL, 'locator': '单件目录 / 旧档案标识与描述',
                         'local_path': display_path(current_page), 'content_sha256': sha256(current_page.read_bytes()).hexdigest()},
                        {'citation': '本地剑桥单件网页快照清单；未下载媒体。', 'type': 'minyag_wolp_current_manifest',
                         'url': CURRENT_ITEM_URL, 'locator': '单件目录网页快照清单', 'local_path': display_path(current_receipt),
                         'content_sha256': sha256(current_receipt.read_bytes()).hexdigest()}]
        model = {**common, 'node_type': 'case', 'z_layer': 1, 'id': f'{PREFIX}{number:02d}',
                 'title': f"四川木雅语目录 · {row['title']}", 'aliases': [row['title']],
                 'relations': related, 'sources': sources}
        body = ('\n## 目录字段与筛查线索\n\n' + literal_block(json.dumps(evidence(row), ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n这是目录条目，不自动等同一篇独立故事。段落署名只是候选，'
                  '须区分采录者、讲述者与其他角色；馆藏语言、时间和范围不自动赋给单条。'
                  '旧档案入口、内容、录音、转写、权利及相关社区要求均待核，未获取录音或转写。'
                  '坐标、叙事年代和标准码留空。对照只表示题名中的人物线索，不能推定同源或传播。\n')
        if number == 19 and current_data is not None:
            body += ('\n## 现行剑桥单件目录对照\n\n' + literal_block(json.dumps(current_data, ensure_ascii=False, indent=2))
                     + '\n\n两处姓名分别保留；单件标注 All Rights Reserved，不自动继承项目网站的使用条款。\n')
        yield NodeMetadata.model_validate(model), body
