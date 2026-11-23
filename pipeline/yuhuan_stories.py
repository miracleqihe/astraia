"""Stage a page-linked finding aid for the 2008 Yuhuan oral-literature volume."""

from datetime import date
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader

from pipeline.build_graph import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

PDF_URL = ("https://zjjcmspublic.oss-cn-hangzhou-zwynet-d01-a.internet.cloud.zj.gov.cn/"
           "jcms_files/jcms1/web3203/site/attach/0/c01efe56afef4430947d9d12885257c3.pdf")
LANDING_URL = "https://zjyhzx.yuhuan.gov.cn/art/2023/12/4/art_1631827_58328269.html"
COLLECTION = "corpus_cn_yuhuan_2008"
DOCUMENT = "政协玉环县文史资料委员会，《玉环文史资料》第二十二辑：非物质文化遗产·民间口头文学选辑，2008年12月。"
CATEGORIES = {"史事传说", "人物传说", "地方传说", "风物传说", "风俗传说", "生活故事和笑话"}


def pdf_page(print_page: int) -> int:
    """The PDF scans two facing book pages: book p. 1 is PDF p. 9."""
    if not isinstance(print_page, int) or isinstance(print_page, bool) or not 1 <= print_page <= 94:
        raise IntakeError("传说故事篇印刷页码须在 1 至 94 之间。")
    return 9 + print_page // 2


def read_index(path: Path) -> dict:
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"玉环目录转记无法读取：{error}") from error
    if (not isinstance(index, dict) or index.get("version") != 1
            or not isinstance(index.get("pdf_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", index["pdf_sha256"])
            or not isinstance(index.get("entries"), list) or not index["entries"]):
        raise IntakeError("玉环目录转记缺少版本、PDF 哈希或条目。")
    pages = []
    for row in index["entries"]:
        if not isinstance(row, dict):
            raise IntakeError("目录条目格式有误。")
        page = row.get("page")
        pdf_page(page)
        if not isinstance(row.get("title"), str) or not row["title"].strip() or row.get("category") not in CATEGORIES:
            raise IntakeError(f"印刷页 {page} 的标题或原目录类别有误。")
        if any("\ufffd" in str(value) or "\x00" in str(value) for value in row.values()):
            raise IntakeError(f"印刷页 {page} 的目录文字存在无效字符。")
        credits, credit_page = row.get("credits"), row.get("credit_page")
        if (credits is None) != (credit_page is None):
            raise IntakeError(f"印刷页 {page} 的旁注和旁注页码须同时提供。")
        if credits is not None:
            if (not isinstance(credits, list) or not credits
                    or any(not isinstance(value, str) or not value.strip() for value in credits)):
                raise IntakeError(f"印刷页 {page} 的旁注格式有误。")
            pdf_page(credit_page)
            if credit_page < page:
                raise IntakeError(f"印刷页 {page} 的旁注不能早于条目开头。")
        if "title_note" in row and (not isinstance(row["title_note"], str) or not row["title_note"].strip()):
            raise IntakeError(f"印刷页 {page} 的标题疑点格式有误。")
        online = row.get("online_source")
        if online is not None:
            if not isinstance(online, dict) or not all(isinstance(online.get(key), str) for key in ("url", "local_path", "sha256", "date")):
                raise IntakeError(f"印刷页 {page} 的网页版本来源格式有误。")
            url = urlsplit(online["url"])
            if (url.scheme != "https" or url.hostname != "yhsz.yuhuan.gov.cn" or not url.path.startswith("/art/")
                    or not re.fullmatch(r"[0-9a-f]{64}", online["sha256"])
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", online["date"])):
                raise IntakeError(f"印刷页 {page} 的网页版本地址或哈希有误。")
        pages.append(page)
    if pages != sorted(set(pages)):
        raise IntakeError("目录印刷页码须递增且不能重复。")
    for row, next_page in zip(index["entries"], pages[1:] + [95], strict=True):
        if row.get("credit_page", row["page"]) > next_page:
            raise IntakeError(f"印刷页 {row['page']} 的旁注超出下一条开头。")
    return index


def _local_file(path: Path) -> tuple[str, str]:
    resolved = path.resolve(strict=True)
    digest = sha256(resolved.read_bytes()).hexdigest()
    try:
        local = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        local = str(resolved)
    return local, digest


def yuhuan_cards(pdf: Path, index_path: Path):
    index = read_index(index_path)
    pdf_local, pdf_digest = _local_file(pdf)
    index_local, index_digest = _local_file(index_path)
    if pdf_digest != index["pdf_sha256"]:
        raise IntakeError("目录对应的 PDF 哈希不匹配；禁止按旧页码导入另一份扫描。")
    # This scan has many broken object offsets. Capture the parser warnings and
    # carry them into every draft instead of flooding the terminal or hiding them.
    messages = []
    class WarningCollector(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())
    collector = WarningCollector()
    logger = logging.getLogger("pypdf")
    old_level, old_propagate = logger.level, logger.propagate
    logger.addHandler(collector)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        try:
            reader = PdfReader(pdf)
            if reader.is_encrypted or len(reader.pages) != 124:
                raise IntakeError("玉环扫描件页数或加密状态不符合本批目录。")
        except Exception as error:
            if isinstance(error, IntakeError):
                raise
            raise IntakeError(f"玉环 PDF 无法读取：{error}") from error
    finally:
        logger.removeHandler(collector)
        logger.setLevel(old_level)
        logger.propagate = old_propagate
    warning_note = (f"PDF 解析器报告 {len(messages)} 条对象引用或结构警告；请以其他查看器核查对应页面。"
                    if messages else "")

    def image_source(page: int, kind: str = "故事开头") -> dict:
        scan = pdf_page(page)
        return {"citation": DOCUMENT, "type": "yuhuan_scan", "url": f"{PDF_URL}#page={scan}",
                "locator": f"传说故事篇 / 印刷第 {page} 页 / PDF 第 {scan} 页 / {kind}",
                "local_path": pdf_local, "content_sha256": pdf_digest}

    index_source = {"citation": "项目按目录影像转记的检索索引，未经人工签核。", "type": "yuhuan_index",
                    "locator": "传说故事篇目录 / PDF 第 5–6 页", "local_path": index_local,
                    "content_sha256": index_digest}
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}
    spatial = {"precision": "culture_region", "location_name": "浙江玉环：选辑范围，非逐篇采录点或故事地点",
               "culture_region": "East Asia · China · Zhejiang"}
    corpus = {**common, "id": COLLECTION, "title": "玉环文史资料 · 民间口头文学选辑（2008）",
              "node_type": "myth_corpus", "z_layer": 2, "spatial": spatial,
              "sources": [image_source(1), index_source]}
    yield NodeMetadata.model_validate(corpus), (
        "\n## 资料组与范围\n\n本册由政协玉环县文史资料委员会于 2008 年 12 月编印，"
        "目录设有传说故事、歌谣和谚语。本批只索引传说故事篇的目录条目；目录类别沿用原书，"
        "未自动转换成图谱体裁。编者说明材料包括早期民间文学集成及后续选编，不能将本册当作"
        "未经整理的现场逐字记录。PDF 为双页扫描，每条分别记录印刷页码及 PDF 页码。"
        "本批不转录正文；出版物及数字扫描的再利用许可未明，须核对。" + warning_note + "\n")

    for row in index["entries"]:
        page = row["page"]
        sources = [image_source(page), index_source]
        if "credit_page" in row:
            sources.append(image_source(row["credit_page"], "采录旁注候选"))
        if row.get("online_source"):
            online = row["online_source"]
            online_file = Path(online["local_path"])
            if not online_file.is_absolute():
                online_file = PROJECT_ROOT / online_file
            online_local, online_digest = _local_file(online_file)
            if online_digest != online["sha256"]:
                raise IntakeError(f"印刷页 {page} 的网页版本快照哈希不符。")
            soup = BeautifulSoup(online_file.read_bytes(), "html.parser")
            if soup.contains_replacement_characters or not soup.title or soup.title.get_text(strip=True) != row["title"]:
                raise IntakeError(f"印刷页 {page} 的网页版本标题或文字编码不符。")
            sources.append({"citation": f"玉环史志网，同题网页版本，{online['date']}；与本册版本须逐项比较。",
                            "type": "yuhuan_web_version", "url": online["url"], "locator": row["title"],
                            "local_path": online_local, "content_sha256": online_digest})
        metadata = {**common, "id": f"case_cn_yuhuan_2008_p{page:03d}",
                    "title": f"玉环传说故事 · {row['title']}", "aliases": [row["title"]],
                    "node_type": "case", "z_layer": 1, "spatial": spatial,
                    "relations": [{"type": "PART_OF_MACRO_TREND", "target": COLLECTION,
                                   "note": "同属这部选辑；不表示同一地点、传承关系或母题对应。"}],
                    "sources": sources}
        lines = [f"- 目录标题：{row['title']}", f"- 目录原类别：{row['category']}",
                 f"- 起始印刷页：{page}；PDF 页：{pdf_page(page)}"]
        if row.get("title_note"):
            lines.append(f"- 标题疑点：{row['title_note']}")
        if row.get("credits"):
            lines += ["", f"## 采录旁注候选（印刷第 {row['credit_page']} 页，待复核）", ""]
            lines += [f"- {credit}" for credit in row["credits"]]
        else:
            lines += ["", "## 采录旁注", "", "尚未摘录本条讲述者、记录整理者及流传区域；请查看原页及条目末尾。"]
        if row.get("online_source"):
            lines += ["", "## 同题网页版本", "", "玉环史志网有同题网页文本；它与本册版本存在文字差异，"
                      "尚未确认共同的采录底本，须逐项比较，不能自动视为同一次讲述。"]
        body = ("\n## 目录索引\n\n" + "\n".join(lines)
                + "\n\n## 原文与复核\n\n来源为双页扫描影像，本卡没有正文转录。请打开出处链接，"
                  "以印刷页码定位并逐篇核对标题、旁注、早期发表版本及实际讲述背景。"
                  "流传区域不等于具体采录点或故事发生地；未自动填坐标、年代或标准码。"
                  "资料的再利用许可未明；人工作出复核决定前不编入正式图谱。" + warning_note + "\n")
        yield NodeMetadata.model_validate(metadata), body
