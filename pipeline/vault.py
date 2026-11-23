"""Read UTF-8 Markdown and validate every card before compiling a graph."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from pipeline.node_model import NodeMetadata

LAYER_DIRECTORIES = {
    1: "01_cases",
    2: "02_myth_corpora",
    3: "03_motifs_standards",
    4: "04_mechanisms_theories",
}
FICTION_DIRECTORY = "05_quarantine_fiction"


class VaultError(ValueError):
    """The vault violates the card contract."""


class FrontmatterLoader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict:
        if not isinstance(node, MappingNode):
            return super().construct_mapping(node, deep=deep)
        keys: set[str] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ConstructorError(None, None, "YAML 属性名须为字符串", key_node.start_mark)
            if key in keys:
                raise ConstructorError(None, None, f"YAML 属性 {key} 重复", key_node.start_mark)
            keys.add(key)
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True)
class VaultCard:
    metadata: NodeMetadata
    source_path: str
    markdown: str


def card_directory(metadata: NodeMetadata) -> str:
    return FICTION_DIRECTORY if metadata.is_fictional_quarantine else LAYER_DIRECTORIES[metadata.z_layer]


def parse_card(text: str) -> tuple[NodeMetadata, str]:
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        raise VaultError("首行须为 YAML Frontmatter 的分隔线 ---")
    end = next((index for index, line in enumerate(lines[1:], 1) if line.rstrip() == "---"), None)
    if end is None:
        raise VaultError("缺少 YAML Frontmatter 的结束分隔线 ---")

    data = yaml.load("\n".join(lines[1:end]), Loader=FrontmatterLoader)
    metadata = NodeMetadata.model_validate(data)
    markdown = "\n".join(lines[end + 1:])
    if not markdown.strip():
        raise VaultError("卡片须包含 Markdown 正文")
    return metadata, markdown


def read_card(vault: Path, path: Path) -> VaultCard:
    relative = path.relative_to(vault)
    metadata, markdown = parse_card(path.read_text(encoding="utf-8-sig"))
    if path.stem != metadata.id:
        raise VaultError(f"文件名须为 {metadata.id}.md")
    directory = card_directory(metadata)
    if relative.parts[0] != directory:
        raise VaultError(f"节点应放在 vault/{directory}/")

    return VaultCard(metadata, relative.as_posix(), markdown)


def load_vault(vault: Path) -> dict[str, VaultCard]:
    if not vault.is_dir():
        raise VaultError(f"知识库目录不存在：{vault}")

    cards: dict[str, VaultCard] = {}
    errors = []
    directories = (*LAYER_DIRECTORIES.values(), FICTION_DIRECTORY)
    for directory in directories:
        for path in sorted((vault / directory).rglob("*.md")):
            try:
                card = read_card(vault, path)
                node_id = card.metadata.id
                if node_id in cards:
                    raise VaultError(f"ID {node_id} 已在 {cards[node_id].source_path} 使用")
                cards[node_id] = card
            except ValidationError as error:
                for issue in error.errors(include_url=False, include_input=False):
                    location = ".".join(str(part) for part in issue["loc"]) or "frontmatter"
                    errors.append(f"{path.relative_to(vault)} [{location}] {issue['msg']}")
            except (OSError, UnicodeError, yaml.YAMLError, VaultError) as error:
                errors.append(f"{path.relative_to(vault)} {error}")

    if errors:
        raise VaultError("\n".join(errors))
    return dict(sorted(cards.items()))
