"""Select unchanged, pending Pangloss recordings for resumable detail enrichment."""
from hashlib import sha256
from pathlib import Path
import re

from pipeline.ingest_agent import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_na import catalogue_rows, load_selection
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

CONFIG = {
    'khmu': {'name': 'Khmu', 'url': 'https://pangloss.cnrs.fr/corpus/Khmu',
             'folder': 'asia_sea_pangloss_khmu', 'prefix': 'case_sea_khmu_', 'source': 'pangloss_khmu'},
    'japhug': {'name': 'Japhug', 'url': 'https://pangloss.cnrs.fr/corpus/Japhug',
               'folder': 'asia_cn_pangloss_japhug', 'prefix': 'case_cn_japhug_', 'source': 'pangloss_japhug'},
}
MARKER = '<!-- astraia:pangloss-detail-supplement-v1 -->'
OLD_CITATION = 'CNRS-LACITO，Pangloss 单条录音页面；详情尚未采集，需回查。'
NEW_CITATION = 'CNRS-LACITO，Pangloss 单条录音页面；首轮未采集，后续详情见补充来源。'


def _path(value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def _base(corpus: Path, initial: Path, kind: str):
    if kind not in CONFIG:
        raise IntakeError('不支持的 Pangloss 语料。')
    config = CONFIG[kind]
    catalog = catalogue_rows(corpus.read_bytes(), config['name'])
    chosen = load_selection(initial, config['url'])
    first_ids = {number for group in chosen['groups'] for number in group['ids']}
    if not first_ids.issubset(catalog):
        raise IntakeError('首轮详情选取不属于馆方目录。')
    return config, catalog, first_ids


def select_targets(vault: Path, corpus: Path, initial: Path, kind: str, limit: int) -> dict:
    if not 1 <= limit <= 200:
        raise IntakeError('每次补充详情须为 1–200 条。')
    config, catalog, first_ids = _base(corpus, initial, kind)
    corpus_hash, initial_hash = sha256(corpus.read_bytes()).hexdigest(), sha256(initial.read_bytes()).hexdigest()
    entries = []
    folder = vault / '00_drafts' / config['folder']
    with vault_writer(vault):
        for number, row in catalog.items():
            if number in first_ids:
                continue
            path = folder / f"{config['prefix']}{number}.md"
            if not path.is_file() or path.is_symlink():
                continue
            raw = path.read_bytes()
            metadata, _ = parse_card(raw.decode('utf-8-sig').replace('\r\n','\n'))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                continue
            if any(source.type in (f"{config['source']}_detail", f"{config['source']}_supplement_detail") for source in metadata.sources):
                continue
            catalogs = [source for source in metadata.sources if source.type == f"{config['source']}_catalogue"]
            originals = [source for source in metadata.sources if source.type == f"{config['source']}_original"]
            selections = [source for source in metadata.sources if source.type == f"{config['source']}_selection"]
            if (metadata.id != path.stem or len(catalogs) != 1 or len(originals) != 1 or len(selections) != 1
                    or not catalogs[0].local_path or _path(catalogs[0].local_path) != corpus.resolve()
                    or catalogs[0].content_sha256 != corpus_hash or str(catalogs[0].url) != config['url']
                    or catalogs[0].locator != f"{config['name']} / DOI {number}"
                    or not selections[0].local_path or _path(selections[0].local_path) != initial.resolve()
                    or selections[0].content_sha256 != initial_hash or str(selections[0].url) != config['url']
                    or selections[0].locator != '未选入首轮详情' or str(originals[0].url) != row['url']
                    or originals[0].doi != row['doi'].removeprefix('https://doi.org/')
                    or originals[0].locator != f'录音 {number}' or originals[0].local_path or originals[0].content_sha256):
                raise IntakeError(f'待审卡与原目录或首轮选取不符，请先核对：{path}')
            entries.append({'id':number, 'card_sha256':sha256(raw).hexdigest()})
            if len(entries) == limit:
                break
    if not entries:
        raise IntakeError('没有可补充详情的待审录音。')
    return {'version':1, 'corpus_url':config['url'], 'corpus_sha256':corpus_hash,
            'base_selection_sha256':initial_hash,
            'selection_method':'按馆方目录顺序选取未补详情且未签核的待审卡；不是随机样本。',
            'limits':'仅追加馆方详情字段，源音视频和转写不复制；原卡变化或签核后跳过。',
            'groups':[{'id':'supplement','label':'后续详情补充','ids':[entry['id'] for entry in entries]}],
            'card_sha256':{entry['id']:entry['card_sha256'] for entry in entries}}


def validate_selection(document: dict, corpus: Path, initial: Path, kind: str) -> tuple[dict, dict]:
    config, catalog, first_ids = _base(corpus, initial, kind)
    if (not isinstance(document, dict) or document.get('version') != 1 or document.get('corpus_url') != config['url']
            or document.get('corpus_sha256') != sha256(corpus.read_bytes()).hexdigest()
            or document.get('base_selection_sha256') != sha256(initial.read_bytes()).hexdigest()
            or not all(isinstance(document.get(key),str) and document[key].strip() for key in ('selection_method','limits'))
            or not isinstance(document.get('groups'),list) or len(document['groups']) != 1):
        raise IntakeError('详情补充选取与来源或首轮选取不符。')
    group = document['groups'][0]
    if (not isinstance(group,dict) or group.get('id') != 'supplement' or group.get('label') != '后续详情补充'
            or not isinstance(group.get('ids'),list) or not 1 <= len(group['ids']) <= 200):
        raise IntakeError('详情补充选取分组无效。')
    ids = group['ids']
    if (any(not isinstance(number,str) or not re.fullmatch(r'\d{7}',number) or number not in catalog or number in first_ids for number in ids)
            or len(ids) != len(set(ids))):
        raise IntakeError('详情补充编号重复、不在目录或已在首轮选取。')
    hashes = document.get('card_sha256')
    if (not isinstance(hashes,dict) or set(hashes) != set(ids)
            or any(not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{64}',value) for value in hashes.values())):
        raise IntakeError('详情补充草稿哈希清单不符。')
    return catalog, group
