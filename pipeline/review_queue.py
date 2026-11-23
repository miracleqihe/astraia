"""Build a source-aware review catalogue for the Scottish and Berezkin drafts."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
from hashlib import file_digest, sha256
from io import StringIO
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unicodedata
from urllib.parse import urlsplit
from zipfile import ZipFile

from bs4 import BeautifulSoup
from pyproj import Transformer
import yaml

from pipeline.berezkin_distribution import REGIONAL_HUBS, read_study, region_crosschecks
from pipeline.bl_khmer import ROOT_ID as BL_KHMER_ROOT, ROOT_URL as BL_KHMER_URL, load_snapshot as load_bl_khmer
from pipeline.bl_yi import (ROOT_ID as BL_YI_ROOT, PREFIX as BL_YI_PREFIX, child_evidence as bl_yi_child_evidence,
    group_evidence as bl_yi_group_evidence, duration_minutes as bl_yi_duration)
from pipeline.bl_burma import (ROOT_ID as BL_BURMA_ROOT, PREFIX as BL_BURMA_PREFIX, REMOTE_MARKER as DSAL_BURMA_MARKER,
    candidates as bl_burma_candidates, selected_candidate as bl_burma_selected, group_evidence as bl_burma_group_evidence,
    item_evidence as bl_burma_item_evidence, source_set as bl_burma_source_set)
from pipeline.bl_dongjing import (ROOT_ID as BL_DONGJING_ROOT, PREFIX as BL_DONGJING_PREFIX,
    group_evidence as bl_dongjing_group_evidence, item_evidence as bl_dongjing_item_evidence,
    source_set as bl_dongjing_source_set)
from pipeline.bl_yi_project import (ROOT_ID as BL_YI_PROJECT_ROOT, GROUP_PREFIX as BL_YI_PROJECT_GROUP_PREFIX,
    CASE_PREFIX as BL_YI_PROJECT_CASE_PREFIX, group_id as bl_yi_project_group_id, node_id as bl_yi_project_node_id,
    old_id as bl_yi_project_old_id, parent_ref as bl_yi_project_parent_ref, reason as bl_yi_project_reason,
    selected as bl_yi_project_selected, title_peers as bl_yi_project_title_peers,
    root_evidence as bl_yi_project_root_evidence, group_evidence as bl_yi_project_group_evidence,
    item_evidence as bl_yi_project_item_evidence, source_set as bl_yi_project_source_set)
from pipeline.fetch_bl_yi_project import load_snapshot as load_bl_yi_project_index
from pipeline.fetch_bl_yi_project_details import load_snapshot as load_bl_yi_project_details
from pipeline.fetch_bl_dongjing import load_snapshot as load_bl_dongjing
from pipeline.fetch_bl_burma import load_snapshot as load_bl_burma
from pipeline.fetch_dsal_burma import load_snapshot as load_dsal_burma
from pipeline.fetch_bl_yi import ROOT_URL as BL_YI_URL, load_snapshot as load_bl_yi
from pipeline.duchas import cited_story_ids as duchas_cited_story_ids, school_coordinates, xml_record
from pipeline import early_asia_editions as early_editions
from pipeline.early_asia_editions import (JADE as JADE_EDITION, SALEEBY as SALEEBY_EDITION,
    JADE_ROOT, JADE_PREFIX, SALEEBY_ROOT, SALEEBY_CASE, LUMAWIG_EXISTING,
    COMPARISONS as JADE_COMPARISONS, ANDERSEN_REGISTER, ANDERSEN_TRANSLATION,
    jade_id, jade_evidence, load_jade, read_andersen, read_pages as early_read_pages,
    scan_mapping as early_scan_mapping, scan_url as early_scan_url)
from pipeline.enrich_yuhuan_credits import read_supplement as read_yuhuan_supplement
from pipeline.ingest_agent import DEFAULT_CODE_TABLE, DEFAULT_VAULT, PROJECT_ROOT, literal_block
from pipeline.graph_links import normalize_code, standard_codes
from pipeline.fetch_lao_dllm import IDENTIFIER as LAO_IDENTIFIER, parse_page as parse_lao_page
from pipeline.lao_manuscripts import (
    VIEWER as LAO_VIEWER, attribution as lao_attribution, load_snapshot as load_lao_snapshot,
    plmp_index as lao_plmp_index, selected_fields as lao_selected_fields,
)
from pipeline.khmer_nitean import (CATALOGUE_URL as NITEAN_URL, ROOT_ID as NITEAN_ROOT,
    chapter_evidence as nitean_evidence, chapter_id as nitean_chapter_id, load_snapshot as load_nitean)
from pipeline.korea_aks_cards import CASE_PREFIX as KOREA_AKS_PREFIX, ROOT_ID as KOREA_AKS_ROOT, korea_cards
from pipeline.lanna_manuscripts import ROOT_ID as LANNA_ROOT, lanna_cards
from pipeline.khmer_wikisource import URL as KHMER_WIKISOURCE_URL, load_snapshot as load_khmer_wikisource
from pipeline.chinese_heritage_2011 import (SOURCE_URL as HERITAGE_2011_URL, evidence as heritage_2011_evidence,
    register_rows as heritage_2011_rows, row_id as heritage_2011_id)
from pipeline.chinese_heritage import SOURCE_URL as HERITAGE_2006_URL, register_rows as heritage_2006_rows
from pipeline.chinese_heritage_batches import (CONFIG as HERITAGE_BATCHES, base_identity as heritage_base_identity,
    evidence as heritage_batch_evidence, project_number as heritage_project_number,
    register_rows as heritage_batch_rows, row_id as heritage_batch_id)
from pipeline.chinese_heritage_2021 import (PDF_URL as HERITAGE_2021_URL, evidence as heritage_2021_evidence,
    load_index as load_heritage_2021, row_id as heritage_2021_id)
from pipeline.local_standards import load_code_table, normalized_text
from pipeline.lowell_folktales import (COLLECTION_URL as LOWELL_SEA_URL, ROOT_ID as LOWELL_SEA_ROOT,
    evidence as lowell_sea_evidence, is_poster as lowell_is_poster, load_snapshot as load_lowell_sea)
from pipeline.fetch_minyag_wolp import CATALOGUE_URL as MINYAG_URL, TERMS_URL as MINYAG_TERMS
from pipeline.fetch_minyag_current import ITEM_URL as MINYAG_CURRENT_URL
from pipeline.minyag_wolp import (ROOT_ID as MINYAG_ROOT, PREFIX as MINYAG_PREFIX, MARKER as MINYAG_MARKER,
    SELECTED as MINYAG_SELECTED, COMPARISONS as MINYAG_COMPARISONS, category as minyag_category,
    evidence as minyag_evidence, group_evidence as minyag_group_evidence, load_snapshot as load_minyag,
    load_current as load_minyag_current)
from pipeline.fetch_temiar_wolp import CATALOGUE_URL as TEMIAR_URL
from pipeline.fetch_temiar_current import ITEM_URL as TEMIAR_CURRENT_URL
from pipeline.temiar_wolp import (ROOT_ID as TEMIAR_ROOT, MARKER as TEMIAR_MARKER, AUDIO_MARKER as TEMIAR_AUDIO_MARKER,
    SONGS as TEMIAR_SONGS, SELECTED as TEMIAR_SELECTED, COMPARISONS as TEMIAR_COMPARISONS,
    category as temiar_category, evidence as temiar_evidence, group_evidence as temiar_group_evidence,
    node_id as temiar_node_id, load_snapshot as load_temiar, load_current as load_temiar_current)
from pipeline.fetch_pumi_wolp import CATALOGUE_URL as PUMI_URL
from pipeline.fetch_pumi_current import ITEM_URL as PUMI_CURRENT_URL
from pipeline.pumi_wolp import (ROOT_ID as PUMI_ROOT, PREFIX as PUMI_PREFIX, MARKER as PUMI_MARKER,
    AUDIO_MARKER as PUMI_AUDIO_MARKER, KIND_NAMES as PUMI_KIND_NAMES, COMPARISONS as PUMI_COMPARISONS,
    evidence as pumi_evidence, group_evidence as pumi_group_evidence,
    load_snapshot as load_pumi, load_current as load_pumi_current)
from pipeline.palue_inventory import (ROOT_ID as PALUE_ROOT, PREFIX as PALUE_PREFIX, MARKER as PALUE_MARKER,
    COLLECTION_URL as PALUE_URL, evidence as palue_evidence, group_evidence as palue_group_evidence,
    node_id as palue_node_id, load_inventory as load_palue)
from pipeline.zibuyu import (ROOT_ID as ZIBUYU_ROOT, VOLUME_PREFIX as ZIBUYU_VOLUME_PREFIX,
    CASE_PREFIX as ZIBUYU_CASE_PREFIX, EXISTING_ID as ZIBUYU_EXISTING, ORIGINAL_MARKER as ZIBUYU_MARKER,
    TALK_URL as ZIBUYU_TALK_URL, evidence as zibuyu_evidence, group_evidence as zibuyu_group_evidence,
    volume_evidence as zibuyu_volume_evidence, source_set as zibuyu_source_set, volume_id as zibuyu_volume_id,
    node_id as zibuyu_node_id, load_snapshot as load_zibuyu, load_talk as load_zibuyu_talk)
from pipeline.node_model import Source
from pipeline.nichibun import card_fields
from pipeline.scottish_identity import DISTANCE_REVIEW_KM, ScottishIdentityIndex
from pipeline.scottish_witchcraft import (
    RESIDENCES, _archive_table, _choose_location, _identifier, _residence_index, historical_reference,
)
from pipeline.shandong_mirrors import load_index as load_shandong_index, story_evidence as shandong_story_evidence
from pipeline.hmml_makassar import (DATASET_PAGE as HMML_DATASET_PAGE, LEGACY as HMML_LEGACY,
    ROOT_ID as HMML_ROOT_ID, evidence as hmml_evidence, load_legacy as load_hmml_legacy,
    load_selection as load_hmml_selection)
from pipeline.philippines_sil import ROOT_ID as SIL_ROOT_ID, SOURCE_URL as SIL_SOURCE_URL, parse_catalogue as parse_sil_catalogue
from pipeline.philippines_cole import (ROOT_ID as COLE_ROOT, PREFIX as COLE_PREFIX,
    evidence as cole_evidence, load_catalogue as load_cole_catalogue, node_id as cole_node_id, scan_url as cole_scan_url)
from pipeline.cole_ocr_segments import load as load_cole_segments
from pipeline.enrich_cole_ocr import MARKER as COLE_OCR_MARKER, note as cole_ocr_note, segment_sources as cole_segment_sources
from pipeline.na_tone_crosswalk import load as load_na_tone_index
from pipeline.enrich_na_tone import (BOOK_PAGE as NA_TONE_BOOK_PAGE, FLAG_TEXT as NA_TONE_FLAGS, MARKER as NA_TONE_MARKER,
    NEW_MARKER as NA_TONE_NEW_MARKER, new_evidence as na_tone_new_evidence,
    new_selection as na_tone_new_selection, note as na_tone_note, sources as na_tone_sources,
    summary as na_tone_summary)
from pipeline.pangloss_na import (CORPUS_URL as PANGLOSS_NA_URL, ROOT_ID as PANGLOSS_NA_ROOT, LOCATION_PAPER as PANGLOSS_LOCATION_PAPER,
    catalogue_rows as pangloss_catalogue_rows, detail_fields as pangloss_detail_fields,
    evidence as pangloss_evidence, json_object as pangloss_json_object,
    load_selection as load_pangloss_selection, load_snapshots as load_pangloss_snapshots)
from pipeline.pangloss_na_context import validate_selection as validate_pangloss_na_context
from pipeline.pangloss_na_catalogue import (MARKER as NA_CANDIDATE_MARKER, PREFIX as NA_CANDIDATE_PREFIX,
    evidence as na_candidate_evidence, validate_selection as validate_na_candidates)
from pipeline.pangloss_japhug import (CORPUS_URL as JAPHUG_URL, ROOT_ID as JAPHUG_ROOT,
    recording_evidence as japhug_evidence)
from pipeline.pangloss_khmu import (CORPUS_URL as KHMU_URL, ROOT_ID as KHMU_ROOT,
    comparison_evidence as khmu_comparison_evidence, load_comparisons as load_khmu_comparisons,
    speaker_identity_unverified as khmu_speaker_identity_unverified, title_suggests_multiple_or_part as khmu_multi_or_part,
    title_mentions_other_language as khmu_other_language, compare_recording_ranges as compare_khmu_recording_ranges)
from pipeline.pangloss_supplement import (CONFIG as PANGLOSS_SUPPLEMENT_CONFIG, MARKER as PANGLOSS_SUPPLEMENT_MARKER,
    NEW_CITATION as PANGLOSS_SUPPLEMENT_CITATION, validate_selection as validate_pangloss_supplement)
from pipeline.pangloss_annotations import primary_oai as pangloss_primary_oai, read_index as read_pangloss_annotation_index, viewer_url as pangloss_viewer_url
from pipeline.enrich_pangloss_annotations import MARKER as PANGLOSS_ANNOTATION_MARKER, card_summary as pangloss_annotation_summary
from pipeline.fetch_sinica_oral import GROUPS as SINICA_GROUPS, detail_url as sinica_detail_url
from pipeline.sinica_oral import load_snapshot as load_sinica_snapshot
from pipeline.sinica_gis import DATA_URL as SINICA_GIS_URL, candidates as sinica_gis_candidates, load_gis as load_sinica_gis, locator as sinica_gis_locator
from pipeline.fetch_vietnam_cham import INTRO as VIETNAM_CHAM_INTRO, RIGHTS as VIETNAM_CHAM_RIGHTS, story_url as vietnam_cham_story_url
from pipeline.thai_folktales import original_text as thai_original_text, read_dataset as read_thai_dataset
from pipeline.yuhuan_stories import PDF_URL as YUHUAN_PDF_URL, pdf_page as yuhuan_pdf_page, read_index as read_yuhuan_index
from pipeline.vault import load_vault, parse_card
from pipeline.vault_write import vault_writer

DEFAULT_TABLES = PROJECT_ROOT / ".local/import-sources/scottish-witches-tables.zip"
DEFAULT_SCHEMA = PROJECT_ROOT / ".local/import-sources/scottish-witches-schema.sql"
DEFAULT_MAPS = PROJECT_ROOT / ".local/import-sources/scottish-witches-maps.zip"
DEFAULT_WIKIDATA = PROJECT_ROOT / ".local/import-sources/wikidata-scottish-p4478.json"
DEFAULT_STUDY = PROJECT_ROOT / ".local/import-sources/liu-2022-supplement-3.zip"
DEFAULT_CATALOGUE = PROJECT_ROOT / ".local/import-sources/berezkin-english-catalogue.html"
DEFAULT_OUTPUT = PROJECT_ROOT / "web/public/review"
REVIEW_NOTES = PROJECT_ROOT / "reference/berezkin_review_notes.yaml"
STANDARD_NAMES = {"atu_types": "ATU", "thompson_motifs": "汤普森", "berezkin_codes": "别列兹金", "ocm_codes": "OCM"}


def issue(category: str, code: str, description: str, *, urgent: bool = False) -> dict:
    return {"category": category, "code": code, "description": description, "urgent": urgent}


def json_block_preserved(markdown: str, expected: dict) -> bool:
    """Compare parsed JSON blocks, including quoted or escaped source values."""
    fences = re.finditer(r"(?ms)^(?P<fence>`{3,})[ \t]*\r?\n(?P<content>.*?)\r?\n(?P=fence)[ \t]*$", markdown)
    for block in fences:
        try:
            document = json.loads(block.group("content"))
        except json.JSONDecodeError:
            continue
        if isinstance(document, dict) and all(document.get(key) == value for key, value in expected.items()):
            return True
    return False


def sinica_fields_preserved(markdown: str, fields: dict) -> bool:
    return json_block_preserved(markdown, {"详情描述字段": fields})


def sinica_titles_match(label: str, description: str) -> bool:
    """Compare catalogue and description titles without assigning a corrected title."""
    title = re.split(r"\s*[‧·]\s*", label, maxsplit=1)[-1]
    description = re.sub(r"^\s*\d{1,3}[.．、]\s*", "", description)
    def normalize(value: str) -> str:
        return "".join(char for char in unicodedata.normalize("NFKC", value).casefold() if char.isalnum())
    one, two = normalize(title), normalize(description)
    if not one or not two:
        return False
    if one in two or two in one:
        return True
    # A detail record may insert further original-language text between the
    # catalogue's original-language title and its parenthesized translation.
    parts = re.fullmatch(r"\s*(.*?)\s*[（(]([^（）()]+)[）)]\s*", title)
    if not parts:
        return False
    original, translation = normalize(parts.group(1)), normalize(parts.group(2))
    start = two.find(original) if original else -1
    return bool(start >= 0 and translation and two.find(translation, start + len(original)) >= 0)


def selected(row: dict[str, str], fields: tuple[str, ...]) -> dict[str, str]:
    return {field: row[field] for field in fields if row.get(field)}


def resolved_source_path(source) -> Path:
    path = Path(source.local_path)
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def zibuyu_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    vm = re.fullmatch(ZIBUYU_VOLUME_PREFIX + r'(\d{2})', metadata.id)
    cm = re.fullmatch(ZIBUYU_CASE_PREFIX + r'(\d{2})_s(\d{3})', metadata.id)
    existing = metadata.id == ZIBUYU_EXISTING
    if not vm and not cm and metadata.id != ZIBUYU_ROOT and not existing:
        return
    if existing and not any(s.type == ZIBUYU_MARKER for s in metadata.sources):
        return
    record['issues'].extend([
        issue('source', 'zibuyu_edition_unchecked', '在线转录尚未对照古籍底本；卷次、文字、排版和注标须逐篇复核。'),
        issue('source', 'zibuyu_citation_license', '原作与数字转录的权利分开核查；站点文字要求保留贡献者、修订版本及 CC BY-SA 4.0 条款。'),
        issue('source', 'zibuyu_literary_scope', '这是志怪文学转录，叙事、讲述者、文献作者与历史事实不能自动等同。'),
        issue('coordinate', 'zibuyu_location_scope', '文献编纂范围或篇中地名不自动确定采录地、事件地点或坐标。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'zibuyu_codes_unassigned', '标准码须按具体原文及本地码表人工核对。'))
    snapshots = [s for s in metadata.sources if s.type == 'zibuyu_snapshot']
    manifests = [s for s in metadata.sources if s.type == 'zibuyu_manifest']
    if len(snapshots) != 1 or len(manifests) != 1 or any(not s.local_path or not s.content_sha256 for s in snapshots + manifests):
        record['issues'].append(issue('source', 'zibuyu_source_missing', '分卷网页或快照清单来源不完整。', urgent=True)); return
    page, receipt = resolved_source_path(snapshots[0]), resolved_source_path(manifests[0])
    if (receipt.name != 'manifest.json' or page.parent != receipt.parent
            or source_hashes.get(page) != snapshots[0].content_sha256 or source_hashes.get(receipt) != manifests[0].content_sha256):
        record['issues'].append(issue('source', 'zibuyu_source_invalid', '网页快照或清单路径、哈希不符。', urgent=True)); return
    folder = receipt.parent
    if folder not in cache:
        try:
            manifest, index, volumes, missing = load_zibuyu(folder)
            by_id = {zibuyu_node_id(row): row for vol in volumes for row in vol}
            cache[folder] = ((manifest, index, volumes, missing, by_id), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record['issues'].append(issue('source', 'zibuyu_snapshot_invalid', f'《子不语》快照无法核验：{error}', urgent=True)); return
    manifest, index, volumes, missing, by_id = loaded
    row = by_id.get(metadata.id) if cm or existing else None
    volume = row['volume'] if row else int(vm.group(1)) if vm else 0
    if (cm or existing) and row is None:
        record['issues'].append(issue('source', 'zibuyu_title_missing', '篇目不在分卷快照中。', urgent=True)); return
    if not 0 <= volume < len(manifest['pages']):
        record['issues'].append(issue('source', 'zibuyu_volume_invalid', '分卷编号超出快照范围。', urgent=True)); return
    required = zibuyu_source_set(folder, manifest, row=row, volume=volume)
    expected = Counter(json.dumps(Source.model_validate(s).model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in required)
    actual = Counter(json.dumps(s.model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in metadata.sources)
    if any(actual[key] < count for key, count in expected.items()):
        record['issues'].append(issue('source', 'zibuyu_source_changed', '固定修订、原网页或目录来源与快照不符。', urgent=True))
    if metadata.id == ZIBUYU_ROOT:
        group = zibuyu_group_evidence(manifest, index, volumes, missing)
        record['evidence']['zibuyu_group'] = group
        record['evidence']['zibuyu_inventory'] = [zibuyu_evidence(row, manifest) for vol in volumes for row in vol]
        record['evidence']['zibuyu_index_only'] = [{'volume': n, **item} for n, items in enumerate(missing, 1) for item in items]
        if metadata.node_type != 'myth_corpus' or not json_block_preserved(record['markdown'], group):
            record['issues'].append(issue('source', 'zibuyu_fields_changed', '总目录对照字段与快照不符。', urgent=True))
        talks = [s for s in metadata.sources if s.type == 'zibuyu_talk']
        receipts = [s for s in metadata.sources if s.type == 'zibuyu_talk_manifest']
        if len(talks) != 1 or len(receipts) != 1 or any(not s.local_path or not s.content_sha256 or str(s.url) != ZIBUYU_TALK_URL for s in talks + receipts):
            record['issues'].append(issue('source', 'zibuyu_talk_missing', '版本讨论页或其清单缺失。', urgent=True)); return
        talk, talk_receipt = resolved_source_path(talks[0]), resolved_source_path(receipts[0])
        if (talk.name != 'talk.html' or talk_receipt != talk.parent / 'manifest.json'
                or source_hashes.get(talk) != talks[0].content_sha256 or source_hashes.get(talk_receipt) != receipts[0].content_sha256):
            record['issues'].append(issue('source', 'zibuyu_talk_invalid', '版本讨论页或清单哈希不符。', urgent=True)); return
        try:
            talk_data = load_zibuyu_talk(talk.parent)
            record['evidence']['zibuyu_talk'] = talk_data
            if not json_block_preserved(record['markdown'], talk_data): raise ValueError('讨论页摘录字段与草稿不符')
        except (ValueError, OSError, KeyError, TypeError) as error:
            record['issues'].append(issue('source', 'zibuyu_talk_invalid', f'版本讨论无法核验：{error}', urgent=True))
        return
    if vm:
        data = zibuyu_volume_evidence(volume, manifest, index, volumes, missing)
        record['evidence']['zibuyu_volume'] = data
        if metadata.node_type != 'myth_corpus' or not json_block_preserved(record['markdown'], data):
            record['issues'].append(issue('source', 'zibuyu_fields_changed', '分卷对照字段与快照不符。', urgent=True))
        target = ZIBUYU_ROOT
    else:
        data = zibuyu_evidence(row, manifest)
        record['evidence']['zibuyu'] = data
        original_text = '\n\n'.join(row['paragraphs'])
        expected_title = f"《子不语》卷 {volume:02d} · {row['title']}"
        if (metadata.node_type != 'case' or (not existing and metadata.title != expected_title)
                or row['title'] not in metadata.aliases or not json_block_preserved(record['markdown'], data)
                or literal_block(original_text) not in record['markdown']):
            record['issues'].append(issue('source', 'zibuyu_fields_changed', '篇题、正文抽取或来源字段与分卷快照不符。', urgent=True))
        if row['index_candidate_kind'] != '同题候选':
            record['issues'].append(issue('source', 'zibuyu_title_disagreement', '总目录与分卷同序题名不同；仅作待核候选，不能自动认定同篇。', urgent=True))
        elif row['index_candidate']['anchor'] != row['anchor']:
            record['issues'].append(issue('source', 'zibuyu_anchor_disagreement', '总目录同题链接锚点与分卷实际锚点不同；均保留待核。', urgent=True))
        if row['index_candidate'] and row['index_candidate']['number'] != row['number']:
            record['issues'].append(issue('source', 'zibuyu_order_disagreement', '总目录与分卷的同题位置不同，须回查。', urgent=True))
        if row.get('inline_annotations'):
            record['issues'].append(issue('source', 'zibuyu_inline_annotation', '原页含内嵌字形或缺字注标；已保留可见符号和原页说明，须对照底本。', urgent=True))
        target = zibuyu_volume_id(volume)
    if not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == target for rel in metadata.relations):
        record['issues'].append(issue('source', 'zibuyu_relation_changed', '所属分卷或资料组关联不符。', urgent=True))


def bl_yi_project_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    case = re.fullmatch(BL_YI_PROJECT_CASE_PREFIX + r'(\d{3})_(\d{3})', metadata.id)
    group = re.fullmatch(BL_YI_PROJECT_GROUP_PREFIX + r'(\d{3})', metadata.id)
    if not case and not group and metadata.id != BL_YI_PROJECT_ROOT: return
    record['issues'].extend([
        issue('classification', 'yi_project_item_not_story', '项目目录、手稿册及影像数不是单篇故事数；关键词只作为筛查线索。'),
        issue('source', 'yi_project_original_unchecked', '未获取手稿影像、转录或音视频；馆方单件与具体内容须回查。'),
        issue('source', 'yi_project_selection_limits', '关键词仅筛查题名和检索摘要，未命中不代表无关；中间检索页未重复采集。'),
        issue('source', 'yi_project_rights', '馆方目录文字 CC BY 4.0（例外另核）；原件、数字内容与社区要求须逐件核查。', urgent=True),
        issue('source', 'yi_project_dates', '目录统一日期、内容说明、手稿制作时间和叙事年代须分别核实。'),
        issue('coordinate', 'yi_project_location', '项目或馆藏地点不等于单件采录地及故事发生地点。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'yi_project_codes_unassigned', '标准码须依据原文及本地码表人工匹配，当前留空。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'yi_project_coordinate_unverified', '项目及馆藏范围不足以确定逐件坐标。', urgent=True))
    indexes = [s for s in metadata.sources if s.type == 'bl_yi_project_index_manifest']
    details = [s for s in metadata.sources if s.type == 'bl_yi_project_details_manifest']
    if len(indexes) != 1 or len(details) != 1 or any(not s.local_path or not s.content_sha256 for s in indexes + details):
        record['issues'].append(issue('source', 'yi_project_manifest_missing', '项目索引或单件快照清单缺失。', urgent=True)); return
    index_path, detail_path = resolved_source_path(indexes[0]), resolved_source_path(details[0])
    if (index_path.name != 'manifest.json' or detail_path.name != 'manifest.json'
            or source_hashes.get(index_path) != indexes[0].content_sha256
            or source_hashes.get(detail_path) != details[0].content_sha256):
        record['issues'].append(issue('source', 'yi_project_manifest_invalid', '项目索引或单件快照清单哈希不符。', urgent=True)); return
    key = (index_path.parent, detail_path.parent)
    if key not in cache:
        try:
            index_manifest, rows = load_bl_yi_project_index(index_path.parent)
            _, parents, items = load_bl_yi_project_details(detail_path.parent, index_path.parent)
            cache[key] = ((index_manifest, rows, parents, items,
                           {bl_yi_project_group_id(r): (r, f) for r, _, f in parents},
                           {bl_yi_project_node_id(r): (r, f) for r, _, f in items}), None)
        except (ValueError, OSError, KeyError, TypeError) as error: cache[key] = (None, str(error))
    loaded, error = cache[key]
    if loaded is None:
        record['issues'].append(issue('source', 'yi_project_snapshot_invalid', f'项目或单件目录快照无法核验：{error}', urgent=True)); return
    manifest, rows, parents, items, by_group, by_case = loaded
    row, parent = None, None
    if metadata.id == BL_YI_PROJECT_ROOT:
        expected = bl_yi_project_root_evidence(manifest, rows, parents, items)
        record['evidence']['yi_project_group'] = expected
        record['evidence']['yi_project_inventory'] = rows
        record['evidence']['yi_project_pages'] = manifest['pages']
        if metadata.node_type != 'myth_corpus':
            record['issues'].append(issue('source', 'yi_project_group_changed', '项目筛查节点类型不符。', urgent=True))
    elif group:
        found = by_group.get(metadata.id)
        if found is None:
            record['issues'].append(issue('source', 'yi_project_parent_missing', '父级馆藏不在选取快照中。', urgent=True)); return
        parent, fields = found; expected = bl_yi_project_group_evidence(parent, fields, rows, items)
        record['evidence']['yi_project_parent'] = expected
        if (metadata.node_type != 'myth_corpus' or metadata.title != f"云南彝文档案 · {parent['shelfmark']} 馆藏"
                or parent['fields']['Title'] not in metadata.aliases
                or not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == BL_YI_PROJECT_ROOT for rel in metadata.relations)):
            record['issues'].append(issue('source', 'yi_project_parent_changed', '父级馆藏题名、类型或项目关联不符。', urgent=True))
        if not fields.get('User Conditions'):
            record['issues'].append(issue('source', 'yi_project_parent_conditions_absent', '父级访问条件未列出，不能推定无限制。', urgent=True))
    else:
        found = by_case.get(metadata.id)
        if found is None:
            record['issues'].append(issue('source', 'yi_project_item_missing', '单件不在选取快照中。', urgent=True)); return
        row, fields = found
        parent_match = [entry for entry in parents if entry[0]['shelfmark'] == bl_yi_project_parent_ref(row)]
        if len(parent_match) != 1:
            record['issues'].append(issue('source', 'yi_project_parent_missing', '单件对应的父级馆藏缺失。', urgent=True)); return
        parent, _, parent_fields = parent_match[0]
        expected = bl_yi_project_item_evidence(row, fields, parent, parent_fields, rows, manifest)
        record['evidence']['yi_project_item'] = expected
        if (metadata.node_type != 'case' or metadata.title != f"云南彝文档案 · {row['shelfmark']}"
                or row['fields']['Title'] not in metadata.aliases
                or not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == bl_yi_project_group_id(parent) for rel in metadata.relations)):
            record['issues'].append(issue('source', 'yi_project_item_changed', '单件题名、类型或所属馆藏关联不符。', urgent=True))
        if expected['同题目录档号（忽略大小写与空白）']:
            record['issues'].append(issue('source', 'yi_project_same_title', '项目目录有相同题名的其他条目；不能仅凭题名合并或认定同一版本。', urgent=True))
        if not fields.get('User Conditions'):
            record['issues'].append(issue('source', 'yi_project_item_conditions_absent', '单件访问条件未列出，不能推定无限制。', urgent=True))
        if not fields.get('Scope & Content'):
            record['issues'].append(issue('source', 'yi_project_description_absent', '单件内容说明缺失，须回查。', urgent=True))
        if expected['馆方影像入口（未取得）']:
            record['issues'].append(issue('source', 'yi_project_viewer_unchecked', '影像入口来自馆方目录；未下载影像，访问与使用条件须核查。'))
        if row['shelfmark'] == 'EAP081/1/192':
            record['issues'].append(issue('source', 'yi_project_viewer_probe_403', '2026-11-23 检索工具访问该影像入口返回 403，未绕过；其他访问方式和权限须依馆方条件核查。', urgent=True))
    required = bl_yi_project_source_set(index_path.parent, manifest, detail_path.parent, row, parent, fields if case else None)
    wanted = Counter(json.dumps(Source.model_validate(s).model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in required)
    actual = Counter(json.dumps(s.model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in metadata.sources)
    if any(actual[k] < n for k, n in wanted.items()):
        record['issues'].append(issue('source', 'yi_project_source_changed', '项目、父级或单件来源与已核验快照不符。', urgent=True))
    if not json_block_preserved(record['markdown'], expected):
        record['issues'].append(issue('source', 'yi_project_fields_changed', '草稿字段与项目或单件快照不符。', urgent=True))


def bl_dongjing_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(BL_DONGJING_PREFIX + r'(\d{2})', metadata.id)
    if not match and metadata.id != BL_DONGJING_ROOT: return
    record['issues'].extend([
        issue('classification', 'bl_dongjing_folder_not_story', '馆方电子文件夹可含多个文件或节目，不能计为单篇故事。'),
        issue('source', 'bl_dongjing_media_unchecked', '仅保存馆方目录；音视频、转写和具体内容尚未核对。'),
        issue('source', 'bl_dongjing_roles', '表演团体、受访者、采访者和录音者以馆方原文为线索分开核实。'),
        issue('source', 'bl_dongjing_rights', '目录文字 CC BY 4.0；父级限研究使用，单件资源及社区要求另核。', urgent=True),
        issue('source', 'bl_dongjing_dates', '题名、内容说明、日期字段与项目标识可能涉及不同环节，不能自动合并为叙事年代。'),
        issue('coordinate', 'bl_dongjing_location', '馆藏系列范围不能直接作为单件采录地、叙事地点或坐标。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'bl_dongjing_codes_unassigned', '须依据具体内容及本地码表人工核定标准码，当前留空。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'bl_dongjing_coordinate_unverified', '馆藏系列范围不足以确定坐标。', urgent=True))
    manifests = [s for s in metadata.sources if s.type == 'bl_dongjing_manifest']
    if len(manifests) != 1 or not manifests[0].local_path or not manifests[0].content_sha256:
        record['issues'].append(issue('source', 'bl_dongjing_manifest_missing', '馆方快照清单缺失。', urgent=True)); return
    path = resolved_source_path(manifests[0])
    if path.name != 'manifest.json' or source_hashes.get(path) != manifests[0].content_sha256:
        record['issues'].append(issue('source', 'bl_dongjing_manifest_invalid', '馆方快照清单路径或哈希不符。', urgent=True)); return
    folder = path.parent
    if folder not in cache:
        try: cache[folder] = (load_bl_dongjing(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error: cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record['issues'].append(issue('source', 'bl_dongjing_snapshot_invalid', f'洞经目录快照无法核验：{error}', urgent=True)); return
    manifest, series, fonds, entries = loaded
    child, fields = None, None
    if match:
        found = [entry for entry in entries if entry[0]['number'] == int(match.group(1))]
        if len(found) != 1:
            record['issues'].append(issue('source', 'bl_dongjing_item_missing', '单件不在馆方快照中。', urgent=True)); return
        child, _, fields = found[0]
        expected = bl_dongjing_item_evidence(child, fields)
        record['evidence']['bl_dongjing'] = expected
        if (metadata.node_type != 'case' or metadata.title != f"云南洞经表演与访谈 · {child['shelfmark']}"
                or child['title'] not in metadata.aliases
                or not any(r.type == 'PART_OF_MACRO_TREND' and r.target == BL_DONGJING_ROOT for r in metadata.relations)):
            record['issues'].append(issue('source', 'bl_dongjing_item_changed', '题名、类型或所属系列与目录不符。', urgent=True))
        if expected['题名年份落在起止字段范围'] is False:
            record['issues'].append(issue('source', 'bl_dongjing_title_year_range', '题名年份不在馆方起止日期字段范围内，字段口径需回查。', urgent=True))
        elif expected['题名年份落在起止字段范围'] is None:
            record['issues'].append(issue('source', 'bl_dongjing_title_year_uncompared', '题名年份与起止日期字段暂无法直接比较。'))
        if expected['日期范围年份落在起止字段范围'] is False:
            record['issues'].append(issue('source', 'bl_dongjing_date_fields_disagree', '日期范围字段所列年份不在起止日期字段范围内，须回查原始编目。', urgent=True))
        if not fields.get('User Conditions'):
            record['issues'].append(issue('source', 'bl_dongjing_item_conditions_absent', '单件未列访问条件，不能据此认定不受限制。', urgent=True))
        if re.search(r'(?<!\d)\d{8}(?!\d)', fields.get('Former Internal References') or ''):
            record['issues'].append(issue('source', 'bl_dongjing_identifier_digits', '项目标识含八位数字，不自动解释为采录日期。'))
    else:
        expected = bl_dongjing_group_evidence(series, fonds, entries)
        record['evidence']['bl_dongjing_group'] = expected
        record['evidence']['bl_dongjing_inventory'] = [bl_dongjing_item_evidence(c, f) for c, _, f in entries]
        if metadata.node_type != 'myth_corpus':
            record['issues'].append(issue('source', 'bl_dongjing_group_changed', '系列节点类型不符。', urgent=True))
        if expected['单件范围字段首项文件数相加'] is not None and expected['单件范围字段首项文件数相加'] != 62:
            record['issues'].append(issue('source', 'bl_dongjing_extent_disagreement', '系列范围写 62 个文件，单件范围首项数字相加不同；统计口径须回查。', urgent=True))
        start, end = series.get('Start Date') or '', series.get('End Date') or ''
        years = re.findall(r'\b(?:19|20)\d{2}\b', series.get('Scope & Content') or '')
        if re.fullmatch(r'\d{4}', start) and re.fullmatch(r'\d{4}', end) and any(not int(start) <= int(y) <= int(end) for y in years):
            record['issues'].append(issue('source', 'bl_dongjing_series_year_range', '系列内容说明的年份不完全落在系列起止日期字段内，字段口径须回查。', urgent=True))
    required = bl_dongjing_source_set(folder, manifest, child)
    wanted = Counter(json.dumps(Source.model_validate(s).model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in required)
    actual = Counter(json.dumps(s.model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in metadata.sources)
    if any(actual[key] < n for key, n in wanted.items()):
        record['issues'].append(issue('source', 'bl_dongjing_source_changed', '馆方出处与快照不符。', urgent=True))
    if not json_block_preserved(record['markdown'], expected):
        record['issues'].append(issue('source', 'bl_dongjing_fields_changed', '草稿字段与馆方目录快照不符。', urgent=True))


def bl_burma_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(BL_BURMA_PREFIX + r'(\d{2})', metadata.id)
    if not match and metadata.id != BL_BURMA_ROOT: return
    record['issues'].extend([
        issue('classification', 'bl_burma_not_story', '一件唱片可包含多段材料，唱片目录不等于单篇故事。'),
        issue('source', 'bl_burma_recording_not_checked', '未取得音频或转写；目录题名、录音面、说话人及内容须回查。'),
        issue('source', 'bl_burma_colonial_context', '殖民语言调查须逐件核查采集语境；系列其他分组记有强制采集，不能推定本分组个人经历。', urgent=True),
        issue('source', 'bl_burma_rights', '目录文字 CC BY 4.0；数字内容、录音和相关社区要求须单独核实。', urgent=True),
        issue('source', 'bl_burma_dsal_scope', 'DSAL 按编号或半号文字形成的候选未核实对应录音面或版本；原接口响应未保留，哈希不能从字段索引重算。'),
        issue('coordinate', 'bl_burma_place', '馆藏分组、说话人来源、采录地点和叙事发生地不能自动等同。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'bl_burma_codes_unassigned', '须按实际内容与本地码表人工匹配标准码，当前留空。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'bl_burma_unverified_coordinate', '馆藏分组不足以确定单件坐标。', urgent=True))
    a = [s for s in metadata.sources if s.type == 'bl_burma_manifest']
    b = [s for s in metadata.sources if s.type == 'dsal_burma_manifest']
    if len(a) != 1 or len(b) != 1 or any(not s.local_path or not s.content_sha256 for s in a + b):
        record['issues'].append(issue('source', 'bl_burma_manifest_missing', '馆方或 DSAL 快照清单缺失。', urgent=True)); return
    ap, bp = resolved_source_path(a[0]), resolved_source_path(b[0])
    if (ap.name != 'manifest.json' or bp.name != 'manifest.json' or source_hashes.get(ap) != a[0].content_sha256
            or source_hashes.get(bp) != b[0].content_sha256):
        record['issues'].append(issue('source', 'bl_burma_manifest_invalid', '馆方或 DSAL 快照清单哈希不符。', urgent=True)); return
    key = (ap.parent, bp.parent)
    if key not in cache:
        try: cache[key] = ((load_bl_burma(ap.parent), load_dsal_burma(bp.parent)), None)
        except (ValueError, OSError, KeyError, TypeError) as error: cache[key] = (None, str(error))
    loaded, error = cache[key]
    if loaded is None:
        record['issues'].append(issue('source', 'bl_burma_snapshot_invalid', f'唱片目录或 DSAL 字段索引无法核验：{error}', urgent=True)); return
    (bl_manifest, root, series, children), (dsal_manifest, dsal_rows) = loaded
    child, fields = None, None
    if match:
        found = [item for item in children if item[0]['number'] == int(match.group(1))]
        if len(found) != 1:
            record['issues'].append(issue('source', 'bl_burma_item_missing', '单件不在馆藏快照中。', urgent=True)); return
        child, _, fields = found[0]
        expected = bl_burma_item_evidence(child, fields, dsal_rows, dsal_manifest)
        record['evidence']['bl_burma'] = expected
        if (metadata.node_type != 'case' or metadata.title != f"缅甸多语唱片目录 · {child['shelfmark']}"
                or child['title'] not in metadata.aliases
                or not any(r.type == 'PART_OF_MACRO_TREND' and r.target == BL_BURMA_ROOT for r in metadata.relations)):
            record['issues'].append(issue('source', 'bl_burma_item_changed', '单件题名或所属馆藏关系与原目录不符。', urgent=True))
        hits = bl_burma_candidates(fields, dsal_rows)
        selected, method = bl_burma_selected(fields, dsal_rows)
        if selected is None:
            record['issues'].append(issue('source', 'bl_burma_candidate_unresolved', '严格编号候选不唯一或缺失，需人工查找。', urgent=True))
        elif len(hits) != 1:
            record['issues'].append(issue('source', 'bl_burma_half_candidate', '大英图书馆 1/2 与 DSAL HALF 为较弱文字线索，须人工核查录音编号和音面。', urgent=True))
        if selected is not None and not selected['fields']['narrator']:
            record['issues'].append(issue('source', 'bl_burma_speaker_missing', 'DSAL 说话人字段为空，须回查原始目录和采集记录。', urgent=True))
    else:
        expected = bl_burma_group_evidence(root, series, children, dsal_rows)
        record['evidence']['bl_burma_group'] = expected
        record['evidence']['bl_burma_inventory'] = [bl_burma_item_evidence(c, f, dsal_rows, dsal_manifest) for c, _, f in children]
        if metadata.node_type != 'myth_corpus':
            record['issues'].append(issue('source', 'bl_burma_group_changed', '馆藏组节点类型不符。', urgent=True))
    required = bl_burma_source_set(ap.parent, bl_manifest, bp.parent, dsal_manifest, child, fields, dsal_rows)
    wanted = Counter(json.dumps(Source.model_validate(s).model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in required)
    actual = Counter(json.dumps(s.model_dump(mode='json'), ensure_ascii=False, sort_keys=True) for s in metadata.sources)
    if any(actual[k] < n for k, n in wanted.items()):
        record['issues'].append(issue('source', 'bl_burma_source_changed', '馆方出处或待核候选与已核验快照不符。', urgent=True))
    if not json_block_preserved(record['markdown'], expected):
        record['issues'].append(issue('source', 'bl_burma_fields_changed', '草稿字段与馆方目录或候选索引不符。', urgent=True))


def palue_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(PALUE_PREFIX + r'(\d{3})', metadata.id)
    if not match and metadata.id != PALUE_ROOT:
        return
    record['issues'].extend([
        issue('classification', 'palue_item_not_story', '目录对象与 Sound 字段不等于已确认的一篇故事，体裁须逐件核查。'),
        issue('source', 'palue_no_media', '未保存叙事描述、音视频或转写；馆方原件及上下文须回查。'),
        issue('source', 'palue_rights_unknown', '须按单件和相关社区要求复核使用条件；目录权利字段为空不能证明无使用限制。', urgent=True),
        issue('source', 'palue_recording_scope', '目录日期性质、说话人及语言字段须回查，不能自动确定故事发生年代或作品语言。'),
        issue('source', 'palue_response_hash_scope', '原始接口响应未保留；只能校验本地字段索引，采集期间仅重复核验首页和末页。'),
        issue('coordinate', 'palue_place_scope', '馆方地区字段性质须回查，不能自动作为故事发生地或地图坐标。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'palue_codes_unassigned', '标准码尚未从本地码表按具体作品匹配。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'palue_coordinate_unverified', '馆藏范围不足以确定逐条坐标。', urgent=True))
    indexes = [s for s in metadata.sources if s.type == 'palue_index']
    manifests = [s for s in metadata.sources if s.type == 'palue_manifest']
    if (len(indexes) != 1 or len(manifests) != 1 or any(not s.local_path or not s.content_sha256 for s in indexes + manifests)
            or str(manifests[0].url) != PALUE_URL or manifests[0].locator != '公开检索与字段索引清单'):
        record['issues'].append(issue('source', 'palue_source_missing', '馆藏字段索引或清单来源不完整。', urgent=True))
        return
    page, receipt = resolved_source_path(indexes[0]), resolved_source_path(manifests[0])
    if (receipt.name != 'manifest.json' or page.parent != receipt.parent
            or source_hashes.get(page) != indexes[0].content_sha256 or source_hashes.get(receipt) != manifests[0].content_sha256):
        record['issues'].append(issue('source', 'palue_source_invalid', '馆藏字段索引或清单路径、哈希不符。', urgent=True))
        return
    folder = receipt.parent
    if folder not in cache:
        try:
            manifest, rows = load_palue(folder)
            cache[folder] = ((manifest, rows, {palue_node_id(row): row for row in rows}), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record['issues'].append(issue('source', 'palue_snapshot_invalid', f'目录快照无法核验：{error}', urgent=True))
        return
    manifest, rows, by_id = loaded
    row = by_id.get(metadata.id) if match else rows[0]
    if row is None or (match and 'Sound' not in row['fields']['dc.type.dcmi']):
        record['issues'].append(issue('source', 'palue_item_invalid', '条目不在本次 Sound 字段筛查范围内。', urgent=True))
        return
    entry = manifest['pages'][row['page']]
    if (page.name != entry['path'] or str(indexes[0].url) != entry['response']['url']
            or indexes[0].locator != f"目录检索页 {row['page']} / {row['id']}"):
        record['issues'].append(issue('source', 'palue_source_invalid', '目录条目与字段索引页不对应。', urgent=True))
        return
    if not match:
        group = palue_group_evidence(manifest, rows)
        record['evidence']['palue_group'] = group
        record['evidence']['palue_inventory'] = rows
        record['evidence']['palue_receipts'] = manifest['pages']
        if metadata.node_type != 'myth_corpus' or not json_block_preserved(record['markdown'], group):
            record['issues'].append(issue('source', 'palue_fields_changed', '馆藏组字段或条目类型与字段索引不符。', urgent=True))
        return
    expected = palue_evidence(row, manifest)
    record['evidence']['palue'] = expected
    originals = [s for s in metadata.sources if s.type == PALUE_MARKER]
    if (len(originals) != 1 or str(originals[0].url) != row['item_url']
            or originals[0].locator != f"馆方单件目录 / {row['id']}"
            or metadata.title != f"印尼 Palu’e 馆藏目录 · {row['id']}" or row['id'] not in metadata.aliases
            or metadata.node_type != 'case' or not json_block_preserved(record['markdown'], expected)):
        record['issues'].append(issue('source', 'palue_fields_changed', '单件字段、类型或来源链接与字段索引不符。', urgent=True))
    if not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == PALUE_ROOT for rel in metadata.relations):
        record['issues'].append(issue('source', 'palue_relation_changed', '所属馆藏关联不符。', urgent=True))
    fields = row['fields']
    if not fields['dc.contributor.speaker']:
        record['issues'].append(issue('source', 'palue_speaker_missing', '说话人字段为空，须回查。', urgent=True))
    if not fields['dc.contributor.recorder']:
        record['issues'].append(issue('source', 'palue_recorder_missing', '采录者字段为空，须回查。', urgent=True))
    if 'Sara Lio' in fields['dc.subject.language']:
        record['issues'].append(issue('source', 'palue_subject_language_variant', '主题语种字段为 Sara Lio，不应按馆藏名称统一标为 Palu’e。', urgent=True))
    if row['genre_hint'] and re.search(r'medicine|healing|ritual', row['genre_hint'], re.I):
        record['issues'].append(issue('source', 'palue_sensitive_knowledge', '目录标签涉及医疗或仪式知识线索，使用条件和社区要求须逐件核实。', urgent=True))


def pumi_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(PUMI_PREFIX + r'(\d{2})', metadata.id)
    if not match and metadata.id != PUMI_ROOT:
        return
    record['issues'].extend([
        issue('classification', 'pumi_unit_not_story', '目录混合访谈、歌曲、仪式、演说和故事题名；一条录音不等于已确认的一篇独立故事。'),
        issue('source', 'pumi_uncached_media', '未取得音频、转写或附件；旧档案及试听入口须逐条回查。'),
        issue('source', 'pumi_rights_community', '网站材料仅用于本地个人或内部非商业研究；各单件权利及社区要求须另核。'),
        issue('source', 'pumi_roles_and_scope', '馆藏总体语言、采录者和时间不自动确定单条演述者、语言和叙事年代。'),
        issue('source', 'pumi_context', '历史叙事和地方观念须作为具体演述复核，不能直接当作历史事实或群体共同观点。'),
        issue('coordinate', 'pumi_place_scope', '馆藏总体地点不能直接确定单条采录地或故事发生地。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'pumi_codes_unassigned', '未依据具体演述及本地码表核定标准码。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'pumi_coordinate_unverified', '馆藏总体范围不足以确定逐条坐标。', urgent=True))
    parents = [s for s in metadata.sources if s.type == 'pumi_wolp_catalogue']
    manifests = [s for s in metadata.sources if s.type == 'pumi_wolp_manifest']
    if (len(parents) != 1 or len(manifests) != 1 or any(not s.local_path or not s.content_sha256 for s in parents + manifests)
            or str(parents[0].url) != PUMI_URL or str(manifests[0].url) != MINYAG_TERMS
            or parents[0].locator != '馆藏总述与编号目录' or manifests[0].locator != '目录与网站条款快照清单'):
        record['issues'].append(issue('source', 'pumi_source_missing', '馆藏目录或网站条款快照来源不完整。', urgent=True))
        return
    parent, receipt = resolved_source_path(parents[0]), resolved_source_path(manifests[0])
    if (parent.name != 'catalogue.html' or receipt != parent.parent / 'manifest.json'
            or source_hashes.get(parent) != parents[0].content_sha256
            or source_hashes.get(receipt) != manifests[0].content_sha256):
        record['issues'].append(issue('source', 'pumi_source_invalid', '馆藏目录或快照清单路径、哈希不符。', urgent=True))
        return
    folder = parent.parent
    if folder not in cache:
        try:
            cache[folder] = (load_pumi(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record['issues'].append(issue('source', 'pumi_snapshot_invalid', f'目录快照无法核验：{error}', urgent=True))
        return
    _, rows = loaded
    current = [s for s in metadata.sources if s.type == 'pumi_wolp_current']
    current_manifests = [s for s in metadata.sources if s.type == 'pumi_wolp_current_manifest']
    current_data = None
    if current or current_manifests:
        if ((match and int(match.group(1)) != 41) or len(current) != 1 or len(current_manifests) != 1
                or any(not s.local_path or not s.content_sha256 or str(s.url) != PUMI_CURRENT_URL for s in current + current_manifests)
                or current[0].locator != '单件目录 / 旧档案标识、馆藏数量与许可'
                or current_manifests[0].locator != '单件目录网页快照清单'):
            record['issues'].append(issue('source', 'pumi_current_source_invalid', '现行单件来源不完整或与第 41 条不对应。', urgent=True))
            return
        page, manifest = resolved_source_path(current[0]), resolved_source_path(current_manifests[0])
        if (page.name != 'item.html' or manifest != page.parent / 'manifest.json'
                or source_hashes.get(page) != current[0].content_sha256
                or source_hashes.get(manifest) != current_manifests[0].content_sha256):
            record['issues'].append(issue('source', 'pumi_current_hash_invalid', '剑桥单件网页或清单路径与哈希不符。', urgent=True))
            return
        try:
            current_data = load_pumi_current(page.parent, rows)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            record['issues'].append(issue('source', 'pumi_current_invalid', f'剑桥单件信息无法核验：{exc}', urgent=True))
            return
        record['evidence']['pumi_wolp_current'] = current_data
        record['issues'].append(issue('source', 'pumi_collection_count_difference', '旧目录称 45 个音频文件，现行单件的馆藏说明称 46 个；口径待核。', urgent=True))
        record['issues'].append(issue('source', 'pumi_current_license_scope', '现行许可仅对应第 41 条单件；不能直接推及其他音频。'))
        if not json_block_preserved(record['markdown'], current_data):
            record['issues'].append(issue('source', 'pumi_current_fields_changed', '现行单件对照字段与草稿不一致。', urgent=True))
    if not match:
        group = pumi_group_evidence(rows, current_data)
        record['evidence']['pumi_wolp_group'] = group
        record['evidence']['pumi_wolp_inventory'] = rows
        if not json_block_preserved(record['markdown'], group):
            record['issues'].append(issue('source', 'pumi_fields_changed', '馆藏组字段与来源快照不符。', urgent=True))
        return
    number = int(match.group(1))
    if not 1 <= number <= 45:
        record['issues'].append(issue('source', 'pumi_number_invalid', '条目不在目录编号范围内。', urgent=True))
        return
    row = rows[number - 1]
    expected = pumi_evidence(row)
    record['evidence']['pumi_wolp'] = expected
    original = [s for s in metadata.sources if s.type == PUMI_MARKER]
    audio = [s for s in metadata.sources if s.type == PUMI_AUDIO_MARKER]
    if (len(original) != 1 or len(audio) != 1 or str(original[0].url) != row['archive_url']
            or str(audio[0].url) != row['audio_url'] or original[0].locator != f'目录第 {number} 条 / 旧档案入口待核'
            or audio[0].locator != f'目录第 {number} 条 / 旧试听入口待核'
            or metadata.title != f"云南普米语目录 · {row['title']}" or row['title'] not in metadata.aliases
            or metadata.node_type != 'case' or not json_block_preserved(record['markdown'], expected)):
        record['issues'].append(issue('source', 'pumi_fields_changed', '目录字段、条目类型或旧入口与快照不符。', urgent=True))
    targets = [rel.target for rel in metadata.relations if rel.type == 'COMPARED_WITH']
    compared = [f'{PUMI_PREFIX}{PUMI_COMPARISONS[number]:02d}'] if number in PUMI_COMPARISONS else []
    if targets != compared or not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == PUMI_ROOT for rel in metadata.relations):
        record['issues'].append(issue('source', 'pumi_relation_changed', '所属馆藏或同题对照关联不符。', urgent=True))
    if number in PUMI_COMPARISONS:
        record['issues'].append(issue('source', 'pumi_comparison_unverified', '题名均含 Madami 仅是对照线索，不证明同一演述、版本或传播。'))


def temiar_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(r'(case|corpus)_my_temiar_wolp_(\d{2})', metadata.id)
    if not match and metadata.id != TEMIAR_ROOT:
        return
    record['issues'].extend([
        issue('classification', 'temiar_unit_not_story', '目录包含音轨、照片和文书；录音或档案条目不等于已确认的独立故事。'),
        issue('source', 'temiar_uncached_media', '未获取音频、转写、照片或文书附件；旧入口及单件内容须回查。'),
        issue('source', 'temiar_rights_community', '网站材料仅用于本地个人或内部非商业研究；单件权利和社区要求须另核。'),
        issue('source', 'temiar_count_scope', '馆藏总述、歌曲说明及编号目录的统计单位和对应关系未核。'),
        issue('source', 'temiar_roles', '收藏者、档案作者、录音工程师和演述者须区分，历史研究评论不能代替社区观点。'),
        issue('coordinate', 'temiar_place_scope', '照片地点或馆藏总体范围不能直接确定单条录音地点和叙事发生地。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'temiar_codes_unassigned', '未根据具体演述与本地码表核定标准码。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'temiar_coordinate_unverified', '尚未核实单条坐标，须回查。', urgent=True))
    parents = [s for s in metadata.sources if s.type == 'temiar_wolp_catalogue']
    manifests = [s for s in metadata.sources if s.type == 'temiar_wolp_manifest']
    if (len(parents) != 1 or len(manifests) != 1 or any(not s.local_path or not s.content_sha256 for s in parents + manifests)
            or str(parents[0].url) != TEMIAR_URL or str(manifests[0].url) != MINYAG_TERMS
            or parents[0].locator != '馆藏总述与编号目录' or manifests[0].locator != '目录与网站条款快照清单'):
        record['issues'].append(issue('source', 'temiar_source_missing', '馆藏目录或网站条款快照来源不完整。', urgent=True))
        return
    parent, receipt = resolved_source_path(parents[0]), resolved_source_path(manifests[0])
    if (parent.name != 'catalogue.html' or receipt != parent.parent / 'manifest.json'
            or source_hashes.get(parent) != parents[0].content_sha256
            or source_hashes.get(receipt) != manifests[0].content_sha256):
        record['issues'].append(issue('source', 'temiar_source_invalid', '馆藏目录或快照清单路径、哈希不符。', urgent=True))
        return
    folder = parent.parent
    if folder not in cache:
        try:
            cache[folder] = (load_temiar(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record['issues'].append(issue('source', 'temiar_snapshot_invalid', f'目录快照无法核验：{error}', urgent=True))
        return
    _, rows = loaded
    group = temiar_group_evidence(rows)
    record['evidence']['temiar_wolp_group'] = group
    if not match:
        record['evidence']['temiar_wolp_inventory'] = rows
        record['issues'].append(issue('source', 'temiar_duplicate_link', '目录第 10、45 条共用旧档案链接；须核查是否重复著录。', urgent=True))
        if not json_block_preserved(record['markdown'], group):
            record['issues'].append(issue('source', 'temiar_fields_changed', '馆藏组字段与快照不符。', urgent=True))
        return
    number = int(match.group(2))
    if number not in TEMIAR_SELECTED or metadata.id != temiar_node_id(number):
        record['issues'].append(issue('source', 'temiar_unselected', '条目不在本轮范围，或音轨与文书节点类型不符。', urgent=True))
        return
    row, expected = rows[number - 1], temiar_evidence(rows[number - 1])
    record['evidence']['temiar_wolp'] = expected
    originals = [s for s in metadata.sources if s.type == TEMIAR_MARKER]
    audios = [s for s in metadata.sources if s.type == TEMIAR_AUDIO_MARKER]
    if (len(originals) != 1 or str(originals[0].url) != row['archive_url']
            or originals[0].locator != f'目录第 {number} 条 / 旧档案入口待核'
            or metadata.title != f"Temiar 馆藏目录 · {row['title']}" or row['title'] not in metadata.aliases
            or metadata.node_type != ('case' if number in TEMIAR_SONGS else 'myth_corpus')
            or not json_block_preserved(record['markdown'], expected)):
        record['issues'].append(issue('source', 'temiar_fields_changed', '目录字段、旧档案链接或条目类型与快照不符。', urgent=True))
    if (len(audios) != (1 if row['audio_url'] else 0)
            or (audios and (str(audios[0].url) != row['audio_url'] or audios[0].locator != f'目录第 {number} 条 / 旧试听入口待核'))):
        record['issues'].append(issue('source', 'temiar_audio_link_changed', '目录所列试听入口与来源快照不符。', urgent=True))
    if number in TEMIAR_SONGS:
        record['issues'].append(issue('source', 'temiar_performer_unverified', '目录音轨的具体演述者和旧试听入口均须回查。'))
    targets = [rel.target for rel in metadata.relations if rel.type == 'COMPARED_WITH']
    compared = [temiar_node_id(TEMIAR_COMPARISONS[number])] if number in TEMIAR_COMPARISONS else []
    if targets != compared or not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == TEMIAR_ROOT for rel in metadata.relations):
        record['issues'].append(issue('source', 'temiar_relation_changed', '所属馆藏或待核对照关联不符。', urgent=True))
    if number in TEMIAR_COMPARISONS:
        record['issues'].append(issue('source', 'temiar_comparison_unverified', '题名或目录署名相近仅是线索，不证明同版、连续演述或传播。'))
    current = [s for s in metadata.sources if s.type == 'temiar_wolp_current']
    current_manifests = [s for s in metadata.sources if s.type == 'temiar_wolp_current_manifest']
    if current or current_manifests:
        if (number != 33 or len(current) != 1 or len(current_manifests) != 1
                or any(not s.local_path or not s.content_sha256 or str(s.url) != TEMIAR_CURRENT_URL for s in current + current_manifests)
                or current[0].locator != '单件目录 / 旧档案标识及 Authors'
                or current_manifests[0].locator != '单件目录网页快照清单'):
            record['issues'].append(issue('source', 'temiar_current_source_invalid', '现行剑桥单件来源不完整或不对应第 33 条。', urgent=True))
            return
        page, manifest = resolved_source_path(current[0]), resolved_source_path(current_manifests[0])
        if (page.name != 'item.html' or manifest != page.parent / 'manifest.json'
                or source_hashes.get(page) != current[0].content_sha256
                or source_hashes.get(manifest) != current_manifests[0].content_sha256):
            record['issues'].append(issue('source', 'temiar_current_hash_invalid', '剑桥单件网页或清单路径与哈希不符。', urgent=True))
            return
        try:
            details = load_temiar_current(page.parent, rows)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            record['issues'].append(issue('source', 'temiar_current_invalid', f'剑桥单件信息无法核验：{exc}', urgent=True))
            return
        record['evidence']['temiar_wolp_current'] = details
        record['issues'].append(issue('source', 'temiar_credit_role', '单件 Authors 字段与照片中同名录音工程师线索须分别核对，不能推作演唱者。', urgent=True))
        if not json_block_preserved(record['markdown'], details):
            record['issues'].append(issue('source', 'temiar_current_fields_changed', '现行单件字段与草稿不一致。', urgent=True))


def minyag_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(MINYAG_PREFIX + r'(\d{2})', metadata.id)
    if not match and metadata.id != MINYAG_ROOT:
        return
    record['issues'].extend([
        issue('classification', 'minyag_directory_unit', '目录条目可能为故事、仪式、口述史或其他内容；不等于已确认的独立故事。'),
        issue('source', 'minyag_details_unchecked', '未取得录音或转写；旧档案入口及单条信息须分别回查。'),
        issue('source', 'minyag_rights', '网站材料仅用于本地个人或内部非商业研究；其他使用及单条资源权利、社区要求另核。'),
        issue('source', 'minyag_count_units', '目录总述为 77 个音频文件，页面编号为 62 条；对应关系待核，不推定缺失。'),
        issue('source', 'minyag_collection_scope', '馆藏总体语言和 2009 年采录时间不自动确定每条语言、录音日期或叙事年代。'),
        issue('coordinate', 'minyag_location_scope', '馆藏总体地点不能直接确定单条录音地点或故事发生地。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'minyag_codes_unassigned', '未据原内容及本地码表核定标准码。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'minyag_coordinate_unverified', '目录总体范围不足以确定逐条坐标。', urgent=True))
    parents = [s for s in metadata.sources if s.type == 'minyag_wolp_catalogue']
    receipts = [s for s in metadata.sources if s.type == 'minyag_wolp_manifest']
    if (len(parents) != 1 or len(receipts) != 1 or any(not s.local_path or not s.content_sha256 for s in parents + receipts)
            or str(parents[0].url) != MINYAG_URL or str(receipts[0].url) != MINYAG_TERMS
            or parents[0].locator != '馆藏总述与编号目录' or receipts[0].locator != '目录与网站条款快照清单'):
        record['issues'].append(issue('source', 'minyag_source_missing', '馆藏目录或网站条款快照来源不完整。', urgent=True))
        return
    parent, receipt = resolved_source_path(parents[0]), resolved_source_path(receipts[0])
    if (parent.name != 'catalogue.html' or receipt != parent.parent / 'manifest.json'
            or source_hashes.get(parent) != parents[0].content_sha256
            or source_hashes.get(receipt) != receipts[0].content_sha256):
        record['issues'].append(issue('source', 'minyag_source_invalid', '目录或快照清单路径、哈希不符。', urgent=True))
        return
    folder = parent.parent
    if folder not in cache:
        try:
            cache[folder] = (load_minyag(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record['issues'].append(issue('source', 'minyag_snapshot_invalid', f'目录快照无法核验：{error}', urgent=True))
        return
    _, rows = loaded
    group = minyag_group_evidence(rows)
    record['evidence']['minyag_wolp_group'] = group
    if not match:
        record['evidence']['minyag_wolp_inventory'] = rows
        if not json_block_preserved(record['markdown'], group):
            record['issues'].append(issue('source', 'minyag_fields_changed', '馆藏组字段与快照不符。', urgent=True))
        return
    number = int(match.group(1))
    if number not in MINYAG_SELECTED:
        record['issues'].append(issue('source', 'minyag_unselected', '条目不在本轮筛选范围内。', urgent=True))
        return
    row = rows[number - 1]
    original = [source for source in metadata.sources if source.type == MINYAG_MARKER]
    expected = minyag_evidence(row)
    record['evidence']['minyag_wolp'] = expected
    if (len(original) != 1 or str(original[0].url) != row['archive_url']
            or original[0].locator != f'目录第 {number} 条 / 旧档案入口待核'
            or metadata.title != f"四川木雅语目录 · {row['title']}" or row['title'] not in metadata.aliases
            or not json_block_preserved(record['markdown'], expected)):
        record['issues'].append(issue('source', 'minyag_fields_changed', '目录字段或旧档案链接与快照不符。', urgent=True))
    targets = [relation.target for relation in metadata.relations if relation.type == 'COMPARED_WITH']
    compared = [f'{MINYAG_PREFIX}{MINYAG_COMPARISONS[number]:02d}'] if number in MINYAG_COMPARISONS else []
    if targets != compared or not any(relation.type == 'PART_OF_MACRO_TREND' and relation.target == MINYAG_ROOT for relation in metadata.relations):
        record['issues'].append(issue('source', 'minyag_relation_changed', '所属馆藏或人物线索对照不符。', urgent=True))
    if number in MINYAG_COMPARISONS:
        record['issues'].append(issue('source', 'minyag_comparison_unverified', '题名有共同人物只提供待核对照，不证明同一故事、来源或传播。'))
    current = [s for s in metadata.sources if s.type == 'minyag_wolp_current']
    current_manifests = [s for s in metadata.sources if s.type == 'minyag_wolp_current_manifest']
    if current or current_manifests:
        if (number != 19 or len(current) != 1 or len(current_manifests) != 1
                or any(not s.local_path or not s.content_sha256 or str(s.url) != MINYAG_CURRENT_URL for s in current + current_manifests)
                or current[0].locator != '单件目录 / 旧档案标识与描述'
                or current_manifests[0].locator != '单件目录网页快照清单'):
            record['issues'].append(issue('source', 'minyag_current_source_invalid', '剑桥单件来源不完整或不对应第 19 条。', urgent=True))
            return
        current_path = resolved_source_path(current[0])
        manifest_path = resolved_source_path(current_manifests[0])
        if (current_path.name != 'item.html' or manifest_path != current_path.parent / 'manifest.json'
                or source_hashes.get(current_path) != current[0].content_sha256
                or source_hashes.get(manifest_path) != current_manifests[0].content_sha256):
            record['issues'].append(issue('source', 'minyag_current_hash_invalid', '剑桥单件网页或清单路径与哈希不符。', urgent=True))
            return
        try:
            current_data = load_minyag_current(current_path.parent, rows)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            record['issues'].append(issue('source', 'minyag_current_invalid', f'剑桥单件信息无法核验：{exc}', urgent=True))
            return
        record['evidence']['minyag_wolp_current'] = current_data
        record['issues'].append(issue('source', 'minyag_name_variant', '旧目录和剑桥单件描述的人名拼写不同；身份与角色待核。', urgent=True))
        if not json_block_preserved(record['markdown'], current_data):
            record['issues'].append(issue('source', 'minyag_current_fields_changed', '草稿中的现行剑桥单件字段与快照不符。', urgent=True))


def bl_yi_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(BL_YI_PREFIX + r'(\d{2})', metadata.id)
    if not match and metadata.id != BL_YI_ROOT:
        return
    record['issues'].extend([
        issue('classification', 'bl_yi_group_not_story', '馆藏组或按讲述者整理的录音子组包含多个文件，不等同单篇故事。'),
        issue('source', 'bl_yi_recording_unavailable', '本地仅保存馆方目录；未取得录音或转写，数字内容入口须另核。'),
        issue('source', 'bl_yi_rights_context', '目录文字按 CC BY 4.0 署名；录音仅供研究，其他使用和社区要求另核。'),
        issue('coordinate', 'bl_yi_location_scope', '馆藏地区、讲述者来源、单条录音地点及叙事发生地须分别核对。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'bl_yi_codes_unassigned', '尚未依据录音内容与本地码表核定标准码。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate', 'bl_yi_coordinate_unverified', '目录范围不足以确定逐条坐标。', urgent=True))
    roots = [s for s in metadata.sources if s.type == 'bl_yi_group']
    manifests = [s for s in metadata.sources if s.type == 'bl_yi_manifest']
    if (len(roots) != 1 or len(manifests) != 1 or any(not s.local_path or not s.content_sha256 or str(s.url) != BL_YI_URL for s in roots + manifests)
            or roots[0].locator != 'EAP081/25 / 馆藏组' or manifests[0].locator != '馆藏组与六个子组的快照清单'):
        record['issues'].append(issue('source', 'bl_yi_source_missing', '馆藏组目录或快照清单来源不唯一或不完整。', urgent=True))
        return
    root_path, manifest_path = resolved_source_path(roots[0]), resolved_source_path(manifests[0])
    if (root_path.name != 'root.html' or manifest_path != root_path.parent / 'manifest.json'
            or source_hashes.get(root_path) != roots[0].content_sha256 or source_hashes.get(manifest_path) != manifests[0].content_sha256):
        record['issues'].append(issue('source', 'bl_yi_source_invalid', '馆藏组和快照清单路径或哈希不符。', urgent=True))
        return
    folder = root_path.parent
    if folder not in cache:
        try:
            cache[folder] = (load_bl_yi(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record['issues'].append(issue('source', 'bl_yi_snapshot_invalid', f'彝语馆藏快照无法核验：{error}', urgent=True))
        return
    selection, root_fields, children = loaded
    root_data = bl_yi_group_evidence(root_fields, children)
    record['evidence']['bl_yi_group'] = root_data
    expected = root_data
    if match:
        number = int(match.group(1))
        found = [item for item in children if item[0]['number'] == number]
        details = [s for s in metadata.sources if s.type == 'bl_yi_child']
        if len(found) != 1 or len(details) != 1 or not details[0].local_path or not details[0].content_sha256 or not details[0].url:
            record['issues'].append(issue('source', 'bl_yi_child_missing', '录音子组来源缺失或不唯一。', urgent=True))
            return
        child, path, checksum, fields = found[0]
        if (resolved_source_path(details[0]) != path.resolve() or details[0].content_sha256 != checksum
                or source_hashes.get(path.resolve()) != checksum or str(details[0].url) != child['url']
                or details[0].locator != f'EAP081/25/{number} / 录音子组'):
            record['issues'].append(issue('source', 'bl_yi_child_invalid', '录音子组目录链接或哈希不符。', urgent=True))
            return
        if not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == BL_YI_ROOT for rel in metadata.relations):
            record['issues'].append(issue('source', 'bl_yi_relation_missing', '子组所属馆藏关联缺失。', urgent=True))
        expected = bl_yi_child_evidence(fields)
        record['evidence']['bl_yi_child'] = expected
        if metadata.title != f'云南彝语口述录音 · EAP081/25/{number}' or fields['Title'] not in metadata.aliases:
            record['issues'].append(issue('source', 'bl_yi_fields_changed', '卡片题名或馆方别名与子组不符。', urgent=True))
        if number == 4 and 'Pu Rongxiang' in fields['Title'] and 'Pu Rongziang' in fields['Scope & Content']:
            record['issues'].append(issue('source', 'bl_yi_name_variant', '题名写 Pu Rongxiang，内容说明写 Pu Rongziang；人物拼写待核。', urgent=True))
    if not json_block_preserved(record['markdown'], expected):
        record['issues'].append(issue('source', 'bl_yi_fields_changed', '草稿字段与馆方目录快照不符。', urgent=True))
    recorded = re.findall(r'\b20\d{2}\b', expected.get('馆方内容说明') or '')
    start, end = expected.get('馆方日期起始原字段'), expected.get('馆方日期结束原字段')
    if recorded and re.fullmatch(r'\d{4}', start or '') and re.fullmatch(r'\d{4}', end or '') and any(not int(start) <= int(year) <= int(end) for year in recorded):
        record['issues'].append(issue('source', 'bl_yi_dates_disagree', '馆方内容说明中的项目或录音年份不在统一日期字段范围内；两处原值分别保留。', urgent=True))
    if not match:
        total = bl_yi_duration(root_fields.get('Extent'))
        subtotal = root_data['六组时长字段相加分钟数（待核）']
        if total is not None and subtotal is not None and total != subtotal:
            record['issues'].append(issue('source', 'bl_yi_duration_difference', '六组所列时长相加与父级约数不同，须核对统计口径。'))


def bl_khmer_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(r"corpus_kh_bl_or16131_(\d{2})", metadata.id)
    if not match and metadata.id != BL_KHMER_ROOT:
        return
    record["issues"].extend([
        issue("source", "bl_khmer_unit_not_story", "馆方登记的是折本册或馆藏组，一册可能包含多件作品，不能作为单篇故事计数。"),
        issue("source", "bl_khmer_catalogue_rights", "目录文字按 CC BY 4.0 署名；手稿影像、内容及访问条件须另核。"),
        issue("source", "bl_khmer_original_unchecked", "本地保存馆方目录页面，未保存手稿影像或转写正文。"),
        issue("source", "bl_khmer_dates_scope", "馆方的手稿日期范围与作品创作年代、叙事发生年代不能自动等同。"),
        issue("coordinate", "bl_khmer_origin_scope", "馆方来源地可能带疑问；馆藏地、手稿来源和故事发生地须分开核对。")])
    if not any(metadata.standards.model_dump().values()):
        record["issues"].append(issue("standard", "bl_khmer_codes_unassigned", "尚未依据手稿内容和本地码表确认类型或母题标准码。"))
    else:
        record["issues"].append(issue("standard", "bl_khmer_codes_need_context", "请核对标准码与手稿内容及本地码表的对应依据。"))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record["issues"].append(issue("coordinate", "bl_khmer_coordinate_unverified", "折本来源地未确认，坐标须回查。", urgent=True))
    roots = [s for s in metadata.sources if s.type == "bl_khmer_catalogue" and s.locator == "Or 16131/1-11 / 馆藏组"]
    if len(roots) != 1 or not roots[0].local_path or not roots[0].content_sha256 or not roots[0].url or str(roots[0].url) != BL_KHMER_URL:
        record["issues"].append(issue("source", "bl_khmer_root_invalid", "馆藏组来源不唯一或不完整。", urgent=True))
        return
    root_path = resolved_source_path(roots[0])
    if root_path.name != "root.html" or source_hashes.get(root_path) != roots[0].content_sha256:
        return
    folder = root_path.parent
    if folder not in cache:
        try:
            cache[folder] = (load_bl_khmer(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record["issues"].append(issue("source", "bl_khmer_snapshot_invalid", f"馆藏批次快照无法核验：{error}", urgent=True))
        return
    selection, root_fields, records = loaded
    record["evidence"]["bl_khmer_group"] = {"馆方档号": root_fields.get("Reference (shelfmark)"),
        "馆方数量": root_fields.get("Extent"), "馆方日期起始": root_fields.get("Start Date"),
        "馆方日期结束": root_fields.get("End Date"), "馆藏组快照SHA256": selection["root_sha256"]}
    if not match:
        return
    number = int(match.group(1))
    found = [item for item in records if item[0]["volume"] == number]
    details = [s for s in metadata.sources if s.type == "bl_khmer_catalogue" and s.locator == f"Or 16131/{number}"]
    if len(found) != 1 or len(details) != 1 or not details[0].local_path or not details[0].url or not details[0].content_sha256:
        record["issues"].append(issue("source", "bl_khmer_detail_invalid", "折本单册来源与册号不对应。", urgent=True))
        return
    child, path, checksum, fields = found[0]
    if (resolved_source_path(details[0]) != path.resolve() or details[0].content_sha256 != checksum
            or source_hashes.get(path.resolve()) != checksum or str(details[0].url) != child["url"]):
        record["issues"].append(issue("source", "bl_khmer_detail_invalid", "折本单册来源链接或快照不符。", urgent=True))
        return
    record["evidence"]["bl_khmer"] = fields
    if not json_block_preserved(record["markdown"], fields):
        record["issues"].append(issue("source", "bl_khmer_fields_changed", "草稿中的馆方单册字段与快照不符。", urgent=True))
    if not fields["数字化字段链接"]:
        record["issues"].append(issue("source", "bl_khmer_no_digital_link", "本次馆方数字化字段未显示链接；不据此认定影像不存在。"))
    origin = re.search(r"Origin:\s*([^\n]+)", fields["馆方内容说明"], re.I)
    if origin and ("?" in origin.group(1) or "possibly" in origin.group(1).lower()):
        record["issues"].append(issue("coordinate", "bl_khmer_origin_uncertain", "馆方来源地点字段含疑问或可能性表述，须回查。"))
    start, end = fields.get("馆方日期起始原字段"), fields.get("馆方日期结束原字段")
    parent_start, parent_end = root_fields.get("Start Date"), root_fields.get("End Date")
    if all(re.fullmatch(r"\d{4}", str(v or "")) for v in (start, end, parent_start, parent_end)):
        if int(start) < int(parent_start) or int(end) > int(parent_end):
            record["issues"].append(issue("source", "bl_khmer_date_parent_conflict",
                f"馆方本册日期 {start}–{end} 超出馆藏组日期 {parent_start}–{parent_end}；两处原值均保留待核。", urgent=True))


def na_candidate_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    originals = [source for source in metadata.sources if source.type == NA_CANDIDATE_MARKER]
    if not originals:
        return
    record['issues'].extend([
        issue('classification', 'na_candidate_not_story', '录音目录题名和选择理由不自动证明内容、体裁或一篇独立故事。'),
        issue('source', 'na_candidate_detail_missing', '本批只使用既有目录快照；单条详情未取得，链接与当前元数据须回查。'),
        issue('source', 'na_candidate_rights', '音视频、转写及其许可未核；相关社区要求须逐条确认。'),
        issue('source', 'na_candidate_comparison', '题名中的版本或前后顺序只提供对照线索，不证明同一演述、来源或传播。'),
        issue('coordinate', 'na_candidate_place', '目录未提供经核实的单条录音地点；馆藏语言范围不是故事地点。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'na_candidate_codes_unassigned', '未依据原文和本地码表核定标准码。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate', 'na_candidate_coordinate_unverified', '本批坐标缺少逐条依据。', urgent=True))
    match = re.fullmatch(NA_CANDIDATE_PREFIX + r'(\d{7})', metadata.id)
    kinds = ['pangloss_na_candidate_catalogue', 'pangloss_na_candidate_first',
             'pangloss_na_candidate_context', 'pangloss_na_candidate_selection']
    sources = [[source for source in metadata.sources if source.type == kind] for kind in kinds]
    if (not match or len(originals) != 1 or any(len(items) != 1 for items in sources)
            or any(not items[0].local_path or not items[0].content_sha256 or str(items[0].url) != PANGLOSS_NA_URL for items in sources)):
        record['issues'].append(issue('source', 'na_candidate_source_missing', '目录或选取来源缺失、重复或链接不符。', urgent=True))
        return
    local = [items[0] for items in sources]
    paths = [resolved_source_path(source) for source in local]
    if any(source_hashes.get(path) != source.content_sha256 for path, source in zip(paths, local, strict=True)):
        return  # The generic source-hash check already reports the discrepancy.
    key = tuple(paths)
    if key not in cache:
        try:
            cache[key] = (validate_na_candidates(*paths), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[key] = (None, str(error))
    validated, error = cache[key]
    if validated is None:
        record['issues'].append(issue('source', 'na_candidate_index_invalid', f'目录或选取索引无法核验：{error}', urgent=True))
        return
    catalog, selection, _ = validated
    number = match.group(1)
    selected = [item for item in selection['choices'] if item['id'] == number]
    if len(selected) != 1 or number not in catalog:
        record['issues'].append(issue('source', 'na_candidate_entry_missing', '卡片不在本轮选取中。', urgent=True))
        return
    row, item, original = catalog[number], selected[0], originals[0]
    data = na_candidate_evidence(row, item)
    record['evidence']['na_catalogue_candidate'] = data
    if (str(original.url) != row['url'] or original.doi != row['doi'].removeprefix('https://doi.org/')
            or original.locator != f'录音 {number}，单条详情及许可待核'
            or metadata.title != f"永宁纳语录音 · {row['title']}" or row['title'] not in metadata.aliases
            or not json_block_preserved(record['markdown'], data)):
        record['issues'].append(issue('source', 'na_candidate_fields_changed', '目录字段、原页链接或草稿内容不一致。', urgent=True))
    targets = [rel.target for rel in metadata.relations if rel.type == 'COMPARED_WITH']
    expected = [NA_CANDIDATE_PREFIX + item['compare_id']] if item['compare_id'] else []
    if targets != expected or not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == PANGLOSS_NA_ROOT for rel in metadata.relations):
        record['issues'].append(issue('source', 'na_candidate_relation_changed', '目录对照或所属馆藏关系与选取不一致。', urgent=True))


def na_tone_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    kinds = ('na_tone_book', 'na_tone_table_source', 'na_tone_crosswalk', 'na_tone_datacite_manifest')
    groups = {kind: [source for source in metadata.sources if source.type == kind] for kind in kinds}
    if not any(groups.values()) and NA_TONE_MARKER not in record['markdown']:
        return
    match = re.fullmatch(NA_CANDIDATE_PREFIX + r'(\d{7})', metadata.id)
    catalogues = [s for s in metadata.sources if s.type in ('pangloss_na_catalogue', 'pangloss_na_candidate_catalogue', 'na_tone_catalogue')]
    if (not match or any(len(group) != 1 for group in groups.values()) or len(catalogues) != 1
            or NA_TONE_MARKER not in record['markdown'] or any(not group[0].local_path or not group[0].content_sha256 for group in groups.values())
            or not catalogues[0].local_path or not catalogues[0].content_sha256):
        record['issues'].append(issue('source', 'na_tone_sources_missing', '专著、目录、DOI 登记或书目索引缺失或重复。', urgent=True))
        return
    ordered = [groups[kind][0] for kind in kinds]
    book, tex, index_path, registry_manifest = (resolved_source_path(source) for source in ordered)
    corpus = resolved_source_path(catalogues[0])
    if (registry_manifest.name != 'manifest.json' or any(source_hashes.get(path) != source.content_sha256
            for path, source in zip((book, tex, index_path, registry_manifest, corpus), (*ordered, catalogues[0]), strict=True))):
        record['issues'].append(issue('source', 'na_tone_sources_invalid', '专著、目录或 DOI 登记快照位置或哈希不符。', urgent=True))
        return
    key = (index_path, book, tex, corpus, registry_manifest.parent)
    if key not in cache:
        try:
            index = load_na_tone_index(index_path, book, tex, corpus, registry_manifest.parent)
            cache[key] = ((index, pangloss_catalogue_rows(corpus.read_bytes())), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[key] = (None, str(error))
    verified, error = cache[key]
    if verified is None:
        record['issues'].append(issue('source', 'na_tone_index_invalid', f'专著对照索引无法从原始来源重算：{error}', urgent=True))
        return
    index, catalog = verified
    number = match.group(1)
    if number not in index['recordings'] or number not in catalog:
        record['issues'].append(issue('source', 'na_tone_record_missing', '录音不在可核验的专著对应结果中。', urgent=True))
        return
    try:
        expected = na_tone_sources(index, number, book, tex, index_path, registry_manifest.parent)
    except (ValueError, OSError, KeyError) as error:
        record['issues'].append(issue('source', 'na_tone_sources_invalid', f'专著来源无法读取：{error}', urgent=True))
        return
    if ordered != expected or na_tone_note(index, number).strip() not in record['markdown']:
        record['issues'].append(issue('source', 'na_tone_content_changed', '书目链接、回执或草稿补充与可核验索引不符。', urgent=True))
        return
    data = na_tone_summary(index, number)
    record['evidence']['na_tone_book'] = data
    record['issues'].extend([
        issue('source', 'na_tone_book_scope', '出版专著提供录音与分句引用线索，尚未核对音频、转写及链接可用性。'),
        issue('source', 'na_tone_distinct_rights', '专著 CC BY 4.0 和 DataCite 元数据 CC0 不决定音频、转写或社群资料的权利。'),
        issue('source', 'na_tone_audio_text_distinction', '录音与附属文本的 DOI 不同；仅按主资源和登记关系作待核对照。')])
    for flag in index['recordings'][number]['flags']:
        record['issues'].append(issue('source', 'na_tone_' + flag, NA_TONE_FLAGS.get(flag, flag),
                                      urgent=flag in ('book_table_doi_reused_across_topics', 'book_catalogue_version_label_differs',
                                                      'datacite_primary_disagrees', 'datacite_record_type_disagrees')))
    originals = [s for s in metadata.sources if s.type == NA_TONE_NEW_MARKER]
    if originals:
        record['issues'].extend([
            issue('classification', 'na_tone_new_not_story', '按专著目录选出的背景录音，不自动当作民间故事或单次演述。'),
            issue('source', 'na_tone_new_details_missing', '馆方单条详情、原音和转写未取得；登记权利及社区条件需回查。'),
            issue('coordinate', 'na_tone_new_place', '馆藏范围不是单条采录地点或故事发生地。')])
        if not any(metadata.standards.model_dump().values()):
            record['issues'].append(issue('standard', 'na_tone_codes_unassigned', '未依据原文和本地码表核定标准码。'))
        else:
            record['issues'].append(issue('standard', 'na_tone_codes_need_context', '请按原文和本地码表核对标准码。'))
        if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
            record['issues'].append(issue('coordinate', 'na_tone_new_coordinate_unverified', '新增候选坐标缺少逐条来源依据。', urgent=True))
        selections = [s for s in metadata.sources if s.type == 'na_tone_new_selection']
        if len(originals) != 1 or len(selections) != 1 or not selections[0].local_path or not selections[0].content_sha256:
            record['issues'].append(issue('source', 'na_tone_new_source_missing', '新增候选的原页或选取来源缺失。', urgent=True))
            return
        selection_path = resolved_source_path(selections[0])
        if source_hashes.get(selection_path) != selections[0].content_sha256:
            return
        try:
            selected = json.loads(selection_path.read_text(encoding='utf-8'))
            def local_path(key):
                path = Path(selected[key])
                return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
            expected_selection = na_tone_new_selection(index, index_path, corpus, local_path('first_path'),
                                                       local_path('context_path'), local_path('prior_path'))
            if selected != expected_selection or number not in selected['ids']:
                raise ValueError('选择范围不符')
        except (ValueError, OSError, KeyError, TypeError) as error:
            record['issues'].append(issue('source', 'na_tone_new_selection_invalid', f'新增候选无法核验：{error}', urgent=True))
            return
        row, original = catalog[number], originals[0]
        expected_relations = [NA_CANDIDATE_PREFIX + '0004448'] if number == '0004549' and '0004448' in selected['ids'] else []
        if (str(original.url) != row['url'] or original.doi != row['doi'].removeprefix('https://doi.org/')
                or metadata.title != f"永宁纳语录音 · {row['title']}" or row['title'] not in metadata.aliases
                or not json_block_preserved(record['markdown'], na_tone_new_evidence(row))
                or [rel.target for rel in metadata.relations if rel.type == 'COMPARED_WITH'] != expected_relations
                or not any(rel.type == 'PART_OF_MACRO_TREND' and rel.target == PANGLOSS_NA_ROOT for rel in metadata.relations)):
            record['issues'].append(issue('source', 'na_tone_new_fields_changed', '新增候选的馆方字段、链接或关系不符。', urgent=True))


def early_edition_review(record: dict, metadata, source_hashes: dict, cache: dict, andersen_cache: dict) -> None:
    jade_case = re.fullmatch(JADE_PREFIX + r'\d{3}', metadata.id)
    is_jade = metadata.id == JADE_ROOT or bool(jade_case)
    is_saleeby = metadata.id in (SALEEBY_ROOT, SALEEBY_CASE)
    if not is_jade and not is_saleeby:
        return
    prefix = 'jade' if is_jade else 'saleeby'
    record['issues'].extend([
        issue('source', f'{prefix}_edition_scope', '历史出版物经过编选或翻译，不能自动视为未经整理的现场口述。'),
        issue('source', f'{prefix}_scan_candidate', '扫描页定位依赖未校对 OCR 与扫描清单；请逐页核对原图。'),
        issue('source', f'{prefix}_rights_context', '原书、数字文本、译本与社区资料的使用条件须分别核查。'),
        issue('coordinate', f'{prefix}_location_scope', '书中地域标签或叙事地名不能自动当作采录地或地理坐标。'),
    ])
    if is_jade:
        record['issues'].append(issue('classification', 'jade_label_not_origin', '原目录地区分类可能指故事场景或编辑归类，不足以证明口述传统来源。'))
    else:
        record['issues'].append(issue('source', 'saleeby_cole_lineage', '1916 年脚注称 Saleeby 最初记录，但未注明具体底本；两版与原始采录的关系待核。'))
        record['issues'].append(issue('coordinate', 'saleeby_region_distinction', '1905 与 1916 年开头分别使用 Magindanao 与 Mindanao，范围不能自动等同。'))
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', f'{prefix}_codes_unassigned', '尚未依据原文及本地码表核定标准码。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate', f'{prefix}_coordinate_unverified', '坐标须有逐条出处和地点性质依据。', urgent=True))
    required = [f'{prefix}_scan', f'{prefix}_ocr', f'{prefix}_index', f'{prefix}_scandata']
    if is_jade:
        required.append('jade_toc')
    sources = {kind: [source for source in metadata.sources if source.type == kind] for kind in required}
    if any(len(value) != 1 for value in sources.values()):
        record['issues'].append(issue('source', f'{prefix}_source_missing', '扫描、OCR、扫描清单或目录索引来源缺失或重复。', urgent=True))
        return
    scan = sources[f'{prefix}_scan'][0]
    local_sources = [sources[kind][0] for kind in required if not kind.endswith('_scan')]
    if any(not source.local_path or not source.content_sha256 for source in local_sources):
        record['issues'].append(issue('source', f'{prefix}_source_invalid', '目录或扫描索引缺少快照路径或哈希。', urgent=True))
        return
    paths = [resolved_source_path(source) for source in local_sources]
    if any(source_hashes.get(path) != source.content_sha256 for path, source in zip(paths, local_sources, strict=True)):
        return
    edition = JADE_EDITION if is_jade else SALEEBY_EDITION
    edition_path = resolved_source_path(sources[f'{prefix}_ocr'][0]).parent
    if edition_path.name != edition or any(resolved_source_path(sources[f'{prefix}_{kind}'][0]).parent != edition_path
                                            for kind in ('index', 'scandata')):
        record['issues'].append(issue('source', f'{prefix}_snapshot_invalid', 'OCR 与扫描清单不是同一馆藏副本。', urgent=True))
        return
    suffixes = {'ocr': 'hocr_searchtext.txt.gz', 'index': 'hocr_pageindex.json.gz', 'scandata': 'scandata.xml'}
    for kind, suffix in suffixes.items():
        source = sources[f'{prefix}_{kind}'][0]
        name = f'{edition}_{suffix}'
        if (resolved_source_path(source).name != name or source.content_sha256 != early_editions.FILES[edition][kind]
                or str(source.url) != f'https://archive.org/download/{edition}/{name}'):
            record['issues'].append(issue('source', f'{prefix}_source_identity_changed', '来源文件、哈希或下载地址与登记的馆藏副本不符。', urgent=True))
            return
    folder = edition_path.parent
    toc = resolved_source_path(sources['jade_toc'][0]) if is_jade else None
    key = (prefix, folder, toc)
    if key not in cache:
        try:
            if is_jade:
                value = load_jade(toc, folder)
            else:
                pages = early_read_pages(folder, edition)
                mapping = early_scan_mapping(folder, edition)
                text = re.sub(r'[^a-z0-9]+', '', pages[22].casefold())
                if 'themythologyofmindanao' not in text or 'magindanao' not in text or mapping[22]['viewer'] is None:
                    raise ValueError('印刷第 16 页候选未检出章节标题和地名。')
                value = mapping[22]
            cache[key] = (value, None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[key] = (None, str(error))
    value, error = cache[key]
    if value is None:
        record['issues'].append(issue('source', f'{prefix}_snapshot_invalid', f'来源或分页索引无法核验：{error}', urgent=True))
        return
    if is_saleeby:
        data = {'印刷页': 16, 'OCR扫描序号': 23, '扫描叶号': value['leaf'], '查看器索引': value['viewer'],
                '扫描链接': early_scan_url(edition, value['viewer'])}
        record['evidence']['saleeby_1905'] = data
        if str(scan.url) != data['扫描链接']:
            record['issues'].append(issue('source', 'saleeby_scan_changed', '1905 年扫描链接与来源清单不一致。', urgent=True))
        if metadata.id == SALEEBY_CASE and not any(rel.type == 'COMPARED_WITH' and rel.target == 'case_ph_cole_1916_p157' for rel in metadata.relations):
            record['issues'].append(issue('source', 'saleeby_comparison_missing', '1905 与 1916 年候选对照关系缺失。', urgent=True))
        return
    rows = value
    if metadata.id == JADE_ROOT:
        record['evidence']['jade_inventory'] = [jade_evidence(row) for row in rows]
        record['issues'].append(issue('source', 'jade_existing_lumawig', '第 28 项复用已有 Lumawig 草稿；原目录共 33 项，新建 32 项。'))
        mapping = early_scan_mapping(folder, edition)
        if str(scan.url) != early_scan_url(edition, mapping[13]['viewer']):
            record['issues'].append(issue('source', 'jade_scan_changed', '目录扫描链接与来源清单不一致。', urgent=True))
        if not any(rel.type == 'COMPARED_WITH' and rel.target == 'corpus_asia_jade_philippines' for rel in metadata.relations):
            record['issues'].append(issue('source', 'jade_comparison_missing', '1922 年菲律宾子集对照关系缺失。', urgent=True))
        return
    matches = [row for row in rows if jade_id(row) == metadata.id]
    if len(matches) != 1:
        record['issues'].append(issue('source', 'jade_entry_missing', '卡片与目录项无法唯一对应。', urgent=True))
        return
    row = matches[0]
    data = jade_evidence(row)
    record['evidence']['jade_1922'] = data
    if (str(scan.url) != data['扫描候选链接'] or metadata.title != f"1922 年英文选集 · {row['title']}"
            or not json_block_preserved(record['markdown'], data)):
        record['issues'].append(issue('source', 'jade_fields_changed', '题名、候选链接或目录字段与本地索引不符。', urgent=True))
    if not row['footer_match']:
        record['issues'].append(issue('source', 'jade_footer_unreadable', 'OCR 未可靠识别目录印刷页码，须看原扫描。'))
    if row['heading_score'] < .96 or row['heading_extended']:
        record['issues'].append(issue('source', 'jade_heading_difference', '正文标题与目录略有差异或 OCR 识别不清，须核原图。'))
    if row['printed_page'] in JADE_COMPARISONS:
        target, _note = JADE_COMPARISONS[row['printed_page']]
        if not any(rel.type == 'COMPARED_WITH' and rel.target == target for rel in metadata.relations):
            record['issues'].append(issue('source', 'jade_comparison_missing', '已登记的 1916 年同题候选对照关系缺失。', urgent=True))
        record['issues'].append(issue('source', 'jade_cole_comparison', '前言说明菲律宾篇目使用 Cole 选集，同题对照不证明独立采录或具体底本。'))
    if row['printed_page'] == 119:
        record['issues'].append(issue('source', 'jade_hauff_reference', '本书前言将此篇归于 Wilhelm Hauff；原作与译本关系待核。'))
    if row['printed_page'] == 3:
        record['issues'].append(issue('classification', 'jade_andersen_candidate', '本篇与安徒生《夜莺》情节高度相似；具体改写底本待核，不能将中国场景当作在地口述来源。', urgent=True))
        refs = [source for source in metadata.sources if source.type == 'jade_andersen_reference']
        expected = {ANDERSEN_REGISTER, ANDERSEN_TRANSLATION}
        if len(refs) != 2 or {str(source.url) for source in refs} != expected or any(not source.local_path or not source.content_sha256 for source in refs):
            record['issues'].append(issue('source', 'jade_andersen_reference_missing', '安徒生中心作品登记或译本对照来源缺失。', urgent=True))
            return
        ref_paths = [resolved_source_path(source) for source in refs]
        if any(source_hashes.get(path) != source.content_sha256 for path, source in zip(ref_paths, refs, strict=True)):
            return
        if ref_paths[0].parent != ref_paths[1].parent:
            record['issues'].append(issue('source', 'jade_andersen_reference_invalid', '安徒生中心参考快照不在同一目录。', urgent=True))
            return
        expected_names = {ANDERSEN_REGISTER: 'register.html', ANDERSEN_TRANSLATION: 'translation.html'}
        if any(path.name != expected_names[str(source.url)] or source.content_sha256 != early_editions.ANDERSEN_SHA[path.name]
               for path, source in zip(ref_paths, refs, strict=True)):
            record['issues'].append(issue('source', 'jade_andersen_reference_invalid', '安徒生中心链接与对应快照不一致。', urgent=True))
            return
        if ref_paths[0].parent not in andersen_cache:
            try:
                read_andersen(ref_paths[0].parent)
                andersen_cache[ref_paths[0].parent] = None
            except (ValueError, OSError, KeyError, TypeError) as error:
                andersen_cache[ref_paths[0].parent] = str(error)
        if andersen_cache[ref_paths[0].parent]:
            record['issues'].append(issue('source', 'jade_andersen_reference_invalid', f"安徒生中心来源无法核验：{andersen_cache[ref_paths[0].parent]}", urgent=True))


def cole_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    if metadata.id != COLE_ROOT and not re.fullmatch(COLE_PREFIX + r'\d{3}', metadata.id):
        return
    record['issues'].extend([
        issue('source', 'cole_edition_scope', '本书为 1916 年编选及重述；单条讲述者、采录出处与版本链均须回查。'),
        issue('source', 'cole_historic_labels', '目录保留历史分类和殖民时期用语，不能直接当作当代社群自称。'),
        issue('source', 'cole_ocr_candidate', '起始扫描序号根据未校对 OCR 生成；须逐页核对影像、标题和印刷页码。'),
        issue('source', 'cole_rights_context', '原书美国公有领域状态不代表其他地区或所有数字副本的许可；复核社区要求。'),
        issue('coordinate', 'cole_location_scope', '书籍的菲律宾覆盖范围不是逐条采录地或故事发生地。'),
    ])
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'cole_codes_unassigned', '未根据原文与本地码表核定标准码。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate', 'cole_coordinate_unverified', '坐标需要逐条来源及地点性质的依据。', urgent=True))
    required = ('cole_toc_index', 'cole_ocr', 'cole_page_index', 'cole_scan_link')
    groups = {kind: [source for source in metadata.sources if source.type == kind] for kind in required}
    if any(len(value) != 1 for value in groups.values()):
        record['issues'].append(issue('source', 'cole_source_missing', '目录、OCR、分页索引或扫描链接缺失或重复。', urgent=True))
        return
    toc, ocr, page_index, scan = (groups[kind][0] for kind in required)
    if any(not source.local_path or not source.content_sha256 for source in (toc, ocr, page_index)):
        record['issues'].append(issue('source', 'cole_source_invalid', '目录或 OCR 快照缺少本地路径或哈希。', urgent=True))
        return
    paths = [resolved_source_path(source) for source in (toc, ocr, page_index)]
    if any(source_hashes.get(path) != source.content_sha256 for path, source in zip(paths, (toc, ocr, page_index), strict=True)):
        return  # The generic checks already report missing/changed bytes.
    if paths[1].parent != paths[2].parent:
        record['issues'].append(issue('source', 'cole_snapshot_invalid', 'OCR 与分页索引不在同一快照目录。', urgent=True))
        return
    key = (paths[0], paths[1].parent)
    if key not in cache:
        try:
            cache[key] = (load_cole_catalogue(*key), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[key] = (None, str(error))
    rows, error = cache[key]
    if rows is None:
        record['issues'].append(issue('source', 'cole_snapshot_invalid', f'目录或分页 OCR 无法核验：{error}', urgent=True))
        return
    if metadata.id == COLE_ROOT:
        record['evidence']['cole_collection_count'] = len(rows)
        return
    matches = [row for row in rows if cole_node_id(row) == metadata.id]
    if len(matches) != 1:
        record['issues'].append(issue('source', 'cole_entry_missing', '卡片与目录条目无法唯一对应。', urgent=True))
        return
    row = matches[0]
    data = cole_evidence(row)
    record['evidence']['cole_1916'] = data
    if (str(scan.url) != cole_scan_url(row['scan']) or metadata.title != f"菲律宾 1916 年选集 · {row['title']}"
            or not json_block_preserved(record['markdown'], data)):
        record['issues'].append(issue('source', 'cole_fields_changed', '题名、候选扫描链接或证据字段与本地目录不符。', urgent=True))
    if not row['footer_match']:
        record['issues'].append(issue('source', 'cole_footer_unreadable', 'OCR 未识别出与目录相符的数字页脚；须看原扫描。'))
    if row['heading_score'] < .96:
        record['issues'].append(issue('source', 'cole_heading_difference', '目录题名与 OCR 章节标题有差异或识别误差；须核原图。'))
    if sum(other['title'].casefold() == row['title'].casefold() for other in rows) > 1:
        record['issues'].append(issue('source', 'cole_same_title', '本册其他分类也有同题条目；不可按题名自动合并。'))
    if row['printed_page'] == 60:
        record['issues'].append(issue('source', 'cole_auto_toc_sayen', '馆藏自动目录将扫描 88 标为另一题名；原书目录与 OCR 均指向 Sayen。', urgent=True))
    if row['printed_page'] == 68:
        record['issues'].append(issue('source', 'cole_auto_toc_magsawi', '馆藏自动目录定位到扫描 100；OCR 起始标题和印刷页 68 对应扫描 96。', urgent=True))
    if row['printed_page'] == 157:
        record['issues'].append(issue('classification', 'cole_chapter_boundary', '本章包含叙事内容；请核查内部篇章边界、前代出处和是否含多个叙述。'))
    if row['printed_page'] == 105:
        record['issues'].append(issue('source', 'cole_jade_comparison', '1922 年同题版本仅为待核对照，文字差异与前代采录关系待查。'))
    cole_page_review(record, metadata, source_hashes, cache, paths[0], paths[1].parent)


def cole_page_review(record: dict, metadata, source_hashes: dict, cache: dict, toc: Path, snapshots: Path) -> None:
    sources = [source for source in metadata.sources if source.type in ('cole_ocr_segments', 'cole_ocr_segments_manifest')]
    if not sources and COLE_OCR_MARKER not in record['markdown']:
        return  # Older catalogue-only cards remain usable without inventing OCR.
    groups = {kind: [source for source in sources if source.type == kind]
              for kind in ('cole_ocr_segments', 'cole_ocr_segments_manifest')}
    if (any(len(group) != 1 for group in groups.values()) or COLE_OCR_MARKER not in record['markdown']
            or any(not s.local_path or not s.content_sha256 for s in sources)):
        record['issues'].append(issue('source', 'cole_ocr_segments_missing', '逐页 OCR 文字或其清单来源不完整。', urgent=True))
        return
    page_source, manifest_source = (groups[kind][0] for kind in ('cole_ocr_segments', 'cole_ocr_segments_manifest'))
    page_path, manifest_path = (resolved_source_path(source) for source in (page_source, manifest_source))
    folder = manifest_path.parent
    if (manifest_path.name != 'manifest.json' or page_path != folder / (metadata.id + '.json')
            or any(source_hashes.get(path) != source.content_sha256
                   for path, source in ((page_path, page_source), (manifest_path, manifest_source)))):
        record['issues'].append(issue('source', 'cole_ocr_segments_invalid', '逐页 OCR 文件位置或哈希不符。', urgent=True))
        return
    key = ('cole_ocr_pages', folder, toc, snapshots)
    if key not in cache:
        try:
            _, segments = load_cole_segments(folder, toc, snapshots)
            cache[key] = ({item['id']: item for item in segments}, None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[key] = (None, str(error))
    segments, error = cache[key]
    segment = segments.get(metadata.id) if segments else None
    if not segment:
        record['issues'].append(issue('source', 'cole_ocr_segments_invalid', f'逐页 OCR 无法追溯原始快照：{error or metadata.id}', urgent=True))
        return
    try:
        expected = cole_segment_sources(segment, folder)
    except (ValueError, OSError) as error:
        record['issues'].append(issue('source', 'cole_ocr_segments_invalid', f'逐页 OCR 来源无法读取：{error}', urgent=True))
        return
    if sources != expected or cole_ocr_note(segment).strip() not in record['markdown']:
        record['issues'].append(issue('source', 'cole_ocr_segments_changed', '逐页 OCR 或来源与原始快照不符；请人工核对。', urgent=True))
        return
    record['issues'].extend([
        issue('source', 'cole_ocr_uncorrected', '逐页文字为未校对 OCR，保留识别错误、页眉和脚注，须对照扫描。'),
        issue('source', 'cole_ocr_boundary_candidate', '候选页范围按下一目录项或发音表截取，不能证明篇章边界。')])
    record['evidence']['cole_ocr_pages'] = segment['pages']
    record['evidence']['cole_ocr_range'] = {'start_scan': segment['start_scan'],
        'end_scan_exclusive': segment['end_scan_exclusive'], 'boundary_basis': segment['boundary_basis']}


def lowell_sea_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(r"corpus_us_lowell_sea_(\d+)", metadata.id)
    if not match and metadata.id != LOWELL_SEA_ROOT:
        return
    record["issues"].extend([
        issue("source", "lowell_item_not_story", "这是社群项目的书籍或文档目录项，可能包含多篇故事，不能按件数计故事数。"),
        issue("source", "lowell_rights_scope", "馆方说明供私人、教育和研究用途；所需权利许可及社区要求仍须核对。"),
        issue("source", "lowell_original_not_saved", "仅保存目录字段索引；文档正文、影像、音视频及网页原响应未保存。"),
        issue("source", "lowell_raw_hash_scope", "原始网页响应未保存，所记响应指纹不能仅凭字段索引离线重算。"),
        issue("source", "lowell_dates_scope", "项目或文档日期不等于叙事发生年代。"),
        issue("coordinate", "lowell_diaspora_scope", "洛厄尔是项目与馆藏范围，不能自动视为故事的原采录地或发生地。")])
    if not any(metadata.standards.model_dump().values()):
        record["issues"].append(issue("standard", "lowell_codes_unassigned", "尚未根据原文与本地码表确认标准码。"))
    else:
        record["issues"].append(issue("standard", "lowell_codes_need_context", "请核对标准码与原文及本地码表的对应依据。"))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record["issues"].append(issue("coordinate", "lowell_coordinate_unverified", "项目位置不等于单篇故事地点，请核对坐标用途。", urgent=True))
    roots = [s for s in metadata.sources if s.type == "lowell_sea_catalogue" and s.locator == "UML 24 / 项目馆藏组"]
    if len(roots) != 1 or not roots[0].local_path or not roots[0].content_sha256 or not roots[0].url or str(roots[0].url) != LOWELL_SEA_URL:
        record["issues"].append(issue("source", "lowell_root_invalid", "项目馆藏组来源不唯一或不完整。", urgent=True))
        return
    root_path = resolved_source_path(roots[0])
    if root_path.name != "selection.json" or source_hashes.get(root_path) != roots[0].content_sha256:
        return
    folder = root_path.parent
    if folder not in cache:
        try:
            cache[folder] = (load_lowell_sea(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record["issues"].append(issue("source", "lowell_snapshot_invalid", f"项目字段索引无法核验：{error}", urgent=True))
        return
    selection, records = loaded
    if not match:
        record["evidence"]["lowell_inventory"] = [{"id": row["id"], "title": row["title"], "url": row["url"],
            "selected": not lowell_is_poster(row), "fields": lowell_sea_evidence(document), "index_sha256": checksum}
            for row, _, checksum, document in records]
        record["evidence"]["lowell_collection_raw_sha256"] = selection["raw_sha256"]
        return
    identifier = int(match.group(1))
    found = [item for item in records if item[0]["id"] == identifier]
    details = [s for s in metadata.sources if s.type == "lowell_sea_catalogue" and s.locator == f"馆方记录 {identifier} / 描述字段"]
    if len(found) != 1 or len(details) != 1 or not details[0].local_path or not details[0].url or not details[0].content_sha256:
        record["issues"].append(issue("source", "lowell_detail_invalid", "项目单件来源与记录号不对应。", urgent=True))
        return
    row, path, checksum, document = found[0]
    if (lowell_is_poster(row) or resolved_source_path(details[0]) != path.resolve() or details[0].content_sha256 != checksum
            or source_hashes.get(path.resolve()) != checksum or str(details[0].url) != row["url"]):
        record["issues"].append(issue("source", "lowell_detail_invalid", "项目单件来源、类型或字段索引不符。", urgent=True))
        return
    data = lowell_sea_evidence(document)
    record["evidence"]["lowell_sea"] = data
    if metadata.title != f"洛厄尔东南亚社群项目 · {row['title']}" or not json_block_preserved(record["markdown"], data):
        record["issues"].append(issue("source", "lowell_fields_changed", "草稿中的馆方单件字段与研究索引不符。", urgent=True))
    if not document["visible_file_link_count"]:
        record["issues"].append(issue("source", "lowell_no_visible_file_link", "本次检查未在指定文件区域检出链接；单件文件是否可访问须回查。"))


def nitean_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    volume_match = re.fullmatch(r"corpus_kh_nitean_v(\d{2})", metadata.id)
    chapter_match = re.fullmatch(r"case_kh_nitean_v(\d{2})_(\d{3})", metadata.id)
    if not volume_match and not chapter_match and metadata.id != NITEAN_ROOT:
        return
    record["issues"].extend([
        issue("source", "nitean_transcription_version", "这是现代网站的数字转录；原印本、编辑与单篇采录背景仍需核查。"),
        issue("source", "nitean_text_rights", "站点所称来源项目的许可不能自动覆盖所有故事文本；再利用及社区要求须逐篇核对。"),
        issue("source", "nitean_raw_not_saved", "本地仅保存题名、链接和出处结构字段；原网页与故事正文未保存，响应指纹不能离线重算。"),
        issue("source", "nitean_edition_comparison", "其他目录的卷数和条数不同；同题或相似题名不自动表示相同版本。"),
        issue("coordinate", "nitean_location_scope", "柬埔寨是选集范围，不能自动当作本篇采录地或故事发生地。")])
    if not any(metadata.standards.model_dump().values()):
        record["issues"].append(issue("standard", "nitean_codes_unassigned", "尚未依据原文和本地码表确认故事类型或母题标准码。"))
    else:
        record["issues"].append(issue("standard", "nitean_codes_need_context", "请核对标准码与原文和本地码表的对应依据。"))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record["issues"].append(issue("coordinate", "nitean_coordinate_unverified", "选集范围不能直接作为单篇坐标，请核对地点性质。", urgent=True))
    catalogues = [s for s in metadata.sources if s.type == "nitean_catalogue"]
    if len(catalogues) != 1 or not catalogues[0].local_path or not catalogues[0].content_sha256 or not catalogues[0].url or str(catalogues[0].url) != NITEAN_URL:
        record["issues"].append(issue("source", "nitean_catalogue_invalid", "转录目录来源不唯一或不完整。", urgent=True))
        return
    source = catalogues[0]
    path = resolved_source_path(source)
    if path.name != "selection.json" or source_hashes.get(path) != source.content_sha256:
        return
    folder = path.parent
    if folder not in cache:
        try:
            cache[folder] = (load_nitean(folder), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[folder] = (None, str(error))
    loaded, error = cache[folder]
    if loaded is None:
        record["issues"].append(issue("source", "nitean_snapshot_invalid", f"转录目录或单篇字段索引无法核验：{error}", urgent=True))
        return
    selection, chapters = loaded
    record["evidence"]["nitean_catalogue"] = {"卷内条数": selection["volume_counts"],
        "故事条数": len(chapters), "目录原响应SHA256": selection["raw_sha256"],
        "目录观察时间": selection["observed_at"], "序言链接": selection["introduction_url"]}
    comparisons = [s for s in metadata.sources if s.type == "wikisource_catalogue"]
    if comparisons:
        if (len(comparisons) != 1 or not comparisons[0].local_path or not comparisons[0].content_sha256
                or not comparisons[0].url or str(comparisons[0].url) != KHMER_WIKISOURCE_URL):
            record["issues"].append(issue("source", "nitean_comparison_invalid", "跨版本目录来源不唯一或不完整。", urgent=True))
        else:
            comparison_source = comparisons[0]
            comparison_path = resolved_source_path(comparison_source)
            if source_hashes.get(comparison_path) == comparison_source.content_sha256:
                cache_key = (comparison_path, 'wikisource')
                if cache_key not in cache:
                    try:
                        cache[cache_key] = (load_khmer_wikisource(comparison_path), None)
                    except (ValueError, OSError, KeyError, TypeError) as error:
                        cache[cache_key] = (None, str(error))
                wiki, error = cache[cache_key]
                if wiki is None or comparison_source.locator != f"目录修订版本 {wiki['revision_id']} / 九卷卷册数量":
                    record["issues"].append(issue("source", "nitean_comparison_invalid", f"跨版本目录字段或定位符不符：{error or '定位符不符'}", urgent=True))
                else:
                    record["evidence"]["wikisource_catalogue"] = {"修订版本": wiki['revision_id'],
                        "卷内条数": wiki['volume_counts'], "故事条数": wiki['total_stories'],
                        "观察时间": wiki['observed_at'], "原响应SHA256": wiki['raw_sha256']}
                    match = chapter_match or volume_match
                    if match:
                        number = int(match.group(1))
                        if 1 <= number <= len(selection['volume_counts']) and selection['volume_counts'][number - 1] != wiki['volume_counts'][number - 1]:
                            record["issues"].append(issue("source", "nitean_volume_count_difference",
                                f"第 {number} 卷 Nitean 列 {selection['volume_counts'][number - 1]} 篇、Wikisource 列 {wiki['volume_counts'][number - 1]} 篇；版本及单篇对应须核查。"))
    if not chapter_match:
        if volume_match:
            volume = int(volume_match.group(1))
            if not 1 <= volume <= len(selection["volume_counts"]) or source.locator != f"目录第 {volume} 卷 / {selection['volume_counts'][volume - 1]} 篇":
                record["issues"].append(issue("source", "nitean_volume_invalid", "卷次或目录数量与索引不符。", urgent=True))
        elif source.locator != "选集目录 / 8 卷 214 章":
            record["issues"].append(issue("source", "nitean_catalogue_invalid", "选集目录定位符不符。", urgent=True))
        return
    volume, position = map(int, chapter_match.groups())
    found = [item for item in chapters if (item[0]["volume"], item[0]["position"]) == (volume, position)]
    details = [s for s in metadata.sources if s.type == "nitean_chapter"]
    if len(found) != 1 or len(details) != 1 or not details[0].local_path or not details[0].url or not details[0].content_sha256:
        record["issues"].append(issue("source", "nitean_chapter_invalid", "单篇来源与卷次或序号不对应。", urgent=True))
        return
    row, chapter_path, checksum, document = found[0]
    if (metadata.id != nitean_chapter_id(row) or resolved_source_path(details[0]) != chapter_path.resolve()
            or details[0].content_sha256 != checksum or source_hashes.get(chapter_path.resolve()) != checksum
            or str(details[0].url) != row["url"] or details[0].locator != f"第 {volume} 卷 / 第 {position} 篇"
            or source.locator != f"目录第 {volume} 卷 / 第 {position} 篇"):
        record["issues"].append(issue("source", "nitean_chapter_invalid", "单篇链接、卷次或字段索引不符。", urgent=True))
        return
    data = nitean_evidence(row, document)
    record["evidence"]["nitean_chapter"] = {**data, "原文链接": row["url"]}
    if metadata.title != row["title"] or not json_block_preserved(record["markdown"], data):
        record["issues"].append(issue("source", "nitean_fields_changed", "草稿题名或出处字段与索引不符。", urgent=True))
    if not document["title_matches_catalogue"]:
        record["issues"].append(issue("source", "nitean_title_mismatch", "目录题名与单篇标题不完全一致，请核对版本与记录身份。", urgent=True))
    if not document["volume_matches_catalogue"]:
        record["issues"].append(issue("source", "nitean_volume_mismatch", "目录卷名与单篇面包屑不一致，请回查。", urgent=True))
    if not document["visible_paragraphs"]:
        record["issues"].append(issue("source", "nitean_paragraphs_not_found", "指定正文结构未检出段落；请回查原站，不据此断言正文不存在。"))
    if not document["printed_locators"]:
        record["issues"].append(issue("source", "nitean_print_locator_missing", "未从单篇页面提取到明确卷册页码；请回查原版或网页。"))
    if document["footnote_count"] != len(document["footnote_anchors"]):
        record["issues"].append(issue("source", "nitean_footnote_anchor_incomplete", "部分脚注未提取到可定位锚点，请回查原页。"))
    displayed = document["displayed_sequence"]
    if displayed and (displayed["position"] != row["ordinal"] + 1 or displayed["total"] != len(chapters) + 1):
        record["issues"].append(issue("source", "nitean_sequence_mismatch", "单篇页面显示次序与目录、序言计数不一致，请回查。"))


def heritage_2011_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    if not re.fullmatch(r'corpus_cn_ich_2011_(?:ext_)?\d{4}', metadata.id):
        return
    record['issues'].extend([
        issue('source', 'heritage_2011_project_scope', '这是名录项目，不是单篇故事、具体演述或采录记录。'),
        issue('coordinate', 'heritage_2011_reporting_area', '申报地区或单位不能直接当作故事采录地或发生地。'),
        issue('standard', 'heritage_2011_number_not_motif', '国家级项目编号是行政登记号，不是国际故事类型或母题标准码。')])
    if metadata.id.startswith('corpus_cn_ich_2011_ext_'):
        record['issues'].append(issue('source', 'heritage_2011_extension', '扩展项目沿用既有项目编号，申报地区应与原名录分别核对。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'heritage_2011_coordinate_unverified', '申报地不能直接用于单篇坐标。', urgent=True))
    sources = [s for s in metadata.sources if s.type == 'heritage_register_2011']
    if len(sources) != 1 or not sources[0].url or str(sources[0].url) != HERITAGE_2011_URL or not sources[0].local_path or not sources[0].content_sha256:
        record['issues'].append(issue('source', 'heritage_2011_source_invalid', '2011 年名录来源不唯一或不完整。', urgent=True))
        return
    source = sources[0]
    path = resolved_source_path(source)
    if source_hashes.get(path) != source.content_sha256:
        return
    if path not in cache:
        try:
            cache[path] = (heritage_2011_rows(path.read_bytes()), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[path] = (None, str(error))
    rows, error = cache[path]
    if rows is None:
        record['issues'].append(issue('source', 'heritage_2011_snapshot_invalid', f'2011 年名录无法核验：{error}', urgent=True))
        return
    found = [row for row in rows if heritage_2011_id(row) == metadata.id]
    if len(found) != 1:
        record['issues'].append(issue('source', 'heritage_2011_row_invalid', '卡片与名录行未唯一对应。', urgent=True))
        return
    row = found[0]
    data = heritage_2011_evidence(row)
    record['evidence']['heritage_2011'] = data
    locator = f"{row['kind']} / 民间文学 / 序号 {row['index']} / 项目编号 {row['project_number']}"
    if (source.locator != locator or metadata.title != f"2011 年国家级非遗{row['kind']} · {row['title']}"
            or not json_block_preserved(record['markdown'], data)):
        record['issues'].append(issue('source', 'heritage_2011_fields_changed', '草稿名录字段或定位符与原表不符。', urgent=True))
        return
    record['evidence']['heritage_project'] = {'year': 2011, 'kind': row['kind'], 'index': row['index'],
        'number': heritage_project_number(row['project_number']), 'raw_number': row['project_number'],
        'title': row['title'], 'area': row['area'], 'url': str(source.url),
        'locator': source.locator, 'snapshot_sha256': source.content_sha256}


def heritage_2006_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(r'corpus_cn_ich_2006_(\d{2})', metadata.id)
    if not match:
        return
    sources = [s for s in metadata.sources if s.type == 'heritage_register']
    if len(sources) != 1 or not sources[0].url or str(sources[0].url) != HERITAGE_2006_URL or not sources[0].local_path or not sources[0].content_sha256:
        record['issues'].append(issue('source', 'heritage_2006_source_invalid', '2006 年名录来源不唯一或不完整。', urgent=True))
        return
    source = sources[0]
    path = resolved_source_path(source)
    if source_hashes.get(path) != source.content_sha256:
        return
    if path not in cache:
        try:
            cache[path] = (heritage_2006_rows(path.read_bytes()), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[path] = (None, str(error))
    rows, error = cache[path]
    if rows is None:
        record['issues'].append(issue('source', 'heritage_2006_snapshot_invalid', f'2006 年名录无法核验：{error}', urgent=True))
        return
    found = [row for row in rows if row['index'] == int(match.group(1))]
    if len(found) != 1:
        record['issues'].append(issue('source', 'heritage_2006_row_invalid', '卡片与名录行未唯一对应。', urgent=True))
        return
    row = found[0]
    expected_locator = f"一、民间文学 / 序号 {row['index']} / 项目编号 {row['code']}"
    if (source.locator != expected_locator or metadata.title != f"国家级非遗名录 · {row['title']}"
            or '\n'.join(row['raw_lines']) not in record['markdown']):
        record['issues'].append(issue('source', 'heritage_2006_fields_changed', '草稿名录字段或定位符与原表不符。', urgent=True))
        return
    record['evidence']['heritage_project'] = {'year': 2006, 'kind': '新增项目', 'index': row['index'],
        'number': heritage_project_number(row['code']), 'raw_number': row['code'], 'title': row['title'],
        'area': '\n'.join(row['area_lines']), 'url': str(source.url), 'locator': source.locator,
        'snapshot_sha256': source.content_sha256}


def heritage_batch_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match = re.fullmatch(r'corpus_cn_ich_(2008|2014)_(?:ext_)?\d{4}', metadata.id)
    if not match:
        return
    year = int(match.group(1))
    record['issues'].extend([
        issue('source', 'heritage_batch_project_scope', '这是名录项目，不是单篇故事、具体演述或采录记录。'),
        issue('coordinate', 'heritage_batch_reporting_area', '申报地区或单位不能直接当作故事采录地或发生地。'),
        issue('standard', 'heritage_batch_number_not_motif', '国家级项目编号是行政登记号，不是国际故事类型或母题标准码。')])
    if '_ext_' in metadata.id:
        record['issues'].append(issue('source', 'heritage_batch_extension', '扩展项目沿用既有项目编号，申报地区应与原名录分别核对。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'heritage_batch_coordinate_unverified', '申报地不能直接用于单篇坐标。', urgent=True))
    sources = [s for s in metadata.sources if s.type == f'heritage_register_{year}']
    if len(sources) != 1 or not sources[0].url or str(sources[0].url) != HERITAGE_BATCHES[year]['url'] or not sources[0].local_path or not sources[0].content_sha256:
        record['issues'].append(issue('source', 'heritage_batch_source_invalid', f'{year} 年名录来源不唯一或不完整。', urgent=True))
        return
    source = sources[0]
    path = resolved_source_path(source)
    if source_hashes.get(path) != source.content_sha256:
        return
    key = (path, year)
    if key not in cache:
        try:
            cache[key] = (heritage_batch_rows(path.read_bytes(), year), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[key] = (None, str(error))
    rows, error = cache[key]
    if rows is None:
        record['issues'].append(issue('source', 'heritage_batch_snapshot_invalid', f'{year} 年名录无法核验：{error}', urgent=True))
        return
    found = [row for row in rows if heritage_batch_id(row) == metadata.id]
    if len(found) != 1:
        record['issues'].append(issue('source', 'heritage_batch_row_invalid', '卡片与名录行未唯一对应。', urgent=True))
        return
    row = found[0]
    data = heritage_batch_evidence(row)
    record['evidence']['heritage_batch'] = data
    locator = f"{row['kind']} / 民间文学 / 序号 {row['index']} / 项目编号 {row['project_number']}"
    if (source.locator != locator or metadata.title != f"{year} 年国家级非遗{row['kind']} · {row['title']}"
            or not json_block_preserved(record['markdown'], data)):
        record['issues'].append(issue('source', 'heritage_batch_fields_changed', '草稿名录字段或定位符与原表不符。', urgent=True))
        return
    if row['kind'] == '扩展项目':
        target = heritage_base_identity(row['index'], row['number'])
        if not any(relation.type == 'COMPARED_WITH' and relation.target == target for relation in metadata.relations):
            record['issues'].append(issue('source', 'heritage_batch_relation_missing', '扩展项目与原项目的待核对关联缺失。', urgent=True))
    record['evidence']['heritage_project'] = {'year': year, 'kind': row['kind'], 'index': row['index'],
        'number': row['number'], 'raw_number': row['project_number'], 'title': row['title'], 'area': row['area'],
        'url': str(source.url), 'locator': source.locator, 'snapshot_sha256': source.content_sha256}


def heritage_2021_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    if not re.fullmatch(r'corpus_cn_ich_2021_(?:ext_)?\d{4}', metadata.id):
        return
    record['issues'].extend([
        issue('source', 'heritage_2021_project_scope', '这是名录项目，不是单篇故事、具体演述或采录记录。'),
        issue('source', 'heritage_2021_pdf_fonts', '公报 PDF 部分字体未嵌入或缺 Unicode 映射；两页文字及版面已交叉检查，仍须人工回查原表。'),
        issue('coordinate', 'heritage_2021_reporting_area', '申报地区或单位不能直接当作故事采录地或发生地。'),
        issue('standard', 'heritage_2021_number_not_motif', '国家级项目编号是行政登记号，不是国际故事类型或母题标准码。')])
    if '_ext_' in metadata.id:
        record['issues'].append(issue('source', 'heritage_2021_extension', '扩展项目沿用既有项目编号，申报地区应与原名录分别核对。'))
    if metadata.spatial and (metadata.spatial.lat is not None or metadata.spatial.lng is not None):
        record['issues'].append(issue('coordinate', 'heritage_2021_coordinate_unverified', '申报地不能直接用于单篇坐标。', urgent=True))
    pdfs = [s for s in metadata.sources if s.type == 'heritage_register_2021_pdf']
    indexes = [s for s in metadata.sources if s.type == 'heritage_register_2021_index']
    if (len(pdfs) != 1 or len(indexes) != 1 or not pdfs[0].local_path or not indexes[0].local_path
            or not pdfs[0].url or not indexes[0].url or not pdfs[0].content_sha256 or not indexes[0].content_sha256):
        record['issues'].append(issue('source', 'heritage_2021_source_invalid', '公报 PDF 与字段索引来源不唯一或不完整。', urgent=True))
        return
    pdf, index = pdfs[0], indexes[0]
    pdf_path, index_path = resolved_source_path(pdf), resolved_source_path(index)
    if source_hashes.get(pdf_path) != pdf.content_sha256 or source_hashes.get(index_path) != index.content_sha256:
        return
    key = (pdf_path, index_path)
    if key not in cache:
        try:
            cache[key] = (load_heritage_2021(pdf_path, index_path), None)
        except (ValueError, OSError, KeyError, TypeError) as error:
            cache[key] = (None, str(error))
    data, error = cache[key]
    if data is None:
        record['issues'].append(issue('source', 'heritage_2021_index_invalid', f'公报 PDF 或字段索引无法核验：{error}', urgent=True))
        return
    found = [row for row in data['records'] if heritage_2021_id(row) == metadata.id]
    if len(found) != 1:
        record['issues'].append(issue('source', 'heritage_2021_row_invalid', '卡片与 PDF 表格行未唯一对应。', urgent=True))
        return
    row = found[0]
    fields = heritage_2021_evidence(row)
    record['evidence']['heritage_2021'] = fields
    locator = f"PDF 第 {row['pdf_page']} 页 / 公报第 {row['printed_page']} 页 / {row['kind']} / 序号 {row['index']} / {row['project_number']}"
    url = f"{HERITAGE_2021_URL}#page={row['pdf_page']}"
    if (str(pdf.url) != url or str(index.url) != url or pdf.locator != locator or index.locator != locator
            or metadata.title != f"2021 年国家级非遗{row['kind']} · {row['title']}"
            or not json_block_preserved(record['markdown'], fields)):
        record['issues'].append(issue('source', 'heritage_2021_fields_changed', '草稿名录字段、页码或定位符与索引不符。', urgent=True))
        return
    if row['kind'] == '扩展项目':
        target = heritage_base_identity(row['index'], row['number'])
        if not any(rel.type == 'COMPARED_WITH' and rel.target == target for rel in metadata.relations):
            record['issues'].append(issue('source', 'heritage_2021_relation_missing', '扩展项目与原项目的待核对关联缺失。', urgent=True))
    record['evidence']['heritage_project'] = {'year': 2021, 'kind': row['kind'], 'index': row['index'],
        'number': row['number'], 'raw_number': row['project_number'], 'title': row['title'], 'area': row['area'],
        'url': str(pdf.url), 'locator': locator, 'snapshot_sha256': pdf.content_sha256}


def reviewed_heritage_projects(vault: Path) -> tuple[list[dict], dict]:
    records, problems, source_hashes = [], {}, {}
    caches = ({}, {}, {}, {})
    for identifier, card in load_vault(vault).items():
        metadata = card.metadata
        if not re.fullmatch(r'corpus_cn_ich_(?:2006|2008|2011|2014|2021)_(?:ext_)?\d{2,4}', identifier):
            continue
        if not metadata.audit.reviewed_by_human or metadata.audit.is_sample:
            continue
        for source in metadata.sources:
            if source.local_path and source.content_sha256:
                path = resolved_source_path(source)
                if path not in source_hashes:
                    source_hashes[path] = sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        record = {'id': identifier, 'markdown': card.markdown.strip(), 'issues': [], 'evidence': {}}
        heritage_2006_review(record, metadata, source_hashes, caches[0])
        heritage_2011_review(record, metadata, source_hashes, caches[1])
        heritage_batch_review(record, metadata, source_hashes, caches[2])
        heritage_2021_review(record, metadata, source_hashes, caches[3])
        if record['evidence'].get('heritage_project'):
            records.append(record)
        else:
            problems[identifier] = '已复核项目的原表或字段索引无法重新核验。'
    return records, problems


def compare_heritage_projects(records: list[dict], reviewed: list[dict], problems: dict) -> None:
    groups = defaultdict(list)
    pending_ids = {record['id'] for record in records}
    for record in records + reviewed:
        item = record['evidence'].get('heritage_project')
        if item:
            groups[(item['index'], item['number'])].append((record, item))
    for record in records:
        missing = [identifier for identifier in record.get('dependencies', []) if identifier in problems]
        if missing:
            record['issues'].append(issue('source', 'heritage_reviewed_target_invalid',
                '已复核的关联项目来源无法重新核验：' + '、'.join(missing), urgent=True))
    for items in groups.values():
        if len(items) < 2:
            continue
        for record, item in items:
            if record['id'] not in pending_ids:
                continue
            others = [{'id': other['id'], 'availability': 'pending' if other['id'] in pending_ids else 'reviewed', **details}
                      for other, details in items if other['id'] != record['id']]
            record['evidence']['heritage_comparisons'] = sorted(others, key=lambda x: (x['year'], x['kind'], x['id']))
            record['issues'].append(issue('source', 'heritage_cross_year_comparison',
                '其他年度名录有相同序号和行政项目编号；申报地区、名称和项目范围须分别核对，不表示同一篇故事。'))
            title = re.sub(r'\s+', '', item['title'])
            if any(re.sub(r'\s+', '', other['title']) != title for other in others):
                record['issues'].append(issue('source', 'heritage_cross_year_title_variant',
                    '相同项目编号的名称在其他年度不完全一致，可能涉及名称或扩展范围变化，请对照原表。'))


def base_record(path: Path, vault: Path, collection: str) -> tuple[dict, object]:
    raw = path.read_bytes()
    metadata, body = parse_card(raw.decode("utf-8-sig").replace("\r\n", "\n"))
    if metadata.id != path.stem or metadata.audit.reviewed_by_human or metadata.audit.is_sample:
        raise ValueError(f"复核清单只接收与文件名相符的待审卡片。{path}")
    relative = path.relative_to(vault).as_posix()
    spatial = metadata.spatial.model_dump(mode="json") if metadata.spatial else None
    record = {
        "id": metadata.id, "title": metadata.title, "collection": collection,
        "batch": path.parent.name, "card_path": f"vault/{relative}",
        "card_sha256": sha256(raw).hexdigest(), "node_type": metadata.node_type,
        "genre": metadata.genre,
        "sources": [source.model_dump(mode="json") for source in metadata.sources],
        "spatial": spatial, "temporal": metadata.temporal.model_dump(mode="json") if metadata.temporal else None,
        "standards": metadata.standards.model_dump(mode="json"), "markdown": body.strip(),
        "dependencies": sorted({relation.target for relation in metadata.relations}
                               | {mechanism.target_id for mechanism in metadata.mechanisms}),
        "issues": [], "evidence": {},
    }
    if not metadata.sources:
        record["issues"].append(issue("source", "source_missing", "卡片没有登记出处。", urgent=True))
    return record, metadata


def scottish_records(vault: Path, tables: Path, schema_path: Path, maps: Path,
                     wikidata_path: Path = DEFAULT_WIKIDATA) -> tuple[list[dict], list[dict]]:
    schema = schema_path.read_text(encoding="utf-8-sig")
    digest = sha256(tables.read_bytes()).hexdigest()
    with ZipFile(tables) as archive:
        accused_rows = _archive_table(archive, schema, "Accused")
        cases = _archive_table(archive, schema, "Case")
        trials = _archive_table(archive, schema, "Trial")
        references = _archive_table(archive, schema, "Reference")
        parishes = {row["Parishref"]: row for row in _archive_table(archive, schema, "Ref_Parish")}
    accused_by_id = {_identifier(row["AccusedRef"]): row for row in accused_rows}
    case_by_id = {_identifier(row["CaseRef"]): row for row in cases}
    cases_by_accused, trials_by_case, refs_by_case = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in cases:
        cases_by_accused[row["AccusedRef"]].append(row)
    for row in trials:
        trials_by_case[row["CaseRef"]].append(row)
    for row in references:
        refs_by_case[row["CaseRef"]].append(row)
    case_ids = {row["CaseRef"] for row in cases}
    unmatched = [selected(row, ("ReferenceRef", "CaseRef", "SourceRef", "Reference", "Notes"))
                 for row in references if row["CaseRef"] not in case_ids]
    residence_index = _residence_index(maps)
    identity_index = ScottishIdentityIndex(wikidata_path, maps) if wikidata_path.is_file() else None
    snapshot_digests = {}
    residences = defaultdict(list)
    with ZipFile(maps) as archive:
        for row in csv.DictReader(StringIO(archive.read(RESIDENCES).decode("utf-8-sig"), newline="")):
            residences[normalized_text(row["Residence"])].append(row)
    transform = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True).transform
    folder = vault / "00_drafts" / "scottish_witchcraft"
    records = []
    for path in sorted(folder.glob("*.md")):
        record, metadata = base_record(path, vault, "scottish")
        records.append(record)
        if metadata.id == "corpus_scottish_witchcraft_survey":
            record["issues"].append(issue("standard", "ocm_batch_assignment", "OCM 754 由项目按调查主题批量标引，须核对适用范围。"))
            continue
        accused = accused_by_id.get(metadata.id, {})
        separate = case_by_id.get(metadata.id)
        case_rows = cases_by_accused[accused["AccusedRef"]] if accused else ([separate] if separate else [])
        if not accused and not separate:
            record["issues"].append(issue("source", "unmatched_record", "档号无法与原始表逐项匹配。", urgent=True))
            continue
        all_refs = [reference for case in case_rows for reference in refs_by_case[case["CaseRef"]]]
        all_trials = [trial for case in case_rows for trial in trials_by_case[case["CaseRef"]]]
        record["evidence"] = {
            "WDB_Accused": selected(accused, ("AccusedRef", "FirstName", "LastName", "Sex", "Res_settlement",
                "Res_parish", "Res_county", "Res_NGR_Letters", "Res_NGR_Easting", "Res_NGR_Northing", "Notes")),
            "WDB_Case": [selected(row, ("CaseRef", "AccusedRef", "NamedIndividual", "CaseStart_date", "Case_date",
                                        "CaseCommonName", "Suspects_text", "Other", "Charnotes")) for row in case_rows],
            "WDB_Trial": [selected(row, ("Trialref", "CaseRef", "TrialDate", "TrialPlace", "Verdict",
                                         "Sentence", "TrialNotes")) for row in all_trials],
            "WDB_Reference": [selected(row, ("ReferenceRef", "CaseRef", "SourceRef", "Reference", "Notes"))
                              for row in all_refs],
        }
        if metadata.sources and metadata.sources[0].content_sha256 != digest:
            record["issues"].append(issue("source", "source_hash_mismatch", "草稿来源哈希与原始数据表不一致。", urgent=True))
        for source in metadata.sources:
            if not source.local_path or not source.content_sha256:
                continue
            snapshot = Path(source.local_path)
            if not snapshot.is_absolute():
                snapshot = PROJECT_ROOT / snapshot
            snapshot = snapshot.resolve()
            if snapshot not in snapshot_digests:
                snapshot_digests[snapshot] = sha256(snapshot.read_bytes()).hexdigest() if snapshot.is_file() else None
            current_digest = snapshot_digests[snapshot]
            if current_digest is None:
                record["issues"].append(issue("source", "source_snapshot_missing", "卡片登记的本地来源快照不存在。", urgent=True))
                break
            if current_digest != source.content_sha256:
                record["issues"].append(issue("source", "source_hash_mismatch", "卡片登记的本地来源快照与内容哈希不一致。", urgent=True))
                break
        expected_locator = (f"WDB_Accused · {accused['AccusedRef']}" if accused
                            else f"WDB_Case · {separate['CaseRef']}")
        if not metadata.sources or metadata.sources[0].locator != expected_locator:
            record["issues"].append(issue("source", "source_locator_mismatch", "草稿出处定位与原始档号不一致。", urgent=True))
        if not case_rows:
            record["issues"].append(issue("source", "no_linked_case", "被告表没有可关联的案件登记。", urgent=True))
        elif not all_refs:
            record["issues"].append(issue("source", "no_archival_reference", "关联案件没有可用的史料索引行。", urgent=True))
        if any(not row["SourceRef"] or not row["Reference"] for row in all_refs):
            record["issues"].append(issue("source", "reference_incomplete", "部分史料索引缺少来源名称或卷页，请检查原表备注。"))
        expected_ref_locators = {f"WDB_Reference · {row['ReferenceRef']} · 案件 {row['CaseRef']}" for row in all_refs}
        recorded = {source.locator for source in metadata.sources if source.type == "historical_reference"}
        if not expected_ref_locators.issubset(recorded):
            record["issues"].append(issue("source", "reference_missing_from_card", "部分史料索引尚未写入草稿。", urgent=True))
        indexed_refs = {source.locator: source for source in metadata.sources if source.type == "historical_reference"}
        for row in all_refs:
            expected_ref = historical_reference(row, digest)
            saved = indexed_refs.get(expected_ref["locator"])
            if saved and (saved.citation != expected_ref["citation"] or saved.content_sha256 != digest):
                record["issues"].append(issue("source", "reference_content_mismatch", "草稿中的史料索引内容或数据哈希与原表不一致。", urgent=True))
                break

        expected, method = _choose_location(accused, parishes.get(accused.get("Res_parish"), {}), residence_index, transform)
        spatial = record["spatial"]
        record["evidence"]["location_method"] = method or "原始数据没有可用坐标"
        record["evidence"]["original_generated_spatial"] = expected
        record["evidence"]["parish"] = selected(parishes.get(accused.get("Res_parish"), {}),
            ("Parishref", "Parish_Name", "Parish_County", "Parish_NGR_Letters", "Parish_NGR_Easting", "Parish_NGR_Northing"))
        identity = None
        if identity_index is None and any(source.type == "external_catalogue" and source.locator
                                          and source.locator.startswith("P4478 · ") for source in metadata.sources):
            record["issues"].append(issue("source", "wikidata_snapshot_missing",
                "未找到用于档号对照的 Wikidata 快照，暂时无法复算。", urgent=True))
        if identity_index is not None and accused:
            original_coords = (expected["lat"], expected["lng"]) if expected["lat"] is not None else None
            identity = identity_index.lookup(accused["AccusedRef"], original_coords)
            record["evidence"]["wikidata_identity"] = identity
            if identity["ambiguous_identity"]:
                record["issues"].append(issue("source", "wikidata_identity_ambiguous",
                    "Wikidata 实体与调查库档号不是一对一，请核对合并或重复记录。", urgent=True))
            if identity["coordinate_conflict"]:
                minimum = min(candidate["distance_km"] for candidate in identity["map_candidates"])
                record["issues"].append(issue("coordinate", "coordinate_cross_source_disagreement",
                    f"原始生成坐标与同档号的地图导出点均相距超过 {DISTANCE_REVIEW_KM:g} 公里（最近约 {minimum:g} 公里），须核对地点范围。", urgent=True))
            elif expected["lat"] is None and identity["map_candidates"]:
                record["issues"].append(issue("coordinate", "identity_linked_candidate_unverified",
                    "同档号的地图导出提供候选位置；尚未确定与原始登记地名的关系，未自动落图。"))
            recorded_identity = {(str(source.url) if source.url else "", source.locator) for source in metadata.sources}
            if any((entity["url"], f"P4478 · {accused['AccusedRef']}") not in recorded_identity
                   for entity in identity["entities"]):
                record["issues"].append(issue("source", "wikidata_identity_not_in_card",
                    "找到同档号的 Wikidata 实体，尚未写入卡片出处。"))
            recorded_wikidata = [source for source in metadata.sources if source.type == "external_catalogue"
                                 and source.locator == f"P4478 · {accused['AccusedRef']}"]
            if any(source.content_sha256 != identity_index.snapshot_sha256 for source in recorded_wikidata):
                record["issues"].append(issue("source", "wikidata_snapshot_mismatch",
                    "卡片中的 Wikidata 来源快照与当前对照快照不一致。", urgent=True))
            if any(str(source.url) not in {entity["url"] for entity in identity["entities"]}
                   for source in recorded_wikidata if source.url):
                record["issues"].append(issue("source", "wikidata_identity_changed",
                    "卡片中的 Wikidata 实体在当前档号对照中不再出现，请核对变更。", urgent=True))
        if not spatial or spatial["lat"] is None:
            if identity and identity["coordinate_conflict"]:
                record["issues"].append(issue("coordinate", "coordinate_conflict_withheld", "坐标存在来源差异，原草稿参考点和地图候选点均留在对照资料中。"))
            else:
                record["issues"].append(issue("coordinate", "coordinate_missing", "暂无经纬度，保留原表地名供复核。"))
        elif expected["lat"] is None or abs(spatial["lat"] - expected["lat"]) > 0.00001 or abs(spatial["lng"] - expected["lng"]) > 0.00001:
            record["issues"].append(issue("coordinate", "coordinate_mismatch", "草稿坐标与本地来源重新计算结果不一致。", urgent=True))
        if method and method.startswith("爱丁堡") and expected["lat"] is not None:
            record["issues"].append(issue("coordinate", "name_only_location", "原生成点按同名住地唯一坐标匹配，需结合郡和教区确认。"))
            names = {
                normalized_text(f"{accused.get('FirstName', '')} {accused.get('LastName', '')}"),
                normalized_text(f"{accused.get('M_Firstname', '')} {accused.get('M_Surname', '')}"),
            } - {""}
            matches = [row for row in residences[normalized_text(accused.get("Res_settlement", ""))]
                       if normalized_text(row["Name"]) in names]
            record["evidence"]["matching_map_rows"] = [selected(row, ("Name", "Residence", "Wikidata Page",
                "Latitude", "Longitude", "Gender")) for row in matches]
            if not matches:
                record["issues"].append(issue("coordinate", "person_not_in_map_export",
                    "地图导出中没有姓名与住地同时匹配的行；可另查看下方档号对照。"))
        elif method and method.startswith("教区") and expected["lat"] is not None:
            record["issues"].append(issue("coordinate", "parish_location", "原生成点采用教区参考点，需确认与案件位置的关系。"))
        grid_values = [accused.get(field, "") for field in ("Res_NGR_Letters", "Res_NGR_Easting", "Res_NGR_Northing")]
        if any(grid_values) and not all(grid_values):
            record["issues"].append(issue("coordinate", "incomplete_grid", "原表国家格网缺少字母、东距或北距。"))
        record["issues"].append(issue("standard", "ocm_batch_assignment", "OCM 754 由项目按调查主题批量标引，须核对本条是否适用。"))
        if metadata.standards.ocm_codes != ["754"]:
            record["issues"].append(issue("standard", "ocm_changed", "草稿 OCM 码与原批次主题标引不一致。", urgent=True))
    return records, unmatched


def catalogue_labels(path: Path) -> dict[str, list[str]]:
    labels = defaultdict(set)
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    for paragraph in soup.find_all("p"):
        match = re.match(r"^([a-z][0-9]+[a-z0-9]*)\.\s+(.+)$", paragraph.get_text(" ", strip=True), re.I)
        if match:
            labels[match[1].lower()].add(match[2].split(". ", 1)[0].strip().rstrip("."))
    return {code: sorted(values) for code, values in labels.items()}


def berezkin_records(vault: Path, study_path: Path, catalogue: Path, table_path: Path) -> list[dict]:
    study = read_study(study_path)
    coordinate_notes = region_crosschecks(study)
    labels = catalogue_labels(catalogue)
    table = load_code_table(table_path)
    note_document = yaml.safe_load(REVIEW_NOTES.read_text(encoding="utf-8"))
    if not isinstance(note_document, dict) or note_document.get("version") != 1 or not isinstance(note_document.get("notes"), dict):
        raise ValueError("母题复核记录格式不正确。")
    review_notes = note_document["notes"]
    folder = vault / "00_drafts" / "berezkin_distribution"
    paths = sorted(folder.glob("*.md"))
    paths += [vault / "00_drafts" / "regional_sources" / f"{node_id}.md" for node_id in REGIONAL_HUBS.values()]
    records = []
    for path in paths:
        if not path.exists():
            continue
        record, metadata = base_record(path, vault, "berezkin")
        records.append(record)
        if metadata.id.startswith("corpus_berezkin_region_"):
            area_id = int(metadata.id.rsplit("_", 1)[-1])
            expected = study.regions.get(area_id)
            record["evidence"] = {"study_region_code": area_id,
                "study_region": expected.model_dump(mode="json") if expected else None}
            if area_id in coordinate_notes:
                note = coordinate_notes[area_id]
                record["evidence"]["coordinate_crosschecks"] = [note]
                record["evidence"]["coordinate_scope"] = "论文附件地区参考点存疑；原值见原始字段，地图点位待核"
                record["issues"].append(issue("coordinate", "region_coordinate_questionable",
                    f"地区 {area_id}（{note['name']}）原参考点 {note['lat']}, {note['lng']}：{note['finding']}", urgent=True))
            if expected is None or metadata.spatial is None:
                record["issues"].append(issue("coordinate", "region_mismatch", "草稿地区坐标与研究附件不一致。", urgent=True))
            elif (area_id in coordinate_notes and metadata.spatial.lat is None and metadata.spatial.lng is None
                  and metadata.spatial.model_copy(update={"lat": expected.lat, "lng": expected.lng}) == expected):
                pass  # Deliberately withhold a questionable point while preserving the source value in evidence.
            elif metadata.spatial != expected:
                record["issues"].append(issue("coordinate", "region_mismatch", "草稿地区坐标与研究附件不一致，需核对修改依据。", urgent=True))
            else:
                record["evidence"].setdefault("coordinate_scope", "论文作者为文化分析区指定的参考点")
            continue
        code = metadata.id.removeprefix("index_berezkin_")
        motif = study.motifs.get(code)
        if motif is None:
            record["issues"].append(issue("source", "motif_missing", "原研究附件中找不到母题编号。", urgent=True))
            continue
        region_counts = Counter(motif.areas)
        unknown = sorted(set(motif.areas) - study.regions.keys())
        duplicates = sorted(area for area, count in region_counts.items() if count > 1)
        record["evidence"] = {"study_code": code, "study_label": motif.label,
            "study_area_ids": list(motif.areas), "catalogue_labels": labels.get(code, []),
            "known_area_names": [study.regions[area].location_name for area in sorted(set(motif.areas) & study.regions.keys())]}
        if code in review_notes:
            record["evidence"]["catalogue_crosscheck"] = {"checked_at": note_document["checked_at"], **review_notes[code]}
        attached_study = [source for source in metadata.sources if source.type == "research_dataset" and source.content_sha256]
        if any(source.content_sha256 != study.digest for source in attached_study):
            record["issues"].append(issue("source", "study_hash_mismatch", "草稿来源哈希与研究附件不一致。", urgent=True))
        if unknown:
            record["issues"].append(issue("coordinate", "unknown_area_ids", f"研究表地区编号 {unknown} 缺少对应地区定义。", urgent=True))
        affected = sorted(set(motif.areas) & coordinate_notes.keys())
        if affected:
            record["evidence"]["coordinate_crosschecks"] = [coordinate_notes[area] for area in affected]
            area_labels = "、".join(f"{area} {coordinate_notes[area]['name']}" for area in affected)
            record["issues"].append(issue("coordinate", "linked_region_coordinate_questionable",
                f"关联地区 {area_labels} 的论文参考点存疑，原值和对照依据见下方。", urgent=True))
        if duplicates:
            record["issues"].append(issue("coordinate", "duplicate_area_ids", f"研究表地区编号 {duplicates} 重复，图谱关系已去重。"))
        if len(labels.get(code, [])) != 1:
            record["issues"].append(issue("standard", "ambiguous_code", f"现行目录中该编号对应 {len(labels.get(code, []))} 个不同标题。", urgent=True))
        if (("berezkin_codes", code) not in table or metadata.standards.berezkin_codes != [code]):
            record["issues"].append(issue("standard", "code_unmatched", "研究原编号未唯一匹配本地码表，标准码留空或需要核对。", urgent=True))
        if code == "f73b":
            record["issues"].append(issue("standard", "label_language", "研究表为英文题名，当前目录题名为俄文，需对照条目含义。"))
        if not any(source.type in {"research_dataset", "official_standard"} for source in metadata.sources):
            record["issues"].append(issue("source", "catalogue_source_missing", "缺少研究数据或原目录来源。", urgent=True))
    return records


def nichibun_records(vault: Path) -> list[dict]:
    records = []
    folders = sorted((vault / "00_drafts").glob("nichibun_*"))
    paths = sorted(path for folder in folders if folder.is_dir() for path in folder.glob("*.md"))
    for path in paths:
        record, metadata = base_record(path, vault, "nichibun")
        records.append(record)
        if metadata.node_type != "case":
            continue
        if metadata.spatial and metadata.spatial.lat is not None:
            record["issues"].append(issue("coordinate", "city_reference", "地图采用市镇参考点，具体采录位置待核。"))
        else:
            record["issues"].append(issue("coordinate", "coordinate_missing", "馆藏卡提供地名，经纬度尚未登记。"))
        if metadata.genre == "unclassified":
            record["issues"].append(issue("classification", "genre_unclassified", "尚未确认体裁，请阅读所引资料后选择。"))
        source = metadata.sources[0] if metadata.sources else None
        snapshot = Path(source.local_path) if source and source.local_path else None
        if snapshot and not snapshot.is_absolute():
            snapshot = PROJECT_ROOT / snapshot
        if not snapshot or not snapshot.is_file():
            record["issues"].append(issue("source", "source_snapshot_missing", "本地馆藏卡快照不存在，请通过出处链接核对。", urgent=True))
            continue
        try:
            fields, digest = card_fields(snapshot)
        except (UnicodeError, ValueError) as error:
            record["issues"].append(issue("source", "source_snapshot_invalid", f"馆藏卡快照无法读取：{error}", urgent=True))
            continue
        record["evidence"] = {"catalogue_fields": fields, "snapshot_sha256": digest}
        if source.content_sha256 != digest:
            record["issues"].append(issue("source", "source_hash_mismatch", "馆藏卡快照与草稿所记哈希不一致。", urgent=True))
    return records


def duchas_records(vault: Path) -> list[dict]:
    records = []
    folders = sorted((vault / "00_drafts").glob("duchas_*")) + [vault / "00_drafts/regional_sources"]
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            if folder.name == "regional_sources" and not path.stem.startswith("case_duchas_"):
                continue
            record, metadata = base_record(path, vault, "duchas")
            story_ids = duchas_cited_story_ids(metadata)
            if folder.name == "regional_sources" and len(story_ids) != 1:
                continue
            records.append(record)
            if metadata.node_type != "case":
                continue
            if len(story_ids) != 1:
                record["issues"].append(issue("source", "story_id_ambiguous", "无法唯一确定此卡引用的馆藏故事编号。", urgent=True))
            story_id = next(iter(story_ids)) if len(story_ids) == 1 else None
            if metadata.genre == "unclassified":
                record["issues"].append(issue("classification", "genre_unclassified", "尚未确认体裁，请阅读所引资料后选择。"))
            if metadata.temporal and metadata.temporal.uncertainty_note and "无法按年月日解析" in metadata.temporal.uncertainty_note:
                record["issues"].append(issue("source", "story_date_invalid", "故事 XML 的日期无法解析，需核对原值。", urgent=True))
            if metadata.spatial and metadata.spatial.lat is not None:
                record["issues"].append(issue("coordinate", "school_reference", "坐标是学校登记地点的参考点，故事地点待核。"))
            else:
                record["issues"].append(issue("coordinate", "coordinate_missing", "学校登记地点暂无可用坐标。"))
            xml_sources = [source for source in metadata.sources if source.local_path and source.content_sha256]
            evidence = {"coordinate_scope": "学校登记地点参考，并非故事发生地点"}
            for source in xml_sources:
                snapshot = Path(source.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                if not snapshot.is_file():
                    record["issues"].append(issue("source", "source_snapshot_missing", "本地馆藏 XML 快照不存在，请通过出处链接核对。", urgent=True))
                    continue
                source_url = urlsplit(str(source.url)) if source.url else None
                xml_match = (re.fullmatch(r"/xml/cbes/(\d+)(?:/(\d+))?(?:/(\d+))?/?", source_url.path)
                             if source_url and source_url.hostname in {"duchas.ie", "www.duchas.ie"} else None)
                if xml_match and xml_match[3]:
                    tag, identifier = "lStory", xml_match[3]
                elif xml_match and xml_match[2]:
                    tag, identifier = "pPage", xml_match[2]
                elif xml_match:
                    tag, identifier = "lChapter", xml_match[1]
                else:
                    digest = sha256(snapshot.read_bytes()).hexdigest()
                    if digest != source.content_sha256:
                        record["issues"].append(issue("source", "source_hash_mismatch", "本地补充来源与草稿所记哈希不一致。", urgent=True))
                    evidence.setdefault("other_local_sources", []).append({"path": source.local_path, "sha256": digest})
                    continue
                try:
                    root, digest = xml_record(snapshot, tag, identifier)
                except (OSError, ValueError) as error:
                    record["issues"].append(issue("source", "source_snapshot_invalid", f"馆藏 XML 无法读取：{error}", urgent=True))
                    continue
                if digest != source.content_sha256:
                    record["issues"].append(issue("source", "source_hash_mismatch", "馆藏 XML 与草稿所记哈希不一致。", urgent=True))
                if tag == "lChapter":
                    location = root.find("schoolLocation")
                    if location is not None and (location.get("lat") or location.get("lon")) and school_coordinates(location) is None:
                        record["issues"].append(issue("coordinate", "school_coordinates_invalid",
                            "学校 XML 的坐标不完整、无效或超出爱尔兰区域，已留空待核。", urgent=True))
                entry = {"entryID": root.get("entryID"), "fields": {
                    item.tag: item.attrib for item in root if item.tag in {"chapter", "title", "pageNumber", "schoolName", "schoolLocation"}
                }}
                if tag == "lStory":
                    entry["pages"] = [item.attrib for item in root.findall("page")]
                    entry["collector"] = [item.attrib for item in root.findall("collector/persName")]
                    entry["informant"] = [item.attrib for item in root.findall("informant/persName")]
                if tag == "pPage":
                    if story_id and not any(item.get("default") == story_id for item in root.findall("story")):
                        record["issues"].append(issue("source", "page_story_mismatch", "馆藏页与故事编号不匹配。", urgent=True))
                    evidence.setdefault("page_snapshots", []).append(entry)
                else:
                    evidence[tag] = entry
            expected_pages = {item.get("default") for item in evidence.get("lStory", {}).get("pages", []) if item.get("default")}
            saved_pages = {item["entryID"] for item in evidence.get("page_snapshots", [])}
            missing_pages = sorted(expected_pages - saved_pages)
            if missing_pages:
                evidence["missing_page_ids"] = missing_pages
                record["issues"].append(issue("source", "story_pages_not_cached",
                    f"故事还有 {len(missing_pages)} 个馆藏页未登记为本地来源，请核对原页。", urgent=True))
            record["evidence"] = evidence
    return records


def other_records(vault: Path, table_path: Path) -> list[dict]:
    table = load_code_table(table_path)
    records = []
    zibuyu_hashes, zibuyu_cache = {}, {}
    inputs = [(collection, sorted((vault / "00_drafts" / folder).glob("*.md")))
              for folder, collection in (("regional_sources", "regional"), ("research_report", "research"))]
    catalogue = [vault / card.source_path for card in load_vault(vault).values()
                 if not (card.metadata.audit.reviewed_by_human or card.metadata.audit.is_sample)]
    inputs.append(("research", catalogue))
    for collection, paths in inputs:
        for path in paths:
            if path.stem in REGIONAL_HUBS.values():
                continue
            record, metadata = base_record(path, vault, collection)
            if collection == "regional" and path.stem.startswith("case_duchas_") and len(duchas_cited_story_ids(metadata)) == 1:
                continue
            if path.relative_to(vault).parts[0] != "00_drafts":
                record["batch"] = "research_report"
            records.append(record)
            if metadata.sources and not any(source.locator for source in metadata.sources):
                record["issues"].append(issue("source", "source_locator_missing", "未单独登记来源定位符，可核对书目中的卷页或记录号。"))
            if metadata.node_type == "case" and (metadata.spatial is None or metadata.spatial.lat is None):
                record["issues"].append(issue("coordinate", "coordinate_missing", "暂无经纬度，按原资料中的地点信息复核。"))
            missing = [f"{system} {code}" for (system, key), code in standard_codes(metadata.standards).items()
                       if (system, key) not in table]
            if missing:
                record["issues"].append(issue("standard", "code_unmatched", f"本地码表未找到：{'、'.join(missing)}。", urgent=True))
            for source in metadata.sources:
                if not source.local_path or not source.content_sha256:
                    continue
                snapshot = Path(source.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if not snapshot.is_file():
                    record["issues"].append(issue("source", "source_snapshot_missing", "所记录的本地来源快照不存在。"))
                    zibuyu_hashes[snapshot] = None
                else:
                    if snapshot not in zibuyu_hashes:
                        zibuyu_hashes[snapshot] = sha256(snapshot.read_bytes()).hexdigest()
                    if zibuyu_hashes[snapshot] != source.content_sha256:
                        record["issues"].append(issue("source", "source_hash_mismatch", "来源快照与所记哈希不一致。", urgent=True))
            record["evidence"] = {"record_type": metadata.node_type}
            zibuyu_review(record, metadata, zibuyu_hashes, zibuyu_cache)
    return records


def pangloss_supplement_review(record: dict, metadata, source_hashes: dict, cache: dict, *, kind: str,
                               row: dict, corpus: Path, initial: Path) -> tuple[dict, dict] | None:
    config = PANGLOSS_SUPPLEMENT_CONFIG[kind]
    types = tuple(f"{config['source']}_supplement_{suffix}" for suffix in ('detail','selection','manifest'))
    sources = [[source for source in metadata.sources if source.type == typ] for typ in types]
    if all(not values for values in sources) and PANGLOSS_SUPPLEMENT_MARKER not in record['markdown']:
        return None
    try:
        if any(len(values) != 1 for values in sources) or PANGLOSS_SUPPLEMENT_MARKER not in record['markdown']:
            raise ValueError('补充详情、选取清单、清单哈希或正文标记不完整')
        detail, selection, manifest = (values[0] for values in sources)
        if any(not source.local_path or not source.content_sha256 for source in (detail,selection,manifest)):
            raise ValueError('补充来源缺少路径或哈希')
        number = row['id']
        if (str(detail.url) != row['url'] or detail.doi != row['doi'].removeprefix('https://doi.org/')
                or detail.locator != f'录音 {number} / 补充详情' or str(selection.url) != config['url']
                or selection.locator != f'录音 {number} / 补充选取' or str(manifest.url) != config['url']
                or manifest.locator != f'录音 {number} / 补充清单'):
            raise ValueError('补充来源链接、DOI 或定位符不符')
        paths = [Path(source.local_path) for source in (detail,selection,manifest)]
        paths = [(path if path.is_absolute() else PROJECT_ROOT/path).resolve() for path in paths]
        if any(source_hashes.get(path) != source.content_sha256 for path,source in zip(paths,(detail,selection,manifest),strict=True)):
            return None  # General source checks already record missing or changed files.
        detail_path, selection_path, manifest_path = paths
        folder = manifest_path.parent
        if selection_path != folder/'selection.json' or detail_path != folder/'records'/number/'page.html':
            raise ValueError('补充详情路径与清单目录不符')
        key = (kind,folder,corpus,initial)
        if key not in cache:
            supplement_selection = pangloss_json_object(selection_path)
            catalog, group = validate_pangloss_supplement(supplement_selection,corpus,initial,kind)
            _, loaded, details = load_pangloss_snapshots(folder,corpus,selection_path,
                corpus_name=config['name'],corpus_url=config['url'])
            if loaded != supplement_selection or set(details) != set(group['ids']):
                raise ValueError('补充详情清单与选取范围不符')
            cache[key] = (catalog,supplement_selection,group,details)
        catalog, supplement_selection, group, details = cache[key]
        if number not in details or catalog.get(number) != row:
            raise ValueError('该录音不在补充选取中')
        fields = details[number]
        expected = japhug_evidence(row,fields,group)
        if not json_block_preserved(record['markdown'],{'详情补充':expected}):
            raise ValueError('补充详情正文与来源快照不符')
        originals = [source for source in metadata.sources if source.type == f"{config['source']}_original"]
        if len(originals) != 1 or originals[0].citation != PANGLOSS_SUPPLEMENT_CITATION:
            raise ValueError('原始详情链接的历史状态未正确保留')
        record['evidence']['pangloss_supplement'] = {'selection_sha256':selection.content_sha256,
            'manifest_sha256':manifest.content_sha256,'detail_sha256':detail.content_sha256,
            'prior_card_sha256':supplement_selection['card_sha256'][number],
            'scope':'后续补充馆方详情；采集前草稿哈希及原目录字段保留'}
        return fields,group
    except (ValueError,KeyError,OSError,TypeError) as error:
        record['issues'].append(issue('source',f'{kind}_supplement_invalid',f'馆方详情补充无法核验：{error}',urgent=True))
        return None


def japhug_review(record: dict, metadata, source_hashes: dict, catalogues: dict, selections: dict, supplements: dict) -> None:
    match = re.fullmatch(r"case_cn_japhug_(\d{7})", metadata.id)
    if not match and metadata.id != JAPHUG_ROOT:
        return
    record['evidence']['japhug_context'] = {
        'url': 'https://langsci-press.org/index.php/LangSci-Press/catalog/book/549',
        'citation': 'Guillaume Jacques, A grammar of Japhug (second edition, 2025), §1.2.',
        'note': '研究者区分自然演述与根据中文故事书翻译的录音；应逐条核对版本，不能仅凭目录题名判断来源。'}
    if match and match.group(1) == '0003371':
        record['evidence']['japhug_fox_reference'] = {
            'catalogue_recording': '0003371', 'grammar_reference': '0004087',
            'note': '研究者另以 0004087 引述《狐狸》与书面版本的关系；两个编号的馆方资源对应须核对。'}
        record['issues'].append(issue('source', 'japhug_fox_reference_difference',
            '语法书另以 0004087 引述《狐狸》改编；本条为目录录音 0003371，编号对应须核对，不能仅凭题名合并。'))
    record['issues'].append(issue('classification', 'japhug_recording_not_story',
        '这是录音目录资源，可能含叙事、技艺、语言资料或书面作品改写；不能自动判定为民间故事。'))
    record['issues'].append(issue('source', 'japhug_nonrepresentative',
        '当前目录多数录音登记为同一讲述者；首轮详情为目的性选取，不能代表全部社区或传统。'))
    record['issues'].append(issue('source', 'japhug_audio_not_copied',
        '本地仅保存目录及部分详情网页，音视频和转写正文请通过馆方页面查阅。'))
    record['issues'].append(issue('source', 'japhug_rights_community',
        '音视频、转写与附件的具体许可和相关社区要求须逐项核对；不得自动套用其他录音的许可。'))
    record['issues'].append(issue('coordinate', 'japhug_recording_scope',
        '馆藏语言范围或采录地不是叙事发生地，录音日期也不是故事发生年代。'))
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'japhug_codes_unassigned', '尚未根据原文与本地码表核定标准码。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate', 'japhug_coordinates_unverified', '坐标需要单条出处和地点性质的独立依据。', urgent=True))
    catalogs = [s for s in metadata.sources if s.type == 'pangloss_japhug_catalogue']
    selected = [s for s in metadata.sources if s.type == 'pangloss_japhug_selection']
    if (len(catalogs) != 1 or len(selected) != 1 or not catalogs[0].local_path or not selected[0].local_path
            or not catalogs[0].content_sha256 or not selected[0].content_sha256
            or str(catalogs[0].url) != JAPHUG_URL or str(selected[0].url) != JAPHUG_URL):
        record['issues'].append(issue('source', 'japhug_source_missing', '缺少可核验的目录或详情选取索引。', urgent=True))
        return
    catalog, selection = catalogs[0], selected[0]
    paths = [Path(catalog.local_path), Path(selection.local_path)]
    paths = [(p if p.is_absolute() else PROJECT_ROOT / p).resolve() for p in paths]
    if any(source_hashes.get(path) != source.content_sha256 for path, source in zip(paths, (catalog, selection), strict=True)):
        return  # Generic source checks already report missing or changed snapshots.
    try:
        if paths[0] not in catalogues:
            catalogues[paths[0]] = pangloss_catalogue_rows(paths[0].read_bytes(), 'Japhug')
        if paths[1] not in selections:
            selections[paths[1]] = load_pangloss_selection(paths[1], JAPHUG_URL)
        rows, selection_data = catalogues[paths[0]], selections[paths[1]]
        if not match:
            if catalog.locator != 'Japhug / 资源目录' or selection.locator != '首轮详情选取方法':
                raise ValueError('馆藏组来源定位符不符')
            return
        number = match.group(1)
        if number not in rows:
            raise ValueError('录音不在馆藏目录快照中')
        row = rows[number]
        group = next((g for g in selection_data['groups'] if number in g['ids']), None)
        if (catalog.locator != f'Japhug / DOI {number}'
                or selection.locator != (group['label'] if group else '未选入首轮详情')):
            raise ValueError('目录或详情选取索引定位符不符')
        originals = [s for s in metadata.sources if s.type in ('pangloss_japhug_detail', 'pangloss_japhug_original')]
        if len(originals) != 1:
            raise ValueError('单条录音来源缺失或重复')
        original = originals[0]
        if (str(original.url) != row['url'] or original.doi != row['doi'].removeprefix('https://doi.org/')
                or original.locator != f'录音 {number}'):
            raise ValueError('单条录音链接、DOI 或定位符与目录不符')
        detail = None
        extra = None
        evidence_group = group
        if group:
            if any(source.type.startswith('pangloss_japhug_supplement_') for source in metadata.sources):
                raise ValueError('首轮已有详情的录音不应再有详情补充')
            if original.type != 'pangloss_japhug_detail' or not original.local_path or not original.content_sha256:
                raise ValueError('已选取录音缺少详情快照')
            path = Path(original.local_path)
            path = (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
            if source_hashes.get(path) != original.content_sha256:
                return
            detail = pangloss_detail_fields(path.read_bytes(), row)
            record['issues'].append(issue('source', 'japhug_license_per_record', '单条详情的原许可和附件、社区要求须分别核对。'))
            if not detail['license']:
                record['issues'].append(issue('source', 'japhug_license_missing', '详情没有显示许可，请回查馆方。', urgent=True))
        else:
            if original.type != 'pangloss_japhug_original' or original.local_path or original.content_sha256:
                raise ValueError('未选取录音的单条来源状态不符')
            extra = pangloss_supplement_review(record,metadata,source_hashes,supplements,kind='japhug',
                                                row=row,corpus=paths[0],initial=paths[1])
            if extra:
                detail,evidence_group = extra
                record['issues'].append(issue('source','japhug_license_per_record','单条详情的原许可和附件、社区要求须分别核对。'))
                if not detail['license']:
                    record['issues'].append(issue('source','japhug_license_missing','详情没有显示许可，请回查馆方。',urgent=True))
            else:
                record['issues'].append(issue('source', 'japhug_detail_unchecked', '尚未采集单条详情；许可、采录地点及角色须回查。'))
        data = japhug_evidence(row, detail, evidence_group)
        record['evidence']['pangloss_japhug'] = data
        if (metadata.title != f"嘉绒语录音目录 · {row['title']}" or row['title'] not in metadata.aliases
                or not json_block_preserved(record['markdown'], japhug_evidence(row,None,None) if extra else data)):
            record['issues'].append(issue('source', 'japhug_fields_changed', '草稿字段与馆方快照不一致。', urgent=True))
        if detail:
            if data['目录与详情录音日期是否一致'] is False:
                record['issues'].append(issue('source', 'japhug_date_conflict', '目录与详情的录音日期不同，请回查。', urgent=True))
            elif data['目录与详情录音日期是否一致'] is None:
                record['issues'].append(issue('source', 'japhug_date_precision', '目录与详情日期精度不同或无法比较。'))
            if any(data[key] is False for key in ('目录与详情讲述者字段是否对应', '目录与详情研究者字段是否对应')):
                record['issues'].append(issue('source', 'japhug_credits_conflict', '目录与详情的讲述者或研究者字段不同。', urgent=True))
    except (ValueError, KeyError, OSError, TypeError) as error:
        record['issues'].append(issue('source', 'japhug_snapshot_invalid', f'Japhug 馆藏元数据无法核验：{error}', urgent=True))


def khmu_review(record: dict, metadata, source_hashes: dict, catalogues: dict, selections: dict, comparisons: dict, supplements: dict) -> None:
    match = re.fullmatch(r'case_sea_khmu_(\d{7})', metadata.id)
    if not match and metadata.id != KHMU_ROOT:
        return
    record['issues'].append(issue('classification', 'khmu_recording_not_story',
        '录音可能包含多个故事、片段、歌唱、祈祷、访谈或词汇；不能将每件自动视为一篇民间故事。'))
    record['issues'].append(issue('source', 'khmu_selection_scope',
        '首轮详情按题名及资料形式目的性选择，不是随机或代表性样本。'))
    record['issues'].append(issue('source', 'khmu_audio_not_copied',
        '本地保存目录及已采集的详情网页；音视频和转写正文请通过馆方页面查阅。'))
    record['issues'].append(issue('source', 'khmu_rights_community',
        '音视频、转写与附件许可及相关社区要求须逐项核对，不能套用其他录音的许可。'))
    record['issues'].append(issue('source', 'khmu_language_scope',
        '馆藏名称不保证每段都只用 Khmu 语，单条语言及演述背景须核对。'))
    record['issues'].append(issue('coordinate', 'khmu_recording_scope',
        '馆藏语言范围、讲述者籍贯、录音地和叙事发生地是不同字段；录音日期不是故事发生年代。'))
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard', 'khmu_codes_unassigned', '尚未根据原文与本地码表核定标准码。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate', 'khmu_coordinates_unverified', '坐标需要单条出处和地点性质的独立依据。', urgent=True))
    types = ('pangloss_khmu_catalogue', 'pangloss_khmu_selection', 'pangloss_khmu_comparison')
    sources = [[s for s in metadata.sources if s.type == typ] for typ in types]
    if (any(len(values) != 1 for values in sources)
            or any(not values[0].local_path or not values[0].content_sha256 or str(values[0].url) != KHMU_URL for values in sources)):
        record['issues'].append(issue('source', 'khmu_source_missing', '缺少可核验的目录、详情选取或对照索引。', urgent=True))
        return
    catalog, selection, comparison = (values[0] for values in sources)
    paths = [Path(s.local_path) for s in (catalog, selection, comparison)]
    paths = [(p if p.is_absolute() else PROJECT_ROOT / p).resolve() for p in paths]
    if any(source_hashes.get(path) != source.content_sha256 for path, source in zip(paths, (catalog, selection, comparison), strict=True)):
        return
    try:
        if paths[0] not in catalogues:
            catalogues[paths[0]] = pangloss_catalogue_rows(paths[0].read_bytes(), 'Khmu')
        if paths[1] not in selections:
            selections[paths[1]] = load_pangloss_selection(paths[1], KHMU_URL)
        if paths[2] not in comparisons:
            comparisons[paths[2]] = load_khmu_comparisons(paths[2], paths[0], catalogues[paths[0]])
        rows, selection_data, comparison_data = catalogues[paths[0]], selections[paths[1]], comparisons[paths[2]]
        if not match:
            if (catalog.locator != 'Khmu / 资源目录' or selection.locator != '首轮详情选取方法'
                    or comparison.locator != '目录题名对照索引'):
                raise ValueError('馆藏组来源定位符不符')
            return
        number = match.group(1)
        if number not in rows:
            raise ValueError('录音不在馆藏目录快照中')
        row = rows[number]
        if number == '0001986' and row['title'] == 'Histoire de Chuang aux pouvoirs magnifiques' and row['doi'] == 'https://doi.org/10.24397/pangloss-0001986':
            record['evidence']['khmu_research_reference'] = {
                'url':'https://doi.org/10.4000/clo.7019',
                'citation':'Alexis Michaud、Minh-Châu Nguyễn、Likun He，2020，Cahiers de littérature orale。',
                'note':'论文引述 Ferlus 1979 年研究并明确链接这条 0001986 录音；讲述者身份与论文、录音之间的具体对应仍须核查。'}
            record['issues'].append(issue('source','khmu_chuang_research_reference',
                '2020 年研究明确指向本条录音并引述 Ferlus 1979 年文章；具体采录与文本版本仍须回查。'))
        elif number == '0001986':
            record['issues'].append(issue('source','khmu_chuang_reference_mismatch',
                '目录中的 0001986 题名或 DOI 与论文所引条目不符；暂不附加研究对照。',urgent=True))
        group = next((g for g in selection_data['groups'] if number in g['ids']), None)
        compared = next((g for g in comparison_data['groups'] if any(m['id'] == number for m in g['members'])), None)
        if (catalog.locator != f'Khmu / DOI {number}'
                or selection.locator != (group['label'] if group else '未选入首轮详情')
                or comparison.locator != (compared['label'] if compared else '无目录对照分组')):
            raise ValueError('目录、详情选取或对照索引定位符不符')
        originals = [s for s in metadata.sources if s.type in ('pangloss_khmu_detail', 'pangloss_khmu_original')]
        if len(originals) != 1:
            raise ValueError('单条录音来源缺失或重复')
        original = originals[0]
        if (str(original.url) != row['url'] or original.doi != row['doi'].removeprefix('https://doi.org/')
                or original.locator != f'录音 {number}'):
            raise ValueError('单条录音链接、DOI 或定位符与目录不符')
        detail = None
        extra = None
        evidence_group = group
        if group:
            if any(source.type.startswith('pangloss_khmu_supplement_') for source in metadata.sources):
                raise ValueError('首轮已有详情的录音不应再有详情补充')
            if original.type != 'pangloss_khmu_detail' or not original.local_path or not original.content_sha256:
                raise ValueError('已选取录音缺少详情快照')
            path = Path(original.local_path)
            path = (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
            if source_hashes.get(path) != original.content_sha256:
                return
            detail = pangloss_detail_fields(path.read_bytes(), row)
            record['issues'].append(issue('source', 'khmu_license_per_record', '单条详情的原许可和附件、社区要求须分别核对。'))
            if not detail['license']:
                record['issues'].append(issue('source', 'khmu_license_missing', '详情没有显示许可，请回查馆方。', urgent=True))
        else:
            if original.type != 'pangloss_khmu_original' or original.local_path or original.content_sha256:
                raise ValueError('未选取录音的单条来源状态不符')
            extra = pangloss_supplement_review(record,metadata,source_hashes,supplements,kind='khmu',
                                                row=row,corpus=paths[0],initial=paths[1])
            if extra:
                detail,evidence_group = extra
                record['issues'].append(issue('source','khmu_license_per_record','单条详情的原许可和附件、社区要求须分别核对。'))
                if not detail['license']:
                    record['issues'].append(issue('source','khmu_license_missing','详情没有显示许可，请回查馆方。',urgent=True))
            else:
                record['issues'].append(issue('source', 'khmu_detail_unchecked', '尚未采集单条详情；许可、采录地点及角色须回查。'))
        data = japhug_evidence(row, detail, evidence_group)
        record['evidence']['pangloss_khmu'] = data
        if (metadata.title != f"Khmu 录音目录 · {row['title']}" or row['title'] not in metadata.aliases
                or not json_block_preserved(record['markdown'], japhug_evidence(row,None,None) if extra else data)):
            record['issues'].append(issue('source', 'khmu_fields_changed', '草稿字段与馆方快照不一致。', urgent=True))
        if khmu_speaker_identity_unverified(row['speakers']):
            record['issues'].append(issue('source', 'khmu_speaker_unknown', '目录讲述者字段未具名或含 unknown；不能推定缺失者身份。'))
        if re.search(r'\bfrom\b', row['speakers'], re.IGNORECASE):
            record['issues'].append(issue('coordinate', 'khmu_speaker_origin', '讲述者字段包含来源地描述；须与单条录音地点分开核对。'))
        if detail and re.search(r'\bFrance\b', detail.get('recording_location') or '', re.IGNORECASE):
            record['issues'].append(issue('coordinate', 'khmu_recorded_in_france', '馆方录音地点字段含 France；语言馆藏范围不表示该录音在东南亚完成。'))
        if khmu_multi_or_part(row['title']):
            record['issues'].append(issue('source', 'khmu_multiple_or_part', '目录题名提示多项内容或分段；数量和边界须回听。'))
        if khmu_other_language(row['title']):
            record['issues'].append(issue('source', 'khmu_multilingual_title', '目录题名提及 Lao 或 Nhuan；各段语言及其角色须分别核对。'))
        if not row['transcription_icon']:
            record['issues'].append(issue('source', 'khmu_transcription_not_shown', '目录未显示转写图标；仍需回查单条页面，不能据此断定不存在转写。'))
        if compared:
            evidence = khmu_comparison_evidence(compared)
            record['evidence']['khmu_comparison'] = evidence
            record['issues'].append(issue('source', 'khmu_comparison_unverified', '目录对照是待复核线索，不证明同一演述、同源或历史传播。'))
            if not json_block_preserved(record['markdown'], evidence):
                record['issues'].append(issue('source', 'khmu_comparison_changed', '草稿对照字段与来源索引不符。', urgent=True))
        expected = [] if not compared or number == compared['members'][0]['id'] else [(f"case_sea_khmu_{compared['members'][0]['id']}", compared['note'])]
        actual = [(relation.target, relation.note) for relation in metadata.relations if relation.type == 'COMPARED_WITH']
        if actual != expected:
            record['issues'].append(issue('source', 'khmu_comparison_relation_changed', '草稿对照关系与来源索引不符。', urgent=True))
        if detail:
            if data['目录与详情录音日期是否一致'] is False:
                record['issues'].append(issue('source', 'khmu_date_conflict', '目录与详情录音日期不同，请回查。', urgent=True))
            elif data['目录与详情录音日期是否一致'] is None:
                range_match = compare_khmu_recording_ranges(row['recorded'],detail['recorded'])
                record['evidence']['khmu_date_range_match'] = range_match
                if range_match is True:
                    record['issues'].append(issue('source','khmu_date_range_equivalent',
                        '目录与详情采用不同的日期范围写法，两个端点一致；双方原字段仍保留。'))
                elif range_match is False:
                    record['issues'].append(issue('source','khmu_date_conflict','目录与详情的日期范围不同，请回查。',urgent=True))
                else:
                    record['issues'].append(issue('source', 'khmu_date_precision', '目录与详情日期精度不同或无法比较；保留双方原值。'))
            if any(data[key] is False for key in ('目录与详情讲述者字段是否对应', '目录与详情研究者字段是否对应')):
                record['issues'].append(issue('source', 'khmu_credits_conflict', '目录与详情讲述者或研究者字段不同，请回查。', urgent=True))
    except (ValueError, KeyError, OSError, TypeError) as error:
        record['issues'].append(issue('source', 'khmu_snapshot_invalid', f'Khmu 馆藏元数据无法核验：{error}', urgent=True))


def korea_aks_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match=re.fullmatch(r'case_kr_aks_dobong_(\d{6})',metadata.id)
    if not match and metadata.id!=KOREA_AKS_ROOT:
        return
    record['issues'].append(issue('classification','korea_aks_directory_not_story',
        '开放目录行与录音不一定各对应一则独立故事；馆方类别、具体演述和版本须人工核对。'))
    record['issues'].append(issue('source','korea_aks_rights_community',
        '目录文件、单条网页、转写及音视频许可范围不同；具体使用条件和相关社区要求须逐项核对。'))
    record['issues'].append(issue('source','korea_aks_metadata_only',
        '本地保存目录及馆方字段索引，未复制网页正文或音视频；网页响应指纹无法单凭索引离线重算。'))
    record['issues'].append(issue('coordinate','korea_aks_recording_scope',
        '采录区域、具体录音地点与叙事发生地不同；调查日期不自动作为故事发生年代。'))
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard','korea_aks_codes_unassigned',
            '馆方目录短编号不是标准码；仅能根据原文和本地码表人工核定。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate','korea_aks_coordinates_unverified',
            '坐标需要单条出处及地点性质的独立依据。',urgent=True))
    types=('korea_aks_catalogue','korea_aks_receipt','korea_aks_search_manifest',
           'korea_aks_detail_manifest','korea_aks_crosswalk_base','korea_aks_crosswalk_detail')
    sources=[[source for source in metadata.sources if source.type==kind] for kind in types]
    if any(len(values)!=1 or not values[0].local_path or not values[0].content_sha256 for values in sources):
        record['issues'].append(issue('source','korea_aks_source_missing','缺少可核验的目录、凭据或字段索引。',urgent=True))
        return
    paths=[Path(values[0].local_path) for values in sources]
    paths=[(path if path.is_absolute() else PROJECT_ROOT/path).resolve() for path in paths]
    if any(source_hashes.get(path)!=values[0].content_sha256 for path,values in zip(paths,sources,strict=True)):
        return
    try:
        key=tuple(paths)
        if key not in cache:
            archive,receipt,search_manifest,detail_manifest,base,reconciled=paths
            if search_manifest.name!='manifest.json' or detail_manifest.name!='manifest.json':
                raise ValueError('馆方字段索引清单路径不符')
            expected={}
            for model,body in korea_cards(archive,receipt,search_manifest.parent,base,detail_manifest.parent,reconciled):
                data=None
                if model.id.startswith(KOREA_AKS_PREFIX):
                    block=re.search(r'(?ms)^(`{3,})\s*\n(.*?)\n\1\s*$',body)
                    if not block:raise ValueError('来源候选字段正文缺失')
                    data=json.loads(block.group(2))
                expected[model.id]=(model,data)
            cache[key]=expected
        if metadata.id not in cache[key]:
            raise ValueError('记录不在开放目录筛查范围中')
        expected,data=cache[key][metadata.id]
        current=Counter(json.dumps(source.model_dump(mode='json'),ensure_ascii=False,sort_keys=True) for source in metadata.sources)
        required=Counter(json.dumps(source.model_dump(mode='json'),ensure_ascii=False,sort_keys=True) for source in expected.sources)
        if (metadata.title!=expected.title or not all(alias in metadata.aliases for alias in expected.aliases)
                or any(current[key]<count for key,count in required.items())
                or (data is not None and not json_block_preserved(record['markdown'],data))):
            record['issues'].append(issue('source','korea_aks_fields_changed',
                '草稿字段或来源与目录和候选索引不符，请回查。',urgent=True))
        if data is not None:
            record['evidence']['korea_aks_dobong']=data
            candidates=data['馆方候选']
            if not candidates:
                record['issues'].append(issue('source','korea_aks_no_candidate',
                    '本次道峰区检索未找到来源候选，不代表馆方不存在该记录。'))
            else:
                record['issues'].append(issue('source','korea_aks_candidate_unverified',
                    '候选基于题名、讲述者、类别与区域；即使字段一致仍须人工核对同一次演述及版本。'))
                if len(candidates)>1 or any(int(candidate['该馆方记录的目录候选数'])>1 for candidate in candidates):
                    record['issues'].append(issue('source','korea_aks_multiple_candidates',
                        '存在一对多或多对一候选，保留所有候选供核查。',urgent=True))
                if any(candidate['题名对照方式']=='相似待核' or candidate['馆方检索题名']!=data['目录字段']['서명'] for candidate in candidates):
                    record['issues'].append(issue('source','korea_aks_title_variant',
                        '目录与馆方检索题名存在不同写法或仅为相似候选。'))
                if any(candidate['目录与详情采录地点']=='不同' for candidate in candidates):
                    record['issues'].append(issue('coordinate','korea_aks_place_disagreement',
                        '目录与馆方详情的采录地点写法不同；须核对历史行政区与地点范围。',urgent=True))
                if any(any(candidate[key]=='不同' for key in ('检索与详情题名','检索与详情讲述者','检索与详情类别','检索与详情日期')) for candidate in candidates):
                    record['issues'].append(issue('source','korea_aks_listing_detail_disagreement',
                        '馆方检索页与单条详情字段不同，请逐项回查。',urgent=True))
            if not data['目录字段']['구연자'].strip():
                record['issues'].append(issue('source','korea_aks_speaker_missing','开放目录未填写讲述者。'))
    except (ValueError,OSError,KeyError,TypeError) as error:
        record['issues'].append(issue('source','korea_aks_snapshot_invalid',f'韩国目录或候选字段无法核验：{error}',urgent=True))


def lanna_review(record: dict, metadata, source_hashes: dict, cache: dict) -> None:
    match=re.fullmatch(r'corpus_th_lanna_([1-9]\d*)',metadata.id)
    if not match and metadata.id!=LANNA_ROOT:return
    record['issues'].append(issue('classification','lanna_manuscript_not_story',
        '手稿馆藏件数不是独立故事数；语种、体裁、版本及具体内容须逐件核查。'))
    record['issues'].append(issue('source','lanna_rights_community',
        '馆方许可、单件归属、可能的例外及相关社区要求须逐项核对；本地未下载影像或转写正文。'))
    record['issues'].append(issue('coordinate','lanna_repository_not_event',
        '馆藏地点及坐标原字段为保管地点线索，不自动作为采录地点或故事发生地；手稿日期不是叙事年代。'))
    if not any(metadata.standards.model_dump().values()):
        record['issues'].append(issue('standard','lanna_codes_unassigned','馆藏编号不是标准码，仅能依据原文及本地码表人工核定。'))
    if metadata.spatial and metadata.spatial.lat is not None:
        record['issues'].append(issue('coordinate','lanna_coordinates_unverified','坐标及地点性质需要单件来源另行核定。',urgent=True))
    source_type='lanna_search' if match else 'lanna_manifest'
    sources=[source for source in metadata.sources if source.type==source_type]
    if len(sources)!=1 or not sources[0].local_path or not sources[0].content_sha256:
        record['issues'].append(issue('source','lanna_source_missing','馆藏检索快照或清单缺失。',urgent=True));return
    path=Path(sources[0].local_path);path=(path if path.is_absolute() else PROJECT_ROOT/path).resolve()
    if source_hashes.get(path)!=sources[0].content_sha256:return
    try:
        folder=path.parent
        if folder not in cache:
            expected={}
            for model,body in lanna_cards(folder):
                data=None
                if model.id!=LANNA_ROOT:
                    block=re.search(r'(?ms)^(`{3,})\s*\n(.*?)\n\1\s*$',body)
                    if not block:raise ValueError('馆藏字段正文缺失')
                    data=json.loads(block.group(2))
                expected[model.id]=(model,data)
            cache[folder]=expected
        if metadata.id not in cache[folder]:raise ValueError('馆藏不在检索范围内')
        expected,data=cache[folder][metadata.id]
        current=Counter(json.dumps(source.model_dump(mode='json'),ensure_ascii=False,sort_keys=True) for source in metadata.sources)
        required=Counter(json.dumps(source.model_dump(mode='json'),ensure_ascii=False,sort_keys=True) for source in expected.sources)
        if (metadata.title!=expected.title or not all(alias in metadata.aliases for alias in expected.aliases)
                or any(current[key]<count for key,count in required.items())
                or (data is not None and not json_block_preserved(record['markdown'],data))):
            record['issues'].append(issue('source','lanna_fields_changed','草稿字段或来源与馆藏快照不符，请回查。',urgent=True))
        if data is not None:
            record['evidence']['lanna']=data
            if data['相同档号馆藏候选']:
                record['issues'].append(issue('source','lanna_duplicate_shelfmark','同一馆藏档号对应多件，不能自动合并。',urgent=True))
            if 'CC BY-NC 4.0' not in data['署名与许可']:
                record['issues'].append(issue('source','lanna_license_unclear','单件署名和许可字段需进一步回查。',urgent=True))
    except (ValueError,OSError,KeyError,TypeError) as error:
        record['issues'].append(issue('source','lanna_snapshot_invalid',f'北泰馆藏快照无法核验：{error}',urgent=True))


def generic_records(vault: Path, table_path: Path, reserved: set[str]) -> list[dict]:
    """Include every other Markdown draft, including direct intake and custom batches."""
    table = load_code_table(table_path)
    labels = {label: system for system, label in STANDARD_NAMES.items()}
    source_hashes, thai_datasets, lao_pages, lao_indexes, yuhuan_indexes, yuhuan_supplements = {}, {}, {}, {}, {}, {}
    sinica_pages, sinica_details, sinica_indexes, sinica_gis = {}, {}, {}, {}
    vietnam_cham_catalogues, vietnam_cham_details = {}, {}
    shandong_indexes = {}
    hmml_selections, hmml_legacy_indexes = {}, {}
    sil_catalogues, cole_catalogues, early_catalogues, andersen_snapshots = {}, {}, {}, {}
    pangloss_catalogues, pangloss_selections, pangloss_contexts, na_candidates = {}, {}, {}, {}
    na_tone_indexes = {}
    japhug_catalogues, japhug_selections = {}, {}
    khmu_catalogues, khmu_selections, khmu_comparisons = {}, {}, {}
    pangloss_supplements = {}
    korea_aks_snapshots, lanna_snapshots = {}, {}
    bl_khmer_snapshots, bl_yi_snapshots, lowell_sea_snapshots, minyag_snapshots, temiar_snapshots, pumi_snapshots = {}, {}, {}, {}, {}, {}
    nitean_snapshots, palue_snapshots, zibuyu_snapshots, bl_burma_snapshots, bl_dongjing_snapshots, bl_yi_project_snapshots = {}, {}, {}, {}, {}, {}
    heritage_2011_snapshots = {}
    heritage_2006_snapshots, heritage_batch_snapshots, heritage_2021_snapshots = {}, {}, {}
    records = []
    queue = vault / "00_drafts"
    for path in sorted(queue.rglob("*.md")):
        relative = f"vault/{path.relative_to(vault).as_posix()}"
        if relative in reserved:
            continue
        if path.is_symlink():
            raise ValueError(f"待审草稿不能是符号链接。{path}")
        try:
            parts = path.relative_to(queue).parts
            collection = "asia" if len(parts) > 1 and parts[0].startswith("asia_") else "intake"
            record, metadata = base_record(path, vault, collection)
        except (ValueError, UnicodeError, yaml.YAMLError) as error:
            raise ValueError(f"待审草稿无法解析，复核清单未更新。{path}\n{error}") from error
        if metadata.genre == "unclassified":
            record["issues"].append(issue("classification", "genre_unclassified", "尚未确认体裁，请阅读来源后选择。"))
        if (metadata.node_type == "case" and metadata.spatial is None) or (metadata.spatial and metadata.spatial.lat is None):
            record["issues"].append(issue("coordinate", "coordinate_missing", "暂无坐标；若资料没有明确地点，可以留空。"))
        if metadata.sources and any(not source.locator for source in metadata.sources):
            record["issues"].append(issue("source", "source_locator_missing", "部分出处没有登记页码、段落或其他定位符。"))
        if any(source.citation == "用户提供的文本" and not source.url for source in metadata.sources):
            record["issues"].append(issue("source", "source_attribution_missing", "文本来源仅标记为用户提供；如有原始出处，请补充。"))
        for source in metadata.sources:
            if source.type == "thai_sac_record_link" and source.url and not source.local_path:
                record["issues"].append(issue("source", "thai_record_page_unchecked",
                    "入库时馆藏站点 robots.txt 限制自动抓取原记录页；请人工回查，数据快照另有哈希。"))
                continue
            if source.type == "lao_dllm_viewer" and source.url and not source.local_path:
                record["issues"].append(issue("source", "lao_image_not_cached",
                    "手稿影像未保存在本地；可打开馆藏页面查看原图。"))
                continue
            if source.type == "sinica_original" and source.url and not source.local_path:
                record["issues"].append(issue("source", "sinica_original_remote",
                    "译文及原音未复制；请通过馆方单条详情浏览并复核。"))
                continue
            if source.type == "pangloss_japhug_original" and source.url and not source.local_path:
                continue  # The source-specific review marks the absent detail page.
            if source.type == "pangloss_khmu_original" and source.url and not source.local_path:
                continue  # The source-specific review marks the absent detail page.
            if source.type == NA_CANDIDATE_MARKER and source.url and not source.local_path:
                continue  # The source-specific review marks the absent detail page.
            if source.type == MINYAG_MARKER and source.url and not source.local_path:
                continue  # The old archive link is identified as an unchecked lead.
            if source.type in (TEMIAR_MARKER, TEMIAR_AUDIO_MARKER) and source.url and not source.local_path:
                continue  # Both legacy links are flagged as unchecked; no media was fetched.
            if source.type in (PUMI_MARKER, PUMI_AUDIO_MARKER) and source.url and not source.local_path:
                continue  # The original legacy entry points are unverified and uncached.
            if source.type == PALUE_MARKER and source.url and not source.local_path:
                continue  # The item page is a remote link; the field index is separately hashed.
            if source.type == 'bl_yi_project_viewer' and source.url and not source.local_path:
                continue  # The image entry point is linked, not accessed or copied.
            if source.type == DSAL_BURMA_MARKER and source.url and not source.local_path:
                continue  # Candidate page is not fetched; the index is hashed separately.
            if source.type == ZIBUYU_MARKER and source.url and not source.local_path:
                continue  # Immutable revision link; the captured page is hashed separately.
            if source.type == "cole_scan_link" and source.url and not source.local_path:
                continue  # Candidate scan is remote; separate OCR and index are hashed.
            if source.type in ("jade_scan", "saleeby_scan") and source.url and not source.local_path:
                continue  # The remote scan is linked; OCR and scan mapping have separate hashes.
            if (source.local_path or source.url) and not source.content_sha256:
                record["issues"].append(issue("source", "source_hash_missing", "来源没有登记内容哈希，无法校验内容。", urgent=True))
            elif source.local_path and source.content_sha256:
                snapshot = Path(source.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if snapshot not in source_hashes:
                    if snapshot.is_file():
                        with snapshot.open("rb") as stream:
                            source_hashes[snapshot] = file_digest(stream, "sha256").hexdigest()
                    else:
                        source_hashes[snapshot] = None
                if source_hashes[snapshot] is None:
                    record["issues"].append(issue("source", "source_snapshot_missing", "登记的本地来源文件不存在。", urgent=True))
                elif source_hashes[snapshot] != source.content_sha256:
                    record["issues"].append(issue("source", "source_hash_mismatch", "来源文件内容与草稿登记的哈希不一致。", urgent=True))
            if source.url and not source.local_path:
                record["issues"].append(issue("source", "source_remote_uncached", "网页来源尚无本地快照，须回查原文。"))
        missing = [f"{STANDARD_NAMES[system]} {code}" for (system, key), code in standard_codes(metadata.standards).items()
                   if (system, key) not in table]
        if missing:
            record["issues"].append(issue("standard", "code_unmatched", f"本地码表未登记：{'、'.join(missing)}。", urgent=True))
        sections = re.split(r"(?m)^## 未匹配的原文编码\s*$", record["markdown"], maxsplit=1)
        unmatched = []
        if len(sections) == 2:
            text = re.split(r"(?m)^## ", sections[1], maxsplit=1)[0]
            for match in re.finditer(r"(?m)^- (ATU|OCM|汤普森|别列兹金) `([A-Za-z0-9.\-]+)` · (.+?)：", text):
                label, code, locator = match.groups()
                system = labels[label]
                available = (system, normalize_code(system, code)) in table
                unmatched.append({"system": label, "code": code, "locator": locator, "now_available": available})
            if unmatched:
                record["issues"].append(issue("standard", "unmatched_explicit_codes",
                    "原文含未匹配编码：" + "、".join(f"{item['system']} {item['code']}" for item in unmatched)
                    + "；标准字段未自动补入，请核对码表与原文。"))
        record["evidence"] = {"record_type": metadata.node_type, "unmatched_explicit_codes": unmatched}
        na_candidate_review(record, metadata, source_hashes, na_candidates)
        na_tone_review(record, metadata, source_hashes, na_tone_indexes)
        early_edition_review(record, metadata, source_hashes, early_catalogues, andersen_snapshots)
        cole_review(record, metadata, source_hashes, cole_catalogues)
        japhug_review(record, metadata, source_hashes, japhug_catalogues, japhug_selections, pangloss_supplements)
        khmu_review(record, metadata, source_hashes, khmu_catalogues, khmu_selections, khmu_comparisons, pangloss_supplements)
        korea_aks_review(record, metadata, source_hashes, korea_aks_snapshots)
        lanna_review(record, metadata, source_hashes, lanna_snapshots)
        bl_khmer_review(record, metadata, source_hashes, bl_khmer_snapshots)
        bl_yi_review(record, metadata, source_hashes, bl_yi_snapshots)
        bl_burma_review(record, metadata, source_hashes, bl_burma_snapshots)
        bl_dongjing_review(record, metadata, source_hashes, bl_dongjing_snapshots)
        bl_yi_project_review(record, metadata, source_hashes, bl_yi_project_snapshots)
        minyag_review(record, metadata, source_hashes, minyag_snapshots)
        temiar_review(record, metadata, source_hashes, temiar_snapshots)
        pumi_review(record, metadata, source_hashes, pumi_snapshots)
        palue_review(record, metadata, source_hashes, palue_snapshots)
        zibuyu_review(record, metadata, source_hashes, zibuyu_snapshots)
        lowell_sea_review(record, metadata, source_hashes, lowell_sea_snapshots)
        nitean_review(record, metadata, source_hashes, nitean_snapshots)
        heritage_2011_review(record, metadata, source_hashes, heritage_2011_snapshots)
        heritage_2006_review(record, metadata, source_hashes, heritage_2006_snapshots)
        heritage_batch_review(record, metadata, source_hashes, heritage_batch_snapshots)
        heritage_2021_review(record, metadata, source_hashes, heritage_2021_snapshots)
        match = re.fullmatch(r"case_thai_sac_([1-9]\d*)", metadata.id)
        dataset = next((source for source in metadata.sources if source.type == "thai_sac_dataset"), None)
        if match and dataset and dataset.local_path and dataset.content_sha256:
            snapshot = Path(dataset.local_path)
            if not snapshot.is_absolute():
                snapshot = PROJECT_ROOT / snapshot
            snapshot = snapshot.resolve()
            if source_hashes.get(snapshot) == dataset.content_sha256:
                if snapshot not in thai_datasets:
                    thai_datasets[snapshot] = read_thai_dataset(snapshot)
                row = thai_datasets[snapshot].get(int(match.group(1)))
                if row is None:
                    record["issues"].append(issue("source", "thai_record_missing", "数据快照中找不到此原记录号。", urgent=True))
                else:
                    text = thai_original_text(row["description"])
                    record["evidence"]["thai_catalogue_fields"] = {key: value for key, value in row.items() if key != "description"}
                    record["evidence"]["thai_original_text_length"] = len(text)
                    if row["title"].strip() not in [metadata.title, *metadata.aliases]:
                        record["issues"].append(issue("source", "thai_title_changed", "卡片标题或别名未保留快照中的泰语原题，请核对。", urgent=True))
                    if not text:
                        record["issues"].append(issue("source", "thai_original_missing", "数据快照的 description 字段为空，尚无原文。", urgent=True))
                    elif text not in record["markdown"]:
                        record["issues"].append(issue("source", "thai_original_changed", "草稿中的泰语原文与数据快照提取文本不一致，请逐字核对。", urgent=True))
                    if not row["creator"].strip():
                        record["issues"].append(issue("source", "thai_creator_missing", "数据快照未填写 creator 字段；其角色也需核查。"))
                    if not row["license"].strip():
                        record["issues"].append(issue("source", "thai_record_license_missing", "本条 license 字段为空，须核对单条许可。", urgent=True))
                    record["issues"].append(issue("coordinate", "thai_location_scope_unknown",
                        "馆藏地点字段的性质未说明；不能自动视为采录地或叙事地。"))
        match = re.fullmatch(r"corpus_lao_dllm_([1-9]\d*)", metadata.id)
        dataset = next((source for source in metadata.sources if source.type == "lao_dllm_search"), None)
        if match and dataset and dataset.local_path and dataset.content_sha256:
            snapshot = Path(dataset.local_path)
            if not snapshot.is_absolute():
                snapshot = PROJECT_ROOT / snapshot
            snapshot = snapshot.resolve()
            if source_hashes.get(snapshot) == dataset.content_sha256:
                page_match = re.fullmatch(r"page-(\d{3})\.json", snapshot.name)
                if not page_match:
                    record["issues"].append(issue("source", "lao_snapshot_name_invalid", "馆藏分页快照名称不符。", urgent=True))
                else:
                    if snapshot not in lao_pages:
                        page = parse_lao_page(snapshot.read_bytes(), int(page_match.group(1)))
                        lao_pages[snapshot] = {LAO_IDENTIFIER.fullmatch(item["resource_id"]).group(1): item for item in page["results"]}
                    row = lao_pages[snapshot].get(match.group(1))
                    if row is None:
                        record["issues"].append(issue("source", "lao_record_missing", "数据快照中找不到此馆藏编号。", urgent=True))
                    else:
                        fields = lao_selected_fields(row)
                        credit = lao_attribution(row)
                        record["evidence"]["lao_catalogue_fields"] = fields
                        record["evidence"]["lao_attribution"] = credit
                        record["evidence"]["coordinate_scope"] = "馆藏地；候选坐标未经复核"
                        record["issues"].append(issue("source", "lao_transcription_missing",
                            "此条仅保存馆藏元数据，尚无手稿正文转录；需回查原图。"))
                        if not credit or "CC BY-NC 4.0" not in credit:
                            record["issues"].append(issue("source", "lao_license_unclear", "此件的署名或许可声明需要核对。", urgent=True))
                        if not fields.get("otherIdentifier.code_number"):
                            record["issues"].append(issue("source", "lao_plmp_code_missing", "馆藏记录未提供 PLMP 档号。"))
                        if snapshot.parent not in lao_indexes:
                            try:
                                _, collection = load_lao_snapshot(snapshot.parent)
                                lao_indexes[snapshot.parent] = (lao_plmp_index(collection), None)
                            except (OSError, ValueError, TypeError, KeyError) as error:
                                lao_indexes[snapshot.parent] = (None, str(error))
                        groups, error = lao_indexes[snapshot.parent]
                        if groups is None:
                            record["issues"].append(issue("source", "lao_crosscheck_unavailable",
                                "无法核验同档号的跨页记录；请检查馆藏批次快照。", urgent=True))
                        else:
                            matches = {}
                            for code in fields.get("otherIdentifier.code_number", {}).get("none", []):
                                for other in groups.get(code.strip(), []):
                                    if str(other.identifier) == match.group(1):
                                        continue
                                    other_fields = lao_selected_fields(other.record)
                                    matches[(code.strip(), other.identifier)] = {"code": code.strip(),
                                        "manifest": other.identifier,
                                        "title": " / ".join(other_fields.get("title", {}).get("en", [])),
                                        "dllm_id": " / ".join(other_fields.get("dc:identifier", {}).get("none", [])),
                                        "viewer": LAO_VIEWER.format(other.identifier)}
                            if matches:
                                record["evidence"]["lao_duplicate_plmp"] = list(matches.values())
                                record["issues"].append(issue("source", "lao_duplicate_plmp_code",
                                    "同一 PLMP 档号出现在不同馆藏记录中；标题或影像可能不同，须逐件回查，不能自动合并。", urgent=True))
                        latitudes = fields.get("schema:latitude", {}).get("none", [])
                        longitudes = fields.get("schema:longitude", {}).get("none", [])
                        try:
                            if len(latitudes) != 1 or len(longitudes) != 1:
                                raise ValueError("坐标数量不符")
                            lat, lng = float(latitudes[0]), float(longitudes[0])
                            if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
                                raise ValueError("坐标超出范围")
                            record["evidence"]["lao_repository_candidate"] = {"lat": lat, "lng": lng,
                                "scope": "馆藏地候选点；非故事发生地或采录地"}
                            record["issues"].append(issue("coordinate", "lao_repository_point_unverified",
                                f"馆藏地候选坐标 {lat}, {lng} 未经核对；不能直接当作故事发生地或采录地。"))
                        except (TypeError, ValueError):
                            record["issues"].append(issue("coordinate", "lao_repository_point_invalid",
                                "馆藏地坐标缺失或无效，需回查原始登记。", urgent=True))
        match = re.fullmatch(r"case_tw_sinica_oral_([1-9]\d*)", metadata.id)
        if metadata.id == "corpus_tw_sinica_oral" or match:
            record["issues"].append(issue("source", "sinica_rights_restricted",
                "原站仅供非营利教育与学术浏览，未经同意不得摘取内容出版；具体使用及社区权益须核对。", urgent=True))
        if match:
            identifier = int(match.group(1))
            record["issues"].append(issue("coordinate", "sinica_collection_scope",
                "目录组和采集地点不等于叙事发生地；坐标与地点性质须分别核对。"))
            original = next((source for source in metadata.sources if source.type == "sinica_original"), None)
            if not original or not original.url or str(original.url) != sinica_detail_url(identifier):
                record["issues"].append(issue("source", "sinica_original_link_invalid", "缺少匹配编号的原站详情链接。", urgent=True))
            catalogue = next((source for source in metadata.sources if source.type == "sinica_catalogue"), None)
            if not catalogue or not catalogue.local_path or not catalogue.content_sha256:
                record["issues"].append(issue("source", "sinica_catalogue_missing", "缺少目录字段研究快照。", urgent=True))
            else:
                snapshot = Path(catalogue.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if source_hashes.get(snapshot) == catalogue.content_sha256:
                    if snapshot not in sinica_pages:
                        sinica_pages[snapshot] = json.loads(snapshot.read_text(encoding="utf-8"))
                    document = sinica_pages[snapshot]
                    rows = [row for row in document.get("entries", []) if row.get("id") == identifier]
                    group = document.get("group")
                    if len(rows) != 1 or group not in SINICA_GROUPS:
                        record["issues"].append(issue("source", "sinica_catalogue_record_missing", "目录快照中找不到唯一条目。", urgent=True))
                    else:
                        record["evidence"]["sinica_group"] = SINICA_GROUPS[group]
                        record["evidence"]["sinica_group_id"] = group
                        record["evidence"]["sinica_catalogue_label"] = rows[0]["label"]
                        if group == 1:
                            if snapshot.parent not in sinica_indexes:
                                try:
                                    sinica_indexes[snapshot.parent] = (load_sinica_snapshot(snapshot.parent)[0], None)
                                except (ValueError, OSError, TypeError, KeyError) as error:
                                    sinica_indexes[snapshot.parent] = (None, str(error))
                            index, error = sinica_indexes[snapshot.parent]
                            if index is None:
                                record["issues"].append(issue("source", "sinica_index_invalid", f"馆藏目录整体校验失败：{error}", urgent=True))
                            else:
                                count = index["group_counts"]["1"]
                                record["evidence"]["sinica_group_count"] = count
                                if count != 30:
                                    record["evidence"]["sinica_group_overview"] = "https://aya.ioe.sinica.edu.tw/index.php/Frontend/Sharer/1"
                                    record["issues"].append(issue("source", "sinica_group_count_difference",
                                        f"馆方介绍称马太安资料共 30 则，当前目录列出 {count} 条；两种计数口径须核对。"))
                        if group == 2:
                            record["evidence"]["sinica_group_audit_example"] = sinica_detail_url(97)
                            record["issues"].append(issue("source", "sinica_group_audit",
                                "该目录组的个别抽查详情页族别与目录组名不一致；不能据此判断本条，请逐条核对。"))
                        if metadata.title != rows[0]["label"]:
                            record["issues"].append(issue("source", "sinica_title_changed", "草稿题名与目录快照不符。", urgent=True))
            detail = next((source for source in metadata.sources if source.type == "sinica_detail_metadata"), None)
            if not detail:
                record["issues"].append(issue("source", "sinica_detail_unchecked",
                    "尚未整理单条详情的档号、角色和采集日期；请回查原站。"))
            elif detail.local_path and detail.content_sha256:
                snapshot = Path(detail.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if source_hashes.get(snapshot) == detail.content_sha256:
                    if snapshot not in sinica_details:
                        sinica_details[snapshot] = json.loads(snapshot.read_text(encoding="utf-8"))
                    document = sinica_details[snapshot]
                    fields = document.get("fields", {})
                    if document.get("id") != identifier or document.get("source_url") != sinica_detail_url(identifier) or not isinstance(fields, dict):
                        record["issues"].append(issue("source", "sinica_detail_invalid", "单条描述字段快照不符。", urgent=True))
                    else:
                        record["evidence"]["sinica_detail_fields"] = fields
                        variant = document.get("rights_notice_variant")
                        if variant not in (None, "original", "extra_de"):
                            record["issues"].append(issue("source", "sinica_rights_variant_invalid", "馆方使用声明的本地记录不明确，须回查。", urgent=True))
                        elif variant == "extra_de":
                            record["evidence"]["sinica_rights_notice_variant"] = "馆方声明在‘目的’后多一‘的’，仍写明非营利教育学术浏览及未经同意不得摘取出版。"
                            record["issues"].append(issue("source", "sinica_rights_notice_variant", "馆方使用声明有轻微字词差异，限制仍须依原页核查。"))
                        if not fields.get("檔案名稱"):
                            record["issues"].append(issue("source", "sinica_archive_id_missing", "详情未登记档案名称，请回查馆方记录。", urgent=True))
                        if not fields.get("族別"):
                            record["issues"].append(issue("source", "sinica_ethnicity_missing", "详情未登记族别，不能根据目录组代填。"))
                        label, description = record["evidence"].get("sinica_catalogue_label", ""), fields.get("說明", "")
                        if not description:
                            record["issues"].append(issue("source", "sinica_description_missing", "详情未登记说明题名，请回查原站。"))
                        elif label and not sinica_titles_match(label, description):
                            record["issues"].append(issue("source", "sinica_title_description_mismatch",
                                "目录题名与详情说明的文字未能对应，请核对记录身份与版本。", urgent=True))
                        group = record["evidence"].get("sinica_group_id")
                        expected = "阿美族" if group in (1, 2) else "雅美族" if group in SINICA_GROUPS else None
                        if expected and fields.get("族別") and fields["族別"] != expected:
                            record["issues"].append(issue("source", "sinica_tribe_conflict",
                                f"目录组标为{expected}，详情族别却标为{fields['族別']}；须回查原文与社区观点。", urgent=True))
                        if group == 2 and any(fields.get(role) and "黃貴潮" not in fields[role] for role in ("記音者", "翻譯者")):
                            record["evidence"]["sinica_group_overview"] = "https://aya.ioe.sinica.edu.tw/index.php/Frontend/Sharer/1"
                            record["issues"].append(issue("source", "sinica_credit_scope_conflict",
                                "项目概述称阿美诸部落资料由黃貴潮负责记音与翻译；详情所列角色不同，具体分工与归属待核。", urgent=True))
                        if not fields.get("報導人"):
                            record["issues"].append(issue("source", "sinica_reporter_missing", "详情未登记報導人，请核对馆方记录。"))
                        if not fields.get("記音者"):
                            record["issues"].append(issue("source", "sinica_transcriber_missing", "详情未登记記音者，请核对馆方记录。"))
                        if not fields.get("翻譯者"):
                            record["issues"].append(issue("source", "sinica_translator_missing", "详情未登记翻譯者，请核对馆方记录。"))
                        if not fields.get("採集日期"):
                            record["issues"].append(issue("source", "sinica_collection_date_missing", "详情未登记采集日期。"))
                        else:
                            raw_date = fields["採集日期"]
                            try:
                                collected = date.fromisoformat(raw_date)
                                if collected.isoformat() != raw_date:
                                    raise ValueError("非标准日期")
                            except ValueError:
                                record["issues"].append(issue("source", "sinica_collection_date_invalid",
                                    "采集日期不是有效的 YYYY-MM-DD 日期，保留原文并请回查。"))
                            else:
                                if group == 2 and not 1982 <= collected.year <= 1985:
                                    record["evidence"]["sinica_group_overview"] = "https://aya.ioe.sinica.edu.tw/index.php/Frontend/Sharer/1"
                                    record["issues"].append(issue("source", "sinica_project_date_scope",
                                        "阿美诸部落项目概述介绍 1982–1985 年采集，详情日期超出此范围；"
                                        "可能涉及后续采录或登记差异，须核对资料归属。"))
                        if not fields.get("採集地點"):
                            record["issues"].append(issue("coordinate", "sinica_collection_place_missing", "详情未登记采集地点。"))
                        if not sinica_fields_preserved(record["markdown"], fields):
                            record["issues"].append(issue("source", "sinica_fields_changed", "草稿未完整保留详情描述字段。", urgent=True))
            else:
                record["issues"].append(issue("source", "sinica_detail_invalid", "详情描述字段快照路径或哈希缺失。", urgent=True))
            gis_sources = [source for source in metadata.sources if source.type == "sinica_community_gis"]
            if gis_sources:
                source = gis_sources[0]
                if len(gis_sources) != 1 or not source.local_path or not source.content_sha256 or not source.url or str(source.url) != SINICA_GIS_URL:
                    record["issues"].append(issue("source", "sinica_gis_source_invalid", "社区 GIS 对照来源不唯一或地址无效。", urgent=True))
                else:
                    snapshot = Path(source.local_path)
                    if not snapshot.is_absolute():
                        snapshot = PROJECT_ROOT / snapshot
                    snapshot = snapshot.resolve()
                    if source_hashes.get(snapshot) == source.content_sha256:
                        if snapshot not in sinica_gis:
                            sinica_gis[snapshot] = load_sinica_gis(snapshot)
                        fields = record["evidence"].get("sinica_detail_fields")
                        if not isinstance(fields, dict):
                            record["issues"].append(issue("source", "sinica_gis_detail_missing", "无法核对 GIS 候选对应的原始采集地字段。", urgent=True))
                        else:
                            location = fields.get("採集地點", "")
                            choices = sinica_gis_candidates(location, sinica_gis[snapshot])
                            if not choices or source.locator != sinica_gis_locator(choices):
                                record["issues"].append(issue("coordinate", "sinica_gis_match_changed", "采集地与 GIS 地标候选不再对应，请重新核查。", urgent=True))
                            else:
                                record["evidence"]["sinica_community_candidates"] = choices
                                record["issues"].append(issue("coordinate", "sinica_community_point_unverified",
                                    "候选坐标是政府数据中的学校、道路等社区地标，非具体采录点或故事发生地；参考系和适用范围待核。"))
                                tribe = fields.get("族別", "").strip()
                                listed = [point["登记族别"].strip() for point in choices if point["登记族别"].strip()]
                                if tribe and listed and all(tribe not in value and value not in tribe for value in listed):
                                    record["issues"].append(issue("source", "sinica_community_ethnicity_disagreement",
                                        "详情族别与政府 GIS 的社区族别登记不同；社区登记不等于个人身份，须回查原始资料和社区观点。", urgent=True))
                                if len(choices) > 1:
                                    record["issues"].append(issue("coordinate", "sinica_community_point_ambiguous", "采集地文字对应多个社区地标；不能自动选点。", urgent=True))
                                if not json_block_preserved(record["markdown"], {"館方採集地點": location, "社区地标候选": choices}):
                                    record["issues"].append(issue("source", "sinica_gis_note_changed", "草稿中的社区地标对照与快照不符。", urgent=True))
        match = re.fullmatch(r"case_vietnam_cham_(\d{3})", metadata.id)
        if match or metadata.id == "corpus_vietnam_cham_folktales":
            record["issues"].append(issue("source", "vietnam_cham_rights_scope",
                "馆方开放教育和研究使用、禁止商业使用；具体转载许可与社区权益仍须核查。", urgent=True))
        if match:
            number = int(match.group(1))
            record["issues"].append(issue("source", "vietnam_cham_original_remote",
                "本地仅存目录和详情字段；越南文全文请通过单篇原站链接查看。"))
            record["issues"].append(issue("source", "vietnam_cham_origin_unverified",
                "前言汇总两类来源，但尚未将本条对应到具体原材料、讲述者或采录者。"))
            record["issues"].append(issue("source", "vietnam_cham_language_scope",
                "当前是越南文选集版本；不能将其自动视为占语原文或未经编辑的口述记录。"))
            record["issues"].append(issue("coordinate", "vietnam_cham_collection_scope",
                "选集涉及的地区不能直接当作本篇采录地或故事发生地。"))
            catalogue = next((source for source in metadata.sources if source.type == "vietnam_cham_catalogue"), None)
            story = next((source for source in metadata.sources if source.type == "vietnam_cham_story"), None)
            if not catalogue or not catalogue.local_path or not catalogue.content_sha256 or not catalogue.url or str(catalogue.url) != VIETNAM_CHAM_INTRO:
                record["issues"].append(issue("source", "vietnam_cham_catalogue_invalid", "缺少有效的选集目录与本地字段快照。", urgent=True))
            else:
                snapshot = Path(catalogue.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if source_hashes.get(snapshot) == catalogue.content_sha256:
                    if snapshot not in vietnam_cham_catalogues:
                        vietnam_cham_catalogues[snapshot] = json.loads(snapshot.read_text(encoding="utf-8"))
                    document = vietnam_cham_catalogues[snapshot]
                    fields, entries = document.get("catalogue_fields"), document.get("entries")
                    rows = [row for row in entries if row.get("number") == number] if isinstance(entries, list) else []
                    if (document.get("source_url") != VIETNAM_CHAM_INTRO or not isinstance(fields, dict)
                            or fields.get("Access Condition") != VIETNAM_CHAM_RIGHTS or fields.get("Languages") != "Vietnamese"
                            or len(rows) != 1):
                        record["issues"].append(issue("source", "vietnam_cham_catalogue_invalid", "目录编号、语言或使用条件与快照不符。", urgent=True))
                    else:
                        record["evidence"]["vietnam_cham_catalogue"] = rows[0]
                        record["evidence"]["vietnam_cham_book_fields"] = fields
                        record["evidence"]["vietnam_cham_preface"] = {"signatory": document.get("preface_signatory"),
                            "date_as_written": document.get("preface_date_as_written")}
                        if metadata.title != f"越南占族故事选集 · {rows[0]['title']}":
                            record["issues"].append(issue("source", "vietnam_cham_title_changed", "草稿题名与目录快照不符。", urgent=True))
            if not story or not story.local_path or not story.content_sha256 or not story.url or str(story.url) != vietnam_cham_story_url(number):
                record["issues"].append(issue("source", "vietnam_cham_story_invalid", "缺少与编号对应的单篇链接和字段快照。", urgent=True))
            else:
                snapshot = Path(story.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if source_hashes.get(snapshot) == story.content_sha256:
                    if snapshot not in vietnam_cham_details:
                        vietnam_cham_details[snapshot] = json.loads(snapshot.read_text(encoding="utf-8"))
                    document = vietnam_cham_details[snapshot]
                    title, paragraphs, chars = document.get("detail_title"), document.get("paragraph_count"), document.get("text_characters")
                    if (document.get("number") != number or document.get("source_url") != vietnam_cham_story_url(number)
                            or not isinstance(title, str) or not title.strip() or type(paragraphs) is not int or paragraphs < 0
                            or type(chars) is not int or chars < 0 or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("raw_sha256", "")))):
                        record["issues"].append(issue("source", "vietnam_cham_story_invalid", "单篇字段快照的编号、标题或正文状态不符。", urgent=True))
                    else:
                        record["evidence"]["vietnam_cham_story"] = {key: document.get(key) for key in
                            ("number", "catalogue_title", "detail_title", "paragraph_count", "text_characters", "heading_text_with_notes",
                             "heading_note_markers", "raw_sha256", "retrieved_at")}
                        row = record["evidence"].get("vietnam_cham_catalogue", {})
                        if row and (document.get("catalogue_title") != row.get("title") or title != row.get("title")):
                            record["issues"].append(issue("source", "vietnam_cham_heading_mismatch", "目录与单篇标题不一致，须回查原站。", urgent=True))
                        if not paragraphs or not chars:
                            record["issues"].append(issue("source", "vietnam_cham_text_unavailable", "单篇页面未检测到正文段落，请回查原站。", urgent=True))
                        markers = document.get("heading_note_markers")
                        if markers:
                            record["issues"].append(issue("source", "vietnam_cham_heading_footnote",
                                "单篇标题旁有脚注按钮；标记已与标题分开，脚注具体内容尚待回查。"))
                        book = record["evidence"].get("vietnam_cham_book_fields", {})
                        expected = {"目录序号": number, "目录越南文题名": document.get("catalogue_title"), "详情页题名": title,
                                    "详情页可见段落数": paragraphs, "标题脚注标记": markers if markers is not None else "未单独提取",
                                    "书目 Date Created": book.get("Date Created"),
                                    "馆方贡献者字段": book.get("Authors"), "出版者字段": book.get("Publisher"), "语言字段": book.get("Languages")}
                        if book and not json_block_preserved(record["markdown"], expected):
                            record["issues"].append(issue("source", "vietnam_cham_fields_changed", "草稿的书目或单篇字段与来源快照不符。", urgent=True))
        pangloss_match = re.fullmatch(r"case_cn_yongning_na_(\d{7})", metadata.id)
        if (pangloss_match and not any(source.type in (NA_CANDIDATE_MARKER, NA_TONE_NEW_MARKER) for source in metadata.sources)) or metadata.id == PANGLOSS_NA_ROOT:
            record["issues"].append(issue("source", "pangloss_selection_scope",
                "按馆方题名选取的比较样本；不等于全部录音、全部纳语叙事或随机样本。"))
            record["issues"].append(issue("source", "pangloss_audio_not_copied",
                "本地保留目录和详情网页；音频与转写正文未复制，须回查馆方单条页面。"))
            record["issues"].append(issue("source", "pangloss_roles_and_context",
                "馆方的研究者与讲述者字段分别保留；多种姓名写法及社区背景须核对。"))
            record["issues"].append(issue("source", "pangloss_comparison_unverified",
                "同题对照只是研究线索，不证明同一次演述、同源或历史传播。"))
            record["issues"].append(issue("coordinate", "pangloss_place_unverified",
                "馆方录音地点和行政名称须核对；采录地也不等于叙事发生地。"))
            if not any(metadata.standards.model_dump().values()):
                record["issues"].append(issue("standard", "pangloss_codes_unassigned",
                    "尚未根据原文及本地码表确认故事类型或母题标准码，暂时留空。"))
            else:
                record["issues"].append(issue("standard", "pangloss_codes_need_context",
                    "请核对所填标准码与录音、类型定义和本地码表的对应依据。"))
            if metadata.spatial and metadata.spatial.lat is not None:
                record["issues"].append(issue("coordinate", "pangloss_coordinates_unverified", "录音的图谱坐标缺少独立核验依据。", urgent=True))
            catalogue = next((item for item in metadata.sources if item.type == "pangloss_na_catalogue"), None)
            selection = next((item for item in metadata.sources if item.type == "pangloss_na_selection"), None)
            detail = next((item for item in metadata.sources if item.type == "pangloss_na_detail"), None)
            if (not catalogue or not selection or not catalogue.local_path or not selection.local_path
                    or not catalogue.content_sha256 or not selection.content_sha256 or not catalogue.url or not selection.url
                    or str(catalogue.url) != PANGLOSS_NA_URL or str(selection.url) != PANGLOSS_NA_URL
                    or (pangloss_match and (not detail or not detail.local_path or not detail.content_sha256 or not detail.url))):
                record["issues"].append(issue("source", "pangloss_source_missing", "缺少可核验的目录、选取索引或单条详情。", urgent=True))
            else:
                paths = [Path(catalogue.local_path), Path(selection.local_path)]
                if pangloss_match:
                    paths.append(Path(detail.local_path))
                paths = [(p if p.is_absolute() else PROJECT_ROOT / p).resolve() for p in paths]
                expected_hashes = [catalogue.content_sha256, selection.content_sha256] + ([detail.content_sha256] if pangloss_match else [])
                if all(source_hashes.get(path) == expected for path, expected in zip(paths, expected_hashes, strict=True)):
                    try:
                        if paths[0] not in pangloss_catalogues:
                            pangloss_catalogues[paths[0]] = pangloss_catalogue_rows(paths[0].read_bytes())
                        if paths[1] not in pangloss_selections:
                            pangloss_selections[paths[1]] = load_pangloss_selection(paths[1])
                        rows, selected = pangloss_catalogues[paths[0]], pangloss_selections[paths[1]]
                        if pangloss_match:
                            number = pangloss_match.group(1)
                            if 'selected_titles' in selected:
                                previous = [item for item in metadata.sources if item.type == 'pangloss_na_context_previous']
                                manifest = [item for item in metadata.sources if item.type == 'pangloss_na_context_manifest']
                                if (len(previous)!=1 or len(manifest)!=1 or not all(item.local_path and item.content_sha256
                                        and item.url and str(item.url)==PANGLOSS_NA_URL for item in previous+manifest)):
                                    raise ValueError('口述背景补充缺少首轮选取或详情清单')
                                context_paths=[Path(previous[0].local_path),Path(manifest[0].local_path)]
                                context_paths=[(path if path.is_absolute() else PROJECT_ROOT/path).resolve() for path in context_paths]
                                if any(source_hashes.get(path)!=item.content_sha256 for path,item in zip(context_paths,previous+manifest,strict=True)):
                                    raise ValueError('口述背景补充来源哈希不符')
                                key=tuple(paths[:2]+context_paths)
                                if key not in pangloss_contexts:
                                    if context_paths[1].name!='manifest.json':raise ValueError('详情清单路径不符')
                                    validate_pangloss_na_context(paths[0],context_paths[0],paths[1])
                                    _,_,context_details=load_pangloss_snapshots(context_paths[1].parent,paths[0],paths[1])
                                    pangloss_contexts[key]=context_details
                                if number not in pangloss_contexts[key] or paths[2]!=(context_paths[1].parent/'records'/number/'page.html').resolve():
                                    raise ValueError('单条详情不属于补充快照清单')
                                record['issues'].append(issue('classification','pangloss_na_context_not_story',
                                    '本批包括仪式访谈、口述背景与歌曲；一条录音不自动等于一则神话或故事。'))
                            group = next((g for g in selected["groups"] if number in g["ids"]), None)
                            if not group or number not in rows:
                                raise ValueError("录音不在目录或选取清单中")
                            row = rows[number]
                            fields = pangloss_detail_fields(paths[2].read_bytes(), row)
                            if (str(detail.url) != row["url"] or detail.locator != f"录音 {number}"
                                    or detail.doi != row["doi"].removeprefix("https://doi.org/")
                                    or catalogue.locator != f"Yongning Na / DOI {number}" or selection.locator != group["label"]):
                                raise ValueError("录音链接、DOI 或定位符与来源不符")
                            data = pangloss_evidence(row, fields, group)
                            record["evidence"]["pangloss_na"] = data
                            if (row["title"] not in metadata.aliases or metadata.title != f"永宁纳语录音 · {row['title']}"
                                    or not json_block_preserved(record["markdown"], data)):
                                record["issues"].append(issue("source", "pangloss_fields_changed", "草稿字段与馆方元数据不一致。", urgent=True))
                            if data["两处日期是否一致"] is not True:
                                record["issues"].append(issue("source", "pangloss_date_needs_review", "目录与详情的录音日期不一致或无法比较。", urgent=True))
                            if re.fullmatch(r"\d{4}", row["recorded"] or ""):
                                record["issues"].append(issue("source", "pangloss_date_year_only", "目录录音日期只精确到年份，月日须回查。"))
                            if data["两处讲述者字段显示是否对应"] is False or data["两处研究者字段显示是否对应"] is False:
                                record["issues"].append(issue("source", "pangloss_credits_conflict", "目录与详情的讲述者或研究者字段不一致，须逐项核查。", urgent=True))
                            if not fields["speakers"]:
                                record["issues"].append(issue("source", "pangloss_speaker_missing", "单条详情未列讲述者，须回查。", urgent=True))
                            if not fields["license"]:
                                record["issues"].append(issue("source", "pangloss_license_missing", "单条详情未列许可，须回查。", urgent=True))
                            else:
                                record["issues"].append(issue("source", "pangloss_license_per_record", "音频与转写的使用须逐条核对详情许可及相关社区要求。"))
                            if not row["transcription_icon"]:
                                record["issues"].append(issue("source", "pangloss_transcription_not_shown", "目录未显示转写图标；不据此断言转写不存在。"))
                            indexed = [source for source in metadata.sources if source.type == "pangloss_annotation_index"]
                            if indexed:
                                if (len(indexed) != 1 or not indexed[0].local_path or not indexed[0].content_sha256
                                        or not indexed[0].url or str(indexed[0].url) != row["url"]
                                        or indexed[0].locator != f"录音 {number} / 关联资源与分句"):
                                    record["issues"].append(issue("source", "pangloss_annotation_source_invalid", "分句索引来源与录音不符。", urgent=True))
                                else:
                                    source = indexed[0]
                                    index_path = Path(source.local_path)
                                    if not index_path.is_absolute():
                                        index_path = PROJECT_ROOT / index_path
                                    index_path = index_path.resolve()
                                    if source_hashes.get(index_path) == source.content_sha256:
                                        index = read_pangloss_annotation_index(index_path, {
                                            "id": number, "primary_oai": pangloss_primary_oai(row["url"]),
                                            "detail_sha256": detail.content_sha256,
                                            "catalogue_transcription_icon": row["transcription_icon"]})
                                        summary = pangloss_annotation_summary(index)
                                        if PANGLOSS_ANNOTATION_MARKER not in record["markdown"] or not json_block_preserved(record["markdown"], summary):
                                            record["issues"].append(issue("source", "pangloss_annotation_fields_changed", "草稿的资源与分句摘要与结构索引不符。", urgent=True))
                                        annotations = []
                                        for resource in index["resources"]:
                                            for annotation in resource["annotations"]:
                                                annotations.append({**annotation, "primary_oai": resource["oai"],
                                                                    "primary_license": resource["primary_license"]})
                                        record["evidence"]["pangloss_annotation_summary"] = summary
                                        record["evidence"]["pangloss_annotations"] = annotations
                                        record["evidence"]["pangloss_annotation_observed_at"] = index["observed_at"]
                                        record["issues"].append(issue("source", "pangloss_annotation_hash_scope",
                                            "只保存结构索引；原始接口响应及转写正文未保存，响应哈希无法离线重算。"))
                                        if annotations:
                                            record["issues"].append(issue("source", "pangloss_annotation_license_unverified",
                                                "附件或转写的单独许可和社区要求尚未核明；主音视频许可不自动覆盖附件。"))
                                        else:
                                            record["issues"].append(issue("source", "pangloss_no_annotation_returned",
                                                "本次接口未返回关联附件；不能据此认定其他版本不存在。"))
                            place = fields["recording_location"] or ""
                            if 'selected_titles' in selected and re.search(r"\bSichuan\b|四川", place, re.IGNORECASE):
                                record["issues"].append(issue("coordinate", "pangloss_na_context_sichuan_recording",
                                    "馆方详情的录音地点原字段写在四川；须与馆藏语言范围、行政名称和叙事地点分别核对。", urgent=True))
                            if re.search(r"(?:comté de|county of) Yongning|Yongning County", place, re.IGNORECASE):
                                record["issues"].append(issue("coordinate", "pangloss_administrative_label",
                                    "馆方原地点写作 Yongning County；研究者其他资料采用宁蒗县永宁乡称谓，二者对应和时点待核。"))
                                record["evidence"]["pangloss_location_context"] = {
                                    "url": PANGLOSS_LOCATION_PAPER,
                                    "citation": "Alexis Michaud，2008 年永宁纳语语音研究，田野地点脚注。",
                                    "note": "该论文描述研究者 2006–2008 年的一处田野地点，不自动证明它与本条录音地点相同。"}
                        elif catalogue.locator != "Yongning Na / 资源目录" or selection.locator != "目的性题名选取 / 对照分组":
                            raise ValueError("资料组定位符不符")
                    except (ValueError, KeyError, OSError, TypeError) as error:
                        record["issues"].append(issue("source", "pangloss_snapshot_invalid", f"Pangloss 馆藏元数据无法核验：{error}", urgent=True))
        if metadata.id == SIL_ROOT_ID or metadata.id in {"case_ph_ilianen_pilanduk", "case_ph_ilianen_tulalang"}:
            record["issues"].append(issue("source", "sil_sample_not_complete",
                "馆方提供录音样本；完整数字录音需按馆方说明申请在马尼拉档案现场收听。"))
            record["issues"].append(issue("source", "sil_rights_community_unverified",
                "音频与转写本的再利用许可及相关社区要求尚待核对。", urgent=True))
            record["issues"].append(issue("source", "sil_audio_transcript_not_copied",
                "本地只保存馆方目录网页，未复制录音样本、完整音频或转写正文。"))
            record["issues"].append(issue("source", "sil_recording_date_not_event",
                "1976 年是馆方列出的录音日期，不能自动作为故事发生年代。"))
            record["issues"].append(issue("coordinate", "sil_recording_place_unknown",
                "馆方介绍研究者曾在北哥打巴托居住，并未指出该样本的具体录音点。"))
            if metadata.spatial and metadata.spatial.lat is not None:
                record["issues"].append(issue("coordinate", "sil_unverified_coordinates", "本样本具体录音地点未知，请核对坐标依据。", urgent=True))
            source = next((item for item in metadata.sources if item.type == "sil_ilianen_catalogue"), None)
            if not source or not source.local_path or not source.content_sha256 or not source.url or str(source.url) != SIL_SOURCE_URL:
                record["issues"].append(issue("source", "sil_catalogue_missing", "缺少可核验的 SIL 原录音目录。", urgent=True))
            else:
                snapshot = Path(source.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if source_hashes.get(snapshot) == source.content_sha256:
                    try:
                        if snapshot not in sil_catalogues:
                            sil_catalogues[snapshot] = parse_sil_catalogue(snapshot)
                        if metadata.id == SIL_ROOT_ID:
                            if source.locator != "录音样本及现场访问说明":
                                raise ValueError("馆藏组定位符不符")
                        else:
                            data = sil_catalogues[snapshot].get(metadata.id)
                            if not data or source.locator != data["馆方题名"]:
                                raise ValueError("样本编号或定位符不符")
                            record["evidence"]["sil_ilianen"] = data
                            if (data["馆方题名"] not in metadata.aliases or data["馆方英文题名"] not in metadata.aliases
                                    or not json_block_preserved(record["markdown"], data)):
                                record["issues"].append(issue("source", "sil_fields_changed", "草稿字段与馆方目录不一致。", urgent=True))
                            record["issues"].append(issue("source", "sil_transcription_unchecked",
                                "馆方列出印刷转写本；具体页码、正文及其与音频样本的对应尚未核查。"))
                    except (ValueError, KeyError, OSError, TypeError) as error:
                        record["issues"].append(issue("source", "sil_catalogue_invalid", f"SIL 馆方目录无法核验：{error}", urgent=True))
        hmml_match = re.fullmatch(r"corpus_hmml_makassar_(\d{5})", metadata.id)
        if hmml_match or metadata.id == HMML_ROOT_ID:
            record["issues"].append(issue("source", "hmml_stub_catalogue",
                "现行馆方数据为未完成编目的馆藏条目，不含旧目录中的题名或正文。", urgent=True))
            record["issues"].append(issue("source", "hmml_legacy_uncached",
                "旧目录字段来自搜索索引；旧站当次不可直接访问，本地字段索引不是原网页快照。", urgent=True))
            record["issues"].append(issue("source", "hmml_images_not_copied",
                "未复制手稿影像或正文；开放查看标志及图像再利用权限需逐件回查。"))
            record["issues"].append(issue("source", "hmml_dates_and_genre_unverified",
                "旧目录所列抄写日期不是叙事发生日期；题名、作者、语种及体裁均须核验。"))
            record["issues"].append(issue("coordinate", "hmml_holding_not_recording",
                "望加锡是馆藏地；不能自动作为文本采录、创作或叙事地点。"))
            if metadata.spatial and metadata.spatial.lat is not None:
                record["issues"].append(issue("coordinate", "hmml_unverified_coordinates",
                    "该候选缺少采录或叙事地点的坐标依据，请核查所填坐标。", urgent=True))
            current = next((item for item in metadata.sources if item.type == "hmml_makassar_metadata"), None)
            legacy_source = next((item for item in metadata.sources if item.type == "hmml_legacy_candidate"), None)
            if not current or not current.local_path or not current.content_sha256 or not current.url or not legacy_source or not legacy_source.local_path or not legacy_source.content_sha256 or not legacy_source.url:
                record["issues"].append(issue("source", "hmml_source_missing", "缺少当前元数据或旧目录候选来源。", urgent=True))
            else:
                snapshot = Path(current.local_path)
                legacy_path = Path(legacy_source.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                if not legacy_path.is_absolute():
                    legacy_path = PROJECT_ROOT / legacy_path
                snapshot, legacy_path = snapshot.resolve(), legacy_path.resolve()
                if source_hashes.get(snapshot) == current.content_sha256 and source_hashes.get(legacy_path) == legacy_source.content_sha256:
                    try:
                        if snapshot.name != "records.jsonl":
                            raise ValueError("当前馆藏选取路径不符")
                        if snapshot not in hmml_selections:
                            hmml_selections[snapshot] = load_hmml_selection(snapshot.parent)
                        if legacy_path not in hmml_legacy_indexes:
                            hmml_legacy_indexes[legacy_path] = load_hmml_legacy(legacy_path)
                        selection, items = hmml_selections[snapshot]
                        legacy = hmml_legacy_indexes[legacy_path]
                        entry = (next((e for e in legacy["entries"] if e["project"].endswith(hmml_match.group(1))), None)
                                 if hmml_match else legacy["entries"][0])
                        if not entry or entry["project"] not in items:
                            raise ValueError("旧目录档号不在馆方数据中")
                        item = items[entry["project"]]
                        expected_url = item["PURL"] if hmml_match else HMML_DATASET_PAGE
                        expected_locator = entry["project"] if hmml_match else "DS 0045 馆藏元数据选取"
                        if (str(current.url) != expected_url or current.locator != expected_locator
                                or str(legacy_source.url) != HMML_LEGACY + str(entry["legacy_id"])
                                or legacy_source.locator != entry["project"]):
                            raise ValueError("馆方或旧目录链接与档号不符")
                        record["evidence"]["hmml_selection_count"] = selection["count"]
                        if hmml_match:
                            details = hmml_evidence(item, entry, legacy)
                            record["evidence"]["hmml_makassar"] = details
                            expected_title = f"望加锡手稿 · {entry['project']}"
                            if (metadata.title != expected_title or entry["native_title"] not in metadata.aliases
                                    or entry["roman_title"] not in metadata.aliases
                                    or not json_block_preserved(record["markdown"], details)):
                                record["issues"].append(issue("source", "hmml_fields_changed",
                                    "草稿中的馆方元数据或旧目录候选字段与登记不一致。", urgent=True))
                    except (ValueError, KeyError, OSError, TypeError) as error:
                        record["issues"].append(issue("source", "hmml_selection_invalid", f"馆藏选取无法核验：{error}", urgent=True))
        shandong_case = bool(re.fullmatch(r"case_cn_sd_[a-z0-9_]+_\d{2}", metadata.id))
        shandong_corpus = bool(re.fullmatch(r"corpus_cn_sd_[a-z0-9_]+_mirror", metadata.id))
        if shandong_case or shandong_corpus:
            record["issues"].append(issue("source", "shandong_mirror_unverified",
                "这是网站自称的方志镜像转录；纸本原书和转录准确性尚未核验。", urgent=True))
            record["issues"].append(issue("source", "shandong_rights_unverified",
                "镜像说明仅供学习、研究和检索；原作及镜像文字的转载许可待核。", urgent=True))
            record["issues"].append(issue("source", "shandong_index_not_snapshot",
                "本地 SHA-256 只校验研究字段索引，不是网页原响应或原书的哈希。"))
            record["issues"].append(issue("coordinate", "shandong_county_scope",
                "方志行政范围不是本篇采录点；叙事地点及历史事件仍需独立证据。"))
            source = next((item for item in metadata.sources if item.type == "shandong_mirror_index"), None)
            if not source or not source.local_path or not source.content_sha256 or not source.url:
                record["issues"].append(issue("source", "shandong_index_invalid", "缺少镜像链接或本地字段索引。", urgent=True))
            else:
                snapshot = Path(source.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if source_hashes.get(snapshot) == source.content_sha256:
                    try:
                        if snapshot not in shandong_indexes:
                            data = load_shandong_index(snapshot)
                            lookup = {}
                            for page in data["pages"]:
                                lookup[page["corpus_id"]] = (page, None)
                                lookup.update({story["id"]: (page, story) for story in page["stories"]})
                            shandong_indexes[snapshot] = lookup
                        selected = shandong_indexes[snapshot].get(metadata.id)
                        if not selected:
                            raise ValueError("索引缺少对应条目")
                        page, story = selected
                        expected_locator = (f"{page['section']} / {story['title']}" if story else
                                            f"{page['section']} / {len(page['stories'])} 条所选题名")
                        expected_title = (f"山东方志镜像 · {story['title']}" if story else
                                          f"山东地方志镜像 · 《{page['book']}》")
                        if str(source.url) != page["url"] or source.locator != expected_locator or metadata.title != expected_title:
                            raise ValueError("链接、定位符或题名与索引不一致")
                        if story:
                            evidence = shandong_story_evidence(page, story)
                            record["evidence"]["shandong_mirror"] = evidence
                            if not json_block_preserved(record["markdown"], evidence):
                                record["issues"].append(issue("source", "shandong_fields_changed", "草稿字段与本地研究索引不一致。", urgent=True))
                            record["issues"].append(issue("source", "shandong_original_remote",
                                "故事全文未复制；请在镜像共享章节中按题名查找并回查原书。"))
                            if not story.get("narrator_candidate"):
                                record["issues"].append(issue("source", "shandong_narrator_missing", "单篇未见讲述人署名，不能将作者或汇编者自动当作讲述人。"))
                            else:
                                record["issues"].append(issue("source", "shandong_narrator_candidate", "讲述人与整理人的候选署名来自镜像，须对照原书。"))
                            if story.get("author_candidate"):
                                record["issues"].append(issue("source", "shandong_author_role", "镜像署作者；不能自动判定其为口述讲述人。"))
                            if "删改" in (story.get("prior_source_claim") or ""):
                                record["issues"].append(issue("source", "shandong_edited_version", "镜像注明收入时有删改；须对照早期版本。"))
                            if story.get("bibliography_note"):
                                record["issues"].append(issue("source", "shandong_related_bibliography",
                                    "另有相近题名的1988年书目；与镜像所称2008年书目是否相关尚未确定。", urgent=True))
                                if not any(item.type == "shandong_bibliography_index" and item.url and str(item.url) == story["bibliography_url"]
                                           for item in metadata.sources):
                                    record["issues"].append(issue("source", "shandong_bibliography_missing", "相关书目对照缺少论文链接。", urgent=True))
                    except (ValueError, KeyError, OSError, TypeError) as error:
                        record["issues"].append(issue("source", "shandong_index_invalid", f"镜像索引无法核验：{error}", urgent=True))
        match = re.fullmatch(r"case_cn_yuhuan_2008_p(\d{3})", metadata.id)
        index_source = next((source for source in metadata.sources if source.type == "yuhuan_index"), None)
        scan = next((source for source in metadata.sources if source.type == "yuhuan_scan"), None)
        if match:
            record["issues"].append(issue("source", "yuhuan_scan_only",
                "这是扫描影像的目录卡，尚无正文转录；请回查原页。"))
            if "PDF 解析器报告" in record["markdown"]:
                record["issues"].append(issue("source", "yuhuan_pdf_structure_warning",
                    "原扫描的 PDF 对象引用或结构存在解析警告；请用其他查看器核对原页是否完整。", urgent=True))
            record["issues"].append(issue("source", "yuhuan_rights_unverified",
                "选辑和数字影像的再利用许可尚未确认。"))
            record["issues"].append(issue("coordinate", "yuhuan_collection_scope",
                "玉环是选辑范围；流传区域、具体采录地点及故事地点须分别核对。"))
            if not index_source or not index_source.local_path or not index_source.content_sha256 or not scan:
                record["issues"].append(issue("source", "yuhuan_source_missing", "目录转记或扫描来源缺失。", urgent=True))
            else:
                snapshot = Path(index_source.local_path)
                if not snapshot.is_absolute():
                    snapshot = PROJECT_ROOT / snapshot
                snapshot = snapshot.resolve()
                if source_hashes.get(snapshot) == index_source.content_sha256:
                    if snapshot not in yuhuan_indexes:
                        try:
                            yuhuan_indexes[snapshot] = (read_yuhuan_index(snapshot), None)
                        except (ValueError, OSError, TypeError, KeyError) as error:
                            yuhuan_indexes[snapshot] = (None, str(error))
                    index, error = yuhuan_indexes[snapshot]
                    if index is None:
                        record["issues"].append(issue("source", "yuhuan_index_invalid", f"目录转记无法读取：{error}", urgent=True))
                    else:
                        page = int(match.group(1))
                        row = next((entry for entry in index["entries"] if entry["page"] == page), None)
                        if not row:
                            record["issues"].append(issue("source", "yuhuan_entry_missing", "目录转记没有此印刷页条目。", urgent=True))
                        else:
                            record["evidence"]["yuhuan_index"] = row
                            record["evidence"]["yuhuan_pdf_page"] = yuhuan_pdf_page(page)
                            if row["title"] not in [metadata.title, *metadata.aliases]:
                                record["issues"].append(issue("source", "yuhuan_title_changed", "卡片未保留目录转记标题。", urgent=True))
                            expected = f"{YUHUAN_PDF_URL}#page={yuhuan_pdf_page(page)}"
                            if str(scan.url) != expected or scan.content_sha256 != index["pdf_sha256"]:
                                record["issues"].append(issue("source", "yuhuan_locator_mismatch", "扫描链接、页码或来源哈希与目录不一致。", urgent=True))
                            if row.get("title_note"):
                                record["issues"].append(issue("source", "yuhuan_title_uncertain", row["title_note"], urgent=True))
                            if row.get("online_source"):
                                record["issues"].append(issue("source", "yuhuan_version_comparison",
                                    "同题网页版本与选辑的文字有差异，须比较出处和底本，不能自动视为同次采录。"))
                            supplemental = None
                            supplemental_source = next((source for source in metadata.sources if source.type == "yuhuan_credit_supplement"), None)
                            if supplemental_source and supplemental_source.local_path and supplemental_source.content_sha256 and scan.local_path:
                                extra_path = Path(supplemental_source.local_path)
                                pdf_path = Path(scan.local_path)
                                if not extra_path.is_absolute():
                                    extra_path = PROJECT_ROOT / extra_path
                                if not pdf_path.is_absolute():
                                    pdf_path = PROJECT_ROOT / pdf_path
                                extra_path, pdf_path = extra_path.resolve(), pdf_path.resolve()
                                if source_hashes.get(extra_path) == supplemental_source.content_sha256:
                                    key = (extra_path, snapshot, pdf_path)
                                    if key not in yuhuan_supplements:
                                        try:
                                            yuhuan_supplements[key] = (read_yuhuan_supplement(extra_path, snapshot, pdf_path), None)
                                        except (ValueError, OSError, TypeError, KeyError) as error:
                                            yuhuan_supplements[key] = (None, str(error))
                                    extra, error = yuhuan_supplements[key]
                                    if extra is None:
                                        record["issues"].append(issue("source", "yuhuan_supplement_invalid", f"旁注补充无法核验：{error}", urgent=True))
                                    else:
                                        supplemental = next((entry for entry in extra["entries"] if entry["page"] == page), None)
                                        if supplemental is None:
                                            record["issues"].append(issue("source", "yuhuan_supplement_missing", "旁注补充索引缺少本条页码。", urgent=True))
                                        else:
                                            record["evidence"]["yuhuan_credit_supplement"] = supplemental
                                            if any(value not in record["markdown"] for value in supplemental["credits"]):
                                                record["issues"].append(issue("source", "yuhuan_supplement_changed", "草稿旁注与补充索引不一致，请逐项核对。", urgent=True))
                                            if supplemental.get("prior_publication"):
                                                record["issues"].append(issue("source", "yuhuan_prior_version_unchecked",
                                                    "早期刊载信息来自选辑旁注，尚未核对该版本原件。"))
                                                if supplemental["prior_publication"] not in record["markdown"]:
                                                    record["issues"].append(issue("source", "yuhuan_supplement_changed", "草稿早期刊载线索与补充索引不一致。", urgent=True))
                                            for number in supplemental["credit_pages"]:
                                                expected_page = f"{YUHUAN_PDF_URL}#page={yuhuan_pdf_page(number)}"
                                                if not any(item.type == "yuhuan_scan" and item.url and str(item.url) == expected_page for item in metadata.sources):
                                                    record["issues"].append(issue("source", "yuhuan_credit_page_missing", "缺少旁注扫描页链接。", urgent=True))
                                                    break
                                            if supplemental.get("conflict"):
                                                record["issues"].append(issue("source", "yuhuan_credit_conflict", supplemental["conflict"], urgent=True))
                                            if supplemental.get("note"):
                                                record["issues"].append(issue("source", "yuhuan_credit_note", supplemental["note"], urgent=True))
                                            if supplemental.get("online_source"):
                                                online = supplemental["online_source"]
                                                record["issues"].append(issue("source", "yuhuan_version_comparison", online["note"]))
                                                if not any(item.type == "yuhuan_web_candidate" and item.url and str(item.url) == online["url"]
                                                           and item.content_sha256 == online["sha256"] for item in metadata.sources):
                                                    record["issues"].append(issue("source", "yuhuan_web_source_missing", "网页对照的链接或快照哈希不符。", urgent=True))
                            if row.get("credits") or supplemental:
                                record["issues"].append(issue("source", "yuhuan_credit_unverified", "已摘录采录旁注候选；请对照扫描件逐字核对。"))
                            else:
                                record["issues"].append(issue("source", "yuhuan_credit_missing", "尚未摘录讲述者、记录者及流传区域，请检查条目末尾。"))
        records.append(record)
    reviewed, problems = reviewed_heritage_projects(vault)
    compare_heritage_projects(records, reviewed, problems)
    return records


def cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "@")) or (text.startswith("-") and not re.fullmatch(r"-\d+(\.\d+)?", text)):
        return "'" + text
    return text


def csv_content(rows: list[dict], columns: list[str]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({key: cell(row.get(key)) for key in columns} for row in rows)
    return stream.getvalue().encode("utf-8-sig")


def scottish_coordinate_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        evidence = record["evidence"]
        accused = evidence.get("WDB_Accused")
        if not accused:
            continue
        comparison = evidence.get("wikidata_identity", {})
        old = evidence.get("original_generated_spatial") or {}
        current = record["spatial"] or {}
        candidates = comparison.get("map_candidates", [])
        distances = [candidate["distance_km"] for candidate in candidates if "distance_km" in candidate]
        issues = [flag["description"] for flag in record["issues"] if flag["category"] in {"coordinate", "source"}]
        rows.append({
            "档号": accused["AccusedRef"], "姓名": record["title"], "原登记住地": accused.get("Res_settlement"),
            "原登记郡": accused.get("Res_county"), "教区": evidence.get("parish", {}).get("Parish_Name"),
            "原格网字母": accused.get("Res_NGR_Letters"), "原格网东距": accused.get("Res_NGR_Easting"),
            "原格网北距": accused.get("Res_NGR_Northing"), "原生成纬度": old.get("lat"), "原生成经度": old.get("lng"),
            "原生成方法": evidence.get("location_method"), "当前草稿纬度": current.get("lat"), "当前草稿经度": current.get("lng"),
            "Wikidata实体": " | ".join(entity["url"] for entity in comparison.get("entities", [])),
            "同实体其他档号": " | ".join(ref for entity in comparison.get("entities", []) for ref in entity["other_survey_ids"]),
            "地图候选点": " | ".join(f"{candidate['residence']} ({candidate['lat']}, {candidate['lng']}) · {candidate['qid']}"
                                     for candidate in candidates),
            "距原生成点最近公里": min(distances) if distances else None, "出处和坐标疑点": " | ".join(issues),
            "调查库来源": "https://doi.org/10.7488/ds/100", "地图来源": comparison.get("map_url"),
            "地图文件": comparison.get("map_local_path"), "地图SHA256": comparison.get("map_sha256"),
            "档号快照SHA256": comparison.get("snapshot_sha256"), "档号快照时间": comparison.get("retrieved_at"),
            "草稿文件": record["card_path"], "草稿SHA256": record["card_sha256"],
        })
    return rows


def lao_manuscript_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r"corpus_lao_dllm_[1-9]\d*", record["id"]):
            continue
        evidence = record["evidence"]
        fields = evidence.get("lao_catalogue_fields", {})
        def values(name: str) -> str:
            return " | ".join(value for group in fields.get(name, {}).values() for value in group)
        point = evidence.get("lao_repository_candidate", {})
        duplicate = evidence.get("lao_duplicate_plmp", [])
        dataset = next((source for source in record["sources"] if source["type"] == "lao_dllm_search"), {})
        viewer = next((source for source in record["sources"] if source["type"] == "lao_dllm_viewer"), {})
        concerns = [flag["description"] for flag in record["issues"] if flag["category"] in {"source", "coordinate", "standard"}]
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({
            "卡片ID": record["id"], "馆藏记录号": record["id"].removeprefix("corpus_lao_dllm_"),
            "PLMP档号": values("otherIdentifier.code_number"), "DLLM编号": values("dc:identifier"),
            "标题": record["title"], "馆藏地点": values("full_location_name"),
            "候选纬度": point.get("lat"), "候选经度": point.get("lng"),
            "坐标用途": point.get("scope"), "手稿日期原字段": values("date_original"),
            "册页及影像数": values("dc:extent"), "语言": values("dc:language"), "文字": values("script"),
            "同号馆藏": " | ".join(f"{item['dllm_id']} / manifest {item['manifest']} / {item['title']}" for item in duplicate),
            "标准码": standards, "出处与坐标疑点": " | ".join(concerns),
            "馆藏影像页面": viewer.get("url"), "数据快照": dataset.get("local_path"),
            "数据SHA256": dataset.get("content_sha256"), "署名与许可": evidence.get("lao_attribution"),
            "草稿SHA256": record["card_sha256"],
        })
    return rows


def lanna_manuscript_rows(records: list[dict]) -> list[dict]:
    rows=[]
    for record in records:
        if not re.fullmatch(r'corpus_th_lanna_[1-9]\d*',record['id']):continue
        data=record['evidence'].get('lanna',{});fields=data.get('馆藏字段',{})
        def values(name):return ' | '.join(value for group in fields.get(name,{}).values() for value in group)
        source=next((item for item in record['sources'] if item['type']=='lanna_search'),{})
        viewer=next((item for item in record['sources'] if item['type']=='lanna_viewer'),{})
        spatial=record['spatial'] or {}
        codes=' | '.join(f'{STANDARD_NAMES[name]} {code}' for name,items in record['standards'].items()
                         if isinstance(items,list) for code in items)
        rows.append({'卡片ID':record['id'],'馆藏编号':record['id'].removeprefix('corpus_th_lanna_'),
            '标题':record['title'],'馆藏档号':values('otherIdentifier.code_number'),'语言':values('dc:language'),
            '文字':values('script'),'馆藏地点':values('full_location_name'),'馆藏纬度原字段':values('schema:latitude'),
            '馆藏经度原字段':values('schema:longitude'),'手稿日期原字段':values('date_original'),
            '同号馆藏候选':' | '.join(str(item) for item in data.get('相同档号馆藏候选',[])),
            '坐标':f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '标准码':codes,'待核问题':' | '.join(item['description'] for item in record['issues']),
            '馆方原图页面':viewer.get('url'),'检索快照SHA256':source.get('content_sha256'),
            '署名与许可':data.get('署名与许可'),'草稿SHA256':record['card_sha256'],'人工复核':'待复核'})
    return rows


def yuhuan_story_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r"case_cn_yuhuan_2008_p\d{3}", record["id"]):
            continue
        evidence = record["evidence"]
        entry = evidence.get("yuhuan_index", {})
        extra = evidence.get("yuhuan_credit_supplement", {})
        scan = next((source for source in record["sources"] if source["type"] == "yuhuan_scan"), {})
        online = next((source for source in record["sources"] if source["type"] in {"yuhuan_web_version", "yuhuan_web_candidate"}), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        concerns = [flag["description"] for flag in record["issues"]]
        rows.append({"卡片ID": record["id"], "标题": record["title"], "目录类别": entry.get("category"),
                     "起始印刷页": entry.get("page"), "起始PDF页": evidence.get("yuhuan_pdf_page"),
                     "采录旁注候选": " | ".join(entry.get("credits", []) + extra.get("credits", [])),
                     "旁注印刷页": "、".join(str(value) for value in extra.get("credit_pages", [])) or entry.get("credit_page"),
                     "早期刊载候选": extra.get("prior_publication"), "网页版本": online.get("url"),
                     "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
                     "标准码": standards, "待核问题": " | ".join(concerns),
                     "原页链接": scan.get("url"), "扫描SHA256": scan.get("content_sha256"),
                     "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def jade_rows(records: list[dict]) -> list[dict]:
    by_id = {record['id']: record for record in records}
    root = by_id.get(JADE_ROOT)
    if not root:
        return []
    rows = []
    for item in root['evidence'].get('jade_inventory', []):
        record = by_id.get(item['关联卡片'])
        flags = [] if not record else [flag['description'] for flag in record['issues']]
        if item['关联卡片'] == LUMAWIG_EXISTING:
            flags.insert(0, '沿用已有 Lumawig 草稿；本清单另提供此扫描本的候选页。')
        if not record:
            flags.append('对应待审卡片缺失。')
        spatial = (record or {}).get('spatial') or {}
        standards = ' | '.join(f"{STANDARD_NAMES[name]} {code}"
            for name, codes in (record or {}).get('standards', {}).items()
            if isinstance(codes, list) for code in codes)
        compare = JADE_COMPARISONS.get(item['目录印刷页'])
        rows.append({'卡片ID': item['关联卡片'], '原目录题名': item['目录原题名'], '整理题名': item['整理题名'],
                     '原目录分类': item['原目录分类'], '阅读顺序（非原编号）': item['正文阅读顺序（非原编号）'],
                     '目录印刷页': item['目录印刷页'], 'OCR扫描序号': item['OCR候选扫描序号'],
                     '扫描叶号': item['扫描叶号'], '查看器索引': item['查看器索引'],
                     'OCR标题相似度': item['OCR标题相似度'], 'OCR页脚数字吻合': item['OCR页脚数字吻合'],
                     'OCR标题较目录扩展': item['OCR标题较目录扩展'],
                     '1916年同题候选卡片': (compare[0] if compare else 'case_ph_cole_1916_p105' if item['目录印刷页'] == 316 else ''),
                     '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                     '标准码': standards, '待核问题': ' | '.join(flags), '原扫描候选链接': item['扫描候选链接'],
                     '草稿SHA256': (record or {}).get('card_sha256'), '人工复核': '待复核'})
    return rows


def early_comparison_rows(records: list[dict]) -> list[dict]:
    by_id = {record['id']: record for record in records}
    jade_root = by_id.get(JADE_ROOT)
    if not jade_root:
        return []
    inventory = {row['目录印刷页']: row for row in jade_root['evidence'].get('jade_inventory', [])}
    rows = []
    for page, (target, note) in JADE_COMPARISONS.items():
        if page not in inventory:
            continue
        item = inventory[page]
        other = by_id.get(target, {})
        other_source = next((source for source in other.get('sources', []) if source['type'] == 'cole_scan_link'), {})
        rows.append({'类别': '1922 与 1916 同题', '甲卡片': item['关联卡片'], '甲原页': item['扫描候选链接'],
                     '乙卡片': target, '乙原页': other_source.get('url'), '对照依据': note, '人工复核': '待复核'})
    if 316 in inventory:
        other = by_id.get('case_ph_cole_1916_p105', {})
        other_source = next((source for source in other.get('sources', []) if source['type'] == 'cole_scan_link'), {})
        rows.append({'类别': '1922 与 1916 同题', '甲卡片': LUMAWIG_EXISTING, '甲原页': inventory[316]['扫描候选链接'],
                     '乙卡片': 'case_ph_cole_1916_p105', '乙原页': other_source.get('url'),
                     '对照依据': '现有 1922 年卡片与 1916 年同题；前言归因及具体采录链需核。', '人工复核': '待复核'})
    saleeby = by_id.get(SALEEBY_CASE, {})
    cole = by_id.get('case_ph_cole_1916_p157', {})
    if saleeby and cole:
        first = next((source for source in saleeby.get('sources', []) if source['type'] == 'saleeby_scan'), {})
        second = next((source for source in cole.get('sources', []) if source['type'] == 'cole_scan_link'), {})
        rows.append({'类别': '1905 与 1916 同题', '甲卡片': SALEEBY_CASE, '甲原页': first.get('url'),
                     '乙卡片': 'case_ph_cole_1916_p157', '乙原页': second.get('url'),
                     '对照依据': '1916 年脚注称 Saleeby 首录；同题与情节为候选，具体底本未确定。', '人工复核': '待复核'})
    if 3 in inventory:
        rows.append({'类别': '1922 与安徒生作品', '甲卡片': inventory[3]['关联卡片'], '甲原页': inventory[3]['扫描候选链接'],
                     '乙卡片': '', '乙原页': ANDERSEN_TRANSLATION,
                     '对照依据': '关键情节高度相似；作品登记及译本仅作对照，直接改写底本待核。', '人工复核': '待复核'})
    return rows


def cole_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(COLE_PREFIX + r'\d{3}', record['id']):
            continue
        data = record['evidence'].get('cole_1916', {})
        scan = next((source for source in record['sources'] if source['type'] == 'cole_scan_link'), {})
        index = next((source for source in record['sources'] if source['type'] == 'cole_toc_index'), {})
        page_source = next((source for source in record['sources'] if source['type'] == 'cole_ocr_segments'), {})
        page_range = record['evidence'].get('cole_ocr_range', {})
        spatial = record['spatial'] or {}
        standards = ' | '.join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record['standards'].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({'卡片ID': record['id'], '原目录题名': data.get('目录题名'), '原目录主组': data.get('原目录主组'),
                     '原目录次组': data.get('原目录次组'), '目录印刷页': data.get('目录印刷页'),
                     'OCR候选扫描序号': data.get('OCR候选扫描序号'), 'OCR标题相似度': data.get('OCR标题相似度'),
                     'OCR页脚数字吻合': data.get('OCR页脚数字吻合'),
                     'OCR候选页范围': (f"{page_range['start_scan']}–{page_range['end_scan_exclusive'] - 1}" if page_range else ''),
                     'OCR候选页数': len(record['evidence'].get('cole_ocr_pages', [])),
                     'OCR逐页文件SHA256': page_source.get('content_sha256'),
                     '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                     '标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']),
                     '原扫描候选链接': scan.get('url'), '目录索引SHA256': index.get('content_sha256'),
                     '草稿SHA256': record['card_sha256'], '人工复核': '待复核'})
    return rows


def sinica_oral_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        match = re.fullmatch(r"case_tw_sinica_oral_([1-9]\d*)", record["id"])
        if not match:
            continue
        evidence = record["evidence"]
        fields = evidence.get("sinica_detail_fields", {})
        catalogue = next((source for source in record["sources"] if source["type"] == "sinica_catalogue"), {})
        detail = next((source for source in record["sources"] if source["type"] == "sinica_detail_metadata"), {})
        gis = next((source for source in record["sources"] if source["type"] == "sinica_community_gis"), {})
        candidates = evidence.get("sinica_community_candidates", [])
        original = next((source for source in record["sources"] if source["type"] == "sinica_original"), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "记录号": match.group(1), "目录组": evidence.get("sinica_group"),
                     "原目录题名": evidence.get("sinica_catalogue_label"), "详情档案名称": fields.get("檔案名稱"),
                     "详情族别": fields.get("族別"), "采集日期": fields.get("採集日期"), "采集地点": fields.get("採集地點"),
                     "报道人": fields.get("報導人"), "记音者": fields.get("記音者"), "翻译者": fields.get("翻譯者"),
                     "候选社区地标": " | ".join(f"{item['部落名称']} / {item['地标']}" for item in candidates),
                     "候选纬度": " | ".join(str(item["纬度"]) for item in candidates),
                     "候选经度": " | ".join(str(item["经度"]) for item in candidates),
                     "候选坐标范围": " | ".join(item["坐标范围"] for item in candidates),
                     "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
                     "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
                     "原站详情": original.get("url"), "目录索引SHA256": catalogue.get("content_sha256"),
                     "详情索引SHA256": detail.get("content_sha256"), "GIS点位SHA256": gis.get("content_sha256"),
                     "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def vietnam_cham_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        match = re.fullmatch(r"case_vietnam_cham_(\d{3})", record["id"])
        if not match:
            continue
        evidence = record["evidence"]
        catalogue = evidence.get("vietnam_cham_catalogue", {})
        book = evidence.get("vietnam_cham_book_fields", {})
        preface = evidence.get("vietnam_cham_preface", {})
        detail = evidence.get("vietnam_cham_story", {})
        source = next((item for item in record["sources"] if item["type"] == "vietnam_cham_story"), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "目录序号": int(match.group(1)), "目录越南文题名": catalogue.get("title"),
                     "详情页题名": detail.get("detail_title"), "可见段落数": detail.get("paragraph_count"),
                     "详情标题原显示": detail.get("heading_text_with_notes"),
                     "标题脚注标记": " | ".join(item.get("label", "") for item in (detail.get("heading_note_markers") or [])),
                     "正文语言": book.get("Languages"), "站点Date Created": book.get("Date Created"),
                     "前言落款": preface.get("date_as_written"), "前言署名": preface.get("signatory"),
                     "馆方贡献者字段": book.get("Authors"), "出版者字段": book.get("Publisher"),
                     "单篇讲述者": "", "单篇来源类别": "", "单篇采集地": "",
                     "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
                     "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
                     "原站详情": source.get("url"), "字段快照SHA256": source.get("content_sha256"),
                     "原响应SHA256": detail.get("raw_sha256"), "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def shandong_mirror_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r"case_cn_sd_[a-z0-9_]+_\d{2}", record["id"]):
            continue
        evidence = record["evidence"].get("shandong_mirror", {})
        source = next((item for item in record["sources"] if item["type"] == "shandong_mirror_index"), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "镜像题名": evidence.get("镜像题名"), "方志": evidence.get("镜像书名"),
                     "章节": evidence.get("镜像章节"), "原页分组": evidence.get("原页分组"),
                     "方志范围": evidence.get("镜像方志范围"), "早期刊载线索": evidence.get("早期刊载线索"),
                     "作者候选": evidence.get("作者候选"), "讲述人候选": evidence.get("讲述人候选"),
                     "讲述人页面字形": evidence.get("讲述人页面字形"), "整理人候选": evidence.get("整理人候选"),
                     "角色与版本备注": evidence.get("角色与版本备注"), "相关书目对照": evidence.get("相关书目对照"),
                     "相关书目出处": evidence.get("相关书目出处"), "采录时间": "", "采录地点": "",
                     "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
                     "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
                     "镜像章节链接": source.get("url"), "研究字段索引SHA256": source.get("content_sha256"),
                     "网页原响应SHA256": "", "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def pangloss_na_inventory_rows(records: list[dict]) -> list[dict]:
    """Expose the entire saved directory without treating every row as a story."""
    by_id = {record['id']: record for record in records}
    candidate = next((record for record in records if any(source['type'] == NA_CANDIDATE_MARKER for source in record['sources'])), None)
    if not candidate:
        return []
    kinds = ['pangloss_na_candidate_catalogue', 'pangloss_na_candidate_first',
             'pangloss_na_candidate_context', 'pangloss_na_candidate_selection']
    sources = [[source for source in candidate['sources'] if source['type'] == kind] for kind in kinds]
    if any(len(items) != 1 or not items[0].get('local_path') or not items[0].get('content_sha256') for items in sources):
        return []
    paths = []
    for items in sources:
        path = Path(items[0]['local_path'])
        path = (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != items[0]['content_sha256']:
            return []
        paths.append(path)
    try:
        catalog, selection, previous = validate_na_candidates(*paths)
    except (ValueError, OSError, KeyError, TypeError):
        return []
    chosen = {item['id']: item for item in selection['choices']}
    result = []
    for number, row in catalog.items():
        identifier = NA_CANDIDATE_PREFIX + number
        record, pick = by_id.get(identifier), chosen.get(number)
        if number in previous:
            status = '此前选取，已有待审卡' if record else '此前选取的卡片缺失'
        elif pick:
            status = '本轮候选，已有待审卡' if record else '本轮候选的卡片缺失'
        else:
            status = ('未选入，未逐条筛查' if not record else '专著目录新增候选，已有待审卡'
                      if any(source['type'] == NA_TONE_NEW_MARKER for source in record['sources']) else '已有其他卡片，需核对选取来源')
        title = row['title']
        hint = ('题名为词汇调查' if title.startswith('Vocabulaire : première enquête de vocabulaire') else
                '题名为数词量词调查' if title.startswith('Numeral-plus-classifier phrases.') else '未按题名细分')
        detail = next((source for source in (record or {}).get('sources', []) if source['type'] == 'pangloss_na_detail'), {})
        spatial = (record or {}).get('spatial') or {}
        standards = ' | '.join(f"{STANDARD_NAMES[name]} {code}" for name, codes in (record or {}).get('standards', {}).items()
                               if isinstance(codes, list) for code in codes)
        result.append({'馆藏编号': number, '馆方目录题名': title, '目录研究者': row['researchers'], '目录讲述者': row['speakers'],
                       '目录录音日期': row['recorded'], '时长': row['duration'], '题名提示': hint,
                       '筛查状态': status, '本轮选取理由': pick['reason'] if pick else '',
                       '待核对照卡片': NA_CANDIDATE_PREFIX + pick['compare_id'] if pick and pick['compare_id'] else '',
                       '待审卡片ID': identifier if record else '', '单条详情': '已登记详情快照' if detail.get('local_path') else '未登记详情快照',
                       '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                       '标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']) if record else '未逐条筛查；题名不能证明体裁。',
                       '馆方单条链接': row['url'], '馆方DOI': row['doi'], '目录页面SHA256': sources[0][0]['content_sha256'],
                       '草稿SHA256': (record or {}).get('card_sha256'), '人工复核': '待复核' if record else '未建卡'})
    return result


def na_tone_link_rows(records: list[dict]) -> list[dict]:
    anchor = next((record for record in records if record['evidence'].get('na_tone_book')), None)
    if not anchor:
        return []
    kinds = ('na_tone_book', 'na_tone_table_source', 'na_tone_crosswalk', 'na_tone_datacite_manifest')
    sources = [next((source for source in anchor['sources'] if source['type'] == kind), None) for kind in kinds]
    catalogue = next((source for source in anchor['sources'] if source['type'] in
                      ('pangloss_na_catalogue', 'pangloss_na_candidate_catalogue', 'na_tone_catalogue')), None)
    if not catalogue or not catalogue.get('local_path') or any(not source or not source.get('local_path') for source in sources):
        return []
    def resolve(source):
        path = Path(source['local_path'])
        return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
    book, tex, index_path, manifest = map(resolve, sources)
    corpus = resolve(catalogue)
    try:
        index = load_na_tone_index(index_path, book, tex, corpus, manifest.parent)
    except (ValueError, OSError, KeyError, TypeError):
        return []
    by_id = {record['id']: record for record in records}
    labels = {'resource': '资源', 'sentence': 'S 分句标识', 'word': 'W 词条标识', 'unknown_fragment': '片段性质待核'}
    rows = []
    for link in index['links']:
        mapping = index['mappings'][link['doi_id']]
        number = mapping['catalogue_recording_id']
        target = by_id.get(NA_CANDIDATE_PREFIX + number) if number else None
        flags = index['recordings'].get(number, {}).get('flags', []) if number else mapping['flags']
        if link['fragment_kind'] == 'unknown_fragment' and 'book_fragment_unclassified' not in flags:
            flags = [*flags, 'book_fragment_unclassified']
        rows.append({'出版PDF页': link['pdf_page'], '印刷页': link['printed_page'], '页面链接序号': link['annotation'],
                     '书中DOI编号': link['doi_id'], '原始片段': link['fragment'], '片段性质': labels[link['fragment_kind']],
                     '目录录音号': number or '', '对应依据': mapping['basis'] or '未确定',
                     'DataCite是否查询': '是' if mapping['datacite_checked'] else '否', 'DataCite资源类型': mapping['datacite_type'],
                     '登记权利原字段': json.dumps(mapping['datacite_rights'], ensure_ascii=False),
                     '待审卡片ID': target['id'] if target else '',
                     '待核问题': ' | '.join(NA_TONE_FLAGS.get(flag, flag) for flag in flags),
                     '书中PDF页链接': f"{NA_TONE_BOOK_PAGE}#page={link['pdf_page']}", '书中原始DOI链接': link['url'],
                     '对照索引SHA256': sources[2]['content_sha256'], '人工复核': '待复核'})
    return rows


def pangloss_na_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        match = re.fullmatch(r"case_cn_yongning_na_(\d{7})", record["id"])
        if not match or any(source['type'] in (NA_CANDIDATE_MARKER, NA_TONE_NEW_MARKER) for source in record['sources']):
            continue
        item = record["evidence"].get("pangloss_na", {})
        detail = next((s for s in record["sources"] if s["type"] == "pangloss_na_detail"), {})
        catalogue = next((s for s in record["sources"] if s["type"] == "pangloss_na_catalogue"), {})
        index = next((s for s in record["sources"] if s["type"] == "pangloss_annotation_index"), {})
        summary = record["evidence"].get("pangloss_annotation_summary", {})
        annotations = record["evidence"].get("pangloss_annotations", [])
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "馆藏编号": match.group(1), "馆方目录题名": item.get("馆方目录题名"),
                     "馆方其他语言题名": json.dumps(item.get("馆方其他语言题名", []), ensure_ascii=False),
                     "题名对照分组": item.get("本项目题名对照分组"), "馆方目录研究者字段": item.get("馆方目录研究者字段"),
                     "馆方详情研究者字段": item.get("馆方详情研究者字段"), "馆方目录讲述者字段": item.get("馆方目录讲述者字段"),
                     "馆方详情讲述者字段": item.get("馆方详情讲述者字段"), "两处讲述者字段显示是否对应": item.get("两处讲述者字段显示是否对应"),
                     "两处研究者字段显示是否对应": item.get("两处研究者字段显示是否对应"), "馆方目录录音日期": item.get("馆方目录录音日期"),
                     "馆方详情录音日期原字段": item.get("馆方详情录音日期原字段"), "两处日期是否一致": item.get("两处日期是否一致"),
                     "馆方录音地点原字段": item.get("馆方详情录音地点原字段"), "馆方时长": item.get("馆方时长"),
                     "馆方媒介图标": " | ".join(item.get("馆方媒介图标", [])), "馆方转写图标": item.get("馆方转写图标"),
                     "馆方许可原字段": item.get("馆方详情许可原字段"), "关联音视频资源数": summary.get("馆方音视频资源数"),
                     "关联附件数": len(annotations) if summary else "", "XML分句数": sum(len(a.get("segments", [])) for a in annotations) if summary else "",
                     "附件单独许可": "尚未核明" if annotations else "", "接口观察时间": record["evidence"].get("pangloss_annotation_observed_at"),
                     "分句索引SHA256": index.get("content_sha256"),
                     "地点对照依据": record["evidence"].get("pangloss_location_context", {}).get("url"),
                     "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
                     "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
                     "馆方单条链接": detail.get("url"), "馆方DOI": detail.get("doi"), "单条页面SHA256": detail.get("content_sha256"),
                     "目录页面SHA256": catalogue.get("content_sha256"), "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def pangloss_japhug_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        match = re.fullmatch(r'case_cn_japhug_(\d{7})', record['id'])
        if not match:
            continue
        data = record['evidence'].get('pangloss_japhug', {})
        details = data.get('馆方详情字段') or {}
        supplemental = next((s for s in record['sources'] if s['type'] == 'pangloss_japhug_supplement_detail'), {})
        original = supplemental or next((s for s in record['sources'] if s['type'] in ('pangloss_japhug_detail', 'pangloss_japhug_original')), {})
        catalogue = next((s for s in record['sources'] if s['type'] == 'pangloss_japhug_catalogue'), {})
        spatial = record['spatial'] or {}
        standards = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, codes in record['standards'].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({'卡片ID': record['id'], '馆藏编号': match.group(1), '目录题名': data.get('馆方目录题名'),
                     '目录研究者': data.get('馆方目录研究者'), '目录讲述者': data.get('馆方目录讲述者'),
                     '目录录音日期': data.get('馆方目录录音日期'), '录音时长': data.get('馆方时长'),
                     '媒介图标': ' | '.join(data.get('馆方媒介图标', [])), '转写图标': data.get('馆方转写图标'),
                     '详情状态': data.get('详情采集状态'), '首轮选取依据': '' if supplemental else data.get('详情选取依据'),
                     '后续详情补充': '是' if supplemental else '',
                     '详情其他题名': json.dumps(details.get('alternate_titles', []), ensure_ascii=False),
                     '详情研究者': details.get('researchers'), '详情讲述者': details.get('speakers'),
                     '详情录音日期': details.get('recorded'), '详情录音地点': details.get('recording_location'),
                     '详情许可原字段': details.get('license'),
                     '目录与详情讲述者一致': data.get('目录与详情讲述者字段是否对应'),
                     '目录与详情研究者一致': data.get('目录与详情研究者字段是否对应'),
                     '目录与详情日期一致': data.get('目录与详情录音日期是否一致'),
                     '语料背景研究': record['evidence'].get('japhug_context', {}).get('url'),
                     '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                     '标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']),
                     '馆方详情链接': original.get('url'), '馆方DOI': original.get('doi'),
                     '详情页面SHA256': original.get('content_sha256'), '目录页面SHA256': catalogue.get('content_sha256'),
                     '草稿SHA256': record['card_sha256'], '人工复核': '待复核'})
    return rows


def pangloss_khmu_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        match = re.fullmatch(r'case_sea_khmu_(\d{7})', record['id'])
        if not match:
            continue
        data = record['evidence'].get('pangloss_khmu', {})
        detail = data.get('馆方详情字段') or {}
        comparison = record['evidence'].get('khmu_comparison') or {}
        supplemental = next((s for s in record['sources'] if s['type'] == 'pangloss_khmu_supplement_detail'), {})
        original = supplemental or next((s for s in record['sources'] if s['type'] in ('pangloss_khmu_detail', 'pangloss_khmu_original')), {})
        catalogue = next((s for s in record['sources'] if s['type'] == 'pangloss_khmu_catalogue'), {})
        comparison_source = next((s for s in record['sources'] if s['type'] == 'pangloss_khmu_comparison'), {})
        spatial = record['spatial'] or {}
        standards = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, codes in record['standards'].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({'卡片ID': record['id'], '馆藏编号': match.group(1), '目录题名': data.get('馆方目录题名'),
                     '目录研究者': data.get('馆方目录研究者'), '目录讲述者': data.get('馆方目录讲述者'),
                     '目录录音日期': data.get('馆方目录录音日期'), '录音时长': data.get('馆方时长'),
                     '媒介图标': ' | '.join(data.get('馆方媒介图标', [])), '转写图标': data.get('馆方转写图标'),
                     '详情状态': data.get('详情采集状态'), '首轮选取依据': '' if supplemental else data.get('详情选取依据'),
                     '后续详情补充': '是' if supplemental else '',
                     '详情其他题名': json.dumps(detail.get('alternate_titles', []), ensure_ascii=False),
                     '详情研究者': detail.get('researchers'), '详情讲述者': detail.get('speakers'),
                     '详情录音日期': detail.get('recorded'), '详情录音地点': detail.get('recording_location'),
                     '详情许可原字段': detail.get('license'),
                     '目录与详情讲述者一致': data.get('目录与详情讲述者字段是否对应'),
                     '目录与详情研究者一致': data.get('目录与详情研究者字段是否对应'),
                     '目录与详情日期一致': data.get('目录与详情录音日期是否一致'),
                     '日期范围端点一致': record['evidence'].get('khmu_date_range_match'),
                     '目录对照分组': comparison.get('label'), '目录对照依据': comparison.get('note'),
                     '待核对照编号': ' | '.join(member['id'] for member in comparison.get('members', []) if member['id'] != match.group(1)),
                     '相关研究链接': record['evidence'].get('khmu_research_reference', {}).get('url'),
                     '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                     '标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']),
                     '馆方详情链接': original.get('url'), '馆方DOI': original.get('doi'),
                     '详情页面SHA256': original.get('content_sha256'), '目录页面SHA256': catalogue.get('content_sha256'),
                     '对照索引SHA256': comparison_source.get('content_sha256'),
                     '草稿SHA256': record['card_sha256'], '人工复核': '待复核'})
    return rows


def pangloss_na_segment_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        match = re.fullmatch(r"case_cn_yongning_na_(\d{7})", record["id"])
        if not match:
            continue
        index = next((s for s in record["sources"] if s["type"] == "pangloss_annotation_index"), {})
        for annotation in record["evidence"].get("pangloss_annotations", []):
            for segment in annotation.get("segments", []):
                rows.append({"卡片ID": record["id"], "馆藏编号": match.group(1), "对应音视频资源": annotation["primary_oai"],
                    "音视频许可原字段": annotation.get("primary_license"), "附件编号": annotation["oai"],
                    "附件DOI": annotation.get("doi"), "附件单独许可": "尚未核明", "原语语言标记": annotation.get("language"),
                    "分句序号": segment["position"], "XML原始ID": segment.get("xml_id"), "开始秒": segment.get("start"),
                    "结束秒": segment.get("end"), "时间有效性": segment["time_status"], "原语文字形式": " | ".join(segment["forms"]),
                    "译文语言标记": " | ".join(segment["translation_languages"]),
                    "原站分句链接": pangloss_viewer_url(annotation["primary_oai"], annotation["oai"], segment["position"]),
                    "接口观察时间": record["evidence"].get("pangloss_annotation_observed_at"),
                    "分句索引SHA256": index.get("content_sha256"), "人工复核": "待复核"})
    return rows


def zibuyu_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [record for record in records if record['id'] == ZIBUYU_ROOT]
    if len(roots) != 1: return []
    root = roots[0]
    by_id = {record['id']: record for record in records}
    result = []
    for data in root['evidence'].get('zibuyu_inventory', []):
        volume, number = data['分卷'], data['分卷篇序']
        identifier = ZIBUYU_EXISTING if (volume, number, data['分卷篇名原文']) == (1, 1, '李通判') else f'{ZIBUYU_CASE_PREFIX}{volume:02d}_s{number:03d}'
        record = by_id.get(identifier)
        candidate = data['总目录候选篇目'] or {}
        spatial = (record or {}).get('spatial') or {}
        standards = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, codes in (record or {}).get('standards', {}).items()
                               if isinstance(codes, list) for code in codes)
        result.append({'记录类型': '分卷标题', '卷次': volume, '分卷篇序': number, '分卷篇名': data['分卷篇名原文'],
            '分卷锚点': data['分卷页面实际锚点'], '分卷修订号': data['分卷修订号'], '候选方式': data['总目录候选方式'],
            '总目录候选篇序': candidate.get('number', ''), '总目录候选题名': candidate.get('title', ''),
            '总目录候选锚点': candidate.get('anchor', ''), '锚点一致': data['锚点一致'],
            '纯文字SHA256': data['抽取纯文字 SHA256'], '段落数': data['段落数'], '卡片ID': identifier,
            '固定修订原文': data['固定修订原文链接'],
            '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '标准码': standards, '待核问题': ' | '.join(i['description'] for i in (record or {}).get('issues', []))
                            if record else '未找到对应草稿，须核对。',
            '草稿SHA256': (record or {}).get('card_sha256', ''), '人工复核': '待复核' if record else '草稿缺失'})
    for item in root['evidence'].get('zibuyu_index_only', []):
        result.append({'记录类型': '目录未找到唯一同题', '卷次': item['volume'], '分卷篇序': '', '分卷篇名': '',
            '分卷锚点': '', '分卷修订号': '', '候选方式': '目录原题须人工与分卷对照',
            '总目录候选篇序': item['number'], '总目录候选题名': item['title'], '总目录候选锚点': item['anchor'],
            '锚点一致': '', '纯文字SHA256': '', '段落数': '', '卡片ID': '', '固定修订原文': '',
            '坐标': '', '标准码': '', '待核问题': '同序题名可能是对照线索，不能自动认定同篇。', '草稿SHA256': '', '人工复核': '待复核'})
    return result


def bl_yi_project_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [r for r in records if r['id'] == BL_YI_PROJECT_ROOT]
    if len(roots) != 1: return []
    root = roots[0]; rows = root['evidence'].get('yi_project_inventory', []); pages = root['evidence'].get('yi_project_pages', [])
    by_id = {r['id']: r for r in records}; result = []
    for row in rows:
        old = bl_yi_project_old_id(row)
        if old:
            identifier, status = old, '既有待审卡' if old in by_id else '既有卡待确认'
        elif row['record_id'].startswith('032-'):
            candidate = bl_yi_project_group_id(row); identifier = candidate if candidate in by_id else ''
            status = '本批父级待审卡' if identifier else '父级未筛入'
        elif bl_yi_project_reason(row):
            candidate = bl_yi_project_node_id(row); identifier = candidate if candidate in by_id else ''
            status = '本批单件待审卡' if identifier else '应入选但草稿缺失'
        else:
            identifier, status = '', '未筛入：仍须人工回查'
        record = by_id.get(identifier, {}); spatial = record.get('spatial') or {}
        codes = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, values in record.get('standards', {}).items()
                           if isinstance(values, list) for code in values)
        source = next((s for s in record.get('sources', []) if s['type'] in ('bl_yi_project_item', 'bl_yi_project_parent')), {})
        viewer = next((s for s in record.get('sources', []) if s['type'] == 'bl_yi_project_viewer'), {})
        page = pages[row['page'] - 1]; fields = row['fields']
        peers = bl_yi_project_title_peers(row, rows) if row['record_id'].startswith('040-') else []
        result.append({'馆方档号': row['shelfmark'], '馆方记录号': row['record_id'], '筛查状态': status, '待审卡片ID': identifier,
            '检索题名原字段': fields.get('Title'), '检索摘要原字段（可能截断）': fields.get('Scope & Content'),
            '检索语言原字段': fields.get('Languages'), '检索日期范围原字段': fields.get('Date Range'), '检索范围原字段': fields.get('Extent'),
            '筛查线索（非体裁判定）': ' | '.join(bl_yi_project_reason(row)), '同题目录档号（非去重依据）': ' | '.join(peers),
            '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '标准码': codes, '待核问题': ' | '.join(issue['description'] for issue in record.get('issues', [])) if record
                       else '项目检索摘要可能截断，未筛入不代表无关；单件及社区要求待核。',
            '馆方目录链接': row['url'], '馆方影像入口（未取得）': viewer.get('url', ''), '检索页面': page['url'], '检索网页SHA256': page['sha256'],
            '检索观察时间': page['observed_at'], '单件或父级网页SHA256': source.get('content_sha256', ''),
            '草稿SHA256': record.get('card_sha256', ''), '人工复核': '待复核' if record else '未筛入'})
    return result


def bl_dongjing_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [r for r in records if r['id'] == BL_DONGJING_ROOT]
    if len(roots) != 1: return []
    root = roots[0]; group = root['evidence'].get('bl_dongjing_group', {})
    items = {r['id']: r for r in records if re.fullmatch(BL_DONGJING_PREFIX + r'\d{2}', r['id'])}
    result = []
    for data in root['evidence'].get('bl_dongjing_inventory', []):
        number = int(data['馆方档号'].rsplit('/', 1)[-1]); record = items.get(f'{BL_DONGJING_PREFIX}{number:02}')
        spatial = (record or {}).get('spatial') or {}
        codes = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, values in (record or {}).get('standards', {}).items()
                           if isinstance(values, list) for code in values)
        source = next((s for s in (record or {}).get('sources', []) if s['type'] == 'bl_dongjing_item'), {})
        compare = data['题名年份落在起止字段范围']; range_compare = data['日期范围年份落在起止字段范围']
        result.append({'馆方档号': data['馆方档号'], '卡片ID': (record or {}).get('id', ''), '馆方题名': data['馆方题名'],
            '馆方内容说明': data['馆方内容说明'], '内容提示（非体裁判定）': ' | '.join(data['内容提示（非体裁判定）']),
            '馆方材料类型': data['馆方材料类型'], '馆方语言原字段': data['馆方语言原字段'], '馆方范围原字段': data['馆方范围原字段'],
            '范围字段首项文件数（待核）': data['范围字段首项文件数（待核）'], '馆藏组范围原字段': group.get('系列范围原字段'),
            '单件范围字段首项文件数相加': group.get('单件范围字段首项文件数相加'),
            '题名方括号年份': data['题名方括号年份'], '馆方起始日期原字段': data['馆方起始日期原字段'],
            '馆方结束日期原字段': data['馆方结束日期原字段'], '馆方日期范围原字段': data['馆方日期范围原字段'],
            '题名年份落在起止字段范围': '是' if compare is True else '否' if compare is False else '无法比较',
            '日期范围年份落在起止字段范围': '是' if range_compare is True else '否' if range_compare is False else '无法比较',
            '馆方内部项目标识原字段': data['馆方内部项目标识原字段'], '馆方数字内容原字段': data['馆方数字内容原字段'],
            '馆方单件访问条件原字段': data['馆方单件访问条件原字段'],
            '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '标准码': codes, '待核问题': ' | '.join(flag['description'] for flag in (record or {}).get('issues', [])) if record else '待审草稿缺失。',
            '馆方单件链接': 'https://searcharchives.bl.uk/catalog/' + data['馆方记录号'],
            '馆方网页SHA256': source.get('content_sha256', ''), '草稿SHA256': (record or {}).get('card_sha256', ''),
            '人工复核': '待复核' if record else '核对草稿状态'})
    return result


def bl_burma_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [r for r in records if r['id'] == BL_BURMA_ROOT]
    if len(roots) != 1: return []
    items = {r['id']: r for r in records if re.fullmatch(BL_BURMA_PREFIX + r'\d{2}', r['id'])}
    result = []
    for data in roots[0]['evidence'].get('bl_burma_inventory', []):
        number = int(data['馆方档号'].rsplit('/', 1)[-1])
        record = items.get(f'{BL_BURMA_PREFIX}{number:02}')
        spatial = (record or {}).get('spatial') or {}
        codes = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, values in (record or {}).get('standards', {}).items()
                           if isinstance(values, list) for code in values)
        dsal = data.get('DSAL候选目录字段') or {}
        source = next((s for s in (record or {}).get('sources', []) if s['type'] == 'bl_burma_item'), {})
        result.append({'馆方档号': data['馆方档号'], '卡片ID': (record or {}).get('id', ''),
            '馆方题名': data['馆方题名'], '馆方语言原字段': data['馆方语言原字段'], '馆方内容说明': data['馆方内容说明'],
            '馆方日期范围原字段': data['馆方日期范围原字段'], '馆方唱片原编号': data['馆方唱片原编号'],
            'DSAL严格编号候选数': data['DSAL严格编号候选数'], 'DSAL半号文字候选数': data['DSAL半号文字候选数'],
            'DSAL候选方式': data['DSAL候选方式'], 'DSAL题名原字段': dsal.get('recording_title', ''),
            'DSAL语言原字段': dsal.get('language', ''), 'DSAL说话人原字段': dsal.get('narrator', ''),
            'DSAL说话人来源地区原字段': dsal.get('narrator_origin_district', ''),
            'DSAL地点原字段': dsal.get('location_populated_place', ''), '坐标': f"{spatial['lat']}, {spatial['lng']}"
                if spatial.get('lat') is not None and spatial.get('lng') is not None else '', '标准码': codes,
            '待核问题': ' | '.join(flag['description'] for flag in (record or {}).get('issues', [])) if record else '待审草稿缺失。',
            '馆方单件链接': 'https://searcharchives.bl.uk/catalog/' + data['馆方记录号'],
            'DSAL候选链接（待核）': data['DSAL候选页面（未核实）'] or '',
            '馆方网页SHA256': source.get('content_sha256', ''), 'DSAL字段索引SHA256': data['DSAL字段索引SHA256'] or '',
            'DSAL原响应SHA256（原响应未保存）': data['DSAL原响应SHA256（原响应未保存）'] or '',
            'DSAL观察时间': data['DSAL观察时间'] or '', '草稿SHA256': (record or {}).get('card_sha256', ''),
            '人工复核': '待复核' if record else '核对草稿状态'})
    return result


def palue_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [record for record in records if record['id'] == PALUE_ROOT]
    if len(roots) != 1:
        return []
    parent = roots[0]
    items = {record['id']: record for record in records if re.fullmatch(PALUE_PREFIX + r'\d{3}', record['id'])}
    receipts = parent['evidence'].get('palue_receipts', [])
    result = []
    for row in parent['evidence'].get('palue_inventory', []):
        f = row['fields']
        selected = 'Sound' in f['dc.type.dcmi']
        record = items.get(palue_node_id(row))
        page = receipts[row['page']]
        spatial = (record or {}).get('spatial') or {}
        standards = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, codes in (record or {}).get('standards', {}).items()
                               if isinstance(codes, list) for code in codes)
        status = ('待审草稿' if record else '已选但草稿缺失' if selected else '未筛入：类型字段未列 Sound')
        result.append({'馆方编号': row['id'], '筛查状态': status, '卡片ID': (record or {}).get('id', ''),
            '馆方类型字段': ' | '.join(f['dc.type.dcmi']), '目录显式 Genre 标签': row['genre_hint'] or '', '标签说明': row['genre_hint_scope'],
            '主题语种原字段': ' | '.join(f['dc.subject.language']), '主题语种代码原字段': ' | '.join(f['dc.subject.languagecode']),
            '内容语言原字段': ' | '.join(f['dc.content.language']), '内容语言代码原字段': ' | '.join(f['dc.content.languagecode']),
            '说话人原字段': ' | '.join(f['dc.contributor.speaker']), '采录者原字段': ' | '.join(f['dc.contributor.recorder']),
            '研究者原字段': ' | '.join(f['dc.contributor.researcher']), '存交者原字段': ' | '.join(f['dc.contributor.depositor']),
            '顾问原字段': ' | '.join(f['dc.contributor.consultant']), '转写者原字段': ' | '.join(f['dc.contributor.transcriber']),
            '译者原字段': ' | '.join(f['dc.contributor.translator']), '起始日期原字段（性质待核）': ' | '.join(f['dc.date.begin']),
            '结束日期原字段（性质待核）': ' | '.join(f['dc.date.finish']), '地区原字段（非事件坐标）': ' | '.join(f['dc.description.region']),
            '格式时长原字段': ' | '.join(f['dc.format.extent']), '权利原字段': ' | '.join(f['dc.rights']),
            '访问权利原字段': ' | '.join(f['dc.rights.access']),
            '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in (record or {}).get('issues', []))
                        if record else '未列 Sound 不代表没有录音；单件权利、社区要求及类型待核。',
            '馆方单件链接': row['item_url'], '永久标识': 'https://hdl.handle.net/' + row['handle'], '检索接口页': page['response']['url'],
            '字段索引SHA256': page['sha256'], '原始响应SHA256（原响应未保存）': page['response']['sha256'],
            '观察时间': page['response']['observed_at'], '草稿SHA256': (record or {}).get('card_sha256', ''),
            '人工复核': '待复核' if record else '未筛入' if not selected else '核对草稿状态'})
    return result


def pumi_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [record for record in records if record['id'] == PUMI_ROOT]
    if len(roots) != 1:
        return []
    parent = roots[0]
    catalogue = next((source for source in parent['sources'] if source['type'] == 'pumi_wolp_catalogue'), {})
    group = parent['evidence'].get('pumi_wolp_group', {})
    items = {record['id']: record for record in records if re.fullmatch(PUMI_PREFIX + r'\d{2}', record['id'])}
    result = []
    for row in parent['evidence'].get('pumi_wolp_inventory', []):
        number = row['number']
        record = items.get(f'{PUMI_PREFIX}{number:02d}')
        spatial = (record or {}).get('spatial') or {}
        current = (record or {}).get('evidence', {}).get('pumi_wolp_current', {})
        standards = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, codes in (record or {}).get('standards', {}).items()
                               if isinstance(codes, list) for code in codes)
        result.append({'目录序号': number, '馆方目录题名': row['title'], '题名标签': PUMI_KIND_NAMES[row['title_kind']],
                       '筛查状态': '待审草稿' if record else '已登记但不在待审队列', '卡片ID': record['id'] if record else '',
                       '旧目录总述音频文件数': group.get('旧目录总述音频文件数'), '页面编号条目数': group.get('页面有序编号条目数'),
                       '现行单件所载馆藏文件数': group.get('现行单件所载馆藏文件数'),
                       '计数口径': '来源文件数、目录项及作品数的关系待核',
                       '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                       '标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in (record or {}).get('issues', [])),
                       '旧档案链接（待核）': row['archive_url'], '旧试听入口（待核）': row['audio_url'],
                       '现行单件链接': current.get('现行单件链接', ''), '现行 Authors 原字段': current.get('现行单件 Authors 字段', ''),
                       '现行单件许可原字段': current.get('现行单件许可原字段', ''),
                       '馆藏目录链接': PUMI_URL, '馆藏目录SHA256': catalogue.get('content_sha256'),
                       '使用范围': '本地个人或内部非商业研究；单件权利和社区要求另核',
                       '草稿SHA256': (record or {}).get('card_sha256', ''),
                       '人工复核': '待复核' if record else '核对草稿状态'})
    return result


def temiar_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [record for record in records if record['id'] == TEMIAR_ROOT]
    if len(roots) != 1:
        return []
    parent = roots[0]
    catalogue = next((source for source in parent['sources'] if source['type'] == 'temiar_wolp_catalogue'), {})
    items = {record['id']: record for record in records if re.fullmatch(r'(case|corpus)_my_temiar_wolp_\d{2}', record['id'])}
    result = []
    for row in parent['evidence'].get('temiar_wolp_inventory', []):
        number = row['number']
        record = items.get(temiar_node_id(number))
        state = '待审草稿' if record else ('已选但不在待审队列' if number in TEMIAR_SELECTED else '未选择')
        spatial = (record or {}).get('spatial') or {}
        current = (record or {}).get('evidence', {}).get('temiar_wolp_current', {})
        standards = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, codes in (record or {}).get('standards', {}).items()
                               if isinstance(codes, list) for code in codes)
        duplicate = '目录 10 与 45 共用旧链接；待核是否重复著录' if number in {10, 45} else ''
        issues = ' | '.join(flag['description'] for flag in (record or {}).get('issues', []))
        result.append({'目录序号': number, '馆方目录题名': row['title'], '筛查类别': temiar_category(number),
                       '筛查状态': state, '卡片ID': record['id'] if record else '', '共用链接疑点': duplicate,
                       '馆方总体音轨数': 10, '另列后期音轨数': 5, '歌曲说明所称音轨数': 9,
                       '目录编号条目数': 50, '计数口径': '统计单位与对应关系未核',
                       '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                       '标准码': standards, '待核问题': issues or duplicate,
                       '旧档案链接（待核）': row['archive_url'], '旧试听入口（待核）': row['audio_url'],
                       '现行单件链接': current.get('现行单件链接', ''), '现行 Authors 原字段': current.get('现行单件 Authors 字段', ''),
                       '现行单件权利标记': current.get('现行单件权利标记', ''), '馆藏目录链接': TEMIAR_URL,
                       '馆藏目录SHA256': catalogue.get('content_sha256'), '使用范围': '本地个人或内部非商业研究；单件权利和社区要求另核',
                       '草稿SHA256': (record or {}).get('card_sha256', ''),
                       '人工复核': '待复核' if record else ('核对草稿状态' if number in TEMIAR_SELECTED else '未筛入，待选择')})
    return result


def minyag_inventory_rows(records: list[dict]) -> list[dict]:
    roots = [record for record in records if record['id'] == MINYAG_ROOT]
    if len(roots) != 1:
        return []
    parent = roots[0]
    catalogue = next((source for source in parent['sources'] if source['type'] == 'minyag_wolp_catalogue'), {})
    items = {record['id']: record for record in records if re.fullmatch(MINYAG_PREFIX + r'\d{2}', record['id'])}
    result = []
    for row in parent['evidence'].get('minyag_wolp_inventory', []):
        number = row['number']
        record = items.get(f'{MINYAG_PREFIX}{number:02d}')
        state = '待审草稿' if record else ('已选但不在待审队列' if number in MINYAG_SELECTED else '未选择')
        spatial = (record or {}).get('spatial') or {}
        current = (record or {}).get('evidence', {}).get('minyag_wolp_current', {})
        standards = ' | '.join(f'{STANDARD_NAMES[name]} {code}' for name, codes in (record or {}).get('standards', {}).items()
                               if isinstance(codes, list) for code in codes)
        result.append({'目录序号': number, '馆方目录题名': row['title'], '目录段落署名候选': row['named_in_description'],
                       '筛查类别': minyag_category(number), '筛查状态': state,
                       '卡片ID': record['id'] if record else '', '馆藏总述文件数': 77, '页面编号条目数': 62,
                       '计数口径': '两种单位的对应关系未核', '坐标': f"{spatial['lat']}, {spatial['lng']}"
                       if spatial.get('lat') is not None and spatial.get('lng') is not None else '', '标准码': standards,
                       '待核问题': ' | '.join(flag['description'] for flag in (record or {}).get('issues', [])),
                       '旧档案链接（待核）': row['archive_url'], '馆藏目录链接': MINYAG_URL,
                       '现行单件链接': current.get('现行单件链接', ''), '现行单件姓名原写法': current.get('现行单件描述姓名原写法', ''),
                       '现行单件权利标记': current.get('现行单件权利标记', ''),
                       '馆藏目录SHA256': catalogue.get('content_sha256'),
                       '使用范围': '本地个人或内部非商业研究；单条权利和社区要求另核',
                       '草稿SHA256': (record or {}).get('card_sha256', ''),
                       '人工复核': '待复核' if record else ('核对草稿状态' if number in MINYAG_SELECTED else '未筛入，待选择')})
    return result


def bl_yi_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(BL_YI_PREFIX + r'\d{2}', record['id']):
            continue
        data, group = record['evidence'].get('bl_yi_child', {}), record['evidence'].get('bl_yi_group', {})
        source = next((s for s in record['sources'] if s['type'] == 'bl_yi_child'), {})
        parent = next((s for s in record['sources'] if s['type'] == 'bl_yi_group'), {})
        spatial = record['spatial'] or {}
        standards = ' | '.join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record['standards'].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({'卡片ID': record['id'], '馆方档号': data.get('馆方档号'), '馆方记录号': data.get('馆方记录号'),
                     '馆方题名': data.get('馆方题名'), '馆方内容说明': data.get('馆方内容说明'),
                     '馆方文件数和时长': data.get('馆方文件数和时长'), '馆方语言字段': data.get('馆方语言字段'),
                     '馆方日期起始原字段': data.get('馆方日期起始原字段'), '馆方日期结束原字段': data.get('馆方日期结束原字段'),
                     '馆方日期范围原字段': data.get('馆方日期范围原字段'), '馆方访问条件': data.get('馆方访问条件'),
                     '馆藏组范围与总时长': group.get('馆方范围与总时长'), '六组时长字段相加分钟数（待核）': group.get('六组时长字段相加分钟数（待核）'),
                     '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
                     '标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']),
                     '馆方子组链接': source.get('url'), '子组网页SHA256': source.get('content_sha256'),
                     '馆藏组网页SHA256': parent.get('content_sha256'), '目录文字许可': 'CC BY 4.0（录音及社区资料另核）',
                     '草稿SHA256': record['card_sha256'], '人工复核': '待复核'})
    return rows


def bl_khmer_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r"corpus_kh_bl_or16131_\d{2}", record["id"]):
            continue
        fields = record["evidence"].get("bl_khmer", {})
        group = record["evidence"].get("bl_khmer_group", {})
        source = next((s for s in record["sources"] if s["type"] == "bl_khmer_catalogue"
                       and s.get("locator") == fields.get("馆方档号")), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "馆方档号": fields.get("馆方档号"), "馆方记录号": fields.get("馆方记录号"),
            "馆方题名": fields.get("馆方题名"), "馆方内容说明": fields.get("馆方内容说明"), "馆方册页数": fields.get("馆方册页数"),
            "馆方语言": fields.get("馆方语言"), "馆方文字": fields.get("馆方文字"), "本册起始日期": fields.get("馆方日期起始原字段"),
            "本册结束日期": fields.get("馆方日期结束原字段"), "馆藏组起始日期": group.get("馆方日期起始"), "馆藏组结束日期": group.get("馆方日期结束"),
            "数字化字段": fields.get("馆方数字化字段"), "数字化字段链接": " | ".join(fields.get("数字化字段链接", [])),
            "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
            "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
            "馆方单册链接": source.get("url"), "单册网页SHA256": source.get("content_sha256"),
            "馆藏组网页SHA256": group.get("馆藏组快照SHA256"), "目录文字许可": "CC BY 4.0；手稿影像及内容另核",
            "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def lowell_sea_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        match = re.fullmatch(r"corpus_us_lowell_sea_(\d+)", record["id"])
        if not match:
            continue
        fields = record["evidence"].get("lowell_sea", {})
        source = next((s for s in record["sources"] if s["type"] == "lowell_sea_catalogue"
                       and s.get("locator") == f"馆方记录 {match.group(1)} / 描述字段"), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "馆方记录号": match.group(1), "馆方题名": " | ".join(fields.get("馆方题名", [])),
            "馆方日期": " | ".join(fields.get("馆方日期原字段", [])), "馆方署名": " | ".join(fields.get("馆方署名", [])),
            "馆方语言": " | ".join(fields.get("馆方语言", [])), "馆方格式": " | ".join(fields.get("馆方格式", [])),
            "馆方标识": " | ".join(fields.get("馆方标识", [])), "馆方覆盖范围": " | ".join(fields.get("馆方覆盖范围", [])),
            "可见文件链接数": fields.get("可见文件链接数"), "馆方使用范围": fields.get("馆方使用范围"),
            "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
            "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
            "馆方单件链接": source.get("url"), "字段索引SHA256": source.get("content_sha256"),
            "网页原响应SHA256": fields.get("网页原响应 SHA256"), "观察时间": fields.get("网页观察时间"),
            "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def lowell_inventory_rows(records: list[dict]) -> list[dict]:
    root = next((r for r in records if r["id"] == LOWELL_SEA_ROOT), None)
    rows = []
    for item in root["evidence"].get("lowell_inventory", []) if root else []:
        fields = item["fields"]
        rows.append({"馆方记录号": item["id"], "馆方题名": item["title"], "馆方日期": " | ".join(fields["馆方日期原字段"]),
            "馆方语言": " | ".join(fields["馆方语言"]), "馆方格式": " | ".join(fields["馆方格式"]),
            "馆方覆盖范围": " | ".join(fields["馆方覆盖范围"]), "可见文件链接数": fields["可见文件链接数"],
            "筛查状态": "叙事相关资料待复核" if item["selected"] else "活动海报；不作为叙事文献入库",
            "待审卡片ID": f"corpus_us_lowell_sea_{item['id']}" if item["selected"] else "",
            "馆方单件链接": item["url"], "字段索引SHA256": item["index_sha256"],
            "网页原响应SHA256": fields["网页原响应 SHA256"], "观察时间": fields["网页观察时间"]})
    return rows


def heritage_2011_csv_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r'corpus_cn_ich_2011_(?:ext_)?\d{4}', record['id']):
            continue
        data = record['evidence'].get('heritage_2011', {})
        source = next((item for item in record['sources'] if item['type'] == 'heritage_register_2011'), {})
        spatial = record['spatial'] or {}
        standards = ' | '.join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record['standards'].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({'卡片ID': record['id'], **data,
            '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '国际标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']),
            '原始名录链接': source.get('url'), '原始名录SHA256': source.get('content_sha256'),
            '草稿SHA256': record['card_sha256'], '人工复核': '待复核'})
    return rows


def heritage_batch_csv_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r'corpus_cn_ich_(?:2008|2014)_(?:ext_)?\d{4}', record['id']):
            continue
        data = record['evidence'].get('heritage_batch', {})
        year = data.get('名录年份')
        source = next((item for item in record['sources'] if item['type'] == f'heritage_register_{year}'), {})
        spatial = record['spatial'] or {}
        standards = ' | '.join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record['standards'].items()
                               if isinstance(codes, list) for code in codes)
        others = record['evidence'].get('heritage_comparisons', [])
        rows.append({'卡片ID': record['id'], **data,
            '跨年对照卡片': ' | '.join(item['id'] for item in others),
            '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '国际标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']),
            '原始名录链接': source.get('url'), '原始名录SHA256': source.get('content_sha256'),
            '草稿SHA256': record['card_sha256'], '人工复核': '待复核'})
    return rows


def heritage_comparison_csv_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        item = record['evidence'].get('heritage_project')
        if not item:
            continue
        for other in record['evidence'].get('heritage_comparisons', []):
            if other.get('availability') != 'reviewed' and record['id'] >= other['id']:
                continue
            rows.append({'序号': item['index'], '行政项目编号数字': item['number'],
                '卡片A': record['id'], 'A年份': item['year'], 'A类别': item['kind'],
                'A原编号': item['raw_number'], 'A名称': item['title'], 'A申报地区或单位': item['area'],
                'A原表链接': item['url'], 'A原表定位': item['locator'], 'A原表SHA256': item['snapshot_sha256'],
                '卡片B': other['id'], 'B状态': '已复核入图' if other.get('availability') == 'reviewed' else '待复核',
                'B年份': other['year'], 'B类别': other['kind'],
                'B原编号': other['raw_number'], 'B名称': other['title'], 'B申报地区或单位': other['area'],
                'B原表链接': other['url'], 'B原表定位': other['locator'], 'B原表SHA256': other['snapshot_sha256'],
                '名称是否完全一致（忽略空白）': re.sub(r'\s+', '', item['title']) == re.sub(r'\s+', '', other['title']),
                '判读范围': '相同序号及行政登记号；名称和地区需核对，不表示相同单篇或传播关系', '人工复核': '待复核'})
    return rows


def heritage_2021_csv_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r'corpus_cn_ich_2021_(?:ext_)?\d{4}', record['id']):
            continue
        data = record['evidence'].get('heritage_2021', {})
        pdf = next((source for source in record['sources'] if source['type'] == 'heritage_register_2021_pdf'), {})
        index = next((source for source in record['sources'] if source['type'] == 'heritage_register_2021_index'), {})
        spatial = record['spatial'] or {}
        standards = ' | '.join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record['standards'].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({'卡片ID': record['id'], **data,
            '跨年对照卡片': ' | '.join(other['id'] for other in record['evidence'].get('heritage_comparisons', [])),
            '坐标': f"{spatial['lat']}, {spatial['lng']}" if spatial.get('lat') is not None and spatial.get('lng') is not None else '',
            '国际标准码': standards, '待核问题': ' | '.join(flag['description'] for flag in record['issues']),
            '原始公报链接': pdf.get('url'), '原始公报SHA256': pdf.get('content_sha256'),
            '字段索引SHA256': index.get('content_sha256'), '草稿SHA256': record['card_sha256'], '人工复核': '待复核'})
    return rows


def nitean_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r"case_kh_nitean_v\d{2}_\d{3}", record["id"]):
            continue
        data = record["evidence"].get("nitean_chapter", {})
        detail = next((s for s in record["sources"] if s["type"] == "nitean_chapter"), {})
        catalogue = next((s for s in record["sources"] if s["type"] == "nitean_catalogue"), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "目录卷次": data.get("目录卷次"), "卷内序号": data.get("目录卷内序号"),
            "目录总序号": data.get("目录总序号"), "目录高棉文题名": data.get("目录高棉文题名"),
            "详情高棉文题名": data.get("详情高棉文题名"), "题名是否一致": data.get("目录与详情题名一致"),
            "目录卷名": data.get("目录卷名"), "详情卷名": data.get("详情卷名"), "卷名是否一致": data.get("目录与详情卷名一致"),
            "页面段落数（含注记）": data.get("页面段落数（含注记）"), "页面所列卷册页码原文": " | ".join(data.get("页面所列卷册页码原文", [])),
            "页面脚注数": data.get("页面脚注数"), "脚注锚点": " | ".join(data.get("可定位脚注", [])),
            "页面显示次序": json.dumps(data.get("页面显示次序"), ensure_ascii=False) if data.get("页面显示次序") else "",
            "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
            "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
            "单篇原文链接": detail.get("url"), "单篇字段索引SHA256": detail.get("content_sha256"),
            "目录字段索引SHA256": catalogue.get("content_sha256"), "网页原响应SHA256": data.get("网页原响应 SHA256"),
            "网页观察时间": data.get("网页观察时间"), "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def sil_ilianen_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if record["id"] not in {"case_ph_ilianen_pilanduk", "case_ph_ilianen_tulalang"}:
            continue
        item = record["evidence"].get("sil_ilianen", {})
        source = next((s for s in record["sources"] if s["type"] == "sil_ilianen_catalogue"), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "馆方题名": item.get("馆方题名"), "馆方英文题名": item.get("馆方英文题名"),
                     "讲述人": item.get("讲述人"), "录音日期（非故事年代）": item.get("馆方录音日期"),
                     "馆方所列转写本": item.get("馆方提及的转写本"), "书目署名及年份（原字段）": item.get("转写本署名及年份（馆方原字段）"),
                     "转写本介绍链接": item.get("转写本介绍链接"), "在线样本链接": item.get("在线样本链接"),
                     "完整录音访问": item.get("完整录音访问"), "具体录音地点": "", "坐标":
                     f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
                     "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
                     "馆方目录链接": source.get("url"), "目录网页SHA256": source.get("content_sha256"),
                     "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def hmml_makassar_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if not re.fullmatch(r"corpus_hmml_makassar_\d{5}", record["id"]):
            continue
        data = record["evidence"].get("hmml_makassar", {})
        current = next((s for s in record["sources"] if s["type"] == "hmml_makassar_metadata"), {})
        legacy = next((s for s in record["sources"] if s["type"] == "hmml_legacy_candidate"), {})
        spatial = record["spatial"] or {}
        standards = " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in record["standards"].items()
                               if isinstance(codes, list) for code in codes)
        rows.append({"卡片ID": record["id"], "馆方档号": data.get("当前馆方档号"), "馆方记录号": data.get("当前馆方记录号"),
                     "馆方编目说明": data.get("当前编目说明"), "馆方在线标志": data.get("馆方开放查看标志"),
                     "馆方访问限制": data.get("馆方访问限制原字段"), "数字化日期（非故事年代）": data.get("数字化日期原字段（非故事年代）"),
                     "旧目录候选卷次": data.get("旧目录卷次候选"), "旧目录原文字题名候选": data.get("旧目录题名候选（原文字）"),
                     "旧目录罗马字题名候选": data.get("旧目录题名候选（罗马字）"), "旧目录署名候选": data.get("旧目录署名候选"),
                     "旧目录语言候选": data.get("旧目录语言候选"), "旧目录文字候选": data.get("旧目录文字候选"),
                     "旧目录原历抄写日期候选": data.get("旧目录原历抄写日期候选"),
                     "旧目录公历抄写日期候选": data.get("旧目录公历抄写日期候选"),
                     "馆藏地": "Makassar (Sulawesi Selatan)", "采录地点": "", "采录时间": "",
                     "坐标": f"{spatial['lat']}, {spatial['lng']}" if spatial.get("lat") is not None and spatial.get("lng") is not None else "",
                     "标准码": standards, "待核问题": " | ".join(flag["description"] for flag in record["issues"]),
                     "馆方记录链接": current.get("url"), "旧目录链接（当次无法访问）": legacy.get("url"),
                     "馆方数据选取SHA256": current.get("content_sha256"), "旧目录候选索引SHA256": legacy.get("content_sha256"),
                     "草稿SHA256": record["card_sha256"], "人工复核": "待复核"})
    return rows


def hmml_inventory_rows(records: list[dict]) -> list[dict]:
    root = next((record for record in records if record["id"] == HMML_ROOT_ID), None)
    if not root:
        return []
    source = next((s for s in root["sources"] if s["type"] == "hmml_makassar_metadata"), None)
    if not source or not source.get("local_path") or not source.get("content_sha256"):
        return []
    path = Path(source["local_path"])
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        with path.open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() != source["content_sha256"]:
                return []
        manifest, items = load_hmml_selection(path.parent)
    except (ValueError, OSError, KeyError, TypeError):
        return []
    candidates = {row["馆方档号"]: row for row in hmml_makassar_rows(records) if row["馆方档号"]}
    raw_hash = {entry["project"]: entry["sha256"] for entry in manifest["entries"]}
    rows = []
    for project, item in sorted(items.items()):
        candidate = candidates.get(project)
        rows.append({"馆方档号": project, "馆方记录号": item["id"], "馆藏地": (item.get("city") or {}).get("name"),
                     "馆藏": (item.get("repository") or {}).get("name"), "馆方类型": item.get("objectType"),
                     "馆方编目说明": item.get("notes"), "馆方在线标志": item.get("viewableOnline"),
                     "馆方访问限制": item.get("accessRestriction"), "数字化日期（非故事年代）": item.get("captureDateDisplay"),
                     "旧目录候选题名": candidate.get("旧目录罗马字题名候选") if candidate else "",
                     "待审卡片ID": candidate.get("卡片ID") if candidate else "", "采录地点": "", "坐标": "", "标准码": "",
                     "筛查状态": "候选分卷待人工复核" if candidate else "未筛查；不等于民间故事",
                     "馆方记录链接": item["PURL"], "馆方单条元数据SHA256": raw_hash[project],
                     "数据许可": "CC BY 4.0（馆方元数据；影像权利另核）", "人工筛查": ""})
    return rows


def export(vault: Path, output: Path, tables: Path, schema: Path, maps: Path, study: Path,
           catalogue: Path, table: Path, wikidata: Path = DEFAULT_WIKIDATA) -> dict:
    with vault_writer(vault):
        return _export_locked(vault, output, tables, schema, maps, study, catalogue, table, wikidata)


def _export_locked(vault: Path, output: Path, tables: Path, schema: Path, maps: Path, study: Path,
                   catalogue: Path, table: Path, wikidata: Path) -> dict:
    queue = vault / "00_drafts"
    scottish_folder = queue / "scottish_witchcraft"
    scottish, unmatched = scottish_records(vault, tables, schema, maps, wikidata) if any(scottish_folder.glob("*.md")) else ([], [])
    berezkin_folder = queue / "berezkin_distribution"
    has_shared = any((queue / "regional_sources" / f"{node_id}.md").is_file() for node_id in REGIONAL_HUBS.values())
    berezkin = berezkin_records(vault, study, catalogue, table) if any(berezkin_folder.glob("*.md")) or has_shared else []
    nichibun = nichibun_records(vault)
    duchas = duchas_records(vault)
    remaining = other_records(vault, table)
    known = scottish + berezkin + nichibun + duchas + remaining
    intake = generic_records(vault, table, {record["card_path"] for record in known})
    records = known + intake
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("复核目录含有重复卡片 ID。")
    summary = {"records": len(records), "collections": dict(Counter(r["collection"] for r in records)),
               "flags": dict(Counter(flag["code"] for r in records for flag in r["issues"])),
               "unmatched_scottish_references": len(unmatched)}
    document = {"version": 1, "summary": summary, "records": records, "unmatched_references": unmatched}
    columns = ["编号", "批次", "标题", "文件", "体裁", "出处及定位", "地点", "纬度", "经度", "标准码",
               "出处疑点", "坐标疑点", "标准码疑点", "体裁疑点", "草稿SHA256", "人工复核", "复核人", "复核备注"]
    rows = []
    for record in records:
        by_category = defaultdict(list)
        for flag in record["issues"]:
            by_category[flag["category"]].append(flag["description"])
        spatial = record["spatial"] or {}
        standards = record["standards"]
        rows.append({"编号": record["id"], "批次": record["collection"], "标题": record["title"],
                     "文件": record["card_path"], "体裁": record["genre"], "出处及定位": " | ".join(
                         " / ".join(filter(None, (source["citation"], source["locator"], source["url"])))
                         for source in record["sources"]),
                     "地点": spatial.get("location_name"), "纬度": spatial.get("lat"), "经度": spatial.get("lng"),
                     "标准码": " | ".join(f"{STANDARD_NAMES[name]} {code}" for name, codes in standards.items()
                                            if isinstance(codes, list) for code in codes),
                     "出处疑点": " | ".join(by_category["source"]), "坐标疑点": " | ".join(by_category["coordinate"]),
                     "标准码疑点": " | ".join(by_category["standard"]), "体裁疑点": " | ".join(by_category["classification"]),
                     "草稿SHA256": record["card_sha256"],
                     "人工复核": "待复核", "复核人": "", "复核备注": ""})
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".astraia-review-", dir=output) as temporary:
        stage = Path(temporary)
        for collection, filename in (("scottish", "scottish.csv"), ("berezkin", "berezkin.csv"),
                                     ("nichibun", "nichibun.csv"), ("duchas", "duchas.csv"),
                                     ("regional", "regional.csv"), ("research", "research.csv"),
                                     ("asia", "asia.csv"), ("intake", "intake.csv")):
            subset = [row for row in rows if row["批次"] == collection]
            (stage / filename).write_bytes(csv_content(subset, columns))
        (stage / "unmatched_references.csv").write_bytes(csv_content(unmatched, ["ReferenceRef", "CaseRef", "SourceRef", "Reference", "Notes"]))
        coordinate_columns = ["档号", "姓名", "原登记住地", "原登记郡", "教区", "原格网字母", "原格网东距", "原格网北距",
                              "原生成纬度", "原生成经度", "原生成方法", "当前草稿纬度", "当前草稿经度", "Wikidata实体",
                              "同实体其他档号", "地图候选点", "距原生成点最近公里", "出处和坐标疑点", "调查库来源", "地图来源",
                              "地图文件", "地图SHA256", "档号快照SHA256", "档号快照时间", "草稿文件", "草稿SHA256"]
        (stage / "scottish_coordinates.csv").write_bytes(csv_content(scottish_coordinate_rows(scottish), coordinate_columns))
        lao_columns = ["卡片ID", "馆藏记录号", "PLMP档号", "DLLM编号", "标题", "馆藏地点", "候选纬度", "候选经度",
                       "坐标用途", "手稿日期原字段", "册页及影像数", "语言", "文字", "同号馆藏", "标准码", "出处与坐标疑点",
                       "馆藏影像页面", "数据快照", "数据SHA256", "署名与许可", "草稿SHA256"]
        (stage / "lao_manuscript_review.csv").write_bytes(csv_content(lao_manuscript_rows(intake), lao_columns))
        lanna_columns=['卡片ID','馆藏编号','标题','馆藏档号','语言','文字','馆藏地点','馆藏纬度原字段','馆藏经度原字段',
                       '手稿日期原字段','同号馆藏候选','坐标','标准码','待核问题','馆方原图页面','检索快照SHA256',
                       '署名与许可','草稿SHA256','人工复核']
        (stage / 'lanna_manuscript_review.csv').write_bytes(csv_content(lanna_manuscript_rows(intake),lanna_columns))
        yuhuan_columns = ["卡片ID", "标题", "目录类别", "起始印刷页", "起始PDF页", "采录旁注候选", "旁注印刷页", "早期刊载候选", "网页版本",
                          "坐标", "标准码", "待核问题", "原页链接", "扫描SHA256", "草稿SHA256", "人工复核"]
        (stage / "yuhuan_story_review.csv").write_bytes(csv_content(yuhuan_story_rows(intake), yuhuan_columns))
        sinica_columns = ["卡片ID", "记录号", "目录组", "原目录题名", "详情档案名称", "详情族别", "采集日期", "采集地点",
                          "报道人", "记音者", "翻译者", "候选社区地标", "候选纬度", "候选经度", "候选坐标范围",
                          "坐标", "标准码", "待核问题", "原站详情", "目录索引SHA256",
                          "详情索引SHA256", "GIS点位SHA256", "草稿SHA256", "人工复核"]
        (stage / "sinica_oral_review.csv").write_bytes(csv_content(sinica_oral_rows(intake), sinica_columns))
        vietnam_cham_columns = ["卡片ID", "目录序号", "目录越南文题名", "详情页题名", "详情标题原显示", "标题脚注标记", "可见段落数", "正文语言", "站点Date Created",
                                "前言落款", "前言署名", "馆方贡献者字段", "出版者字段", "单篇讲述者", "单篇来源类别", "单篇采集地",
                                "坐标", "标准码", "待核问题", "原站详情", "字段快照SHA256", "原响应SHA256", "草稿SHA256", "人工复核"]
        (stage / "vietnam_cham_review.csv").write_bytes(csv_content(vietnam_cham_rows(intake), vietnam_cham_columns))
        shandong_columns = ["卡片ID", "镜像题名", "方志", "章节", "原页分组", "方志范围", "早期刊载线索", "作者候选",
                            "讲述人候选", "讲述人页面字形", "整理人候选", "角色与版本备注", "相关书目对照", "相关书目出处", "采录时间", "采录地点",
                            "坐标", "标准码", "待核问题", "镜像章节链接", "研究字段索引SHA256", "网页原响应SHA256", "草稿SHA256", "人工复核"]
        (stage / "shandong_mirror_review.csv").write_bytes(csv_content(shandong_mirror_rows(intake), shandong_columns))
        hmml_columns = ["卡片ID", "馆方档号", "馆方记录号", "馆方编目说明", "馆方在线标志", "馆方访问限制", "数字化日期（非故事年代）",
                        "旧目录候选卷次", "旧目录原文字题名候选", "旧目录罗马字题名候选", "旧目录署名候选", "旧目录语言候选", "旧目录文字候选",
                        "旧目录原历抄写日期候选", "旧目录公历抄写日期候选", "馆藏地", "采录地点", "采录时间", "坐标", "标准码", "待核问题",
                        "馆方记录链接", "旧目录链接（当次无法访问）", "馆方数据选取SHA256", "旧目录候选索引SHA256", "草稿SHA256", "人工复核"]
        (stage / "hmml_makassar_review.csv").write_bytes(csv_content(hmml_makassar_rows(intake), hmml_columns))
        inventory_columns = ["馆方档号", "馆方记录号", "馆藏地", "馆藏", "馆方类型", "馆方编目说明", "馆方在线标志", "馆方访问限制",
                             "数字化日期（非故事年代）", "旧目录候选题名", "待审卡片ID", "采录地点", "坐标", "标准码", "筛查状态", "馆方记录链接",
                             "馆方单条元数据SHA256", "数据许可", "人工筛查"]
        (stage / "hmml_makassar_inventory.csv").write_bytes(csv_content(hmml_inventory_rows(intake), inventory_columns))
        sil_columns = ["卡片ID", "馆方题名", "馆方英文题名", "讲述人", "录音日期（非故事年代）", "馆方所列转写本", "书目署名及年份（原字段）",
                       "转写本介绍链接", "在线样本链接", "完整录音访问", "具体录音地点", "坐标", "标准码", "待核问题", "馆方目录链接",
                       "目录网页SHA256", "草稿SHA256", "人工复核"]
        (stage / "philippines_ilianen_review.csv").write_bytes(csv_content(sil_ilianen_rows(intake), sil_columns))
        cole_columns = ['卡片ID', '原目录题名', '原目录主组', '原目录次组', '目录印刷页', 'OCR候选扫描序号',
                        'OCR标题相似度', 'OCR页脚数字吻合', 'OCR候选页范围', 'OCR候选页数', 'OCR逐页文件SHA256',
                        '坐标', '标准码', '待核问题', '原扫描候选链接',
                        '目录索引SHA256', '草稿SHA256', '人工复核']
        (stage / 'philippines_cole_1916_review.csv').write_bytes(csv_content(cole_rows(intake), cole_columns))
        jade_columns = ['卡片ID', '原目录题名', '整理题名', '原目录分类', '阅读顺序（非原编号）', '目录印刷页',
                        'OCR扫描序号', '扫描叶号', '查看器索引', 'OCR标题相似度', 'OCR页脚数字吻合', 'OCR标题较目录扩展',
                        '1916年同题候选卡片', '坐标', '标准码', '待核问题', '原扫描候选链接', '草稿SHA256', '人工复核']
        (stage / 'jade_1922_review.csv').write_bytes(csv_content(jade_rows(intake), jade_columns))
        comparison_columns = ['类别', '甲卡片', '甲原页', '乙卡片', '乙原页', '对照依据', '人工复核']
        (stage / 'early_asia_versions_review.csv').write_bytes(csv_content(early_comparison_rows(intake), comparison_columns))
        pangloss_columns = ["卡片ID", "馆藏编号", "馆方目录题名", "馆方其他语言题名", "题名对照分组", "馆方目录研究者字段", "馆方详情研究者字段",
                            "馆方目录讲述者字段", "馆方详情讲述者字段", "两处讲述者字段显示是否对应", "两处研究者字段显示是否对应",
                            "馆方目录录音日期", "馆方详情录音日期原字段", "两处日期是否一致",
                            "馆方录音地点原字段", "馆方时长", "馆方媒介图标", "馆方转写图标", "馆方许可原字段", "关联音视频资源数", "关联附件数", "XML分句数", "附件单独许可", "接口观察时间", "分句索引SHA256", "地点对照依据", "坐标", "标准码", "待核问题",
                            "馆方单条链接", "馆方DOI", "单条页面SHA256", "目录页面SHA256", "草稿SHA256", "人工复核"]
        (stage / "pangloss_yongning_na_review.csv").write_bytes(csv_content(pangloss_na_rows(intake), pangloss_columns))
        na_tone_columns = ['出版PDF页', '印刷页', '页面链接序号', '书中DOI编号', '原始片段', '片段性质', '目录录音号',
                           '对应依据', 'DataCite是否查询', 'DataCite资源类型', '登记权利原字段', '待审卡片ID',
                           '待核问题', '书中PDF页链接', '书中原始DOI链接', '对照索引SHA256', '人工复核']
        (stage / 'pangloss_yongning_na_tone_book_links.csv').write_bytes(csv_content(na_tone_link_rows(intake), na_tone_columns))
        inventory_columns = ['馆藏编号', '馆方目录题名', '目录研究者', '目录讲述者', '目录录音日期', '时长', '题名提示',
                             '筛查状态', '本轮选取理由', '待核对照卡片', '待审卡片ID', '单条详情', '坐标', '标准码', '待核问题',
                             '馆方单条链接', '馆方DOI', '目录页面SHA256', '草稿SHA256', '人工复核']
        (stage / 'pangloss_yongning_na_inventory.csv').write_bytes(csv_content(pangloss_na_inventory_rows(intake), inventory_columns))
        japhug_columns = ['卡片ID', '馆藏编号', '目录题名', '目录研究者', '目录讲述者', '目录录音日期', '录音时长',
                          '媒介图标', '转写图标', '详情状态', '首轮选取依据', '后续详情补充', '详情其他题名', '详情研究者', '详情讲述者',
                          '详情录音日期', '详情录音地点', '详情许可原字段', '目录与详情讲述者一致', '目录与详情研究者一致',
                          '目录与详情日期一致', '语料背景研究', '坐标', '标准码', '待核问题', '馆方详情链接', '馆方DOI', '详情页面SHA256',
                          '目录页面SHA256', '草稿SHA256', '人工复核']
        (stage / 'pangloss_japhug_review.csv').write_bytes(csv_content(pangloss_japhug_rows(intake), japhug_columns))
        khmu_columns = ['卡片ID', '馆藏编号', '目录题名', '目录研究者', '目录讲述者', '目录录音日期', '录音时长',
                        '媒介图标', '转写图标', '详情状态', '首轮选取依据', '后续详情补充', '详情其他题名', '详情研究者', '详情讲述者',
                        '详情录音日期', '详情录音地点', '详情许可原字段', '目录与详情讲述者一致', '目录与详情研究者一致',
                        '目录与详情日期一致', '日期范围端点一致', '目录对照分组', '目录对照依据', '待核对照编号', '相关研究链接', '坐标', '标准码', '待核问题',
                        '馆方详情链接', '馆方DOI', '详情页面SHA256', '目录页面SHA256', '对照索引SHA256', '草稿SHA256', '人工复核']
        (stage / 'pangloss_khmu_review.csv').write_bytes(csv_content(pangloss_khmu_rows(intake), khmu_columns))
        segment_columns = ["卡片ID", "馆藏编号", "对应音视频资源", "音视频许可原字段", "附件编号", "附件DOI", "附件单独许可", "原语语言标记",
                           "分句序号", "XML原始ID", "开始秒", "结束秒", "时间有效性", "原语文字形式", "译文语言标记", "原站分句链接", "接口观察时间", "分句索引SHA256", "人工复核"]
        (stage / "pangloss_yongning_na_segments.csv").write_bytes(csv_content(pangloss_na_segment_rows(intake), segment_columns))
        bl_columns = ["卡片ID", "馆方档号", "馆方记录号", "馆方题名", "馆方内容说明", "馆方册页数", "馆方语言", "馆方文字",
                      "本册起始日期", "本册结束日期", "馆藏组起始日期", "馆藏组结束日期", "数字化字段", "数字化字段链接",
                      "坐标", "标准码", "待核问题", "馆方单册链接", "单册网页SHA256", "馆藏组网页SHA256", "目录文字许可", "草稿SHA256", "人工复核"]
        (stage / "bl_khmer_folding_books_review.csv").write_bytes(csv_content(bl_khmer_rows(intake), bl_columns))
        yi_columns = ['卡片ID', '馆方档号', '馆方记录号', '馆方题名', '馆方内容说明', '馆方文件数和时长', '馆方语言字段',
                      '馆方日期起始原字段', '馆方日期结束原字段', '馆方日期范围原字段', '馆方访问条件',
                      '馆藏组范围与总时长', '六组时长字段相加分钟数（待核）', '坐标', '标准码', '待核问题',
                      '馆方子组链接', '子组网页SHA256', '馆藏组网页SHA256', '目录文字许可', '草稿SHA256', '人工复核']
        (stage / 'bl_yi_recordings_review.csv').write_bytes(csv_content(bl_yi_rows(intake), yi_columns))
        yi_project_columns = ['馆方档号', '馆方记录号', '筛查状态', '待审卡片ID', '检索题名原字段', '检索摘要原字段（可能截断）',
                              '检索语言原字段', '检索日期范围原字段', '检索范围原字段', '筛查线索（非体裁判定）',
                              '同题目录档号（非去重依据）', '坐标', '标准码', '待核问题', '馆方目录链接', '馆方影像入口（未取得）', '检索页面',
                              '检索网页SHA256', '检索观察时间', '单件或父级网页SHA256', '草稿SHA256', '人工复核']
        (stage / 'bl_yi_project_inventory.csv').write_bytes(csv_content(bl_yi_project_inventory_rows(intake), yi_project_columns))
        dongjing_columns = ['馆方档号', '卡片ID', '馆方题名', '馆方内容说明', '内容提示（非体裁判定）', '馆方材料类型',
                            '馆方语言原字段', '馆方范围原字段', '范围字段首项文件数（待核）', '馆藏组范围原字段',
                            '单件范围字段首项文件数相加', '题名方括号年份', '馆方起始日期原字段', '馆方结束日期原字段',
                            '馆方日期范围原字段', '题名年份落在起止字段范围', '日期范围年份落在起止字段范围',
                            '馆方内部项目标识原字段', '馆方数字内容原字段',
                            '馆方单件访问条件原字段', '坐标', '标准码', '待核问题', '馆方单件链接', '馆方网页SHA256', '草稿SHA256', '人工复核']
        (stage / 'bl_dongjing_recordings_inventory.csv').write_bytes(csv_content(bl_dongjing_inventory_rows(intake), dongjing_columns))
        burma_columns = ['馆方档号', '卡片ID', '馆方题名', '馆方语言原字段', '馆方内容说明', '馆方日期范围原字段',
                         '馆方唱片原编号', 'DSAL严格编号候选数', 'DSAL半号文字候选数', 'DSAL候选方式',
                         'DSAL题名原字段', 'DSAL语言原字段', 'DSAL说话人原字段',
                         'DSAL说话人来源地区原字段', 'DSAL地点原字段', '坐标', '标准码', '待核问题', '馆方单件链接',
                         'DSAL候选链接（待核）', '馆方网页SHA256', 'DSAL字段索引SHA256',
                         'DSAL原响应SHA256（原响应未保存）', 'DSAL观察时间', '草稿SHA256', '人工复核']
        (stage / 'bl_burma_recordings_inventory.csv').write_bytes(csv_content(bl_burma_inventory_rows(intake), burma_columns))
        minyag_columns = ['目录序号', '馆方目录题名', '目录段落署名候选', '筛查类别', '筛查状态', '卡片ID',
                          '馆藏总述文件数', '页面编号条目数', '计数口径', '坐标', '标准码', '待核问题',
                          '旧档案链接（待核）', '馆藏目录链接', '现行单件链接', '现行单件姓名原写法', '现行单件权利标记',
                          '馆藏目录SHA256', '使用范围', '草稿SHA256', '人工复核']
        (stage / 'minyag_wolp_inventory.csv').write_bytes(csv_content(minyag_inventory_rows(intake), minyag_columns))
        temiar_columns = ['目录序号', '馆方目录题名', '筛查类别', '筛查状态', '卡片ID', '共用链接疑点',
                          '馆方总体音轨数', '另列后期音轨数', '歌曲说明所称音轨数', '目录编号条目数', '计数口径',
                          '坐标', '标准码', '待核问题', '旧档案链接（待核）', '旧试听入口（待核）',
                          '现行单件链接', '现行 Authors 原字段', '现行单件权利标记', '馆藏目录链接',
                          '馆藏目录SHA256', '使用范围', '草稿SHA256', '人工复核']
        (stage / 'temiar_wolp_inventory.csv').write_bytes(csv_content(temiar_inventory_rows(intake), temiar_columns))
        pumi_columns = ['目录序号', '馆方目录题名', '题名标签', '筛查状态', '卡片ID', '旧目录总述音频文件数', '页面编号条目数',
                        '现行单件所载馆藏文件数', '计数口径', '坐标', '标准码', '待核问题', '旧档案链接（待核）',
                        '旧试听入口（待核）', '现行单件链接', '现行 Authors 原字段', '现行单件许可原字段',
                        '馆藏目录链接', '馆藏目录SHA256', '使用范围', '草稿SHA256', '人工复核']
        (stage / 'pumi_wolp_inventory.csv').write_bytes(csv_content(pumi_inventory_rows(intake), pumi_columns))
        palue_columns = ['馆方编号', '筛查状态', '卡片ID', '馆方类型字段', '目录显式 Genre 标签', '标签说明',
                         '主题语种原字段', '主题语种代码原字段', '内容语言原字段', '内容语言代码原字段',
                         '说话人原字段', '采录者原字段', '研究者原字段', '存交者原字段', '顾问原字段',
                         '转写者原字段', '译者原字段', '起始日期原字段（性质待核）', '结束日期原字段（性质待核）',
                         '地区原字段（非事件坐标）', '格式时长原字段', '权利原字段', '访问权利原字段', '坐标', '标准码', '待核问题',
                         '馆方单件链接', '永久标识', '检索接口页', '字段索引SHA256', '原始响应SHA256（原响应未保存）',
                         '观察时间', '草稿SHA256', '人工复核']
        (stage / 'palue_inventory.csv').write_bytes(csv_content(palue_inventory_rows(intake), palue_columns))
        zibuyu_columns = ['记录类型', '卷次', '分卷篇序', '分卷篇名', '分卷锚点', '分卷修订号', '候选方式',
                          '总目录候选篇序', '总目录候选题名', '总目录候选锚点', '锚点一致', '纯文字SHA256',
                          '段落数', '卡片ID', '固定修订原文', '坐标', '标准码', '待核问题', '草稿SHA256', '人工复核']
        (stage / 'zibuyu_inventory.csv').write_bytes(csv_content(zibuyu_inventory_rows(records), zibuyu_columns))
        lowell_columns = ["卡片ID", "馆方记录号", "馆方题名", "馆方日期", "馆方署名", "馆方语言", "馆方格式", "馆方标识", "馆方覆盖范围",
                          "可见文件链接数", "馆方使用范围", "坐标", "标准码", "待核问题", "馆方单件链接", "字段索引SHA256",
                          "网页原响应SHA256", "观察时间", "草稿SHA256", "人工复核"]
        (stage / "lowell_sea_folktales_review.csv").write_bytes(csv_content(lowell_sea_rows(intake), lowell_columns))
        inventory_columns = ["馆方记录号", "馆方题名", "馆方日期", "馆方语言", "馆方格式", "馆方覆盖范围", "可见文件链接数", "筛查状态",
                             "待审卡片ID", "馆方单件链接", "字段索引SHA256", "网页原响应SHA256", "观察时间"]
        (stage / "lowell_sea_folktales_inventory.csv").write_bytes(csv_content(lowell_inventory_rows(intake), inventory_columns))
        nitean_columns = ["卡片ID", "目录卷次", "卷内序号", "目录总序号", "目录高棉文题名", "详情高棉文题名", "题名是否一致",
                          "目录卷名", "详情卷名", "卷名是否一致", "页面段落数（含注记）", "页面所列卷册页码原文", "页面脚注数", "脚注锚点",
                          "页面显示次序", "坐标", "标准码", "待核问题", "单篇原文链接", "单篇字段索引SHA256", "目录字段索引SHA256",
                          "网页原响应SHA256", "网页观察时间", "草稿SHA256", "人工复核"]
        (stage / "khmer_nitean_chapter_review.csv").write_bytes(csv_content(nitean_rows(intake), nitean_columns))
        heritage_columns = ['卡片ID', '名录类别', '表内顺序', '序号', '项目编号（非母题标准码）', '项目名称',
                            '申报地区或单位（原表）', '坐标', '国际标准码', '待核问题', '原始名录链接',
                            '原始名录SHA256', '草稿SHA256', '人工复核']
        (stage / 'chinese_heritage_2011_review.csv').write_bytes(csv_content(heritage_2011_csv_rows(intake), heritage_columns))
        batch_columns = ['卡片ID', '名录年份', '名录类别', '表内顺序', '序号', '项目编号（非母题标准码）', '项目名称',
                         '申报地区或单位（原表）', '跨年对照卡片', '坐标', '国际标准码', '待核问题', '原始名录链接',
                         '原始名录SHA256', '草稿SHA256', '人工复核']
        (stage / 'chinese_heritage_2008_2014_review.csv').write_bytes(csv_content(heritage_batch_csv_rows(intake), batch_columns))
        comparison_columns = ['序号', '行政项目编号数字', '卡片A', 'A年份', 'A类别', 'A原编号', 'A名称',
                              'A申报地区或单位', 'A原表链接', 'A原表定位', 'A原表SHA256',
                              '卡片B', 'B状态', 'B年份', 'B类别', 'B原编号', 'B名称', 'B申报地区或单位',
                              'B原表链接', 'B原表定位', 'B原表SHA256', '名称是否完全一致（忽略空白）', '判读范围', '人工复核']
        (stage / 'chinese_heritage_cross_year_review.csv').write_bytes(csv_content(heritage_comparison_csv_rows(intake), comparison_columns))
        heritage_2021_columns = ['卡片ID', '名录年份', '名录类别', '表内顺序', '序号原文', '序号',
                                 '项目编号（非母题标准码）', '项目名称', '申报地区或单位（原表）', 'PDF 页码', '印刷页码',
                                 '跨年对照卡片', '坐标', '国际标准码', '待核问题', '原始公报链接', '原始公报SHA256',
                                 '字段索引SHA256', '草稿SHA256', '人工复核']
        (stage / 'chinese_heritage_2021_review.csv').write_bytes(csv_content(heritage_2021_csv_rows(intake), heritage_2021_columns))
        payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        (stage / "data.js").write_text("window.ASTRAIA_REVIEW_DATA=" + payload + ";\n", encoding="utf-8")
        (stage / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for file in stage.iterdir():
            file.replace(output / file.name)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tables", type=Path, default=DEFAULT_TABLES)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--maps", type=Path, default=DEFAULT_MAPS)
    parser.add_argument("--wikidata", type=Path, default=DEFAULT_WIKIDATA)
    parser.add_argument("--study", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--code-table", type=Path, default=DEFAULT_CODE_TABLE)
    args = parser.parse_args()
    summary = export(args.vault, args.output, args.tables, args.schema, args.maps, args.study, args.catalogue, args.code_table, args.wikidata)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
