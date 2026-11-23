"""Cache a dated Wikidata P4478 identifier snapshot for Scottish record linkage."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pipeline.ingest_agent import PROJECT_ROOT

ENDPOINT = "https://query.wikidata.org/sparql"
QUERY = "SELECT ?item ?survey WHERE { ?item wdt:P4478 ?survey. }"
DEFAULT_OUTPUT = PROJECT_ROOT / ".local/import-sources/wikidata-scottish-p4478.json"


def parse_snapshot(raw: bytes) -> list[tuple[str, str]]:
    document = json.loads(raw.decode("utf-8"))
    if document.get("head", {}).get("vars") != ["item", "survey"]:
        raise ValueError("Wikidata 查询结果的字段不符合预期。")
    results = document.get("results", {}).get("bindings")
    if not isinstance(results, list) or not results:
        raise ValueError("Wikidata 查询结果为空。")
    parsed = []
    for row in results:
        item, survey = row.get("item", {}), row.get("survey", {})
        url, identifier = item.get("value", ""), survey.get("value", "")
        if (item.get("type") != "uri" or survey.get("type") not in {"literal", "typed-literal"}
                or not re.fullmatch(r"https?://www\.wikidata\.org/entity/Q[1-9]\d*", url)
                or not re.fullmatch(r"A/[A-Z]+/\d+", identifier)):
            raise ValueError(f"Wikidata 查询结果包含无效的实体或被告档号。{url} / {identifier}")
        parsed.append((url.rsplit("/", 1)[-1], identifier))
    return parsed


def fetch(output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"已保留已有快照。如需重新获取，请指定新文件名。{output}")
    url = ENDPOINT + "?" + urlencode({"query": QUERY, "format": "json"})
    request = Request(url, headers={"User-Agent": "Astraia research project/1.0 (local evidence audit)",
                                   "Accept": "application/sparql-results+json"})
    with urlopen(request, timeout=60) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Wikidata 查询结果超出预期大小。")
    records = parse_snapshot(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(raw)
    manifest = {"endpoint": ENDPOINT, "query": QUERY, "property": "P4478", "license": "CC0 1.0",
                "retrieved_at": datetime.now(timezone.utc).isoformat(), "sha256": sha256(raw).hexdigest(),
                "bindings": len(records), "distinct_pairs": len(set(records))}
    manifest_path = output.with_suffix(".manifest.json")
    try:
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError:
        output.unlink(missing_ok=True)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(fetch(args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
