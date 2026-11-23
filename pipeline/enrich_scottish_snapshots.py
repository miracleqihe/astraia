"""Add existing, hash-matched Scottish source snapshot paths to pending cards."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT
from pipeline.scottish_witchcraft import DATASET_URL, MAP_URL, snapshot_path
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def add_paths(text: str, metadata, sources: dict[tuple[str, str], tuple[str, str]]) -> tuple[str, int]:
    # Work inside the top-level source list only, keeping body and manual YAML comments intact.
    match = re.search(r"(?ms)^sources:[ \t]*\r?\n(?P<items>.*?)(?=^[A-Za-z_][A-Za-z_0-9]*:|\Z)", text)
    if not match:
        raise ValueError(f"草稿缺少 sources 区块。{metadata.id}")
    items = match.group("items")
    chunks = re.split(r"(?=^- citation:)", items, flags=re.M)
    source_chunks = [index for index, chunk in enumerate(chunks) if chunk.startswith("- citation:")]
    if len(source_chunks) != len(metadata.sources):
        raise ValueError(f"草稿来源格式已修改，保留原文，请人工检查。{metadata.id}")
    added = 0
    for index, source in zip(source_chunks, metadata.sources, strict=True):
        definition = sources.get((source.type, str(source.url) if source.url else ""))
        if not definition or source.local_path is not None:
            continue
        expected_hash, local_path = definition
        if source.content_sha256 != expected_hash:
            raise ValueError(f"草稿来源哈希与待关联的本地快照不一致。{metadata.id}")
        chunk = chunks[index]
        path_line = f"  local_path: {json.dumps(local_path, ensure_ascii=False)}"
        if re.search(r"(?m)^  local_path:[ \t]*null[ \t]*(?:#.*)?\r?$", chunk):
            chunk, count = re.subn(r"(?m)^  local_path:[ \t]*null(?=[ \t]*(?:#.*)?\r?$)", path_line, chunk, count=1)
        elif not re.search(r"(?m)^  local_path:", chunk):
            chunk, count = re.subn(r"(?m)^(  content_sha256:)", path_line + "\n" + r"\1", chunk, count=1)
        else:
            raise ValueError(f"草稿本地路径格式需要人工核对。{metadata.id}")
        if count != 1:
            raise ValueError(f"草稿缺少可定位的来源哈希。{metadata.id}")
        chunks[index] = chunk
        added += 1
    return text[:match.start("items")] + "".join(chunks) + text[match.end("items"):], added


def enrich(vault: Path, tables: Path, maps: Path, *, check: bool = False) -> dict:
    definitions = {
        ("scholarly_database", DATASET_URL): (digest(tables), snapshot_path(tables)),
        ("gazetteer", MAP_URL): (digest(maps), snapshot_path(maps)),
    }
    folder = vault / "00_drafts/scottish_witchcraft"
    plans = []
    with vault_writer(vault):
        for path in sorted(folder.glob("*.md")):
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, _ = parse_card(text.replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                continue
            revised, count = add_paths(text, metadata, definitions)
            if count:
                encoded = revised.encode("utf-8")
                if raw.startswith(b"\xef\xbb\xbf"):
                    encoded = b"\xef\xbb\xbf" + encoded
                plans.append((path, raw, encoded, count))
        if not check:
            for path, original, revised, _ in plans:
                with NamedTemporaryFile(dir=path.parent, prefix=".source-snapshot-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise ValueError(f"草稿在更新来源路径时发生变化。{path}")
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
    return {"cards": len(plans), "snapshot_paths": sum(item[3] for item in plans), "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--tables", type=Path, default=PROJECT_ROOT / ".local/import-sources/scottish-witches-tables.zip")
    parser.add_argument("--maps", type=Path, default=PROJECT_ROOT / ".local/import-sources/scottish-witches-maps.zip")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(enrich(args.vault.resolve(), args.tables.resolve(), args.maps.resolve(), check=args.check),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
