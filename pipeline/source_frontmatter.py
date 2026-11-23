"""Append validated YAML sources while preserving existing card text and comments."""

import re

import yaml

from pipeline.node_model import Relation, Source


def append_sources(text: str, additions: list[Source]) -> str:
    if not additions:
        return text
    match = re.search(r"(?ms)^sources:[ \t]*\r?\n(?P<items>.*?)(?=^[A-Za-z_][A-Za-z_0-9]*:|\Z)", text)
    if not match:
        raise ValueError("草稿来源区块无法定位。")
    linebreak = "\r\n" if "\r\n" in text[:match.end()] else "\n"
    block = yaml.safe_dump([source.model_dump(mode="json") for source in additions],
                           allow_unicode=True, sort_keys=False).replace("\n", linebreak)
    items = match.group("items")
    if not items.endswith(("\n", "\r")):
        items += linebreak
    return text[:match.start("items")] + items + block + text[match.end("items"):]


def append_relations(text: str, additions: list[Relation]) -> str:
    if not additions:
        return text
    linebreak = "\r\n" if "\r\n" in text else "\n"
    block = yaml.safe_dump([relation.model_dump(mode="json") for relation in additions],
                           allow_unicode=True, sort_keys=False).replace("\n", linebreak)
    empty = re.search(r"(?m)^relations:[ \t]*\[\]([ \t]*(?:\#.*)?)\r?$", text)
    if empty:
        return text[:empty.start()] + "relations:" + empty[1] + linebreak + block.rstrip("\r\n") + text[empty.end():]
    match = re.search(r"(?ms)^relations:[ \t]*\r?\n(?P<items>.*?)(?=^[A-Za-z_][A-Za-z_0-9]*:|\Z)", text)
    if not match:
        raise ValueError("草稿关联区块无法定位。")
    items = match.group("items")
    if not items.endswith(("\n", "\r")):
        items += linebreak
    return text[:match.start("items")] + items + block + text[match.end("items"):]
