from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from pipeline.ingest_agent import serialize_card
from pipeline.node_model import Relation
from pipeline.vault import parse_card


class ReviewApprovalTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.output = self.root / "graph.json"
        for card_id, node_type in (("test_corpus", "myth_corpus"), ("test_case", "case")):
            result = subprocess.run([
                sys.executable, "-X", "utf8", "-m", "pipeline.ingest_agent", "draft",
                "--vault", str(self.vault), "--id", card_id, "--node-type", node_type,
                "--genre", "historical_archive", "--text", "测试原始资料", "--citation", "测试档案",
            ], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        case_path = self.vault / "00_drafts" / "test_case.md"
        card, body = parse_card(case_path.read_text(encoding="utf-8"))
        card.relations = [Relation(type="PART_OF_MACRO_TREND", target="test_corpus")]
        case_path.write_bytes(serialize_card(card, body))
        self.decisions_path = self.root / "decisions.json"

    def decision(self, card_id, status="reviewed"):
        path = self.vault / "00_drafts" / f"{card_id}.md"
        return {"id": card_id, "status": status, "card_sha256": sha256(path.read_bytes()).hexdigest(),
                "reviewer": "测试复核人", "note": "核对过档号", "reviewed_at": datetime.now(timezone.utc).isoformat()}

    def run_review(self, decisions, *options, success=True):
        self.decisions_path.write_text(json.dumps({"version": 1, "decisions": decisions}, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([
            sys.executable, "-X", "utf8", "-m", "pipeline.review_approval", str(self.decisions_path),
            "--vault", str(self.vault), "--output", str(self.output), *options,
        ], capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def test_approval_requires_dependency_and_preserves_review_evidence(self):
        child = self.decision("test_case")
        result = self.run_review([child], "--check")
        self.assertIn("等待关联卡片复核 1", result.stdout)
        self.assertFalse(self.output.exists())

        parent = self.decision("test_corpus")
        self.run_review([child, parent], "--check")
        self.assertFalse(self.output.exists())
        self.run_review([child, parent])
        graph = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual({node["id"] for node in graph["nodes"]}, {"test_case", "test_corpus"})
        self.assertTrue(all(node["audit"]["reviewer"] == "测试复核人" for node in graph["nodes"]))
        self.assertTrue(all(node["audit"]["review_note"] == "核对过档号" for node in graph["nodes"]))
        self.assertEqual(graph["links"][0]["target"], "test_corpus")

    def test_changed_draft_rejected_and_correction_is_not_published(self):
        child = self.decision("test_case")
        parent = self.decision("test_corpus", "correction")
        path = self.vault / "00_drafts" / "test_case.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n追加资料\n", encoding="utf-8")
        result = self.run_review([child, parent], success=False)
        self.assertIn("复核后发生变化", result.stderr)
        self.assertFalse(self.output.exists())
        child = self.decision("test_case", "correction")
        result = self.run_review([child, parent])
        self.assertIn("依赖齐全 0 张", result.stdout)
        self.assertTrue(path.exists())
        self.assertFalse(self.output.exists())

    def test_review_can_record_the_chosen_genre(self):
        path = self.vault / "00_drafts" / "test_case.md"
        card, body = parse_card(path.read_text(encoding="utf-8"))
        card.genre = "unclassified"
        path.write_bytes(serialize_card(card, body))
        child = self.decision("test_case")
        child["genre"] = "fabulate"
        parent = self.decision("test_corpus")
        self.run_review([child, parent])
        graph = json.loads(self.output.read_text(encoding="utf-8"))
        case = next(node for node in graph["nodes"] if node["id"] == "test_case")
        self.assertEqual(case["genre"], "fabulate")
        self.assertEqual(case["audit"]["reviewer"], "测试复核人")

    def test_catalogued_pending_card_is_reviewed_in_place(self):
        decisions = [self.decision("test_case"), self.decision("test_corpus")]
        draft = self.vault / "00_drafts" / "test_case.md"
        path = self.vault / "01_cases" / draft.name
        path.parent.mkdir()
        draft.rename(path)
        original = path.read_bytes()
        self.run_review(decisions, "--check")
        self.assertEqual(path.read_bytes(), original)

        self.output.mkdir()
        self.run_review(decisions, success=False)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.vault / "02_myth_corpora" / "test_corpus.md").exists())
        self.output.rmdir()

        self.run_review(decisions)
        card, _ = parse_card(path.read_text(encoding="utf-8"))
        self.assertEqual(card.audit.reviewer, "测试复核人")
        self.assertFalse(draft.exists())
        graph = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual({node["id"] for node in graph["nodes"]}, {"test_case", "test_corpus"})

    def test_changed_or_missing_local_source_cannot_be_signed(self):
        source_path = self.root / "原始资料.txt"
        source_path.write_text("原始资料", encoding="utf-8")
        card_path = self.vault / "00_drafts" / "test_case.md"
        card, body = parse_card(card_path.read_text(encoding="utf-8"))
        card.sources[0].local_path = str(source_path)
        card.sources[0].content_sha256 = sha256(source_path.read_bytes()).hexdigest()
        card_path.write_bytes(serialize_card(card, body))
        decisions = [self.decision("test_case"), self.decision("test_corpus")]
        self.run_review(decisions, "--check")

        source_path.write_text("资料在复核后发生变化", encoding="utf-8")
        result = self.run_review(decisions, success=False)
        self.assertIn("本地来源内容与草稿登记的哈希不一致", result.stderr)
        self.assertFalse(self.output.exists())
        self.assertTrue(card_path.exists())

        source_path.unlink()
        result = self.run_review(decisions, "--check", success=False)
        self.assertIn("本地来源文件不存在", result.stderr)
        self.assertFalse(self.output.exists())

        source_path.write_text("原始资料", encoding="utf-8")
        self.run_review(decisions)
        self.assertTrue(self.output.exists())


if __name__ == "__main__":
    unittest.main()
