"""Attach separately sourced Yuhuan credit candidates without replacing existing drafts."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import Source
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer
from pipeline.yuhuan_stories import DOCUMENT, PDF_URL, _local_file, pdf_page, read_index

MARKER = "<!-- astraia:yuhuan-credits-v1 -->"
PLACEHOLDER = "尚未摘录本条讲述者、记录整理者及流传区域；请查看原页及条目末尾。"


def read_supplement(path: Path, base: Path, pdf: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"玉环旁注补充索引无法读取：{error}") from error
    baseline = read_index(base)
    if (not isinstance(data, dict) or data.get("version") != 1
            or data.get("base_index_sha256") != sha256(base.read_bytes()).hexdigest()
            or data.get("pdf_sha256") != baseline["pdf_sha256"]
            or data.get("pdf_sha256") != sha256(pdf.read_bytes()).hexdigest()
            or not isinstance(data.get("entries"), list) or not data["entries"]):
        raise IntakeError("旁注补充索引与原目录或扫描快照不一致。")
    by_page = {item["page"]: item for item in baseline["entries"]}
    next_page = {item["page"]: following for item, following in zip(
        baseline["entries"], [item["page"] for item in baseline["entries"][1:]] + [95], strict=True)}
    seen = set()
    for row in data["entries"]:
        if not isinstance(row, dict) or row.get("page") not in by_page:
            raise IntakeError("旁注补充含原目录之外的页码。")
        page = row["page"]
        if page in seen or row.get("title") != by_page[page]["title"]:
            raise IntakeError(f"印刷页 {page} 的旁注重复或标题与原目录不一致。")
        seen.add(page)
        credit_pages = row.get("credit_pages")
        if (not isinstance(credit_pages, list) or not credit_pages
                or any(type(item) is not int or not page <= item <= min(next_page[page], 94) for item in credit_pages)
                or credit_pages != sorted(set(credit_pages))):
            raise IntakeError(f"印刷页 {page} 的旁注页码无效。")
        credits = row.get("credits")
        if (not isinstance(credits, list) or not credits
                or any(not isinstance(value, str) or not value.strip() or "\ufffd" in value or "\0" in value for value in credits)):
            raise IntakeError(f"印刷页 {page} 的旁注文字无效。")
        for field in ("note", "conflict", "prior_publication"):
            if field in row and (not isinstance(row[field], str) or not row[field].strip()):
                raise IntakeError(f"印刷页 {page} 的 {field} 字段无效。")
        online = row.get("online_source")
        if online is not None:
            if not isinstance(online, dict) or not all(isinstance(online.get(key), str) and online[key].strip()
                    for key in ("title", "url", "local_path", "sha256", "date", "note")):
                raise IntakeError(f"印刷页 {page} 的网页版本格式有误。")
            url = urlsplit(online["url"])
            if (url.scheme != "https" or url.hostname != "yhsz.yuhuan.gov.cn" or not url.path.startswith("/art/")
                    or not re.fullmatch(r"[0-9a-f]{64}", online["sha256"])
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", online["date"])):
                raise IntakeError(f"印刷页 {page} 的网页来源地址或哈希无效。")
    return data


def supplement_sources(row: dict, supplement: Path, pdf: Path, data: dict) -> list[Source]:
    supplement_local, supplement_hash = _local_file(supplement)
    pdf_local, pdf_hash = _local_file(pdf)
    pages = "、".join(str(number) for number in row["credit_pages"])
    sources = [Source.model_validate({"citation": "项目根据原册扫描摘录的采录旁注候选，尚未经人工签核。",
        "type": "yuhuan_credit_supplement", "locator": f"故事印刷第 {row['page']} 页 / 旁注印刷第 {pages} 页",
        "local_path": supplement_local, "content_sha256": supplement_hash})]
    for scan in sorted({pdf_page(number) for number in row["credit_pages"]}):
        printed = "、".join(str(number) for number in row["credit_pages"] if pdf_page(number) == scan)
        sources.append(Source.model_validate({"citation": DOCUMENT, "type": "yuhuan_scan",
            "url": f"{PDF_URL}#page={scan}", "locator": f"传说故事篇 / 旁注印刷第 {printed} 页 / PDF 第 {scan} 页",
            "local_path": pdf_local, "content_sha256": pdf_hash}))
    online = row.get("online_source")
    if online:
        online_file = Path(online["local_path"])
        if not online_file.is_absolute():
            online_file = PROJECT_ROOT / online_file
        local, digest = _local_file(online_file)
        soup = BeautifulSoup(online_file.read_bytes(), "html.parser")
        if digest != online["sha256"] or soup.contains_replacement_characters or not soup.title or soup.title.get_text(strip=True) != online["title"]:
            raise IntakeError(f"印刷页 {row['page']} 的网页版本快照、标题或编码不符。")
        sources.append(Source.model_validate({"citation": f"玉环史志网网页版本《{online['title']}》，{online['date']}；与选辑的关系待核。",
            "type": "yuhuan_web_candidate", "url": online["url"], "locator": online["title"],
            "local_path": local, "content_sha256": digest}))
    return sources


def supplement_note(row: dict) -> str:
    pages = "、".join(str(number) for number in row["credit_pages"])
    lines = ["", MARKER, f"## 采录与早期刊载旁注补充（印刷第 {pages} 页，待复核）", ""]
    lines.extend(f"- {credit}" for credit in row["credits"])
    if row.get("prior_publication"):
        lines.append(f"- 原册所列早期刊载线索（未核对该版原件）：{row['prior_publication']}")
    if row.get("note"):
        lines.append(f"- 原文字形或地名待核：{row['note']}")
    if row.get("conflict"):
        lines.append(f"- 现有登记与新读法有歧义：{row['conflict']}")
    if row.get("online_source"):
        lines.append(f"- 网页版本对照待核：{row['online_source']['note']}")
    lines += ["", "这些是选辑旁注的转记候选，不代表已核实原始采录、早期刊物或人名；"
                   "流传区域不等同于故事地点或记录地点。", ""]
    return "\n".join(lines)


def enrich(vault: Path, supplement: Path, base: Path, pdf: Path, *, check: bool = False) -> dict:
    data = read_supplement(supplement, base, pdf)
    folder = vault / "00_drafts/asia_yuhuan_2008"
    plans, skipped, already = [], [], 0
    with vault_writer(vault):
        for row in data["entries"]:
            path = folder / f"case_cn_yuhuan_2008_p{row['page']:03d}.md"
            if not path.is_file() or path.is_symlink():
                skipped.append({"page": row["page"], "reason": "草稿不存在或是符号链接"})
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, _ = parse_card(text.replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                skipped.append({"page": row["page"], "reason": "已经复核或为示例"})
                continue
            original_index = next((item for item in metadata.sources if item.type == "yuhuan_index"), None)
            scan = next((item for item in metadata.sources if item.type == "yuhuan_scan"), None)
            if (metadata.id != path.stem or not original_index or original_index.content_sha256 != data["base_index_sha256"]
                    or not scan or scan.content_sha256 != data["pdf_sha256"]):
                raise IntakeError(f"原草稿档号、目录或扫描来源不一致：{path}")
            sources = supplement_sources(row, supplement, pdf, data)
            previous = [source for source in metadata.sources if source.type == "yuhuan_credit_supplement"]
            if previous and any(source.content_sha256 != sources[0].content_sha256 for source in previous):
                raise IntakeError(f"草稿已有不同版本的旁注补充；保留现有内容：{path}")
            if MARKER in text:
                if not previous:
                    raise IntakeError(f"草稿已有补充标记但缺少来源；保留现有内容：{path}")
                already += 1
                continue
            existing = {(item.type, str(item.url) if item.url else None, item.locator) for item in metadata.sources}
            additions = [item for item in sources if (item.type, str(item.url) if item.url else None, item.locator) not in existing]
            revised = append_sources(text, additions)
            if PLACEHOLDER in revised:
                revised = revised.replace(PLACEHOLDER, "原批次未摘录；后附采录旁注候选，仍待复核。", 1)
            revised += supplement_note(row)
            encoded = revised.encode("utf-8")
            if raw.startswith(b"\xef\xbb\xbf"):
                encoded = b"\xef\xbb\xbf" + encoded
            plans.append((path, raw, encoded))
        if not check:
            for path, original, revised in plans:
                with NamedTemporaryFile(dir=path.parent, prefix=".yuhuan-credits-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise IntakeError(f"草稿在补充旁注时发生变化：{path}")
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
    return {"cards_to_update": len(plans), "already_enriched": already, "skipped": skipped, "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--supplement", type=Path, default=PROJECT_ROOT / "reference/yuhuan_2008_credits_v1.json")
    parser.add_argument("--base-index", type=Path, default=PROJECT_ROOT / "reference/yuhuan_2008_story_index.json")
    parser.add_argument("--pdf", type=Path, default=PROJECT_ROOT / ".local/import-sources/china-yuhuan/yuhuan-oral-literature-2008.pdf")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = enrich(args.vault.resolve(), args.supplement.resolve(), args.base_index.resolve(), args.pdf.resolve(), check=args.check)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
