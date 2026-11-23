"""本地资料入库。抽取可定位的证据，人工签核后发布图谱。"""

import argparse
from contextlib import nullcontext
from datetime import date
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from typing import get_args
from zipfile import BadZipFile

import yaml

from pipeline.build_graph import DEFAULT_OUTPUTS, PROJECT_ROOT, compile_cards
from pipeline.graph_links import standard_codes
from pipeline.graph_output import publish_graph
from pipeline.intake_sources import IntakeError, Material, Passage, one_line, read_material
from pipeline.local_standards import (
    SYSTEMS, CodeEntry, CodeMatch, UnmatchedCode, load_code_table, match_codes, normalized_text, phrase_pattern,
    unmatched_explicit_codes, verify_codes,
)
from pipeline.node_model import CredibilityTier, Genre, LAYER_BY_TYPE, NodeMetadata, NodeType, Standards
from pipeline.public_fingerprint import public_content_sha256
from pipeline.vault import VaultCard, card_directory, load_vault, parse_card
from pipeline.vault_write import create_card, vault_writer

DEFAULT_VAULT = PROJECT_ROOT / "vault"
DEFAULT_CODE_TABLE = PROJECT_ROOT / "reference" / "standards.json"
DRAFT_DIRECTORY = "00_drafts"


def literal_block(text: str) -> str:
    run = max((len(sequence) for sequence in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, run + 1)
    return f"{fence}\n{text}\n{fence}"


def serialize_card(metadata: NodeMetadata, body: str) -> bytes:
    frontmatter = yaml.safe_dump(metadata.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
    return f"---\n{frontmatter}---\n{body}".encode("utf-8")


def select_passages(material: Material, matches: list[CodeMatch], unmatched: list[UnmatchedCode]) -> list[Passage]:
    by_locator = {part.locator: part for part in material.passages}
    locators = dict.fromkeys([material.passages[0].locator, *(match.locator for match in matches),
                              *(item.locator for item in unmatched), *by_locator])
    return [by_locator[locator] for locator in locators if locator in by_locator][:5]


def excerpt(part: Passage, matches: list[CodeMatch]) -> str:
    limit = 1200
    if len(part.text) <= limit:
        return part.text
    matching_terms = [match.term for match in matches if match.locator == part.locator]
    offset = next((hit.start() for term in matching_terms
                   if (hit := re.search(re.escape(term), part.text, re.IGNORECASE))), 0)
    start = max(0, offset - 350)
    end = min(len(part.text), start + limit)
    return ("[…]\n" if start else "") + part.text[start:end] + ("\n[…]" if end < len(part.text) else "")


def related_mentions(material: Material, standards: Standards, cards: dict[str, VaultCard], fiction: bool) -> list[str]:
    text = normalized_text(" ".join(part.text for part in material.passages))
    source_codes = set(standard_codes(standards))
    suggestions = []
    for card in cards.values():
        node = card.metadata
        if node.is_fictional_quarantine != fiction or not (node.audit.reviewed_by_human or node.audit.is_sample):
            continue
        overlap = source_codes.intersection(standard_codes(node.standards))
        names = (name for name in (node.title, *node.aliases) if len(name) >= 4)
        reason = "共用本地标引" if overlap else "正文出现名称" if any(re.search(phrase_pattern(name), text) for name in names) else ""
        if not reason:
            continue
        if node.node_type in {"mechanism", "theory"}:
            reason += "，解释状态待复核"
        if node.audit.is_sample and not node.audit.reviewed_by_human:
            reason += "，样例"
        suggestions.append(f"- `{node.id}` · {node.title}（{reason}）")
    return suggestions[:5]


def draft_body(material: Material, passages: list[Passage], matches: list[CodeMatch],
               unmatched: list[UnmatchedCode], mentions: list[str]) -> str:
    body = ["", "## 原文摘录", ""]
    for part in passages:
        body.extend([f"**{part.locator}**", "", literal_block(excerpt(part, matches)), ""])
    if len(passages) < len(material.passages):
        body.extend([f"共定位到 {len(material.passages)} 个原文单元，此处摘录 {len(passages)} 个。", ""])

    body.extend(["## 本地标引依据", ""])
    for match in matches:
        entry = match.entry
        body.append(f"- {SYSTEMS[entry.system][0]} `{entry.code}` · {entry.label}。{match.locator}命中「{match.term}」。"
                    f"[码表出处]({entry.url})")
    if not matches:
        body.append("本地码表没有精确命中，标准码字段留空。")

    if unmatched:
        body.extend(["", "## 未匹配的原文编码", ""])
        for item in unmatched:
            body.append(f"- {SYSTEMS[item.system][0]} `{item.code}` · {item.locator}：本地码表未登记，字段留空。")

    body.extend(["", "## 复核线索", "", "- 请核对体裁、信源和引用范围，并在有依据时填写时间、地点与解释状态。"])
    body.extend(f"- {note}" for note in material.notes)
    if mentions:
        body.extend(["", "### 现有节点线索", "", *mentions])
    return "\n".join(body) + "\n"


def cache_material(material: Material, vault: Path) -> str:
    """Persist the exact bytes of remote or inline input without replacing an existing snapshot."""
    raw = material.raw_bytes
    if sha256(raw).hexdigest() != material.content_sha256:
        raise IntakeError("来源内容与计算出的哈希不一致，无法保存快照。")
    suffix = {"pdf": ".pdf", "web_page": ".html", "plain_text": ".txt"}.get(material.source_type, ".bin")
    folder = vault.parent / ".local" / "intake-sources"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{material.content_sha256}{suffix}"
    if not target.exists():
        with TemporaryDirectory(prefix=".astraia-source-", dir=folder) as temporary:
            staged = Path(temporary) / "source"
            staged.write_bytes(raw)
            try:
                os.link(staged, target)
            except FileExistsError:
                pass
    with target.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != material.content_sha256:
            raise IntakeError(f"同名来源快照内容不一致，已保留原文件。{target}")
    resolved = target.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def draft(args: argparse.Namespace, vault: Path, table: dict[tuple[str, str], CodeEntry]) -> int:
    if args.source is not None and args.text is not None:
        raise IntakeError("请在位置参数和 --text 中任选一种输入。")
    material = read_material(args.source, args.text, args.encoding, sys.stdin.buffer)
    matches = match_codes(table, material.passages)
    unmatched = unmatched_explicit_codes(table, material.passages)
    codes = {system: [] for system in SYSTEMS}
    for match in matches:
        codes[match.entry.system].append(match.entry.code)
    genre = args.genre or ("creepypasta_ostension" if args.tier == "F" else "unclassified")
    tier = args.tier or ("F" if genre == "creepypasta_ostension" else "B")
    passages = select_passages(material, matches, unmatched)
    metadata = NodeMetadata.model_validate({
        "id": args.id or f"intake_{material.content_sha256[:16]}",
        "title": one_line(args.title or material.title),
        "node_type": args.node_type,
        "z_layer": LAYER_BY_TYPE[args.node_type],
        "genre": genre,
        "credibility_tier": tier,
        "is_fictional_quarantine": tier == "F",
        "spatial": None,
        "temporal": None,
        "standards": codes,
        "sources": [{
            "citation": one_line(args.citation or material.citation),
            "type": material.source_type,
            "url": material.url or args.source_url,
            "doi": args.doi or material.doi,
            "locator": "、".join(part.locator for part in passages),
            "local_path": material.local_path,
            "content_sha256": material.content_sha256,
        }],
        "audit": {"created_at": date.today(), "reviewed_by_human": False},
    })
    with vault_writer(vault):
        cards = load_vault(vault)
        if metadata.id in cards:
            raise IntakeError(f"知识库已收录 {metadata.id}。请使用不同 ID 创建单独的卡片。")
        queue = vault / DRAFT_DIRECTORY
        if any(queue.rglob(f"{metadata.id}.md")):
            raise IntakeError(f"待审目录已存在 {metadata.id}。请使用不同 ID。")
        if material.local_path is None:
            metadata.sources[0].local_path = cache_material(material, vault)
        mentions = related_mentions(material, metadata.standards, cards, metadata.is_fictional_quarantine)
        path = vault / DRAFT_DIRECTORY / f"{metadata.id}.md"
        create_card(path, serialize_card(metadata, draft_body(material, passages, matches, unmatched, mentions)))
    print(f"已生成待审草稿 {path}", flush=True)
    print(f"本地码表命中 {len(matches)} 条。", flush=True)
    if unmatched:
        print(f"原文有 {len(unmatched)} 个未匹配编码，已留空并标记待核。")
    if vault == DEFAULT_VAULT.resolve():
        from pipeline.review_queue import (
            DEFAULT_CATALOGUE, DEFAULT_MAPS, DEFAULT_OUTPUT, DEFAULT_SCHEMA, DEFAULT_STUDY, DEFAULT_TABLES, export,
        )
        print("正在更新复核清单……", flush=True)
        try:
            summary = export(vault, DEFAULT_OUTPUT, DEFAULT_TABLES, DEFAULT_SCHEMA, DEFAULT_MAPS,
                             DEFAULT_STUDY, DEFAULT_CATALOGUE, args.code_table)
            print(f"复核清单已更新，当前 {summary['records']} 张待审卡片。")
        except (OSError, ValueError, BadZipFile, yaml.YAMLError) as error:
            print(f"草稿已保存，但复核清单未更新；请检查来源文件后运行 pipeline.review_queue。{error}", file=sys.stderr)
    return 0


def draft_path(vault: Path, value: str) -> Path:
    queue = (vault / DRAFT_DIRECTORY).resolve()
    argument = Path(value)
    if argument.parent == Path("."):
        name = argument.name if argument.suffix == ".md" else f"{argument.name}.md"
        argument = queue / name
        if not argument.is_file():
            matches = list(queue.rglob(name))
            if len(matches) > 1:
                raise IntakeError("存在多张同名草稿，请指定完整的文件路径。")
            if matches:
                argument = matches[0]
    path = argument.resolve()
    if not path.is_relative_to(queue) or path.suffix != ".md":
        raise IntakeError(f"请从 {queue} 选择一张草稿。")
    return path


def export_policy(output: Path, args: argparse.Namespace) -> dict[str, bool]:
    current = {}
    if output.is_file():
        try:
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            if isinstance(snapshot, dict) and isinstance(snapshot.get("visibility"), dict):
                current = snapshot["visibility"]
        except (UnicodeError, json.JSONDecodeError):
            pass
    return {option: value if value is not None else current.get(option) is True
            for option, value in (("include_samples", args.include_samples), ("exclude_fiction", args.exclude_fiction))}


def verify_local_sources(cards: list[VaultCard]) -> None:
    """Recheck declared snapshots without assuming that all online sources are cached."""
    expected = {}
    for card in cards:
        for source in card.metadata.sources:
            if not source.local_path or not source.content_sha256:
                continue
            path = Path(source.local_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            path = path.resolve()
            previous = expected.setdefault(path, source.content_sha256)
            if previous != source.content_sha256:
                raise IntakeError(f"同一本地来源被登记为不同的内容哈希，请核对出处。{path}")
    for path, digest in expected.items():
        if not path.is_file():
            raise IntakeError(f"登记的本地来源文件不存在，请恢复文件或更新出处并重新复核。{path}")
        try:
            with path.open("rb") as stream:
                actual = file_digest(stream, "sha256").hexdigest()
        except OSError as error:
            raise IntakeError(f"无法读取登记的本地来源。{path}\n{error}") from error
        if actual != digest:
            raise IntakeError(f"本地来源内容与草稿登记的哈希不一致，请核对来源并重新复核。{path}")


def approve(args: argparse.Namespace, vault: Path, table: dict[tuple[str, str], CodeEntry],
            *, selected_paths: list[Path] | None = None) -> int:
    if selected_paths is not None:
        queue = (vault / DRAFT_DIRECTORY).resolve()
        paths = [path.resolve() for path in selected_paths]
        if any(not path.is_relative_to(queue) or path.suffix != ".md" for path in paths):
            raise IntakeError("复核记录须指向待审目录中的 Markdown 草稿。")
    elif args.command == "approve":
        paths = [draft_path(vault, args.draft)]
    else:
        queue = (vault / DRAFT_DIRECTORY).resolve()
        paths = []
        for name in dict.fromkeys(args.batch):
            batch = (queue / name).resolve()
            if batch.parent != queue or name != batch.name:
                raise IntakeError("请指定待审目录下的批次名称。")
            cards_in_batch = sorted(batch.glob("*.md"))
            if not cards_in_batch:
                raise IntakeError(f"该批次没有待审卡片。{batch}")
            if any(path.is_symlink() for path in cards_in_batch):
                raise IntakeError("批次内的卡片须存放在批次目录中。")
            paths.extend(cards_in_batch)
    default = DEFAULT_OUTPUTS["json"] if vault == DEFAULT_VAULT.resolve() else vault.parent / ".local" / "graph_data.json"
    output = (args.output or default).resolve()
    if output.is_relative_to(vault):
        raise IntakeError("编译产物须保存到 vault 之外。")

    with (nullcontext() if args.check else vault_writer(vault)):
        cards = load_vault(vault)
        planned = []
        for path in paths:
            original = path.read_bytes()
            expected = getattr(args, "review_decisions", {}).get(path.stem)
            if expected and sha256(original).hexdigest() != expected["card_sha256"]:
                raise IntakeError(f"草稿在复核后发生变化，请重新复核。{path}")
            try:
                candidate = prepare_card(path, original, args, table)
            except (ValueError, yaml.YAMLError) as error:
                raise IntakeError(f"{path.name}\n{error}") from error
            previous = cards.get(candidate.metadata.id)
            if previous is not None and previous != candidate:
                raise IntakeError(f"正式目录已有不同内容的同名卡片，已保留原卡。{previous.source_path}")
            cards[candidate.metadata.id] = candidate
            planned.append((path, original, candidate, previous is None))
        verify_local_sources([candidate for _, _, candidate, _ in planned])
        graph = compile_cards(cards, **export_policy(output, args))
        totals = f"{len(planned)} 张卡片。快照可见 {len(graph['nodes'])} 个节点、{len(graph['links'])} 条关系。"
        if args.check:
            print(f"签核预检通过。{totals}")
            return 0
        if any(path.read_bytes() != original for path, original, _, _ in planned):
            raise IntakeError("草稿在校验期间已修改。请核对新内容后再次签核。")
        verify_local_sources([candidate for _, _, candidate, _ in planned])

        created = []
        try:
            for _, _, candidate, is_new in planned:
                if is_new:
                    destination = vault / candidate.source_path
                    content = serialize_card(candidate.metadata, candidate.markdown)
                    create_card(destination, content)
                    created.append((destination, content))
            publish_graph(output, graph, "json")
        except (ValueError, OSError):
            for destination, content in created:
                if destination.exists() and destination.read_bytes() == content:
                    destination.unlink()
            raise

        for path, original, _, _ in planned:
            try:
                if path.read_bytes() == original:
                    path.unlink()
                else:
                    print(f"草稿有新编辑，仍保留在 {path}", file=sys.stderr)
            except OSError as error:
                print(f"卡片和快照已写入，草稿清理待处理。{error}", file=sys.stderr)
        for directory in dict.fromkeys(path.parent for path in paths):
            manifest_path = directory / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict) or manifest.get("batch") != directory.name:
                    raise IntakeError(f"批次清单内容有误。{manifest_path}")
                remaining = sum(path.is_file() for path in directory.glob("*.md"))
                manifest["review_state"] = "partially_approved" if remaining else "review_closed"
                manifest["remaining_drafts"] = remaining
                publish_graph(manifest_path, manifest, "json")
            except (ValueError, OSError) as error:
                print(f"签核已完成，批次清单更新待处理。{error}", file=sys.stderr)

    print(f"已签核 {totals}")
    print(f"已更新前端快照 {output}")
    return 0


def prepare_card(path: Path, original: bytes, args: argparse.Namespace,
                 table: dict[tuple[str, str], CodeEntry]) -> VaultCard:
    metadata, body = parse_card(original.decode("utf-8-sig").replace("\r\n", "\n"))
    if path.stem != metadata.id:
        raise IntakeError(f"草稿文件名须与 ID 一致。预期 {metadata.id}.md。")
    data = metadata.model_dump(mode="json")
    decision = getattr(args, "review_decisions", {}).get(metadata.id)
    data["genre"] = (decision.get("genre") if decision else None) or args.genre or metadata.genre
    if args.tier or data["genre"] == "creepypasta_ostension":
        data["credibility_tier"] = args.tier or "F"
    data["is_fictional_quarantine"] = data["credibility_tier"] == "F"
    data["audit"].update(reviewed_by_human=True, is_sample=False)
    if decision:
        data["audit"].update(reviewer=decision["reviewer"], reviewed_at=decision["reviewed_at"],
                             review_note=decision["note"] or None)
    metadata = NodeMetadata.model_validate(data)
    if decision and decision.get("public_release"):
        signed = metadata.model_dump(mode="json")
        signed["audit"].update(public_release=True, public_rights_note=decision["public_rights_note"],
                               public_content_sha256=None)
        signed["audit"]["public_content_sha256"] = public_content_sha256(signed, body)
        metadata = NodeMetadata.model_validate(signed)
    if not metadata.sources:
        raise IntakeError("签核需要至少一条出处。")
    verify_codes(metadata.standards, table)
    return VaultCard(metadata, f"{card_directory(metadata)}/{path.name}", body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--vault", type=Path, default=DEFAULT_VAULT, help="知识库目录")
    common.add_argument("--code-table", type=Path, default=DEFAULT_CODE_TABLE, help="本地标准码表 JSON")
    commands = parser.add_subparsers(dest="command", required=True)
    drafting = commands.add_parser("draft", parents=[common], help="抽取资料并写入待审目录")
    drafting.add_argument("source", nargs="?", help="本地文件、HTTP(S) URL 或标准输入 -")
    drafting.add_argument("--text", help="直接提供纯文本")
    drafting.add_argument("--encoding", help="本地纯文本、标准输入或 HTML 的原编码")
    drafting.add_argument("--id", help="稳定节点 ID")
    drafting.add_argument("--title", help="卡片标题")
    drafting.add_argument("--citation", help="书目、档号或其他准确出处")
    drafting.add_argument("--source-url", help="本地材料对应的公开出处链接")
    drafting.add_argument("--doi", help="文献 DOI")
    drafting.add_argument("--node-type", choices=get_args(NodeType), default="case")
    drafting.add_argument("--genre", choices=get_args(Genre))
    drafting.add_argument("--tier", choices=get_args(CredibilityTier))

    review = argparse.ArgumentParser(add_help=False, parents=[common])
    review.add_argument("--genre", choices=[value for value in get_args(Genre) if value != "unclassified"])
    review.add_argument("--tier", choices=get_args(CredibilityTier))
    review.add_argument("--check", action="store_true", help="预检正式卡片和图谱编译")
    review.add_argument("--output", type=Path, help="前端 JSON 快照路径")
    review.add_argument("--include-samples", action=argparse.BooleanOptionalAction, default=None)
    review.add_argument("--exclude-fiction", action=argparse.BooleanOptionalAction, default=None)
    signing = commands.add_parser("approve", parents=[review], help="人工签核草稿并重编译前端快照")
    signing.add_argument("draft", help="待审卡片 ID 或文件路径")
    batch = commands.add_parser("approve-batch", parents=[review], help="人工签核整批草稿并重编译前端快照")
    batch.add_argument("batch", nargs="+", help="待审目录下的一个或多个批次名称")
    args = parser.parse_args()
    try:
        table = load_code_table(args.code_table)
        vault = args.vault.resolve()
        if args.command == "draft":
            return draft(args, vault, table)
        return approve(args, vault, table)
    except (ValueError, OSError, yaml.YAMLError) as error:
        print(f"入库操作未完成\n{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
