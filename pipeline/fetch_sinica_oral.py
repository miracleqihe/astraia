"""Build a local research-only index of public Academia Sinica catalogue pages.

Only catalogue labels and selected descriptive fields are retained. Translations,
recordings, page HTML and other copyrighted content are not saved.
"""
import argparse
from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from pipeline.build_graph import PROJECT_ROOT
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError, _challenge_page

BASE = "https://aya.ioe.sinica.edu.tw"
AGENT = "Astraia/0.1 (local research intake)"
GROUPS = {
    1: "阿美族：馬太安 Unak Tafong",
    2: "阿美族：諸部落",
    3: "雅美族：紅頭（Imorod）",
    4: "雅美族：椰油（Yayo）",
    5: "雅美族：東清（Iranmeilek）",
    6: "雅美族：漁人（Iratay）",
    7: "雅美族：朗島（Iraralay）",
    8: "雅美族：野銀（Ivalinu）",
}
FIELDS = ("檔案名稱", "採集日期", "族別", "記音者", "報導人", "翻譯者", "採集地點", "說明")
MAX_BYTES = 3 * 1024 * 1024
DETAIL = re.compile(r"/index\.php/Frontend/loreDetail/([1-9]\d*)")
LIST = re.compile(r"/index\.php/Frontend/SharerLore/([1-8])(?:/([1-9]\d*))?")


def detail_url(identifier: int) -> str:
    return f"{BASE}/index.php/Frontend/loreDetail/{identifier}"


def list_url(group: int, page: int = 1) -> str:
    return f"{BASE}/index.php/Frontend/SharerLore/{group}" + (f"/{page}" if page != 1 else "")


def _url(url: str, pattern: re.Pattern) -> re.Match | None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "aya.ioe.sinica.edu.tw" or parsed.query or parsed.fragment:
        return None
    return pattern.fullmatch(parsed.path)


def _soup(raw: bytes) -> BeautifulSoup:
    soup = BeautifulSoup(raw, "html.parser", from_encoding="utf-8")
    if soup.contains_replacement_characters or _challenge_page(soup):
        raise IntakeError("网页编码不可靠或返回访问验证；停止获取。")
    if not soup.title or "阿美族、雅美族口語傳說採錄翻譯" not in soup.title.get_text():
        raise IntakeError("网页不是预期的馆方目录；停止获取。")
    return soup


def parse_listing(raw: bytes, group: int, page: int) -> dict:
    soup = _soup(raw)
    entries, seen, pages = [], set(), set()
    for anchor in soup.select("a[href]"):
        url = urljoin(BASE, anchor["href"])
        detail = _url(url, DETAIL)
        listing = _url(url, LIST)
        if detail:
            identifier = int(detail.group(1))
            title = " ".join(anchor.stripped_strings)
            if not title or identifier in seen:
                raise IntakeError(f"目录 {group}/{page} 存在空题名或重复条目。")
            seen.add(identifier)
            entries.append({"id": identifier, "label": title})
        elif listing and int(listing.group(1)) == group:
            pages.add(int(listing.group(2) or 1))
    if not entries:
        raise IntakeError(f"目录 {group}/{page} 没有馆藏条目。")
    return {"group": group, "page": page, "entries": entries, "linked_pages": sorted(pages)}


def parse_detail(raw: bytes, identifier: int) -> dict:
    soup = _soup(raw)
    table = soup.select_one("#Table1")
    if not table:
        raise IntakeError(f"详情 {identifier} 未显示馆藏字段。")
    fields = {}
    for row in table.select("tr"):
        headers, values = row.find_all("th", recursive=False), row.find_all("td", recursive=False)
        if len(headers) != len(values):
            continue
        for header, value in zip(headers, values, strict=True):
            key = header.get_text(" ", strip=True).rstrip("：: ")
            if key in FIELDS:
                if key in fields:
                    raise IntakeError(f"详情 {identifier} 存在重复字段 {key}。")
                fields[key] = " ".join(value.stripped_strings)
    if not fields or not any(value.strip() for value in fields.values()):
        raise IntakeError(f"详情 {identifier} 没有可识别的描述字段。")
    notice = table.get_text(" ", strip=True)
    normal = "非營利性教育與學術目的瀏覽使用"
    extra_de = "非營利性教育與學術目的的瀏覽使用"
    if (normal not in notice and extra_de not in notice) or "非經同意不得以任何形式擷取內容出版" not in notice:
        raise IntakeError(f"详情 {identifier} 的使用声明发生变化，请人工核查。")
    variant = "extra_de" if extra_de in notice else "original"
    return {"id": identifier, "fields": fields, "rights_notice_present": True, "rights_notice_variant": variant}


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _request(url: str, delay: float) -> bytes:
    time.sleep(delay)
    request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=30) as response:
        if response.geturl() != url or response.headers.get_content_type() != "text/html":
            raise IntakeError(f"来源重定向或内容类型变化：{url}")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise IntakeError(f"页面过大：{url}")
    return raw


def _robots(delay: float) -> tuple[RobotFileParser, str]:
    url = BASE + "/robots.txt"
    time.sleep(delay)
    try:
        with urlopen(Request(url, headers={"User-Agent": AGENT}), timeout=30) as response:
            if response.geturl() != url:
                raise IntakeError("robots.txt 重定向，须人工检查。")
            raw = response.read(256 * 1024 + 1)
            if len(raw) > 256 * 1024:
                raise IntakeError("robots.txt 超出大小限制。")
            lines = raw.decode("utf-8-sig").splitlines()
            status = "200"
    except HTTPError as error:
        if error.code != 404:
            raise IntakeError(f"robots.txt 返回 {error.code}，停止获取。") from error
        lines, status = [], "404"
    parser = RobotFileParser()
    parser.parse(lines)
    return parser, status


def _save_or_reuse(path: Path, url: str, parse, parser: RobotFileParser, delay: float) -> dict:
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise IntakeError(f"中断后的快照无法读取：{path}") from error
        if value.get("source_url") != url or not re.fullmatch(r"[0-9a-f]{64}", value.get("raw_sha256", "")):
            raise IntakeError(f"中断后的快照地址或原始哈希无效：{path}")
        return value
    if not parser.can_fetch(AGENT, url):
        raise IntakeError(f"robots.txt 不允许获取 {url}。")
    raw = _request(url, delay)
    value = {"source_url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
             "raw_sha256": sha256(raw).hexdigest(), **parse(raw)}
    exclusive_write(path, _json_bytes(value))
    return value


def fetch(output: Path, delay: float = 1.0, details_per_group: int = 3) -> dict:
    if delay < 1 or not 0 <= details_per_group <= 30:
        raise IntakeError("请求间隔至少 1 秒；每组详情样本数须为 0–30。")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise IntakeError("此目录已有完整清单，请指定新目录以获取新快照。")
    robots, robots_status = _robots(delay)
    pages, detail_rows, records, selected, group_counts = [], [], {}, set(), {}
    for group in GROUPS:
        queue, visited, group_seen, group_selection = deque([1]), set(), set(), []
        while queue:
            number = queue.popleft()
            if number in visited:
                continue
            if number > 100:
                raise IntakeError("目录分页异常，停止获取。")
            visited.add(number)
            path = output / f"group-{group}-page-{number:03d}.json"
            url = list_url(group, number)
            value = _save_or_reuse(path, url, lambda raw: parse_listing(raw, group, number), robots, delay)
            if value.get("group") != group or value.get("page") != number or not isinstance(value.get("entries"), list):
                raise IntakeError(f"本地目录页内容不符：{path}")
            for entry in value["entries"]:
                identifier, label = entry.get("id"), entry.get("label")
                if type(identifier) is not int or identifier <= 0 or not isinstance(label, str) or not label:
                    raise IntakeError(f"本地目录页条目无效：{path}")
                if identifier in group_seen:
                    raise IntakeError(f"同一目录的不同分页出现重复编号 {identifier}。")
                group_seen.add(identifier)
                if identifier in records:
                    raise IntakeError(f"不同目录重复出现编号 {identifier}；请人工核对。")
                records[identifier] = (group, number, label)
                if len(group_selection) < details_per_group:
                    group_selection.append(identifier)
            for linked in value.get("linked_pages", []):
                if type(linked) is not int or not 1 <= linked <= 100:
                    raise IntakeError(f"本地目录页分页编号无效：{path}")
                if linked not in visited:
                    queue.append(linked)
            pages.append({"group": group, "page": number, "path": path.name,
                          "sha256": sha256(path.read_bytes()).hexdigest(), "records": len(value["entries"])})
            print(f"目录 {group}/{number}：{len(value['entries'])} 条。", flush=True)
        group_counts[str(group)] = len(group_seen)
        selected.update(group_selection)
    for identifier in sorted(selected):
        path = output / f"detail-{identifier}.json"
        url = detail_url(identifier)
        value = _save_or_reuse(path, url, lambda raw: parse_detail(raw, identifier), robots, delay)
        if value.get("id") != identifier or not isinstance(value.get("fields"), dict):
            raise IntakeError(f"本地详情索引不符：{path}")
        detail_rows.append({"id": identifier, "path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()})
        print(f"目录详情样本 {identifier} 已记录描述字段。", flush=True)
    manifest = {"version": 1, "scope": "本地研究索引；未保存网页正文、译文或录音，不用于未经同意出版",
                "robots_status": robots_status, "groups": GROUPS, "group_counts": group_counts,
                "total_records": len(records), "details_per_group": details_per_group,
                "pages": pages, "details": detail_rows}
    exclusive_write(output / "manifest.json", _json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".local/import-sources/sinica-oral")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--details-per-group", type=int, default=3)
    args = parser.parse_args()
    try:
        manifest = fetch(args.output, args.delay, args.details_per_group)
    except (IntakeError, OSError, HTTPError, URLError) as error:
        print(f"馆藏索引未完成；已保存的研究快照未覆盖。{error}", file=sys.stderr)
        return 1
    print(f"馆藏目录索引：{manifest['total_records']} 条，详情字段样本 {len(manifest['details'])} 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
