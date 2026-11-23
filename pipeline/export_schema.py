"""Regenerate the JSON Schema from the frontmatter model."""

import argparse
import json
from pathlib import Path

from pipeline.node_model import NodeMetadata

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "node_schema.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check the committed schema")
    args = parser.parse_args()
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **NodeMetadata.model_json_schema(),
    }
    content = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not SCHEMA_PATH.is_file() or SCHEMA_PATH.read_text(encoding="utf-8") != content:
            parser.error("JSON Schema 与 Pydantic 模型不同步，请重新运行本模块")
        print(f"Schema 校验通过。{SCHEMA_PATH}")
    else:
        SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_PATH.write_text(content, encoding="utf-8", newline="\n")
        print(f"已生成 {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
