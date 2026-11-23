"""Save the DLLM Folk Tale search pages without downloading manuscript images."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pipeline.build_graph import PROJECT_ROOT
from pipeline.intake_sources import IntakeError

ENDPOINT = "https://iiif.crossasia.org/s/dllm/madoc/api/search?page={}"
SEARCH_URL = ("https://iiif.crossasia.org/s/dllm/search?"
              "facets=%5B%7B%22k%22%3A%22dc%3Asubject%22%2C%22v%22%3A%22Folk%20Tale%22%7D%5D&fulltext=")
PAYLOAD = {"fulltext": "", "facet_fields": ["dc:language", "script", "dc:subject", "material",
                                              "full_location_name", "is_illustrated", "is_color"],
           "facets": [{"type": "metadata", "subtype": "dc:subject", "value": "Folk Tale"}],
           "facet_on_manifests": True, "search_type": "websearch", "number_of_facets": 100,
           "iiif_type": "Manifest", "non_latin_fulltext": True, "search_multiple_fields": False}
MAX_PAGE_BYTES = 4 * 1024 * 1024
IDENTIFIER = re.compile(r"urn:madoc:manifest:([1-9]\d*)")


def metadata_values(item: dict, key: str) -> dict[str, list[str]]:
    combined: dict[str, list[str]] = {}
    metadata = item.get("metadata", [])
    if not isinstance(metadata, list):
        raise IntakeError("馆藏元数据不是列表。")
    for entry in metadata:
        if not isinstance(entry, dict) or not isinstance(entry.get("label"), dict) or not isinstance(entry.get("value"), dict):
            raise IntakeError("馆藏元数据结构不符。")
        if any(key in names for names in entry["label"].values() if isinstance(names, list)):
            for language, values in entry["value"].items():
                if not isinstance(language, str) or not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                    raise IntakeError(f"馆藏字段 {key} 的语言或值不符。")
                combined.setdefault(language, []).extend(values)
    return combined


def parse_page(raw: bytes, number: int) -> dict:
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"第 {number} 页不是有效的 UTF-8 JSON。{error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("pagination"), dict) or not isinstance(document.get("results"), list):
        raise IntakeError(f"第 {number} 页缺少分页信息或结果。")
    pagination, items = document["pagination"], document["results"]
    required = ("page", "pageSize", "totalPages", "totalResults")
    if any(type(pagination.get(key)) is not int for key in required) or pagination["page"] != number:
        raise IntakeError(f"第 {number} 页分页信息不符。")
    if pagination["pageSize"] < 1 or pagination["totalPages"] < number or pagination["totalResults"] < 1:
        raise IntakeError(f"第 {number} 页分页范围无效。")
    expected = min(pagination["pageSize"], pagination["totalResults"] - (number - 1) * pagination["pageSize"])
    if len(items) != expected:
        raise IntakeError(f"第 {number} 页应有 {expected} 条，实际 {len(items)} 条。")
    for item in items:
        if not isinstance(item, dict) or item.get("resource_type") != "Manifest" or not IDENTIFIER.fullmatch(str(item.get("resource_id", ""))):
            raise IntakeError(f"第 {number} 页存在无效的馆藏编号。")
        if "Folk Tale" not in metadata_values(item, "dc:subject").get("en", []):
            raise IntakeError(f"第 {number} 页含不属于 Folk Tale 结果的条目。")
    return document


def exclusive_write(path: Path, content: bytes) -> None:
    with TemporaryDirectory(prefix=".astraia-dllm-", dir=path.parent) as temporary:
        staged = Path(temporary) / "snapshot"
        staged.write_bytes(content)
        try:
            os.link(staged, path)
        except FileExistsError as error:
            raise IntakeError(f"已有同名文件，未覆盖。{path}") from error


def fetch(output: Path, delay: float = 1.0) -> dict:
    if delay < 1:
        raise IntakeError("请求间隔至少为 1 秒。")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise IntakeError("此目录已有完整批次清单，请指定新目录以获取新快照。")
    body = json.dumps(PAYLOAD, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    pages, ids, totals, number = [], set(), None, 1
    while totals is None or number <= totals[1]:
        path = output / f"page-{number:03d}.json"
        if path.exists():
            raw = path.read_bytes()
            retrieved = None
        else:
            request = Request(ENDPOINT.format(number), data=body, method="POST", headers={
                "User-Agent": "Astraia/0.1 (local research intake)", "Content-Type": "application/json",
                "Accept": "application/json", "Accept-Encoding": "identity"})
            with urlopen(request, timeout=30) as response:
                raw = response.read(MAX_PAGE_BYTES + 1)
                if response.headers.get_content_type() != "application/json" or len(raw) > MAX_PAGE_BYTES:
                    raise IntakeError(f"第 {number} 页不是预期的 JSON 或超过大小限制，已停止。")
            retrieved = datetime.now(timezone.utc).isoformat()
            parse_page(raw, number)
            exclusive_write(path, raw)
            print(f"已保存馆藏检索第 {number} 页。", flush=True)
            time.sleep(delay)
        document = parse_page(raw, number)
        info = document["pagination"]
        current = (info["totalResults"], info["totalPages"], info["pageSize"])
        if totals is None:
            totals = current
        elif totals != current:
            raise IntakeError("获取期间馆藏检索总数或分页发生变化；已保留快照，请另建目录重取。")
        for item in document["results"]:
            identifier = IDENTIFIER.fullmatch(item["resource_id"]).group(1)
            if identifier in ids:
                raise IntakeError(f"分页中发现重复馆藏编号 {identifier}，请另建目录重取。")
            ids.add(identifier)
        pages.append({"page": number, "path": path.name, "sha256": sha256(raw).hexdigest(),
                      "retrieved_at": retrieved, "records": len(document["results"])})
        number += 1
    if len(ids) != totals[0]:
        raise IntakeError("保存的唯一馆藏编号数与检索总数不符。")
    manifest = {"version": 1, "search_url": SEARCH_URL, "endpoint": ENDPOINT, "payload": PAYLOAD,
                "total_results": totals[0], "total_pages": totals[1], "page_size": totals[2], "pages": pages,
                "scope": "目录分类 Folk Tale 的检索元数据；不含手稿影像或正文转录"}
    exclusive_write(output / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".local/import-sources/lao-dllm")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    try:
        manifest = fetch(args.output, args.delay)
    except (IntakeError, OSError, HTTPError, URLError) as error:
        print(f"馆藏检索未完成；已保存的快照不会被覆盖。{error}", file=sys.stderr)
        return 1
    print(f"检索快照完成：{manifest['total_results']} 条、{manifest['total_pages']} 页。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
