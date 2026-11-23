"""Cache the individual public catalogue pages linked from a saved search result."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import Lock
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from pipeline.nichibun import SEARCH_URL, card_fields

ORIGIN = "www.nichibun.ac.jp"
CARD_PATH = "/cgi-bin/YoukaiDB3/youkai_card.cgi"


def search_records(search_html: Path) -> list[tuple[str, str]]:
    page = BeautifulSoup(search_html.read_bytes(), "html.parser")
    records = {}
    for link in page.find_all("a", href=True):
        url = urljoin(SEARCH_URL, link["href"])
        parsed = urlparse(url)
        values = parse_qs(parsed.query)
        identifiers = values.get("ID", [])
        if (parsed.scheme != "https" or parsed.netloc != ORIGIN or parsed.path != CARD_PATH
                or len(identifiers) != 1 or not re.fullmatch(r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)*", identifiers[0])):
            continue
        records.setdefault(identifiers[0], f"https://{ORIGIN}{CARD_PATH}?ID={identifiers[0]}")
    if not records:
        raise ValueError("搜索结果中没有日文研馆藏卡链接。")
    return list(records.items())


def fetch(search_html: Path, output: Path, limit: int | None = None) -> tuple[int, list[str]]:
    records = search_records(search_html)
    if limit is not None:
        records = records[:limit]
    output.mkdir(parents=True, exist_ok=True)
    lock = Lock()
    next_request = 0.0

    def one(record: tuple[str, str]) -> tuple[str, str | None]:
        nonlocal next_request
        identifier, url = record
        destination = output / f"{identifier}.html"
        if destination.is_file():
            try:
                card_fields(destination)
                return identifier, None
            except (OSError, UnicodeError, ValueError) as error:
                return identifier, f"已保存快照无法校验：{error}"
        for attempt in range(3):
            try:
                with lock:
                    wait = max(0.0, next_request - time.monotonic())
                    if wait:
                        time.sleep(wait)
                    next_request = time.monotonic() + 0.7
                request = Request(url, headers={"User-Agent": "Astraia/1.0 (local research catalogue)"})
                with urlopen(request, timeout=20) as response:
                    final = urlparse(response.geturl())
                    if final.scheme != "https" or final.netloc != ORIGIN or final.path != CARD_PATH:
                        raise ValueError("馆藏地址重定向到非预期站点。")
                    raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("馆藏页面大小超过预期。")
                with TemporaryDirectory(prefix=".nichibun-download-", dir=output) as temporary:
                    staged = Path(temporary) / destination.name
                    staged.write_bytes(raw)
                    card_fields(staged)
                    if destination.exists():
                        card_fields(destination)
                    else:
                        staged.rename(destination)
                return identifier, None
            except (OSError, UnicodeError, ValueError, HTTPError, URLError) as error:
                if attempt == 2:
                    return identifier, str(error)
                time.sleep(1.5 * (attempt + 1))
        return identifier, "获取失败"

    errors = []
    completed = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, record) for record in records]
        for future in as_completed(futures):
            identifier, error = future.result()
            completed += 1
            if error:
                errors.append(f"{identifier} · {error}")
            if completed % 20 == 0 or completed == len(records):
                print(f"已处理 {completed}/{len(records)}，未完成 {len(errors)}。", flush=True)
    return len(records) - len(errors), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit 必须大于零")
    count, errors = fetch(args.search_html, args.output, args.limit)
    print(f"已校验 {count} 张本地馆藏卡。")
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
