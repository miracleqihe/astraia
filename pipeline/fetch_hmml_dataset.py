"""Download HMML's published CC BY 4.0 Reading Room metadata dataset once."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from zipfile import BadZipFile, ZipFile

from pipeline.intake_sources import IntakeError

DATASET_URL = "https://www.vhmml.org/datasets/vhmml_rr_fulldata.zip"
DATASET_PAGE = "https://www.vhmml.org/dataPortal/dataset"
TERMS = "https://www.vhmml.org/terms"
ROBOTS_URL = "https://www.vhmml.org/robots.txt"
USER_AGENT = "AstraiaResearchIndex/1.0 (local attribution-preserving metadata intake)"
MAX_BYTES = 150 * 1024 * 1024


def fetch(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    archive, manifest = output / "vhmml_rr_fulldata.zip", output / "manifest.json"
    if archive.exists() or manifest.exists():
        raise IntakeError("目标已有馆藏文件或清单；请另建目录，不覆盖现有快照。")
    request = Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise IntakeError("无法核实馆方 robots.txt，已停止。")
        robots = response.read(64 * 1024).decode("utf-8", "strict")
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(robots.splitlines())
    if not parser.can_fetch(USER_AGENT, DATASET_URL):
        raise IntakeError("馆方 robots.txt 不允许获取此数据导出。")
    with TemporaryDirectory(prefix=".astraia-hmml-", dir=output) as temporary:
        staged = Path(temporary) / archive.name
        digest, total = sha256(), 0
        request = Request(DATASET_URL, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        with urlopen(request, timeout=45) as response, staged.open("wb") as stream:
            if response.status != 200 or urlsplit(response.geturl()).netloc != "www.vhmml.org":
                raise IntakeError("馆方数据导出响应或域名不符。")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_BYTES:
                raise IntakeError("馆方数据导出超过允许大小。")
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise IntakeError("馆方数据导出超过允许大小。")
                digest.update(chunk)
                stream.write(chunk)
            if not total or (declared and total != int(declared)):
                raise IntakeError("馆方数据导出不完整。")
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
        with ZipFile(staged) as zipped:
            entries = [{"name": info.filename, "bytes": info.file_size} for info in zipped.infolist() if not info.is_dir()]
            if len(entries) != 1 or not entries[0]["name"].lower().endswith((".json", ".jsonl", ".ndjson")):
                raise IntakeError("馆方 ZIP 内的文件结构与预期不符。")
        info = {"version": 1, "source_url": DATASET_URL, "dataset_page": DATASET_PAGE,
                "terms": TERMS, "metadata_license": "CC BY 4.0", "archive": archive.name,
                "sha256": digest.hexdigest(), "bytes": total, "entries": entries,
                "retrieved_at": datetime.now(timezone.utc).isoformat(), "etag": etag, "last_modified": last_modified,
                "scope": "馆方元数据导出；未获取、复制或转录手稿图像"}
        manifest_staged = Path(temporary) / manifest.name
        manifest_staged.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            os.link(staged, archive)
            os.link(manifest_staged, manifest)
        except FileExistsError as error:
            raise IntakeError("目标文件已出现，未覆盖。") from error
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        info = fetch(args.output)
    except (IntakeError, OSError, ValueError, UnicodeError, BadZipFile) as error:
        print(f"馆方元数据获取未完成：{error}", file=sys.stderr)
        return 1
    print(f"已保存 {info['bytes']} 字节馆藏元数据；SHA-256 {info['sha256']}。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
