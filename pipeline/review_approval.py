"""Publish only cards explicitly approved in an exported human-review record."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import get_args
from zipfile import BadZipFile

import yaml
from pipeline.build_graph import DEFAULT_OUTPUTS
from pipeline.ingest_agent import DEFAULT_CODE_TABLE, DEFAULT_VAULT, DRAFT_DIRECTORY, approve, export_policy
from pipeline.local_standards import load_code_table
from pipeline.node_model import Genre
from pipeline.vault import load_vault, parse_card


def load_decisions(path: Path) -> dict[str, dict]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("decisions"), list):
        raise ValueError("复核记录格式不正确。")
    result = {}
    for entry in document["decisions"]:
        if not isinstance(entry, dict) or entry.get("status") not in {"reviewed", "correction"}:
            raise ValueError("复核记录中的状态不正确。")
        card_id, digest = entry.get("id"), entry.get("card_sha256")
        if not isinstance(card_id, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", card_id):
            raise ValueError("复核记录中的卡片 ID 不正确。")
        if card_id in result or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError(f"复核记录的卡片重复或哈希无效。{card_id}")
        reviewer, note, reviewed_at = entry.get("reviewer"), entry.get("note", ""), entry.get("reviewed_at")
        genre = entry.get("genre")
        if genre is not None and (not isinstance(genre, str) or genre not in get_args(Genre) or genre == "unclassified"):
            raise ValueError(f"复核记录中的体裁无效。{card_id}")
        if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(note, str) or not isinstance(reviewed_at, str):
            raise ValueError(f"复核记录缺少复核人、备注或时间。{card_id}")
        timestamp = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        if timestamp.utcoffset() is None:
            raise ValueError(f"复核时间缺少时区。{card_id}")
        result[card_id] = {"id": card_id, "card_sha256": digest, "status": entry["status"],
                           "reviewer": reviewer.strip(), "note": note, "reviewed_at": reviewed_at, "genre": genre}
    return result


def prepare_selection(vault: Path, decisions: dict[str, dict], include_samples: bool) -> tuple[list[Path], dict[str, list[str]]]:
    queue = vault / DRAFT_DIRECTORY
    pending = {}
    for path in queue.rglob("*.md"):
        if path.stem in pending:
            raise ValueError(f"存在同名草稿，不能定位复核记录。{path.stem}")
        pending[path.stem] = path
    published = {node_id for node_id, card in load_vault(vault).items()
                 if card.metadata.audit.reviewed_by_human or (include_samples and card.metadata.audit.is_sample)}
    candidates = {}
    for card_id, decision in decisions.items():
        if decision["status"] != "reviewed" or card_id in published:
            continue
        path = pending.get(card_id)
        if path is None:
            raise ValueError(f"复核通过的草稿不存在。{card_id}")
        original = path.read_bytes()
        if sha256(original).hexdigest() != decision["card_sha256"]:
            raise ValueError(f"草稿在复核后发生变化，请重新复核。{card_id}")
        metadata, _ = parse_card(original.decode("utf-8-sig").replace("\r\n", "\n"))
        if metadata.id != card_id or metadata.audit.reviewed_by_human or metadata.audit.is_sample:
            raise ValueError(f"草稿 ID 或复核状态不正确。{card_id}")
        dependencies = {relation.target for relation in metadata.relations}
        dependencies.update(mechanism.target_id for mechanism in metadata.mechanisms)
        candidates[card_id] = (path, dependencies)
    blocked = {}
    while True:
        missing = {card_id: sorted(dependencies - published - candidates.keys())
                   for card_id, (_, dependencies) in candidates.items()
                   if dependencies - published - candidates.keys()}
        if not missing:
            break
        blocked.update(missing)
        for card_id in missing:
            del candidates[card_id]
    return [candidates[card_id][0] for card_id in sorted(candidates)], blocked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decisions", type=Path, help="复核页面导出的 JSON")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--code-table", type=Path, default=DEFAULT_CODE_TABLE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="预检可签核的卡片与依赖")
    args = parser.parse_args()
    try:
        args.vault = args.vault.resolve()
        args.command = "approve-reviewed"
        args.genre = None
        args.tier = None
        args.include_samples = None
        args.exclude_fiction = None
        args.review_decisions = load_decisions(args.decisions)
        output = args.output or (DEFAULT_OUTPUTS["json"] if args.vault == DEFAULT_VAULT.resolve()
                                 else args.vault.parent / ".local" / "graph_data.json")
        policy = export_policy(output, args)
        paths, blocked = prepare_selection(args.vault, args.review_decisions, policy["include_samples"])
        print(f"复核通过且依赖齐全 {len(paths)} 张，等待关联卡片复核 {len(blocked)} 张。")
        for card_id, dependencies in sorted(blocked.items()):
            shown = "、".join(dependencies[:8])
            suffix = f"等 {len(dependencies)} 张" if len(dependencies) > 8 else ""
            print(f"{card_id} 依赖 {shown}{suffix}")
        if not paths:
            return 0
        result = approve(args, args.vault, load_code_table(args.code_table), selected_paths=paths)
        if result == 0 and not args.check and args.vault == DEFAULT_VAULT.resolve():
            from pipeline.review_queue import (
                DEFAULT_CATALOGUE, DEFAULT_MAPS, DEFAULT_OUTPUT, DEFAULT_SCHEMA, DEFAULT_STUDY,
                DEFAULT_TABLES, export,
            )
            try:
                summary = export(args.vault, DEFAULT_OUTPUT, DEFAULT_TABLES, DEFAULT_SCHEMA, DEFAULT_MAPS,
                                 DEFAULT_STUDY, DEFAULT_CATALOGUE, args.code_table)
                print(f"复核清单已更新，当前还有 {summary['records']} 张待审卡片。")
            except (OSError, ValueError, BadZipFile, yaml.YAMLError) as error:
                print(f"卡片已签核，复核清单更新待处理。{error}", file=sys.stderr)
        return result
    except (ValueError, OSError) as error:
        print(f"复核签核未完成\n{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
