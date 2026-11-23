"""Cache selected public Dúchas XML records, respecting the site's crawl delay."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import yaml

from pipeline.ingest_agent import PROJECT_ROOT
from pipeline.intake_sources import IntakeError

USER_AGENT = "AstraiaResearch/1.0 (local source-linked research)"
BASE = "https://www.duchas.ie"
MAX_BYTES = 8 * 1024 * 1024


def candidates(path: Path) -> list[dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("candidates"), list):
        raise IntakeError("Dúchas 候选清单格式不正确。")
    result, seen = [], set()
    for item in document["candidates"]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            raise IntakeError("Dúchas 候选项缺少网址。")
        url = urlsplit(item["url"])
        match = re.fullmatch(r"/(?:en|ga)/cbes/(\d+)/(\d+)/(\d+)", url.path)
        if url.scheme != "https" or url.netloc != "www.duchas.ie" or url.query or url.fragment or not match:
            raise IntakeError(f"Dúchas 候选网址格式不正确。{item['url']}")
        chapter, page, story = match.groups()
        if story in seen:
            raise IntakeError(f"候选清单包含重复故事编号。{story}")
        seen.add(story)
        result.append({"url": item["url"], "context": item.get("search_context", ""),
                       "chapter": chapter, "page": page, "story": story})
    return result


def read_remote(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/plain;q=0.8"})
    with urlopen(request, timeout=35) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise IntakeError(f"来源文件超出允许大小。{url}")
    return raw


def parse_xml(raw: bytes, tag: str, identifier: str):
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise IntakeError(f"来源不是有效的馆藏 XML。{error}") from error
    if root.tag != tag or root.get("entryID") != identifier:
        raise IntakeError(f"馆藏 XML 类型或编号不匹配。{tag} {identifier}")
    return root


def validate_story(root, chapter: str, page: str) -> None:
    parent, title = root.find("chapter"), root.find("title")
    if (parent is None or parent.get("default") != chapter or page not in {item.get("default") for item in root.findall("page")}
            or title is None or title.get("default", "").casefold() not in {"fairy fort", "fairy forts"}):
        raise IntakeError("故事的学校、页面或题名与候选清单不一致。")


def fetch(selection: list[dict], output: Path, *, include_all_pages: bool = False) -> dict:
    robot_text = read_remote(f"{BASE}/robots.txt").decode("utf-8-sig")
    if "<html" in robot_text.lower():
        raise IntakeError("无法读取站点爬取规则。")
    robots = RobotFileParser()
    robots.parse(robot_text.splitlines())
    delay = max(2.0, float(robots.crawl_delay(USER_AGENT) or 0))
    last_request = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    results = []

    def snapshot(path: Path, url: str, tag: str, identifier: str, validator=None):
        nonlocal last_request
        if path.exists():
            raw = path.read_bytes()
            state = "cached"
        else:
            if not robots.can_fetch(USER_AGENT, url):
                raise IntakeError(f"站点爬取规则不允许读取该地址。{url}")
            wait = delay - (time.monotonic() - last_request)
            if wait > 0:
                time.sleep(wait)
            last_request = time.monotonic()
            raw = read_remote(url)
            state = "downloaded"
        root = parse_xml(raw, tag, identifier)
        if validator:
            validator(root)
        if state == "downloaded":
            with path.open("xb") as stream:
                stream.write(raw)
        return root, {"path": str(path.resolve()), "sha256": sha256(raw).hexdigest(), "state": state}

    for item in selection:
        chapter, page, story = (item[key] for key in ("chapter", "page", "story"))
        row = {"url": item["url"], "context": item["context"], "story": story, "files": {}}
        try:
            root, row["files"]["story"] = snapshot(
                output / f"story-{chapter}-{page}-{story}.xml", f"{BASE}/xml/cbes/{chapter}/{page}/{story}",
                "lStory", story, lambda value: validate_story(value, chapter, page),
            )
            _, row["files"]["school"] = snapshot(output / f"school-{chapter}.xml", f"{BASE}/xml/cbes/{chapter}",
                                                "lChapter", chapter)
            _, row["files"]["page"] = snapshot(output / f"page-{chapter}-{page}.xml", f"{BASE}/xml/cbes/{chapter}/{page}",
                                              "pPage", page, lambda value: validate_page(value, story))
            if include_all_pages:
                page_ids = [element.get("default", "") for element in root.findall("page")]
                if any(not re.fullmatch(r"\d+", identifier) for identifier in page_ids) or len(set(page_ids)) != len(page_ids):
                    raise IntakeError(f"故事 {story} 包含无效或重复页面编号。")
                row["files"]["additional_pages"] = []
                for identifier in page_ids:
                    if identifier == page:
                        continue
                    _, entry = snapshot(output / f"page-{chapter}-{identifier}.xml", f"{BASE}/xml/cbes/{chapter}/{identifier}",
                                        "pPage", identifier, lambda value: validate_page(value, story))
                    row["files"]["additional_pages"].append(entry)
            row["status"] = "ready"
            row["title"] = root.find("title").get("default")
            print(f"已核验 {story} · {item['context']}", flush=True)
        except (HTTPError, URLError, OSError, ValueError, IntakeError) as error:
            row["status"] = "stopped"
            row["error"] = str(error)
            results.append(row)
            print(f"停止获取 {story}：{error}", flush=True)
            break
        results.append(row)
    return {"retrieved_at": datetime.now(timezone.utc).isoformat(), "crawl_delay_seconds": delay,
            "license": "https://creativecommons.org/licenses/by-nc/4.0/", "results": results,
            "ready": sum(row["status"] == "ready" for row in results), "selected": len(selection)}


def validate_page(root, story: str) -> None:
    if not any(item.get("default") == story for item in root.findall("story")):
        raise IntakeError(f"馆藏页未包含故事 {story}。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, nargs="+", default=[PROJECT_ROOT / "reference/duchas_fairyfort_candidates.yaml"])
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".local/import-sources/duchas")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / ".local/intake-qa/duchas-fairyfort-fetch.json")
    parser.add_argument("--all-pages", action="store_true", help="一并保存故事 XML 登记的其他页面")
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(f"已保留已有获取记录，请指定新报告文件名。{args.report}")
    selected = [item for path in args.candidates for item in candidates(path)]
    if len({item["story"] for item in selected}) != len(selected):
        raise IntakeError("候选文件之间包含重复故事编号。")
    result = fetch(selected, args.output, include_all_pages=args.all_pages)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if result["ready"] == result["selected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
