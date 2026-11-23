"""Find traceable, exact matches in a user-editable local code table."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Annotated, Literal
import unicodedata

from pydantic import Field, HttpUrl

from pipeline.graph_links import normalize_code, standard_codes
from pipeline.intake_sources import IntakeError, Passage
from pipeline.node_model import NonBlank, Standards, StrictModel

CodeSystem = Literal["atu_types", "thompson_motifs", "berezkin_codes", "ocm_codes"]
Code = Annotated[str, Field(pattern=r"^[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*$")]
SYSTEMS = {
    "atu_types": ("ATU", r"ATU"),
    "thompson_motifs": ("汤普森", r"(?:thompson|汤普森)"),
    "berezkin_codes": ("别列兹金", r"(?:berezkin|别列兹金)"),
    "ocm_codes": ("OCM", r"OCM"),
}


class CodeEntry(StrictModel):
    system: CodeSystem
    code: Code
    label: NonBlank
    aliases: list[NonBlank] = Field(default_factory=list)
    citation: NonBlank
    url: HttpUrl
    match_label: bool = True


class CodeEdition(StrictModel):
    system: CodeSystem
    citation: NonBlank
    url: HttpUrl
    content_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    codes: list[Code]


class CodeTable(StrictModel):
    version: Literal[1]
    entries: list[CodeEntry]
    editions: list[CodeEdition] = Field(default_factory=list)


@dataclass(frozen=True)
class CodeMatch:
    entry: CodeEntry
    locator: str
    term: str


@dataclass(frozen=True)
class UnmatchedCode:
    system: CodeSystem
    code: str
    locator: str
    term: str


def load_code_table(path: Path) -> dict[tuple[str, str], CodeEntry]:
    table = CodeTable.model_validate_json(path.read_text(encoding="utf-8-sig"))
    index = {}
    for entry in table.entries:
        key = entry.system, normalize_code(entry.system, entry.code)
        if key in index:
            raise IntakeError(f"本地码表有重复条目 {SYSTEMS[entry.system][0]} {entry.code}。")
        index[key] = entry
    for edition in table.editions:
        for code in edition.codes:
            key = edition.system, normalize_code(edition.system, code)
            if key in index:
                continue
            index[key] = CodeEntry(system=edition.system, code=code, url=edition.url, match_label=False,
                                   label=f"{SYSTEMS[edition.system][0]} {code}", citation=f"{edition.citation}, {code}.")
    return index


def normalized_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def phrase_pattern(phrase: str) -> str:
    term = normalized_text(phrase)
    left = r"(?<![a-z0-9])" if term[0].isascii() and term[0].isalnum() else ""
    right = r"(?![a-z0-9])" if term[-1].isascii() and term[-1].isalnum() else ""
    return f"{left}{re.escape(term)}{right}"


def match_codes(table: dict[tuple[str, str], CodeEntry], passages: list[Passage]) -> list[CodeMatch]:
    texts = [(part.locator, normalized_text(part.text)) for part in passages]
    matches = []
    for entry in table.values():
        system_prefix = SYSTEMS[entry.system][1].lower()
        code = r"\s*".join(re.escape(ch) for ch in entry.code.casefold())
        explicit = rf"(?<![a-z0-9_]){system_prefix}\s*(?:[-:#]\s*)?{code}(?![a-z0-9_]|[.\-][a-z0-9])"
        terms = [entry.label, *entry.aliases] if entry.match_label else entry.aliases
        patterns = [re.compile(explicit)]
        if terms:
            patterns.append(re.compile("|".join(phrase_pattern(term) for term in terms)))
        for pattern in patterns:
            hit = next(((locator, result) for locator, text in texts if (result := pattern.search(text))), None)
            if hit is not None:
                locator, result = hit
                matches.append(CodeMatch(entry, locator, result.group()))
                break
    return matches


def unmatched_explicit_codes(table: dict[tuple[str, str], CodeEntry], passages: list[Passage]) -> list[UnmatchedCode]:
    """Record explicit code-like references without adding them to the standards fields."""
    formats = {
        "atu_types": r"\d+[a-z]*(?:[.\-][a-z0-9]+)*",
        "ocm_codes": r"\d+[a-z]*(?:[.\-][a-z0-9]+)*",
        "thompson_motifs": r"[a-z]\d+[a-z0-9]*(?:[.\-][a-z0-9]+)*",
        "berezkin_codes": r"[a-z]\d+[a-z0-9]*(?:[.\-][a-z0-9]+)*",
    }
    patterns = {system: re.compile(rf"(?<![a-z0-9_]){prefix.lower()}\s*(?:[-:#]\s*)?"
                                   rf"(?P<code>{formats[system]})(?![a-z0-9_]|[./\-][a-z0-9])")
                for system, (_, prefix) in SYSTEMS.items()}
    result, seen = [], set()
    for part in passages:
        text = normalized_text(part.text)
        for system, pattern in patterns.items():
            for hit in pattern.finditer(text):
                code = hit["code"] if system == "berezkin_codes" else hit["code"].upper()
                key = (system, normalize_code(system, code))
                if key not in table and key not in seen:
                    result.append(UnmatchedCode(system, code, part.locator, hit.group()))
                    seen.add(key)
    return result


def verify_codes(standards: Standards, table: dict[tuple[str, str], CodeEntry]) -> None:
    missing = [f"{SYSTEMS[system][0]} {code}" for (system, key), code in standard_codes(standards).items()
               if (system, key) not in table]
    if missing:
        raise IntakeError(f"下列编码未登记在本地码表中，请删除或查证后补录码表。{'、'.join(missing)}。")
