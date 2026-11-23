"""Add original archival reference pointers to the existing Scottish drafts."""

import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from pipeline.ingest_agent import DEFAULT_VAULT, serialize_card
from pipeline.node_model import Source
from pipeline.scottish_witchcraft import _archive_table, _identifier, historical_reference
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer


def enrich(vault: Path, archive_path: Path, schema_path: Path, *, check: bool = False) -> tuple[int, int]:
    digest = sha256(archive_path.read_bytes()).hexdigest()
    schema = schema_path.read_text(encoding="utf-8-sig")
    with ZipFile(archive_path) as archive:
        accused = _archive_table(archive, schema, "Accused")
        cases = _archive_table(archive, schema, "Case")
        references = _archive_table(archive, schema, "Reference")
    by_accused, by_case = defaultdict(list), defaultdict(list)
    accused_refs = {row["AccusedRef"] for row in accused}
    for case in cases:
        by_accused[case["AccusedRef"]].append(case)
    for reference in references:
        by_case[reference["CaseRef"]].append(reference)

    folder = vault / "00_drafts" / "scottish_witchcraft"
    plans = []
    for accused_row, source_cases in [*((row, by_accused[row["AccusedRef"]]) for row in accused),
                                      *(({}, [case]) for case in cases if case["AccusedRef"] not in accused_refs)]:
        reference = accused_row.get("AccusedRef") or source_cases[0]["CaseRef"]
        path = folder / f"{_identifier(reference)}.md"
        if not path.exists():
            continue
        original = path.read_bytes()
        metadata, body = parse_card(original.decode("utf-8-sig").replace("\r\n", "\n"))
        if metadata.audit.reviewed_by_human or not metadata.sources or metadata.sources[0].content_sha256 != digest:
            raise ValueError(f"草稿的复核状态或来源哈希不匹配。{path}")
        known = {source.locator for source in metadata.sources if source.type == "historical_reference"}
        additions = [Source.model_validate(historical_reference(row, digest))
                     for case in source_cases for row in by_case[case["CaseRef"]]
                     if historical_reference(row, digest)["locator"] not in known]
        if additions:
            metadata.sources.extend(additions)
            plans.append((path, original, serialize_card(metadata, body), len(additions)))

    if not check:
        with vault_writer(vault), TemporaryDirectory(prefix=".astraia-references-", dir=folder) as temporary:
            for index, (path, original, new, _) in enumerate(plans):
                if path.read_bytes() != original:
                    raise ValueError(f"草稿已修改，请重新执行。{path}")
                staged = Path(temporary) / f"{index}.tmp"
                staged.write_bytes(new)
                staged.replace(path)
    return len(plans), sum(item[3] for item in plans)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--tables", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed, added = enrich(args.vault, args.tables, args.schema, check=args.check)
    print(f"{'可补充' if args.check else '已补充'} {changed} 张草稿、{added} 条调查库登记的史料线索。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
