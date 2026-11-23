from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

import yaml

from pipeline.build_graph import compile_graph
from pipeline.graph_output import publish_graph


class CompilerTests(unittest.TestCase):
    def setUp(self):
        work = TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()

    def add_card(self, node_id, directory="01_cases", *, omit=(), **fields):
        metadata = {
            "id": node_id,
            "title": "中文档案",
            "node_type": "case",
            "z_layer": 1,
            "genre": "historical_archive",
            "credibility_tier": "B",
            "is_fictional_quarantine": False,
            "spatial": None,
            "temporal": None,
            "standards": {},
            "sources": [],
            "audit": {"created_at": "2026-11-22", "reviewed_by_human": True},
        }
        metadata.update(fields)
        for key in omit:
            del metadata[key]
        path = self.vault / directory / f"{node_id}.md"
        path.parent.mkdir(exist_ok=True)
        frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        path.write_text(f"---\n{frontmatter}---\n    中文代码示例\n", encoding="utf-8")

    def test_invalid_frontmatter_leaves_previous_export_in_place(self):
        self.add_card("missing_tier", omit=("credibility_tier",))
        self.add_card("invalid_coordinates", spatial={
            "precision": "city", "lat": "30.04", "lng": 190, "location_name": "开罗",
        })
        output = self.root / "graph.json"
        output.write_text('{"previous":true}', encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "pipeline.build_graph", "--vault", str(self.vault),
             "--output", str(output)],
            capture_output=True, encoding="utf-8", check=False,
        )

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("[credibility_tier]", result.stderr)
        self.assertIn("[spatial.lat]", result.stderr)
        self.assertIn("[spatial.lng]", result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"previous": True})

    def test_standard_links_and_fiction_quarantine(self):
        self.add_card("case_archive", standards={"ocm_codes": ["OCM 754"]})
        self.add_card("index_sorcery", "03_motifs_standards", node_type="motif_index", z_layer=3,
                      genre="academic_model", standards={"ocm_codes": ["754"]})
        self.add_card(
            "fiction", "05_quarantine_fiction", credibility_tier="F", is_fictional_quarantine=True,
            genre="creepypasta_ostension", standards={"ocm_codes": ["754"]},
            audit={"created_at": "2026-11-22", "reviewed_by_human": False, "is_sample": True},
            relations=[{"type": "COMPARED_WITH", "target": "case_archive"}],
        )
        self.add_card("ordinary_draft", audit={"created_at": "2026-11-22", "reviewed_by_human": False})

        regular = compile_graph(self.vault)
        preview = compile_graph(self.vault, include_samples=True)
        research = compile_graph(self.vault, include_samples=True, exclude_fiction=True)

        self.assertEqual([node["id"] for node in regular["nodes"]], ["case_archive", "index_sorcery"])
        self.assertEqual(research["nodes"], regular["nodes"])
        self.assertEqual(research["links"], regular["links"])
        self.assertEqual(len(preview["nodes"]), 3)
        self.assertEqual(len(preview["links"]), 2)
        implicit, cross_partition = preview["links"]
        self.assertEqual(implicit["matched_codes"], [{"system": "ocm_codes", "code": "754"}])
        self.assertEqual(implicit["type"], "TAGGED_OCM")
        self.assertTrue(cross_partition["is_fictional_quarantine"])
        self.assertEqual(preview["nodes"][0]["metrics"], regular["nodes"][0]["metrics"])
        self.assertIsNone(preview["nodes"][1]["metrics"])

    def test_utf8_and_snapshot_match_in_json_and_sqlite(self):
        self.add_card("case_archive")
        graph = compile_graph(self.vault)
        json_path = self.root / "graph.json"
        sqlite_path = self.root / "graph.sqlite3"
        publish_graph(json_path, graph, "json")
        publish_graph(sqlite_path, graph, "sqlite")

        exported = json.loads(json_path.read_text(encoding="utf-8"))
        with closing(sqlite3.connect(sqlite_path)) as database:
            title, payload = database.execute("SELECT title, payload FROM nodes").fetchone()
            snapshot, = database.execute("SELECT value FROM metadata WHERE key = 'snapshot_id'").fetchone()
            self.assertEqual(database.execute("PRAGMA foreign_key_check").fetchall(), [])

        self.assertEqual(title, "中文档案")
        self.assertEqual(json.loads(payload), exported["nodes"][0])
        self.assertEqual(exported["nodes"][0]["markdown"], "    中文代码示例\n")
        self.assertEqual(json.loads(snapshot), exported["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
