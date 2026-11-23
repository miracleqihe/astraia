"""Fetch a bounded, resumable set of catalogue-detail fields for local research."""
import argparse
from collections import defaultdict, deque
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError

from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.fetch_sinica_oral import _json_bytes, _robots, _save_or_reuse, detail_url, parse_detail
from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.sinica_oral import load_snapshot
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

BASE = PROJECT_ROOT / ".local/import-sources/sinica-oral"


def select_targets(vault: Path, base: Path, limit: int) -> list[dict]:
    """Balance groups and catalogue pages while excluding signed or already enriched cards."""
    if not 1 <= limit <= 200:
        raise IntakeError("单次详情请求数须为 1–200。")
    _, records = load_snapshot(base)
    groups: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(deque))
    folder = vault / "00_drafts/asia_tw_sinica_oral"
    with vault_writer(vault):
        for item in records:
            if item.detail is not None:
                continue
            path = folder / f"case_tw_sinica_oral_{item.identifier}.md"
            if not path.is_file() or path.is_symlink():
                continue
            raw = path.read_bytes()
            metadata, _ = parse_card(raw.decode("utf-8-sig").replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                continue
            if any(source.type == "sinica_detail_metadata" for source in metadata.sources):
                continue
            catalogue = next((source for source in metadata.sources if source.type == "sinica_catalogue"), None)
            original = next((source for source in metadata.sources if source.type == "sinica_original"), None)
            if (metadata.id != path.stem or not catalogue or catalogue.content_sha256 != item.page_digest
                    or not original or not original.url or str(original.url) != detail_url(item.identifier)):
                raise IntakeError(f"草稿与原目录记录不一致，请先核对：{path}")
            groups[item.group][item.page].append({"id": item.identifier, "group": item.group, "page": item.page,
                "label": item.label, "catalogue_sha256": item.page_digest, "card_sha256": sha256(raw).hexdigest()})
    # Interleave pages inside each group, then round-robin groups. This is not a random sample.
    ordered: dict[int, deque] = {}
    for group, pages in groups.items():
        queue = deque()
        while any(pages.values()):
            for page in sorted(pages):
                if pages[page]:
                    queue.append(pages[page].popleft())
        ordered[group] = queue
    selected = []
    while len(selected) < limit and any(ordered.values()):
        for group in sorted(ordered):
            if ordered[group] and len(selected) < limit:
                selected.append(ordered[group].popleft())
    return selected


def validate_selection(selection: dict, base: Path) -> list[dict]:
    manifest, records = load_snapshot(base)
    index = {item.identifier: item for item in records}
    if (not isinstance(selection, dict) or selection.get("version") != 1
            or selection.get("base_manifest_sha256") != sha256((base / "manifest.json").read_bytes()).hexdigest()
            or not isinstance(selection.get("entries"), list) or not selection["entries"]
            or len(selection["entries"]) > 200):
        raise IntakeError("详情补充的选取清单或基础目录哈希不符。")
    seen = set()
    for row in selection["entries"]:
        identifier = row.get("id") if isinstance(row, dict) else None
        if type(identifier) is not int or identifier in seen or identifier not in index:
            raise IntakeError("详情补充选取清单含重复或无效编号。")
        seen.add(identifier)
        item = index[identifier]
        if ((row.get("group"), row.get("page"), row.get("label"), row.get("catalogue_sha256"))
                != (item.group, item.page, item.label, item.page_digest)
                or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("card_sha256", "")))):
            raise IntakeError(f"详情补充选取与原目录不符：{identifier}")
    return selection["entries"]


def fetch(vault: Path, base: Path, output: Path, *, limit: int = 120, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError("详情补充请求间隔至少为 2 秒。")
    vault, base = vault.resolve(strict=True), base.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise IntakeError("此目录已有完整详情补充清单；请使用新目录。")
    selection_path = output / "selection.json"
    if selection_path.exists():
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    else:
        selected = select_targets(vault, base, limit)
        if not selected:
            raise IntakeError("没有可补充详情的待审条目。")
        selection = {"version": 1, "base_manifest_sha256": sha256((base / "manifest.json").read_bytes()).hexdigest(),
                     "sampling": "按馆藏组与分页轮流选取；非随机或代表性样本", "entries": selected}
        exclusive_write(selection_path, _json_bytes(selection))
    entries = validate_selection(selection, base)
    robots, status = _robots(delay)
    results = []
    for row in entries:
        identifier = row["id"]
        url = detail_url(identifier)
        path = output / f"detail-{identifier}.json"
        value = _save_or_reuse(path, url, lambda raw: parse_detail(raw, identifier), robots, delay)
        if value.get("id") != identifier or value.get("rights_notice_present") is not True or not isinstance(value.get("fields"), dict):
            raise IntakeError(f"馆方详情字段快照不符：{path}")
        results.append({"id": identifier, "path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()})
        print(f"已保存详情字段 {len(results)}/{len(entries)} · {identifier}", flush=True)
    manifest = {"version": 1, "selection_sha256": sha256(selection_path.read_bytes()).hexdigest(),
                "base_manifest_sha256": selection["base_manifest_sha256"], "robots_status": status,
                "scope": "仅本地研究目录字段；不保存译文、录音或完整网页；未经同意不得摘取内容出版",
                "records": results}
    exclusive_write(output / "manifest.json", _json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        result = fetch(args.vault, args.base, args.output, limit=args.limit, delay=args.delay)
    except (ValueError, OSError, HTTPError, URLError) as error:
        print(f"详情获取未完成；已有快照与选取清单保留，未覆盖。{error}", file=sys.stderr)
        return 1
    print(f"详情补充索引完成：{len(result['records'])} 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
