"""Retrieve structural Pangloss annotation indexes without saving transcription text."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.fetch_pangloss_na import AGENT, robot_rules
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_annotations import (API, capture_selection, digest, json_object,
    parse_annotations, parse_primary, read_index, validate_selection)

MAX_RESPONSE = 12 * 1024 * 1024


def request_api(params: dict, delay: float, retries: int = 2) -> tuple[bytes, str]:
    url = API + "?" + urlencode(params)
    for attempt in range(retries + 1):
        try:
            with urlopen(Request(url, headers={"User-Agent": AGENT, "Accept-Encoding": "identity"}), timeout=30) as response:
                final = urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https" or final.netloc != "pangloss.cnrs.fr"
                        or final.path != "/api/api.php" or parse_qs(final.query) != parse_qs(urlsplit(url).query)):
                    raise IntakeError("Pangloss 接口响应或跳转不符。")
                raw = response.read(MAX_RESPONSE + 1)
                if b"SQLSTATE[" in raw and b"Connection refused" in raw:
                    raise URLError("馆方数据库暂时拒绝连接")
                if response.headers.get_content_type() != "application/json" or not raw or len(raw) > MAX_RESPONSE:
                    raise IntakeError("Pangloss 接口类型或响应大小不符。")
            time.sleep(delay)
            return raw, url
        except HTTPError as error:
            if error.code == 429:
                raise IntakeError('Pangloss 接口返回 HTTP 429；已停止请求，请遵循馆方限流后再续跑。') from error
            if error.code not in (500, 502, 503, 504):
                raise
            reason = f"HTTP {error.code}"
        except (URLError, TimeoutError, ConnectionError) as error:
            reason = str(error)
        if attempt >= retries:
            raise IntakeError(f"Pangloss 接口暂不可用：{reason}")
        wait = 10 * (attempt + 1)
        print(f"Pangloss 接口暂不可用，等待 {wait} 秒后重试。", flush=True)
        time.sleep(wait)
    raise IntakeError("Pangloss 接口获取失败。")


def collect(vault: Path, corpus: Path, chosen: Path, details: Path, output: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError("Pangloss 请求间隔至少为 2 秒。")
    output.mkdir(parents=True, exist_ok=True)
    selection_path = output / "selection.json"
    if selection_path.exists():
        selection = json_object(selection_path)
    else:
        selection = capture_selection(vault, corpus, chosen, details)
        exclusive_write(selection_path, (json.dumps(selection, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    rows = validate_selection(selection, corpus, chosen, details)
    if (output / "manifest.json").exists():
        manifest = json_object(output / "manifest.json")
        entries = manifest.get("records")
        if (manifest.get("version") != 1 or manifest.get("selection_sha256") != digest(selection_path)
                or not isinstance(entries, list) or len(entries) != len(rows)):
            raise IntakeError("已完成的分句清单与选取范围不符。")
        for row, entry in zip(rows, entries, strict=True):
            number = row["id"]
            if (not isinstance(entry, dict) or entry.get("id") != number
                    or entry.get("path") != f"record-{number}.json"):
                raise IntakeError(f"已完成的分句清单路径不符：{number}")
            path = output / entry["path"]
            if digest(path) != entry.get("sha256"):
                raise IntakeError(f"已完成的分句索引哈希不符：{number}")
            read_index(path, row)
        return manifest
    rules, robots_status = robot_rules()
    if rules and not rules.can_fetch(AGENT, API):
        raise IntakeError("Pangloss robots.txt 不允许访问元数据接口。")
    records = []
    for row in rows:
        number = row["id"]
        path = output / f"record-{number}.json"
        if path.exists():
            index = read_index(path, row)
        else:
            raw, primary_url = request_api({"action": "getresourcesByOAI", "oai": row["primary_oai"]}, delay)
            resources = parse_primary(raw, row["primary_oai"])
            responses = []
            for resource in resources:
                if resource["secondary"]:
                    params = {"action": "getAnnotations", "oais": json.dumps(resource["secondary"], ensure_ascii=False, separators=(",", ":"))}
                    annotation_raw, annotation_url = request_api(params, delay)
                    resource["annotations"] = parse_annotations(annotation_raw, resource["secondary"], resource["oai"])
                    responses.append({"resource_oai": resource["oai"], "url": annotation_url,
                                      "sha256": sha256(annotation_raw).hexdigest(), "bytes": len(annotation_raw)})
                    del annotation_raw
                else:
                    resource["annotations"] = []
            index = {"version": 1, "id": number, "primary_oai": row["primary_oai"],
                     "detail_sha256": row["detail_sha256"], "catalogue_transcription_icon": row["catalogue_transcription_icon"],
                     "primary_url": primary_url, "primary_response_sha256": sha256(raw).hexdigest(),
                     "primary_response_bytes": len(raw), "responses": responses, "resources": resources,
                     "observed_at": datetime.now(timezone.utc).isoformat(),
                     "scope": "仅资源标识、分句位置、时间及文字类型；不保留接口原响应、音视频或转写正文"}
            del raw
            encoded = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            exclusive_write(path, encoded)
            read_index(path, row)
        records.append({"id": number, "path": path.name, "sha256": digest(path)})
        annotations = sum(len(item["annotations"]) for item in index["resources"])
        segments = sum(len(annotation.get("segments", [])) for item in index["resources"] for annotation in item["annotations"])
        print(f"已登记分句 {len(records)}/{len(rows)} · {number} · 关联资源 {annotations} · 段 {segments}", flush=True)
    manifest = {"version": 1, "selection_sha256": digest(selection_path), "robots_status": robots_status,
                "scope": "本地结构索引；原始 API 响应和转写正文不保存，响应哈希不能离线重算", "records": records}
    exclusive_write(output / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--chosen", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        result = collect(args.vault.resolve(), args.corpus, args.chosen, args.details, args.output, args.delay)
    except (ValueError, OSError, KeyError, TypeError, HTTPError) as error:
        print(f"Pangloss 分句索引暂未完成；可在同一选取范围下续跑：{error}", file=sys.stderr)
        return 1
    print(f"已核验 {len(result['records'])} 个录音条目的结构索引。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
