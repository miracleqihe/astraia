"""Fetch a bounded selection of Pangloss metadata pages without downloading media."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_na import CORPUS_URL, catalogue_rows, detail_fields, json_object, load_selection, load_snapshots

AGENT = "AstraiaResearchIndex/1.0 (local source attribution)"
ROBOTS = "https://pangloss.cnrs.fr/robots.txt"
MAX_BYTES = 2 * 1024 * 1024


def robot_rules() -> tuple[RobotFileParser | None, str]:
    try:
        with urlopen(Request(ROBOTS, headers={"User-Agent": AGENT}), timeout=25) as response:
            if response.status != 200 or response.headers.get_content_type() != "text/plain":
                raise IntakeError("Pangloss robots.txt 返回格式不符，停止获取。")
            raw = response.read(65537)
            if len(raw) > 65536:
                raise IntakeError("Pangloss robots.txt 超出大小限制。")
    except HTTPError as error:
        if error.code == 404:
            return None, "404"
        raise IntakeError(f"无法核查 Pangloss robots.txt：HTTP {error.code}") from error
    rules = RobotFileParser()
    rules.set_url(ROBOTS)
    rules.parse(raw.decode("utf-8", "strict").splitlines())
    return rules, "200"


def _seed_entries(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    data = json_object(path)
    if data.get("version") != 1 or not isinstance(data.get("records"), list):
        raise IntakeError("Pangloss 首次详情快照清单无效。")
    entries = {}
    for entry in data["records"]:
        if (not isinstance(entry, dict) or not isinstance(entry.get("id"), str)
                or entry.get("path") != f"record-{entry['id']}.html" or entry["id"] in entries):
            raise IntakeError("Pangloss 首次详情快照编号或路径无效。")
        snapshot = path.parent / entry["path"]
        if sha256(snapshot.read_bytes()).hexdigest() != entry.get("sha256"):
            raise IntakeError(f"Pangloss 首次详情快照哈希不符：{entry['id']}")
        entries[entry["id"]] = entry
    return entries


def download_detail(row: dict, retries: int = 2) -> bytes:
    """Retry only transient transport/server errors, never identity mismatches."""
    for attempt in range(retries + 1):
        request = Request(row["url"], headers={"User-Agent": AGENT, "Accept-Encoding": "identity"})
        try:
            with urlopen(request, timeout=30) as response:
                final = urlsplit(response.geturl())
                if (response.status != 200 or response.headers.get_content_type() != "text/html"
                        or final.scheme != "https" or final.netloc != "pangloss.cnrs.fr" or final.path != "/corpus/show"
                        or parse_qs(final.query) != parse_qs(urlsplit(row["url"]).query)):
                    raise IntakeError(f"Pangloss 详情响应或跳转无效：{row['id']}")
                raw = response.read(MAX_BYTES + 1)
            if not raw or len(raw) > MAX_BYTES:
                raise IntakeError(f"Pangloss 详情为空或过大：{row['id']}")
            if b"SQLSTATE[" in raw and b"Connection refused" in raw:
                raise URLError("馆方数据库暂时拒绝连接")
            return raw
        except HTTPError as error:
            if error.code == 429:
                raise IntakeError('Pangloss 返回 HTTP 429；已停止请求，请遵循馆方限流后再续跑。') from error
            if error.code not in (500, 502, 503, 504):
                raise
            reason = f"HTTP {error.code}"
        except (URLError, TimeoutError, ConnectionError) as error:
            reason = str(error)
        if attempt >= retries:
            raise IntakeError(f"Pangloss 详情暂不可用：{row['id']}，{reason}")
        wait = 10 * (attempt + 1)
        print(f"Pangloss 详情暂不可用：{row['id']}，等待 {wait} 秒后重试。", flush=True)
        time.sleep(wait)
    raise IntakeError(f"Pangloss 详情获取失败：{row['id']}")


def fetch(corpus: Path, selection: Path, output: Path, seed: Path | None = None, delay: float = 2.0,
          *, corpus_name: str = "Yongning Na", corpus_url: str = CORPUS_URL) -> dict:
    if delay < 2:
        raise IntakeError("Pangloss 请求间隔至少为 2 秒。")
    corpus_raw, selection_raw = corpus.read_bytes(), selection.read_bytes()
    catalog, selected = catalogue_rows(corpus_raw, corpus_name), load_selection(selection, corpus_url)
    ids = [number for group in selected["groups"] for number in group["ids"]]
    if any(number not in catalog for number in ids):
        raise IntakeError("选取清单中有馆方目录未列出的录音。")
    seeds = _seed_entries(seed)
    if set(seeds) - set(ids):
        raise IntakeError("首轮详情快照含未选取的录音。")
    output.mkdir(parents=True, exist_ok=True)
    (output / "records").mkdir(exist_ok=True)
    control = {"version": 1, "corpus_sha256": sha256(corpus_raw).hexdigest(),
               "selection_sha256": sha256(selection_raw).hexdigest(), "selected_ids": ids,
               "seed_sha256": sha256(seed.read_bytes()).hexdigest() if seed else None}
    control_path = output / "acquisition.json"
    if control_path.exists():
        if json_object(control_path) != control:
            raise IntakeError("目录或选取清单已改变；请使用新的快照目录。")
    else:
        exclusive_write(control_path, (json.dumps(control, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if (output / "manifest.json").exists():
        load_snapshots(output, corpus, selection, corpus_name=corpus_name, corpus_url=corpus_url)
        return json_object(output / "manifest.json")
    rules, robots_status = robot_rules()
    if rules and any(not rules.can_fetch(AGENT, catalog[number]["url"]) for number in ids):
        raise IntakeError("Pangloss robots.txt 不允许获取所选详情页。")
    records = []
    for number in ids:
        row = catalog[number]
        target = output / "records" / number
        if target.exists():
            receipt = json_object(target / "receipt.json")
            raw = (target / "page.html").read_bytes()
            if (receipt.get("id") != number or receipt.get("url") != row["url"]
                    or receipt.get("sha256") != sha256(raw).hexdigest()):
                raise IntakeError(f"已保存的 Pangloss 详情与收据不符：{number}")
            detail_fields(raw, row)
        else:
            if number in seeds:
                raw = (seed.parent / seeds[number]["path"]).read_bytes()
                origin = "已核验的首轮详情快照"
                observed_at = None
            else:
                raw = download_detail(row)
                origin = "馆方详情页"
                observed_at = datetime.now(timezone.utc).isoformat()
            detail_fields(raw, row)
            receipt = {"id": number, "url": row["url"], "sha256": sha256(raw).hexdigest(),
                       "origin": origin, "observed_at": observed_at}
            with TemporaryDirectory(prefix=".pangloss-", dir=output / "records") as temporary:
                stage = Path(temporary) / number
                stage.mkdir()
                (stage / "page.html").write_bytes(raw)
                (stage / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                stage.rename(target)
            if origin == "馆方详情页":
                time.sleep(delay)
        records.append({"id": number, "path": f"records/{number}/page.html", "sha256": receipt["sha256"]})
        print(f"已核验 {corpus_name} 录音 {len(records)}/{len(ids)} · {number}", flush=True)
    manifest = {**control, "robots_status": robots_status, "scope": "馆方目录及单条详情页 HTML（可能含馆方简介）；未下载音视频或转写",
                "records": records}
    exclusive_write(output / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    load_snapshots(output, corpus, selection, corpus_name=corpus_name, corpus_url=corpus_url)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        manifest = fetch(args.corpus, args.selection, args.output, args.seed, args.delay)
    except (ValueError, OSError, KeyError, TypeError, HTTPError) as error:
        print(f"Pangloss 元数据获取停止，已保存内容可在同一选取范围下续跑：{error}", file=sys.stderr)
        return 1
    print(f"已保存 {len(manifest['records'])} 条馆方录音元数据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
