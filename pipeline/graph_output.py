"""Publish one complete graph snapshot as UTF-8 JSON or SQLite."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

SQL_SCHEMA = """
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    node_type TEXT NOT NULL,
    z_layer INTEGER NOT NULL,
    genre TEXT NOT NULL,
    credibility_tier TEXT NOT NULL,
    is_fictional_quarantine INTEGER NOT NULL,
    lat REAL,
    lng REAL,
    year_start INTEGER,
    year_end INTEGER,
    source_path TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE links (
    source TEXT NOT NULL REFERENCES nodes(id),
    target TEXT NOT NULL REFERENCES nodes(id),
    type TEXT NOT NULL,
    status TEXT,
    is_fictional_quarantine INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (source, target, type)
);
CREATE INDEX nodes_temporal ON nodes(year_start, year_end);
CREATE INDEX links_target ON links(target);
"""


def graph_json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=indent)


def write_sqlite(path: Path, graph: dict) -> None:
    with closing(sqlite3.connect(path)) as database, database:
        database.execute("PRAGMA foreign_keys = ON")
        database.executescript(SQL_SCHEMA)
        database.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            [(key, graph_json(value)) for key, value in graph.items() if key not in {"nodes", "links"}],
        )

        rows = []
        for node in graph["nodes"]:
            spatial = node["spatial"] or {}
            temporal = node["temporal"] or {}
            rows.append((
                node["id"], node["title"], node["node_type"], node["z_layer"], node["genre"],
                node["credibility_tier"], node["is_fictional_quarantine"],
                spatial.get("lat"), spatial.get("lng"), temporal.get("year_start"),
                temporal.get("year_end"), node["source_path"], graph_json(node),
            ))
        database.executemany(
            """INSERT INTO nodes (
                id, title, node_type, z_layer, genre, credibility_tier, is_fictional_quarantine,
                lat, lng, year_start, year_end, source_path, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        database.executemany(
            "INSERT INTO links (source, target, type, status, is_fictional_quarantine, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (link["source"], link["target"], link["type"], link["status"],
                 link["is_fictional_quarantine"], graph_json(link))
                for link in graph["links"]
            ],
        )


def publish_graph(path: Path, graph: dict, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".astraia-build-", dir=path.parent) as directory:
        staged = Path(directory) / path.name
        if output_format == "json":
            staged.write_text(graph_json(graph, indent=2) + "\n", encoding="utf-8", newline="\n")
        else:
            write_sqlite(staged, graph)
        staged.replace(path)
