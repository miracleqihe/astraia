"""Index the public Vietnamese Cham folktale edition for local non-commercial research.

Retains titles, catalogue metadata and page fingerprints only; no story text or full HTML.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from pipeline.build_graph import PROJECT_ROOT
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError, _challenge_page

HOST = "https://www.digitizingvietnam.com"
PATH = "/en/our-collections/vietnamese-folk-literature/truyen-co-dan-gian-cham"
INTRO = f"{HOST}{PATH}?muc=loi-gioi-thieu"
AGENT = "Astraia/0.1 (local research intake)"
RIGHTS = "Open access for educational and research purposes; commercial use prohibited."
MAX_BYTES = 3 * 1024 * 1024


def story_url(number: int) -> str:
    return f"{HOST}{PATH}?muc=truyen-{number}"


def _valid_url(url: str, section: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.netloc == "www.digitizingvietnam.com" and parsed.path == PATH
            and parse_qs(parsed.query, keep_blank_values=True) == {"muc": [section]} and not parsed.fragment)


def _soup(raw: bytes) -> BeautifulSoup:
    soup = BeautifulSoup(raw, "html.parser", from_encoding="utf-8")
    if soup.contains_replacement_characters or _challenge_page(soup):
        raise IntakeError("网页编码不可靠或返回访问验证；停止获取。")
    if not soup.title or "Folktales of Cham People" not in soup.title.get_text(" ", strip=True):
        raise IntakeError("来源不是预期的越南占族故事选集。")
    return soup


def _field(soup: BeautifulSoup, label: str) -> str:
    node = soup.find(string=lambda value: value is not None and value.strip() == label)
    if node is None or not node.parent or not node.parent.parent:
        return ""
    children = node.parent.parent.find_all("div", recursive=False)
    return children[1].get_text(" ", strip=True) if len(children) == 2 else ""


def _rights(soup: BeautifulSoup) -> None:
    if _field(soup, "Access Condition") != RIGHTS:
        raise IntakeError("馆方访问条件发生变化或缺失，须人工核对。")


def parse_intro(raw: bytes) -> dict:
    soup = _soup(raw)
    _rights(soup)
    entries, seen = [], set()
    for button in soup.select("button"):
        span = button.find("span", recursive=False)
        if not span:
            continue
        raw_number = span.get_text(strip=True).removesuffix(".")
        if not raw_number.isdigit():
            continue
        number = int(raw_number)
        match = re.match(r"^\d+\s*\.\s*(.+)$", button.get_text(" ", strip=True))
        if number in seen or not match or not match.group(1).strip():
            raise IntakeError("馆方目录存在重复编号或无效标题。")
        seen.add(number)
        entries.append({"number": number, "title": match.group(1).strip()})
    if len(entries) != 58 or [item["number"] for item in entries] != list(range(1, 59)):
        raise IntakeError("馆方目录不是连续的 58 条；请人工核查变化。")
    article = soup.select_one("article")
    if not article or not article.find("h2") or article.find("h2").get_text(" ", strip=True) != "Lời giới thiệu":
        raise IntakeError("馆方前言页面结构不符。")
    preface = article.get_text(" ", strip=True)
    if not all(part in preface for part in ("32 truyện", "26 truyện", "Tuấn Dũng", "1997", "TRƯƠNG HIẾN MAI")):
        raise IntakeError("前言中的数量、署名或日期线索有变化，请人工核查。")
    fields = {label: _field(soup, label) for label in ("Authors", "Date Created", "Languages", "Publisher", "Access Condition")}
    if fields["Languages"] != "Vietnamese" or not fields["Date Created"] or not fields["Publisher"]:
        raise IntakeError("馆方语言、日期或出版信息缺失。")
    return {"entries": entries, "catalogue_fields": fields,
            "preface_signatory": "TRƯƠNG HIẾN MAI", "preface_date_as_written": "Phan Rang, thu năm 1997",
            "collection_note": "前言称 32 条由馆藏及家庭材料整理翻译，另 26 条由 Tuấn Dũng 从书刊选录；未逐条分组。"}


def parse_story(raw: bytes, number: int, expected_title: str) -> dict:
    soup = _soup(raw)
    _rights(soup)
    current = [button for button in soup.select('button[aria-current="true"]')
               if button.find("span", recursive=False)]
    if len(current) != 1 or not current[0].find("span", recursive=False).get_text(strip=True).startswith(f"{number}."):
        raise IntakeError(f"详情页所选目录编号与 {number} 不符。")
    articles = soup.select("article")
    if len(articles) != 1 or not articles[0].find("h2", recursive=False):
        raise IntakeError(f"第 {number} 篇的详情页结构不符。")
    article = articles[0]
    original_heading = article.find("h2", recursive=False)
    heading_text = original_heading.get_text(" ", strip=True)
    heading_copy = BeautifulSoup(str(original_heading), "html.parser").find("h2")
    notes = []
    for button in heading_copy.find_all("button"):
        label = button.get("aria-label", "")
        if not re.fullmatch(r"Footnote [1-9]\d*", label):
            raise IntakeError(f"第 {number} 篇标题中存在未知按钮，请人工核对。")
        notes.append({"label": label, "display": button.get_text(" ", strip=True)})
        button.decompose()
    heading = heading_copy.get_text(" ", strip=True)
    found = re.fullmatch(rf"{number}\.\s*(.+)", heading)
    if not found:
        raise IntakeError(f"第 {number} 篇的详情标题编号不符。")
    title = found.group(1).strip()
    paragraphs = [p.get_text(" ", strip=True) for p in article.find_all("p", recursive=False)]
    paragraphs = [value for value in paragraphs if value]
    next_urls = []
    for anchor in soup.select("a[href]"):
        if anchor.get_text(" ", strip=True).startswith("Next"):
            next_urls.append(urljoin(HOST, anchor["href"]))
    if number < 58:
        if len(next_urls) != 1 or not _valid_url(next_urls[0], f"truyen-{number + 1}"):
            raise IntakeError(f"第 {number} 篇的下一篇链接不符。")
        next_url = next_urls[0]
    else:
        if next_urls:
            raise IntakeError("第 58 篇存在未预期的下一篇链接。")
        next_url = None
    return {"number": number, "catalogue_title": expected_title, "detail_title": title,
            "paragraph_count": len(paragraphs), "text_characters": sum(len(p) for p in paragraphs),
            "title_matches": expected_title == title, "heading_text_with_notes": heading_text,
            "heading_note_markers": notes, "next_url": next_url}


def _json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _robots(delay: float) -> RobotFileParser:
    time.sleep(delay)
    url = HOST + "/robots.txt"
    with urlopen(Request(url, headers={"User-Agent": AGENT}), timeout=30) as response:
        if response.geturl() != url or response.headers.get_content_type() != "text/plain":
            raise IntakeError("robots.txt 内容类型或地址变化。")
        raw = response.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise IntakeError("robots.txt 超过大小限制。")
    parser = RobotFileParser()
    parser.parse(raw.decode("utf-8-sig").splitlines())
    return parser


def _request(url: str, parser: RobotFileParser, delay: float) -> bytes:
    if not parser.can_fetch(AGENT, url):
        raise IntakeError(f"robots.txt 不允许获取：{url}")
    time.sleep(delay)
    with urlopen(Request(url, headers={"User-Agent": AGENT, "Accept": "text/html", "Accept-Encoding": "identity"}), timeout=35) as response:
        if response.geturl() != url or response.headers.get_content_type() != "text/html":
            raise IntakeError(f"来源地址重定向或内容类型变化：{url}")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise IntakeError(f"来源页面超出大小限制：{url}")
    return raw


def _capture(path: Path, url: str, parser: RobotFileParser, delay: float, parse) -> dict:
    if path.exists():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise IntakeError(f"已有研究快照无法读取：{path}") from error
        if document.get("source_url") != url or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("raw_sha256", ""))):
            raise IntakeError(f"已有研究快照的来源或响应哈希不符：{path}")
        return document
    raw = _request(url, parser, delay)
    document = {"source_url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "raw_sha256": sha256(raw).hexdigest(), **parse(raw)}
    exclusive_write(path, _json(document))
    return document


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError("馆藏请求间隔至少为 2 秒。")
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "manifest.json").exists():
        raise IntakeError("目录已有完整批次清单；请指定新目录。")
    robots = _robots(delay)
    catalogue_path = folder / "catalogue.json"
    intro = _capture(catalogue_path, INTRO, robots, delay, parse_intro)
    entries = intro.get("entries")
    if not isinstance(entries, list) or len(entries) != 58 or [x.get("number") for x in entries] != list(range(1, 59)):
        raise IntakeError("本地目录快照内容不符。")
    if intro.get("catalogue_fields", {}).get("Access Condition") != RIGHTS:
        raise IntakeError("本地目录快照的使用条件不符。")
    seed_path = folder / "seed.json"
    seed_digest = None
    if seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        if (not isinstance(seed, dict) or seed.get("version") != 1
                or seed.get("catalogue_sha256") != sha256(catalogue_path.read_bytes()).hexdigest()
                or not isinstance(seed.get("reused"), list) or not isinstance(seed.get("refetch"), list)):
            raise IntakeError("修订批次的基线目录不符。")
        reused = set()
        for row in seed["reused"]:
            number = row.get("number") if isinstance(row, dict) else None
            if type(number) is not int or not 1 <= number <= 58 or number in reused:
                raise IntakeError("修订批次的复用编号无效。")
            reused.add(number)
            if sha256((folder / f"story-{number:03d}.json").read_bytes()).hexdigest() != row.get("sha256"):
                raise IntakeError(f"复用的第 {number} 篇快照哈希不符。")
        refetch = seed["refetch"]
        if (any(type(number) is not int or not 1 <= number <= 58 for number in refetch)
                or len(set(refetch)) != len(refetch) or reused & set(refetch)
                or reused | set(refetch) != set(range(1, 59))):
            raise IntakeError("修订批次的复用与重查范围不符。")
        seed_digest = sha256(seed_path.read_bytes()).hexdigest()
    captures, next_url = [], story_url(1)
    for entry in entries:
        number = entry["number"]
        if not _valid_url(next_url, f"truyen-{number}"):
            raise IntakeError(f"第 {number} 篇的链接链不符。")
        path = folder / f"story-{number:03d}.json"
        document = _capture(path, next_url, robots, delay,
                            lambda raw: parse_story(raw, number, entry["title"]))
        if (document.get("number") != number or document.get("catalogue_title") != entry["title"]
                or not isinstance(document.get("detail_title"), str)
                or type(document.get("paragraph_count")) is not int or type(document.get("text_characters")) is not int):
            raise IntakeError(f"第 {number} 篇的本地字段快照不符。")
        captures.append({"number": number, "path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()})
        next_url = document.get("next_url")
        print(f"目录详情 {number}/58：已核对标题与原站链接。", flush=True)
    manifest = {"version": 1, "catalogue_url": INTRO, "catalogue_path": catalogue_path.name,
                "catalogue_sha256": sha256(catalogue_path.read_bytes()).hexdigest(),
                "scope": "非商业教育与研究目录；未保存故事正文或完整网页", "stories": captures}
    if seed_digest:
        manifest["seed_path"] = seed_path.name
        manifest["seed_sha256"] = seed_digest
    exclusive_write(folder / "manifest.json", _json(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".local/import-sources/vietnam-cham-folktales")
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        manifest = fetch(args.output, args.delay)
    except (ValueError, OSError, HTTPError, URLError) as error:
        print(f"越南选集目录获取未完成，已保存的研究索引未覆盖。{error}", file=sys.stderr)
        return 1
    print(f"选集目录索引完成：{len(manifest['stories'])} 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
