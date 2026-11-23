from argparse import Namespace
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.build_graph import compile_cards
from pipeline.fetch_lao_dllm import fetch
from pipeline.import_datasets import stage_batch
from pipeline.ingest_agent import prepare_card, verify_local_sources
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import lao_cards, load_snapshot
from pipeline.local_standards import load_code_table
from pipeline.review_queue import export
from tests.test_lao_dllm_fetch import Response, page


def field(name, values):
    return {"label": {"en": [name]}, "value": values}


def item(identifier, *, latitude="17.9639", license_value=True, code=None):
    return {"resource_id": f"urn:madoc:manifest:{identifier}", "resource_type": "Manifest",
            "label": {"none": [f"Lao story {identifier} (ນິທານ)"]},
            "metadata": [field("dc:subject", {"en": ["Folk Tale"], "lo": ["ນິທານຊາວບ້ານ"]}),
                         field("title", {"en": [f"Lao story {identifier}"], "lo": ["ນິທານ"]}),
                         field("dc:identifier", {"none": [f"dllm_{identifier}"]}),
                         field("otherIdentifier.code_number", {"none": [code or f"01012912012_{identifier:02d}"]}),
                         field("full_location_name", {"en": ["National Library of Laos"]}),
                         field("schema:latitude", {"none": [latitude]}),
                         field("schema:longitude", {"none": ["102.608"]}),
                         field("date_original", {"en": ["(Undated)"]})],
            "requiredStatement": ({"value": {"en": ["Example credit (CC BY-NC 4.0)"]}} if license_value else None)}


class LaoManuscriptTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshots = self.root / "snapshots"
        responses = [Response(page(1, [item(11), item(12, latitude="bad", license_value=False)])),
                     Response(page(2, [item(13, code="01012912012_11")]))]
        with patch("pipeline.fetch_lao_dllm.urlopen", side_effect=responses), patch("pipeline.fetch_lao_dllm.time.sleep"):
            fetch(self.snapshots)
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.vault = self.root / "vault"
        self.vault.mkdir()

    def test_snapshot_integrity_and_no_inferred_coordinates(self):
        manifest, items = load_snapshot(self.snapshots)
        self.assertEqual((manifest["total_results"], len(items)), (3, 3))
        entries = list(lao_cards(self.snapshots))
        self.assertEqual(len(entries), 4)
        metadata, body = entries[1]
        self.assertIsNone(metadata.spatial.lat)
        self.assertIsNone(metadata.temporal)
        self.assertFalse(any(metadata.standards.model_dump().values()))
        self.assertIn("未下载手稿图像，也未生成文字转录", body)
        self.assertIn("ນິທານ", body)
        self.assertTrue(str(metadata.sources[1].url).endswith("/manifests/11"))
        self.assertIn("PLMP 档号对照待核", body)
        self.assertTrue(any(source.type == "lao_dllm_crosscheck" for source in metadata.sources))
        (self.snapshots / "page-001.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(IntakeError, "哈希不符"):
            load_snapshot(self.snapshots)

    def test_review_flags_storage_candidates_and_missing_permissions(self):
        manifest = stage_batch(self.vault, "asia_lao_dllm", lao_cards(self.snapshots), self.table, {})
        self.assertEqual(manifest["counts"]["records"], 4)
        self.assertEqual(manifest["counts"]["with_coordinates"], 0)
        absent = self.root / "absent"
        output = self.root / "review"
        summary = export(self.vault, output, absent, absent, absent, absent, absent, self.table, absent)
        self.assertEqual(summary["collections"], {"asia": 4})
        raw = (output / "data.js").read_text(encoding="utf-8")
        records = {record["id"]: record for record in json.loads(
            raw.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]}
        first, second = records["corpus_lao_dllm_11"], records["corpus_lao_dllm_12"]
        self.assertEqual(first["evidence"]["lao_repository_candidate"]["lat"], 17.9639)
        self.assertTrue({"lao_image_not_cached", "lao_transcription_missing", "lao_repository_point_unverified",
                         "lao_duplicate_plmp_code"}
                        .issubset({flag["code"] for flag in first["issues"]}))
        self.assertEqual(first["evidence"]["lao_duplicate_plmp"][0]["manifest"], 13)
        self.assertTrue({"lao_repository_point_invalid", "lao_license_unclear"}
                        .issubset({flag["code"] for flag in second["issues"]}))
        csv_path = output / "lao_manuscript_review.csv"
        self.assertTrue(csv_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        self.assertEqual(len(csv_rows), 3)
        one = next(row for row in csv_rows if row["馆藏记录号"] == "11")
        self.assertEqual(one["PLMP档号"], "01012912012_11")
        self.assertEqual(one["候选纬度"], "17.9639")
        self.assertIn("manifest 13", one["同号馆藏"])
        table = load_code_table(self.table)
        paths = list((self.vault / "00_drafts/asia_lao_dllm").glob("*.md"))
        candidates = [prepare_card(path, path.read_bytes(), Namespace(genre="folktale", tier=None), table) for path in paths]
        verify_local_sources(candidates)
        graph = compile_cards({card.metadata.id: card for card in candidates})
        self.assertEqual((len(graph["nodes"]), len(graph["links"])), (4, 3))


if __name__ == "__main__":
    unittest.main()
