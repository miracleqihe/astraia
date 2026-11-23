"""Stage source-attributed dataset batches for human review."""

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from zipfile import BadZipFile

import yaml

from pipeline.berezkin_distribution import distribution_cards, read_study, update_code_table
from pipeline.bl_khmer import ROOT_URL as BL_KHMER_URL, bl_cards
from pipeline.bl_yi import cards as bl_yi_cards
from pipeline.bl_burma import cards as bl_burma_cards
from pipeline.bl_dongjing import cards as bl_dongjing_cards
from pipeline.bl_yi_project import cards as bl_yi_project_cards
from pipeline.chinese_heritage import SOURCE_URL as CHINESE_HERITAGE_URL, heritage_cards
from pipeline.chinese_heritage_2011 import SOURCE_URL as CHINESE_HERITAGE_2011_URL, heritage_2011_cards
from pipeline.chinese_heritage_batches import CONFIG as CHINESE_HERITAGE_BATCHES, heritage_cards as heritage_batch_cards
from pipeline.chinese_heritage_2021 import PDF_URL as HERITAGE_2021_URL, heritage_2021_cards
from pipeline.duchas import COLLECTION as DUCHAS_COLLECTION, CORPUS as DUCHAS_CORPUS, INDEX as DUCHAS_INDEX
from pipeline.duchas import cited_story_ids as duchas_cited_story_ids, duchas_cards, story_node_id as duchas_node_id
from pipeline.early_asia_editions import JADE_BOOK, SALEEBY_BOOK, early_edition_cards
from pipeline.fetch_duchas import candidates as duchas_candidates
from pipeline.ingest_agent import DEFAULT_CODE_TABLE, DEFAULT_VAULT, DRAFT_DIRECTORY, PROJECT_ROOT, serialize_card
from pipeline.intake_sources import IntakeError
from pipeline.hmml_makassar import DATASET_PAGE as HMML_DATASET_PAGE, hmml_cards
from pipeline.khmer_nitean import CATALOGUE_URL as NITEAN_URL, nitean_cards
from pipeline.korea_aks_cards import korea_cards
from pipeline.korea_aks_inventory import SOURCE_URL as KOREA_AKS_URL
from pipeline.local_standards import load_code_table, verify_codes
from pipeline.lao_manuscripts import lao_cards
from pipeline.lanna_manuscripts import lanna_cards
from pipeline.fetch_lanna import SEARCH_URL as LANNA_SEARCH_URL
from pipeline.lowell_folktales import COLLECTION_URL as LOWELL_SEA_URL, lowell_cards
from pipeline.minyag_wolp import cards as minyag_wolp_cards
from pipeline.fetch_minyag_wolp import CATALOGUE_URL as MINYAG_WOLP_URL
from pipeline.temiar_wolp import cards as temiar_wolp_cards
from pipeline.fetch_temiar_wolp import CATALOGUE_URL as TEMIAR_WOLP_URL
from pipeline.pumi_wolp import cards as pumi_wolp_cards
from pipeline.fetch_pumi_wolp import CATALOGUE_URL as PUMI_WOLP_URL
from pipeline.palue_inventory import cards as palue_inventory_cards, COLLECTION_URL as PALUE_URL
from pipeline.zibuyu import cards as zibuyu_cards, EXISTING_ID as ZIBUYU_EXISTING
from pipeline.fetch_zibuyu import page_url as zibuyu_page_url
from pipeline.nichibun import CORPUS as NICHIBUN_CORPUS, INDEX as NICHIBUN_INDEX
from pipeline.nichibun import SEARCH_URL, nichibun_cards, node_id as nichibun_node_id
from pipeline.node_model import LAYER_BY_TYPE, NodeMetadata
from pipeline.philippines_sil import SOURCE_URL as SIL_ILIANEN_URL, ilianen_cards
from pipeline.philippines_cole import BOOK_URL as COLE_BOOK_URL, cole_cards
from pipeline.pangloss_na import CORPUS_URL as PANGLOSS_NA_URL, pangloss_cards
from pipeline.pangloss_na_context import context_cards as pangloss_na_context_cards
from pipeline.pangloss_na_catalogue import cards as pangloss_na_catalogue_cards
from pipeline.pangloss_japhug import CORPUS_URL as PANGLOSS_JAPHUG_URL, japhug_cards
from pipeline.pangloss_khmu import CORPUS_URL as PANGLOSS_KHMU_URL, khmu_cards
from pipeline.scottish_witchcraft import DATASET_URL, MAP_URL, scottish_cards
from pipeline.shandong_mirrors import mirror_cards
from pipeline.sinica_oral import sinica_cards
from pipeline.thai_folktales import DATASET_URL as THAI_DATASET_URL, thai_cards
from pipeline.vietnam_cham import cham_cards
from pipeline.yuhuan_stories import PDF_URL as YUHUAN_PDF_URL, yuhuan_cards
from pipeline.vault import FrontmatterLoader, load_vault, parse_card
from pipeline.vault_write import vault_writer


def curated_cards(path: Path):
    source = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=FrontmatterLoader)
    if not isinstance(source, dict) or source.get("version") != 1 or not isinstance(source.get("cards"), list):
        raise IntakeError("来源清单须包含 version: 1 和 cards 列表。")
    for entry in source["cards"]:
        data = dict(entry)
        body = data.pop("markdown")
        if not isinstance(body, str) or not body.strip():
            raise IntakeError(f"来源卡片缺少正文。{data.get('id', '')}")
        tier = data.get("credibility_tier", "B")
        model = {"spatial": None, "temporal": None, "standards": {}, "credibility_tier": tier, **data,
                 "z_layer": LAYER_BY_TYPE[data["node_type"]], "is_fictional_quarantine": tier == "F",
                 "audit": {"created_at": date.today(), "reviewed_by_human": False}}
        yield NodeMetadata.model_validate(model), "\n" + body


def stage_batch(vault: Path, batch: str, cards, code_table: Path, source: dict) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", batch):
        raise IntakeError("批次名称须以小写英文字母开头，可包含数字和下划线。")
    table = load_code_table(code_table)
    queue = vault / DRAFT_DIRECTORY
    target = queue / batch
    with vault_writer(vault):
        if target.exists():
            raise IntakeError(f"已保留现有批次。{target}")
        queue.mkdir(exist_ok=True)
        existing = set(load_vault(vault))
        existing.update(path.stem for path in queue.rglob("*.md"))
        totals = {"records": 0, "with_coordinates": 0, "with_years": 0, "fiction": 0, "indexed": 0}
        with TemporaryDirectory(prefix=".astraia-import-", dir=vault) as temporary:
            candidate = Path(temporary) / batch
            candidate.mkdir()
            for metadata, body in cards:
                if metadata.id in existing:
                    raise IntakeError(f"已存在卡片 {metadata.id}，批次未写入。")
                if metadata.audit.reviewed_by_human or metadata.audit.is_sample or not metadata.sources:
                    raise IntakeError(f"批量入库只接收有出处的待审卡片。{metadata.id}")
                verify_codes(metadata.standards, table)
                existing.add(metadata.id)
                (candidate / f"{metadata.id}.md").write_bytes(serialize_card(metadata, body))
                totals["records"] += 1
                totals["with_coordinates"] += bool(metadata.spatial and metadata.spatial.lat is not None)
                totals["with_years"] += bool(metadata.temporal and metadata.temporal.year_start is not None)
                totals["fiction"] += metadata.is_fictional_quarantine
                totals["indexed"] += any(metadata.standards.model_dump().values())
            if not totals["records"]:
                raise IntakeError("没有可导入的记录。")
            manifest = {"batch": batch, "review_state": "pending", "source": source, "counts": totals}
            (candidate / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            candidate.rename(target)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    common.add_argument("--code-table", type=Path, default=DEFAULT_CODE_TABLE)
    common.add_argument("--batch")
    commands = parser.add_subparsers(dest="adapter", required=True)
    scottish = commands.add_parser("scottish", parents=[common], help="爱丁堡调查库发布档案")
    scottish.add_argument("--tables", type=Path, required=True)
    scottish.add_argument("--schema", type=Path, required=True)
    scottish.add_argument("--maps", type=Path)
    regional = commands.add_parser("references", parents=[common], help="来源注释与区域样本")
    regional.add_argument("--records", type=Path, default=PROJECT_ROOT / "reference" / "regional_records.yaml")
    heritage = commands.add_parser("chinese-heritage", parents=[common], help="第一批国家级非遗名录中的民间文学项目")
    heritage.add_argument("--file", type=Path, required=True, help="文化和旅游部通知的本地 HTML 快照")
    heritage_2011 = commands.add_parser("chinese-heritage-2011", parents=[common], help="2011 年国家级民间文学名录与扩展项目")
    heritage_2011.add_argument("--file", type=Path, required=True, help="文化和旅游部通知的本地 HTML 快照")
    heritage_batch = commands.add_parser("chinese-heritage-batch", parents=[common], help="2008 或 2014 年国家级民间文学项目与扩展项目")
    heritage_batch.add_argument("--year", type=int, choices=sorted(CHINESE_HERITAGE_BATCHES), required=True)
    heritage_batch.add_argument("--file", type=Path, required=True, help="政府公开名录的本地 HTML 快照")
    heritage_2021 = commands.add_parser("chinese-heritage-2021", parents=[common], help="2021 年国家级民间文学项目与扩展项目")
    heritage_2021.add_argument("--pdf", type=Path, required=True, help="国务院公报原 PDF 快照")
    heritage_2021.add_argument("--index", type=Path, required=True, help="双引擎核对的 PDF 表格字段索引")
    thai = commands.add_parser("thai-folktales", parents=[common], help="泰国诗琳通人类学中心泰语故事 JSON")
    thai.add_argument("--file", type=Path, required=True, help="馆藏 JSON 原始快照")
    thai.add_argument("--catalogue", type=Path, required=True, help="馆藏目录与许可说明的 HTML 快照")
    lao = commands.add_parser("lao-manuscripts", parents=[common], help="老挝数字手稿馆民间故事分类的本地检索快照")
    lao.add_argument("--snapshots", type=Path, required=True, help="含 manifest.json 与分页 JSON 的目录")
    lanna = commands.add_parser("lanna-folktales", parents=[common], help="北泰数字手稿馆 Folk Tale 类馆藏")
    lanna.add_argument("--snapshots", type=Path, required=True, help="含分页与凭据的检索快照目录")
    sinica = commands.add_parser("sinica-oral", parents=[common], help="中研院口语资料的本地研究目录")
    sinica.add_argument("--snapshots", type=Path, required=True, help="含 manifest.json 与字段快照的目录")
    cham = commands.add_parser("vietnam-cham", parents=[common], help="越南占族故事选集的逐篇研究目录")
    cham.add_argument("--snapshots", type=Path, required=True, help="含 manifest.json 与逐篇字段索引的目录")
    shandong = commands.add_parser("shandong-mirrors", parents=[common], help="山东方志镜像的逐篇研究索引")
    shandong.add_argument("--index", type=Path, required=True, help="本地登记的 UTF-8 题名与署名索引")
    hmml = commands.add_parser("hmml-makassar", parents=[common], help="HMML 望加锡馆藏及旧目录候选分卷")
    hmml.add_argument("--snapshots", type=Path, required=True, help="馆方元数据选取目录")
    hmml.add_argument("--legacy", type=Path, required=True, help="旧目录搜索索引的候选字段")
    ilianen = commands.add_parser("philippines-ilianen", parents=[common], help="SIL 菲律宾 Ilianen Manobo 录音样本目录")
    ilianen.add_argument("--file", type=Path, required=True, help="馆方录音目录 HTML 快照")
    cole = commands.add_parser("philippines-cole", parents=[common], help="1916 年菲律宾故事选集目录与扫描页候选")
    cole.add_argument("--toc", type=Path, required=True, help="原书目录的 UTF-8 字段转记")
    cole.add_argument("--snapshots", type=Path, required=True, help="密歇根大学扫描本的分页 OCR 与索引快照")
    early_asia = commands.add_parser("early-asia-editions", parents=[common], help="1905 与 1922 年亚洲英文文献的版本对照")
    early_asia.add_argument("--toc", type=Path, required=True, help="1922 年原书目录字段转记")
    early_asia.add_argument("--snapshots", type=Path, required=True, help="两部扫描本的分页 OCR 与扫描清单")
    early_asia.add_argument("--andersen", type=Path, required=True, help="安徒生中心登记与译文对照快照")
    pangloss = commands.add_parser("pangloss-na", parents=[common], help="Pangloss 永宁纳语录音及待复核对照")
    pangloss.add_argument("--corpus", type=Path, required=True, help="馆方语料目录 HTML 快照")
    pangloss.add_argument("--selection", type=Path, required=True, help="目的性题名选取索引")
    pangloss.add_argument("--snapshots", type=Path, required=True, help="带清单的单条详情快照目录")
    na_context = commands.add_parser("pangloss-na-context", parents=[common], help="永宁纳语仪式及口述背景的补充选取")
    na_context.add_argument("--corpus", type=Path, required=True, help="原馆方目录 HTML 快照")
    na_context.add_argument("--previous", type=Path, required=True, help="已有首轮选取索引")
    na_context.add_argument("--selection", type=Path, required=True, help="带原题名与来源哈希的补充选取索引")
    na_context.add_argument("--snapshots", type=Path, required=True, help="带清单的单条详情快照目录")
    na_catalogue = commands.add_parser("pangloss-na-catalogue", parents=[common], help="从既有永宁纳语目录筛选待核候选")
    na_catalogue.add_argument("--corpus", type=Path, required=True, help="已有馆方目录 HTML 快照")
    na_catalogue.add_argument("--first", type=Path, required=True, help="首轮选取索引")
    na_catalogue.add_argument("--context", type=Path, required=True, help="口述背景选取索引")
    na_catalogue.add_argument("--selection", type=Path, required=True, help="本轮目录候选及来源哈希")
    japhug = commands.add_parser("pangloss-japhug", parents=[common], help="Pangloss Japhug 全部目录及已核详情")
    japhug.add_argument("--corpus", type=Path, required=True, help="馆方语料目录 HTML 快照")
    japhug.add_argument("--selection", type=Path, required=True, help="首轮详情选取索引")
    japhug.add_argument("--snapshots", type=Path, required=True, help="带清单的单条详情快照目录")
    khmu = commands.add_parser("pangloss-khmu", parents=[common], help="Pangloss Khmu 录音目录及待核对照")
    khmu.add_argument("--corpus", type=Path, required=True, help="馆方语料目录 HTML 快照")
    khmu.add_argument("--selection", type=Path, required=True, help="首轮详情选取索引")
    khmu.add_argument("--snapshots", type=Path, required=True, help="带清单的单条详情快照目录")
    khmu.add_argument("--comparisons", type=Path, required=True, help="与目录哈希绑定的待核对照索引")
    korea = commands.add_parser("korea-aks-dobong", parents=[common], help="韩国道峰区口碑目录与待核来源候选")
    korea.add_argument("--archive", type=Path, required=True, help="公共数据门户目录 ZIP")
    korea.add_argument("--receipt", type=Path, required=True, help="目录下载凭据")
    korea.add_argument("--search", type=Path, required=True, help="馆方检索字段索引目录")
    korea.add_argument("--crosswalk", type=Path, required=True, help="基础来源候选对照 CSV")
    korea.add_argument("--details", type=Path, required=True, help="馆方单条元数据字段索引目录")
    korea.add_argument("--reconciled", type=Path, required=True, help="含详情的来源候选对照 CSV")
    bl_khmer = commands.add_parser("bl-khmer", parents=[common], help="大英图书馆高棉文折本逐册目录")
    bl_khmer.add_argument("--snapshots", type=Path, required=True, help="含馆藏组及逐册目录快照的目录")
    bl_yi = commands.add_parser("bl-yi", parents=[common], help="大英图书馆云南彝语口述录音子组")
    bl_yi.add_argument("--snapshots", type=Path, required=True, help="大英图书馆 EAP081/25 目录快照")
    bl_burma = commands.add_parser('bl-burma', parents=[common], help='大英图书馆缅甸多语唱片目录与 DSAL 待核候选')
    bl_burma.add_argument('--snapshots', type=Path, required=True, help='大英图书馆 IOR/S/2/3 目录快照')
    bl_burma.add_argument('--dsal', type=Path, required=True, help='DSAL 语言卷字段索引')
    dongjing = commands.add_parser('bl-dongjing', parents=[common], help='大英图书馆云南洞经表演与口述访谈目录')
    dongjing.add_argument('--snapshots', type=Path, required=True, help='EAP012/6/2 馆方目录快照')
    yi_project = commands.add_parser('bl-yi-project', parents=[common], help='彝文 EAP081 项目完整目录筛查与候选')
    yi_project.add_argument('--index', type=Path, required=True, help='项目检索分页快照目录')
    yi_project.add_argument('--details', type=Path, required=True, help='入选单件及父级馆藏快照目录')
    minyag = commands.add_parser("minyag-wolp", parents=[common], help="剑桥项目四川木雅语目录筛查")
    minyag.add_argument("--snapshots", type=Path, required=True, help="馆藏目录与网站条款的本地快照")
    minyag.add_argument("--current", type=Path, help="可选的剑桥第 19 条单件页面快照")
    temiar = commands.add_parser("temiar-wolp", parents=[common], help="马来西亚 Temiar 馆藏目录与音轨线索")
    temiar.add_argument("--snapshots", type=Path, required=True, help="馆藏目录及网站条款的本地快照")
    temiar.add_argument("--current", type=Path, help="可选的剑桥第 33 条单件页面快照")
    pumi = commands.add_parser("pumi-wolp", parents=[common], help="云南王家沟普米语馆藏录音目录")
    pumi.add_argument("--snapshots", type=Path, required=True, help="馆藏目录及网站条款的本地快照")
    pumi.add_argument("--current", type=Path, help="可选的剑桥第 41 条单件页面快照")
    palue = commands.add_parser("palue-inventory", parents=[common], help="印尼 Palu’e 馆藏公开目录字段筛查")
    palue.add_argument("--snapshots", type=Path, required=True, help="含分页字段索引与清单的目录")
    zibuyu = commands.add_parser("zibuyu-wikisource", parents=[common], help="《子不语》在线转录逐篇核查")
    zibuyu.add_argument("--snapshots", type=Path, required=True, help="总目录及 24 卷网页快照目录")
    zibuyu.add_argument("--talk", type=Path, required=True, help="维基文库版本讨论页快照目录")
    lowell = commands.add_parser("lowell-sea", parents=[common], help="洛厄尔东南亚社群故事项目目录")
    lowell.add_argument("--snapshots", type=Path, required=True, help="含馆藏组与单件字段研究索引的目录")
    nitean = commands.add_parser("khmer-nitean", parents=[common], help="Nitean 高棉文故事逐篇目录与出处字段")
    nitean.add_argument("--snapshots", type=Path, required=True, help="含目录与逐篇字段研究索引的目录")
    nitean.add_argument("--comparison", type=Path, help="Wikisource 卷册数量对照字段索引")
    yuhuan = commands.add_parser("yuhuan-stories", parents=[common], help="玉环口头文学选辑的传说故事篇目录")
    yuhuan.add_argument("--pdf", type=Path, required=True, help="玉环市政协网公开的扫描 PDF 快照")
    yuhuan.add_argument("--index", type=Path, required=True, help="按目录影像转记的 UTF-8 JSON 索引")
    motifs = commands.add_parser("berezkin", parents=[common], help="公开论文附件的母题分布")
    motifs.add_argument("--study", type=Path, required=True)
    nichibun = commands.add_parser("nichibun", parents=[common], help="日文研北海道·东北地区河童馆藏卡的本地 HTML")
    nichibun.add_argument("--files", type=Path, nargs="+", required=True)
    duchas = commands.add_parser("duchas", parents=[common], help="Dúchas 学校采录的故事与学校 XML")
    duchas.add_argument("--stories", type=Path, nargs="+", required=True)
    duchas.add_argument("--selection", type=Path, help="可选的公开馆藏候选清单，用于记录选取范围")
    codes = commands.add_parser("berezkin-codes", parents=[common], help="从本地官方目录快照校对码表")
    codes.add_argument("--study", type=Path, required=True)
    codes.add_argument("--catalogue", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.adapter == "berezkin-codes":
            count = update_code_table(args.code_table, args.catalogue, read_study(args.study))
            print(f"本地目录校对通过并保存 {count} 个母题码。")
            return 0
        if args.adapter == "scottish":
            cards = scottish_cards(args.tables, args.schema, args.maps)
            source = {"dataset": DATASET_URL, "license": "https://creativecommons.org/licenses/by/4.0/",
                      "residence_index": MAP_URL if args.maps else None}
            default_batch = "scottish_witchcraft"
        elif args.adapter == "berezkin":
            study = read_study(args.study)
            table = load_code_table(args.code_table)
            cards = distribution_cards(study, table)
            source = study.manifest(table)
            default_batch = "berezkin_distribution"
        elif args.adapter == "nichibun":
            existing = set(load_vault(args.vault.resolve()))
            existing.update(path.stem for path in (args.vault / DRAFT_DIRECTORY).rglob("*.md"))
            groups = {NICHIBUN_CORPUS, NICHIBUN_INDEX} & existing
            if len(groups) == 1:
                raise IntakeError("日文研资料组缺少档案组或称谓索引，请先核对现有卡片。")
            new_files = [path for path in args.files if nichibun_node_id(path.stem) not in existing]
            if not new_files:
                raise IntakeError("这些日文研馆藏卡均已入库或在待审目录中。")
            cards = nichibun_cards(new_files, include_groups=not groups)
            source = {"catalogue_search": SEARCH_URL, "rights": "国际日本文化研究中心保留权利",
                      "snapshots": [str(path.resolve()) for path in new_files]}
            default_batch = "nichibun_tohoku"
        elif args.adapter == "duchas":
            published = load_vault(args.vault.resolve())
            existing = set(published)
            cited = set().union(*(duchas_cited_story_ids(card.metadata) for card in published.values()))
            for pending_path in (args.vault / DRAFT_DIRECTORY).rglob("*.md"):
                existing.add(pending_path.stem)
                raw = pending_path.read_bytes()
                if b"duchas.ie" in raw and b"/cbes/" in raw:
                    metadata, _ = parse_card(raw.decode("utf-8-sig").replace("\r\n", "\n"))
                    cited.update(duchas_cited_story_ids(metadata))
            groups = {DUCHAS_CORPUS, DUCHAS_INDEX} & existing
            if len(groups) == 1:
                raise IntakeError("Dúchas 资料组缺少档案组或称谓索引，请先核对现有卡片。")
            identifiers = [duchas_node_id(path) for path in args.stories]
            if len(set(identifiers)) != len(identifiers):
                raise IntakeError("同一 Dúchas 故事包含多个输入文件，请先选择对应页面。")
            new_files = [path for path, node_id in zip(args.stories, identifiers, strict=True)
                         if node_id not in existing and node_id.removeprefix("case_duchas_") not in cited]
            if not new_files:
                raise IntakeError("这些 Dúchas 故事均已入库或在待审目录中。")
            cards = duchas_cards(new_files, include_groups=not groups)
            source = {"collection": DUCHAS_COLLECTION, "license": "https://creativecommons.org/licenses/by-nc/4.0/",
                      "snapshots": [str(path.resolve()) for path in new_files]}
            if args.selection:
                selected_ids = {f"case_duchas_{item['story']}" for item in duchas_candidates(args.selection)}
                if any(duchas_node_id(path) not in selected_ids for path in new_files):
                    raise IntakeError("新增故事不在所指定的候选清单中。")
                source["selection_register"] = str(args.selection.resolve())
                source["selection_sha256"] = sha256(args.selection.read_bytes()).hexdigest()
            default_batch = "duchas_fairyforts"
        elif args.adapter == "chinese-heritage":
            cards = heritage_cards(args.file)
            source = {"register": CHINESE_HERITAGE_URL, "snapshot": str(args.file.resolve()),
                      "sha256": sha256(args.file.read_bytes()).hexdigest(),
                      "scope": "第一批国家级非遗名录，一、民间文学；申报地与采录地须区分"}
            default_batch = "asia_chinese_heritage_2006"
        elif args.adapter == "chinese-heritage-2011":
            cards = heritage_2011_cards(args.file)
            source = {"url": CHINESE_HERITAGE_2011_URL, "snapshot": str(args.file.resolve()),
                      "sha256": sha256(args.file.read_bytes()).hexdigest(),
                      "scope": "2011 年民间文学新增与扩展项目；申报地不能作为故事采录地"}
            default_batch = "asia_chinese_heritage_2011"
        elif args.adapter == "chinese-heritage-batch":
            cards = heritage_batch_cards(args.file, args.year)
            source = {"url": CHINESE_HERITAGE_BATCHES[args.year]['url'], "snapshot": str(args.file.resolve()),
                      "sha256": sha256(args.file.read_bytes()).hexdigest(),
                      "scope": f"{args.year} 年民间文学新增与扩展项目；申报地不是故事采录地"}
            default_batch = f"asia_chinese_heritage_{args.year}"
        elif args.adapter == "chinese-heritage-2021":
            cards = heritage_2021_cards(args.pdf, args.index)
            source = {"url": HERITAGE_2021_URL, "pdf": str(args.pdf.resolve()),
                      "pdf_sha256": sha256(args.pdf.read_bytes()).hexdigest(), "index": str(args.index.resolve()),
                      "index_sha256": sha256(args.index.read_bytes()).hexdigest(),
                      "scope": "2021 年民间文学项目与扩展项目；PDF 字体映射及逐行原表须复核"}
            default_batch = "asia_chinese_heritage_2021"
        elif args.adapter == "thai-folktales":
            cards = thai_cards(args.file, args.catalogue)
            source = {"dataset": THAI_DATASET_URL, "snapshot": str(args.file.resolve()),
                      "sha256": sha256(args.file.read_bytes()).hexdigest(),
                      "catalogue": str(args.catalogue.resolve()),
                      "catalogue_sha256": sha256(args.catalogue.read_bytes()).hexdigest(),
                      "license": "Creative Commons Attribution Non-Commercial；版本及个别记录待核"}
            default_batch = "asia_thai_sac"
        elif args.adapter == "lao-manuscripts":
            cards = lao_cards(args.snapshots)
            manifest_file = args.snapshots / "manifest.json"
            source = {"search": "https://iiif.crossasia.org/s/dllm", "snapshot_manifest": str(manifest_file.resolve()),
                      "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "Folk Tale 馆藏手稿元数据；不含影像或转录正文"}
            default_batch = "asia_lao_dllm"
        elif args.adapter == "lanna-folktales":
            cards = lanna_cards(args.snapshots)
            manifest_file = args.snapshots / "manifest.json"
            source = {"search":LANNA_SEARCH_URL,"manifest":str(manifest_file.resolve()),
                      "manifest_sha256":sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope":"北泰 Folk Tale 分类手稿目录，不含影像或转录；馆藏地不是故事发生地"}
            default_batch = "asia_th_lanna_folktales"
        elif args.adapter == "yuhuan-stories":
            cards = yuhuan_cards(args.pdf, args.index)
            source = {"pdf": YUHUAN_PDF_URL, "snapshot": str(args.pdf.resolve()),
                      "sha256": sha256(args.pdf.read_bytes()).hexdigest(),
                      "index": str(args.index.resolve()), "index_sha256": sha256(args.index.read_bytes()).hexdigest(),
                      "scope": "传说故事篇目录；正文扫描未转录，出版物再利用许可待核"}
            default_batch = "asia_yuhuan_2008"
        elif args.adapter == "sinica-oral":
            cards = sinica_cards(args.snapshots)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": "https://aya.ioe.sinica.edu.tw/", "manifest": str(manifest_file.resolve()),
                      "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "本地研究目录；未保存正文和录音；未经同意不得摘取内容出版"}
            default_batch = "asia_tw_sinica_oral"
        elif args.adapter == "vietnam-cham":
            cards = cham_cards(args.snapshots)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": "https://www.digitizingvietnam.com/en/our-collections/vietnamese-folk-literature/truyen-co-dan-gian-cham?muc=loi-gioi-thieu",
                      "manifest": str(manifest_file.resolve()), "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "越南文选集索引；教育研究用途，禁止商业使用；未复制正文"}
            default_batch = "asia_vietnam_cham_folktales"
        elif args.adapter == "shandong-mirrors":
            cards = mirror_cards(args.index)
            source = {"register": str(args.index.resolve()), "register_sha256": sha256(args.index.read_bytes()).hexdigest(),
                      "scope": "题名与书目字段索引；方志镜像，未保存正文或原网页；原书与再利用许可待核"}
            default_batch = "asia_shandong_mirrors"
        elif args.adapter == "hmml-makassar":
            cards = hmml_cards(args.snapshots, args.legacy)
            manifest_file = args.snapshots / "manifest.json"
            source = {"dataset": HMML_DATASET_PAGE, "selection_manifest": str(manifest_file.resolve()),
                      "selection_manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "legacy_index": str(args.legacy.resolve()), "legacy_index_sha256": sha256(args.legacy.read_bytes()).hexdigest(),
                      "scope": "馆藏元数据与旧目录候选；无手稿图像或正文；人工复核前不入图"}
            default_batch = "asia_hmml_makassar"
        elif args.adapter == "philippines-ilianen":
            cards = ilianen_cards(args.file)
            source = {"catalogue": SIL_ILIANEN_URL, "snapshot": str(args.file.resolve()),
                      "sha256": sha256(args.file.read_bytes()).hexdigest(),
                      "scope": "两个口述录音样本的馆方目录；未复制音频或转写正文；再利用条件待核"}
            default_batch = "asia_ph_ilianen_sil"
        elif args.adapter == "philippines-cole":
            cards = cole_cards(args.toc, args.snapshots)
            source = {"book": COLE_BOOK_URL, "toc": str(args.toc.resolve()),
                      "toc_sha256": sha256(args.toc.read_bytes()).hexdigest(),
                      "scope": "1916 年选集目录项；扫描候选由 OCR 定位，未复制故事正文，人工复核前不入图"}
            default_batch = "asia_ph_cole_1916"
        elif args.adapter == "early-asia-editions":
            cards = early_edition_cards(args.toc, args.snapshots, args.andersen)
            source = {"jade_book": JADE_BOOK, "saleeby_book": SALEEBY_BOOK, "toc": str(args.toc.resolve()),
                      "toc_sha256": sha256(args.toc.read_bytes()).hexdigest(),
                      "scope": "1922 年目录及 1905 年章节的版本对照；不等于现场口述；不复制正文，人工复核前不入图"}
            default_batch = "asia_early_editions"
        elif args.adapter == "pangloss-na":
            cards = pangloss_cards(args.snapshots, args.corpus, args.selection)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": PANGLOSS_NA_URL, "catalogue_sha256": sha256(args.corpus.read_bytes()).hexdigest(),
                      "selection_sha256": sha256(args.selection.read_bytes()).hexdigest(),
                      "detail_manifest": str(manifest_file.resolve()), "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "按题名目的性选取口述录音元数据；未复制音频或转写；许可证和社区要求逐条复核"}
            default_batch = "asia_cn_pangloss_na"
        elif args.adapter == "pangloss-na-context":
            cards = pangloss_na_context_cards(args.snapshots,args.corpus,args.previous,args.selection)
            manifest_file=args.snapshots/'manifest.json'
            source={"catalogue":PANGLOSS_NA_URL,"catalogue_sha256":sha256(args.corpus.read_bytes()).hexdigest(),
                    "previous_selection_sha256":sha256(args.previous.read_bytes()).hexdigest(),
                    "selection_sha256":sha256(args.selection.read_bytes()).hexdigest(),
                    "detail_manifest":str(manifest_file.resolve()),"manifest_sha256":sha256(manifest_file.read_bytes()).hexdigest(),
                    "scope":"目的性选取的仪式、口述背景与歌曲；未复制音视频及转写，不自动判为民间故事"}
            default_batch="asia_cn_pangloss_na_context"
        elif args.adapter == "pangloss-na-catalogue":
            cards = pangloss_na_catalogue_cards(args.corpus, args.first, args.context, args.selection)
            source = {"catalogue": PANGLOSS_NA_URL, "catalogue_sha256": sha256(args.corpus.read_bytes()).hexdigest(),
                      "first_selection_sha256": sha256(args.first.read_bytes()).hexdigest(),
                      "context_selection_sha256": sha256(args.context.read_bytes()).hexdigest(),
                      "selection_sha256": sha256(args.selection.read_bytes()).hexdigest(),
                      "scope": "既有目录按题名选取的待核候选；未获取单条详情、音视频或转写；不自动分类"}
            default_batch = "asia_cn_pangloss_na_catalogue"
        elif args.adapter == "pangloss-japhug":
            cards = japhug_cards(args.corpus, args.selection, args.snapshots)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": PANGLOSS_JAPHUG_URL, "catalogue_sha256": sha256(args.corpus.read_bytes()).hexdigest(),
                      "selection_sha256": sha256(args.selection.read_bytes()).hexdigest(),
                      "detail_manifest": str(manifest_file.resolve()), "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "馆方录音目录和选取的单条详情；录音不等于故事；未复制音频或转写；许可和社区要求逐条核对"}
            default_batch = "asia_cn_pangloss_japhug"
        elif args.adapter == "pangloss-khmu":
            cards = khmu_cards(args.corpus, args.selection, args.snapshots, args.comparisons)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": PANGLOSS_KHMU_URL, "catalogue_sha256": sha256(args.corpus.read_bytes()).hexdigest(),
                      "selection_sha256": sha256(args.selection.read_bytes()).hexdigest(),
                      "comparison_sha256": sha256(args.comparisons.read_bytes()).hexdigest(),
                      "detail_manifest": str(manifest_file.resolve()), "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "馆方录音目录与待核对照；一条录音不等于一篇故事；未复制音频或转写，许可和社区要求逐条核对"}
            default_batch = "asia_sea_pangloss_khmu"
        elif args.adapter == "korea-aks-dobong":
            cards = korea_cards(args.archive,args.receipt,args.search,args.crosswalk,args.details,args.reconciled)
            source = {"catalogue":KOREA_AKS_URL,"archive_sha256":sha256(args.archive.read_bytes()).hexdigest(),
                      "search_manifest_sha256":sha256((args.search/'manifest.json').read_bytes()).hexdigest(),
                      "detail_manifest_sha256":sha256((args.details/'manifest.json').read_bytes()).hexdigest(),
                      "crosswalk_sha256":sha256(args.reconciled.read_bytes()).hexdigest(),
                      "scope":"开放目录行及待核馆方来源候选；未复制转写、音视频或馆方网页原响应；许可与社区要求逐条核对"}
            default_batch = "asia_kr_aks_dobong"
        elif args.adapter == "bl-khmer":
            cards = bl_cards(args.snapshots)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": BL_KHMER_URL, "manifest": str(manifest_file.resolve()),
                      "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "高棉文折本逐册馆藏目录；非逐篇故事；目录文字 CC BY 4.0；影像权利另核"}
            default_batch = "asia_kh_bl_folding_books"
        elif args.adapter == "bl-yi":
            cards = bl_yi_cards(args.snapshots)
            manifest_file = args.snapshots / 'manifest.json'
            source = {"catalogue": "https://searcharchives.bl.uk/catalog/032-001617335",
                      "manifest": str(manifest_file.resolve()), "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "云南彝语录音馆藏组与六个子组；目录文字 CC BY 4.0，音频未下载，研究访问条件另核"}
            default_batch = "asia_cn_bl_yi_eap081"
        elif args.adapter == 'bl-burma':
            cards = bl_burma_cards(args.snapshots, args.dsal)
            manifest_file, dsal_file = args.snapshots / 'manifest.json', args.dsal / 'manifest.json'
            source = {'catalogue': 'https://searcharchives.bl.uk/catalog/037-000091137',
                      'manifest_sha256': sha256(manifest_file.read_bytes()).hexdigest(),
                      'dsal_manifest_sha256': sha256(dsal_file.read_bytes()).hexdigest(),
                      'scope': '35 件唱片目录与编号或半号文字候选；非故事计数；未保存音频或转写，权利及社区要求逐件复核。'}
            default_batch = 'asia_mm_bl_burma'
        elif args.adapter == 'bl-dongjing':
            cards = bl_dongjing_cards(args.snapshots)
            manifest_file = args.snapshots / 'manifest.json'
            source = {'catalogue': 'https://searcharchives.bl.uk/catalog/036-001577227',
                      'manifest_sha256': sha256(manifest_file.read_bytes()).hexdigest(),
                      'scope': '馆方文件夹目录及字段差异；非故事计数；未保存音视频或转写，单件权利及社区要求待核。'}
            default_batch = 'asia_cn_bl_dongjing_eap012'
        elif args.adapter == 'bl-yi-project':
            cards = bl_yi_project_cards(args.index, args.details)
            index_manifest, detail_manifest = args.index / 'manifest.json', args.details / 'manifest.json'
            source = {'catalogue': 'https://searcharchives.bl.uk/',
                      'index_manifest_sha256': sha256(index_manifest.read_bytes()).hexdigest(),
                      'details_manifest_sha256': sha256(detail_manifest.read_bytes()).hexdigest(),
                      'scope': '项目检索全文目录与关键词候选；馆藏和目录行不是故事数；未保存手稿影像或音视频。'}
            default_batch = 'asia_cn_bl_yi_project_eap081'
        elif args.adapter == "minyag-wolp":
            cards = minyag_wolp_cards(args.snapshots, args.current)
            manifest_file = args.snapshots / 'manifest.json'
            source = {'catalogue': MINYAG_WOLP_URL, 'manifest': str(manifest_file.resolve()),
                      'manifest_sha256': sha256(manifest_file.read_bytes()).hexdigest(),
                      'scope': '本地个人或内部非商业目录筛查；未获取录音和转写，单条权利另核。'}
            if args.current:
                source['current_manifest_sha256'] = sha256((args.current / 'manifest.json').read_bytes()).hexdigest()
            default_batch = 'asia_cn_minyag_wolp'
        elif args.adapter == "temiar-wolp":
            cards = temiar_wolp_cards(args.snapshots, args.current)
            manifest_file = args.snapshots / 'manifest.json'
            source = {'catalogue': TEMIAR_WOLP_URL, 'manifest': str(manifest_file.resolve()),
                      'manifest_sha256': sha256(manifest_file.read_bytes()).hexdigest(),
                      'scope': '本地个人或内部非商业目录筛查；未获取录音、照片、信件或附件，单件权利另核。'}
            if args.current:
                source['current_manifest_sha256'] = sha256((args.current / 'manifest.json').read_bytes()).hexdigest()
            default_batch = 'asia_my_temiar_wolp'
        elif args.adapter == "pumi-wolp":
            cards = pumi_wolp_cards(args.snapshots, args.current)
            manifest_file = args.snapshots / 'manifest.json'
            source = {'catalogue': PUMI_WOLP_URL, 'manifest': str(manifest_file.resolve()),
                      'manifest_sha256': sha256(manifest_file.read_bytes()).hexdigest(),
                      'scope': '本地个人或内部非商业目录筛查；未获取录音、转写或附件，单件权利另核。'}
            if args.current:
                source['current_manifest_sha256'] = sha256((args.current / 'manifest.json').read_bytes()).hexdigest()
            default_batch = 'asia_cn_pumi_wolp'
        elif args.adapter == "palue-inventory":
            cards = palue_inventory_cards(args.snapshots)
            manifest_file = args.snapshots / 'manifest.json'
            source = {'catalogue': PALUE_URL, 'manifest': str(manifest_file.resolve()),
                      'manifest_sha256': sha256(manifest_file.read_bytes()).hexdigest(),
                      'scope': '仅保存公开目录必要字段；未保存原始响应、叙事描述、媒体或转写，单件权利与社区要求待核。'}
            default_batch = 'asia_sea_palue_inventory'
        elif args.adapter == "zibuyu-wikisource":
            vault_path = args.vault.resolve()
            existing_ids = set(load_vault(vault_path))
            existing_ids.update(path.stem for path in (vault_path / DRAFT_DIRECTORY).rglob('*.md'))
            cards = zibuyu_cards(args.snapshots, args.talk, include_existing=ZIBUYU_EXISTING not in existing_ids)
            manifest_file = args.snapshots / 'manifest.json'
            source = {'catalogue': zibuyu_page_url(0), 'manifest': str(manifest_file.resolve()),
                      'manifest_sha256': sha256(manifest_file.read_bytes()).hexdigest(),
                      'talk_manifest_sha256': sha256((args.talk / 'manifest.json').read_bytes()).hexdigest(),
                      'scope': '维基文库在线转录与目录；古籍底本及单篇对应待核，保留修订及站点文字使用条款。'}
            default_batch = 'asia_cn_zibuyu_wikisource'
        elif args.adapter == "lowell-sea":
            cards = lowell_cards(args.snapshots)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": LOWELL_SEA_URL, "manifest": str(manifest_file.resolve()),
                      "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "洛厄尔东南亚社群项目单件字段；未保存原网页或叙事正文；不是逐篇故事"}
            default_batch = "asia_us_lowell_sea"
        elif args.adapter == "khmer-nitean":
            cards = nitean_cards(args.snapshots, args.comparison)
            manifest_file = args.snapshots / "manifest.json"
            source = {"catalogue": NITEAN_URL, "manifest": str(manifest_file.resolve()),
                      "manifest_sha256": sha256(manifest_file.read_bytes()).hexdigest(),
                      "scope": "高棉文故事转录站逐篇目录与出处字段；不保存正文；原版与权利待核"}
            if args.comparison:
                source["comparison"] = str(args.comparison.resolve())
                source["comparison_sha256"] = sha256(args.comparison.read_bytes()).hexdigest()
            default_batch = "asia_kh_nitean_folktales"
        else:
            cards = curated_cards(args.records)
            source = {"register": str(args.records.resolve())}
            default_batch = "regional_sources"
        vault = args.vault.resolve()
        batch = args.batch or default_batch
        manifest = stage_batch(vault, batch, cards, args.code_table, source)
    except (ValueError, OSError, KeyError, TypeError, BadZipFile, yaml.YAMLError) as error:
        print(f"批量入库未完成\n{error}", file=sys.stderr)
        return 1
    print(f"已写入待审批次 {vault / DRAFT_DIRECTORY / batch}")
    print(json.dumps(manifest["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
