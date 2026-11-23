"""Reuse matching catalogue snapshots while rechecking titles with visible annotations."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from pipeline.build_graph import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.vietnam_cham import load_snapshot


def prepare(base: Path, output: Path) -> dict:
    base = base.resolve(strict=True)
    manifest, _, stories = load_snapshot(base)
    output = output.resolve()
    if output.exists():
        raise IntakeError(f"修订目录已存在，未覆盖：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    refetch = [story.number for story in stories if story.catalogue_title != story.detail_title]
    if not refetch:
        raise IntakeError("原目录没有待重查的标题差异。")
    reused = []
    with TemporaryDirectory(prefix=".cham-revision-", dir=output.parent) as temporary:
        stage = Path(temporary) / "revision"
        stage.mkdir()
        catalogue = base / "catalogue.json"
        (stage / "catalogue.json").write_bytes(catalogue.read_bytes())
        for item in stories:
            if item.number in refetch:
                continue
            destination = stage / item.snapshot.name
            destination.write_bytes(item.snapshot.read_bytes())
            reused.append({"number": item.number, "sha256": item.digest})
        seed = {"version": 1, "base_manifest_path": display_path(base / "manifest.json"),
                "base_manifest_sha256": sha256((base / "manifest.json").read_bytes()).hexdigest(),
                "catalogue_sha256": manifest["catalogue_sha256"], "reused": reused, "refetch": refetch,
                "scope": "原快照保留；仅重查标题存在可见差异的页面"}
        (stage / "seed.json").write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)
    return seed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=PROJECT_ROOT / ".local/import-sources/vietnam-cham-folktales")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        seed = prepare(args.base, args.output)
    except (OSError, ValueError) as error:
        print(f"越南目录修订准备未完成：{error}", file=sys.stderr)
        return 1
    print(json.dumps({"reused": len(seed["reused"]), "refetch": seed["refetch"],
                      "base_manifest_sha256": seed["base_manifest_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
