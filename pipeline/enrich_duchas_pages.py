"""Attach cached continuation-page citations to existing pending Dúchas cards."""

import argparse
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
from xml.etree import ElementTree

from pipeline.duchas import CORPUS, INDEX, cited_story_ids, duchas_cards
from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT
from pipeline.source_frontmatter import append_relations, append_sources
from pipeline.vault import load_vault, parse_card
from pipeline.vault_write import vault_writer

MARKER = "<!-- astraia:duchas-multipage-sources-v1 -->"


def enrich(vault: Path, snapshots: Path, *, check: bool = False) -> dict:
    folder = vault / "00_drafts"
    candidates = sorted(path for directory in folder.glob("duchas_*") if directory.is_dir()
                        for path in directory.glob("*.md"))
    candidates.extend(sorted((folder / "regional_sources").glob("*.md")))
    plans, missing = [], {}
    added_count = relation_count = 0
    with vault_writer(vault):
        existing_ids = set(load_vault(vault)) | {path.stem for path in folder.rglob("*.md")}
        missing_groups = sorted({CORPUS, INDEX} - existing_ids)
        for path in candidates:
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            metadata, _ = parse_card(text.replace("\r\n", "\n"))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                continue
            story_ids = cited_story_ids(metadata)
            if len(story_ids) != 1:
                continue
            story_id = next(iter(story_ids))
            matches = sorted(snapshots.glob(f"story-*-*-{story_id}.xml"))
            if not matches:
                continue
            if len(matches) != 1:
                raise ValueError(f"故事有多个本地故事快照，请先选择对应版本。{story_id}")
            story_path = matches[0]
            root = ElementTree.fromstring(story_path.read_bytes())
            expected_pages = [item.get("default") for item in root.findall("page")]
            generated, _ = next(duchas_cards([story_path], include_groups=False))
            if generated.id != f"case_duchas_{story_id}":
                raise ValueError(f"故事快照与档号不一致。{story_path}")
            generated_story = next(source for source in generated.sources if source.locator == f"故事 XML {story_id}")
            existing_stories = [source for source in metadata.sources if source.local_path and source.content_sha256
                                and source.url and re.fullmatch(rf"/xml/cbes/\d+/\d+/{story_id}/?", urlsplit(str(source.url)).path)]
            if existing_stories and any(source.content_sha256 != generated_story.content_sha256 for source in existing_stories):
                raise ValueError(f"卡片引用的故事快照与待补页面的版本不一致。{path}")
            existing_pages = {str(source.url): source for source in metadata.sources if source.url}
            additions = []
            page_sources = [source for source in generated.sources if source.type == "primary_archive"
                            and source.local_path and source.locator and source.locator.startswith("馆藏页 ")]
            for source in page_sources:
                previous = existing_pages.get(str(source.url))
                if previous and previous.content_sha256 and previous.content_sha256 != source.content_sha256:
                    raise ValueError(f"卡片已有的页面快照与新快照哈希不一致。{path}")
                if previous is None or not previous.local_path or not previous.content_sha256:
                    additions.append(source)
            existing_relations = {(relation.type, relation.target) for relation in metadata.relations}
            relations = [relation for relation in generated.relations
                         if not missing_groups and relation.target in {CORPUS, INDEX}
                         and (relation.type, relation.target) not in existing_relations]
            available_ids = {re.search(r"馆藏页 (\d+)", source.locator)[1] for source in page_sources}
            remaining = sorted(set(expected_pages) - available_ids)
            if remaining:
                missing[story_id] = remaining
            if not additions and not relations:
                continue
            revised = append_relations(append_sources(text, additions), relations)
            if additions and len(expected_pages) > 1 and MARKER not in revised:
                revised += ("\n" + MARKER + "\n## 跨页出处\n\n本故事跨多个馆藏页；已保存的各页列在出处，"
                            "具体文字与手稿可通过馆藏链接核查。\n")
            encoded = revised.encode("utf-8")
            if raw.startswith(b"\xef\xbb\xbf"):
                encoded = b"\xef\xbb\xbf" + encoded
            plans.append((path, raw, encoded))
            added_count += len(additions)
            relation_count += len(relations)
        if not check:
            for path, original, revised in plans:
                with NamedTemporaryFile(dir=path.parent, prefix=".duchas-pages-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise ValueError(f"草稿在补充跨页来源时发生变化。{path}")
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
    return {"cards": len(plans), "additional_page_sources": added_count, "additional_relations": relation_count,
            "uncached_pages": missing, "missing_groups": missing_groups, "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--snapshots", type=Path, default=PROJECT_ROOT / ".local/import-sources/duchas")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(enrich(args.vault.resolve(), args.snapshots.resolve(), check=args.check), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
