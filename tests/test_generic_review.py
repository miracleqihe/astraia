from argparse import Namespace
from contextlib import redirect_stderr
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from pipeline.review_queue import export
from pipeline.ingest_agent import draft, serialize_card
from pipeline.local_standards import load_code_table
from pipeline.node_model import Source
from pipeline.vault import parse_card


class GenericReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [{
            "system": "ocm_codes", "code": "754", "label": "巫术指控", "citation": "本地测试码表",
            "url": "https://example.org/ocm/754"}], "editions": []}, ensure_ascii=False), encoding="utf-8")
        self.output = self.root / "review"
        self.absent = self.root / "no-dataset"

    def draft(self, *arguments, success=True):
        result = subprocess.run([sys.executable, "-X", "utf8", "-m", "pipeline.ingest_agent", "draft",
                                 "--vault", str(self.vault), "--code-table", str(self.table), *arguments],
                                capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def build_review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent, self.absent,
                      self.absent, self.table, self.absent)

    def records(self):
        script = (self.output / "data.js").read_text(encoding="utf-8")
        return json.loads(script.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]

    def create_pdf(self, path):
        writer = PdfWriter()
        page = writer.add_blank_page(width=400, height=300)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (Archive OCM 754.) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.write(str(path))

    def test_all_drafts_enter_review_and_only_human_decisions_publish(self):
        text_path = self.root / "中文资料.txt"
        text_path.write_text("记录涉及 OCM 754，也提到 OCM 9999 和 ATU 425AB。", encoding="utf-8")
        self.draft(str(text_path), "--id", "local_text", "--citation", "田野笔记第七册")
        html_path = self.root / "资料.html"
        html_path.write_text("<html><title>网页档案</title><body><p>记载 OCM 754。</p></body></html>", encoding="utf-8")
        self.draft(str(html_path), "--id", "html_note")
        nested = self.vault / "00_drafts" / "custom_batch"
        nested.mkdir()
        (self.vault / "00_drafts/html_note.md").rename(nested / "html_note.md")
        duplicate = self.draft("--id", "html_note", "--text", "重复资料", success=False)
        self.assertIn("已存在", duplicate.stderr)
        pdf = self.root / "source.pdf"
        self.create_pdf(pdf)
        self.draft(str(pdf), "--id", "pdf_note")
        self.draft("--id", "inline_note", "--text", "没有提供外部书目。")

        summary = self.build_review()
        self.assertEqual(summary["records"], 4)
        self.assertEqual(summary["collections"], {"intake": 4})
        records = {record["id"]: record for record in self.records()}
        self.assertEqual(set(records), {"local_text", "html_note", "pdf_note", "inline_note"})
        self.assertEqual(records["html_note"]["batch"], "custom_batch")
        self.assertEqual(records["local_text"]["standards"]["ocm_codes"], ["754"])
        self.assertTrue(any(flag["code"] == "unmatched_explicit_codes" for flag in records["local_text"]["issues"]))
        unmatched = {(item["system"], item["code"]) for item in records["local_text"]["evidence"]["unmatched_explicit_codes"]}
        self.assertEqual(unmatched, {("OCM", "9999"), ("ATU", "425AB")})
        self.assertIn("PDF 第 1 页", records["pdf_note"]["sources"][0]["locator"])
        self.assertTrue(any(flag["code"] == "source_attribution_missing" for flag in records["inline_note"]["issues"]))
        cached = Path(records["inline_note"]["sources"][0]["local_path"])
        self.assertEqual(cached.read_text(encoding="utf-8"), "没有提供外部书目。")
        self.assertEqual(sha256(cached.read_bytes()).hexdigest(), records["inline_note"]["sources"][0]["content_sha256"])
        self.assertTrue((self.output / "intake.csv").read_bytes().startswith(b"\xef\xbb\xbf"))

        text_path.write_text("来源文件在复核后改变。", encoding="utf-8")
        self.build_review()
        changed = {record["id"]: record for record in self.records()}["local_text"]
        self.assertTrue(any(flag["code"] == "source_hash_mismatch" for flag in changed["issues"]))
        graph = self.root / "graph.json"
        decisions = self.root / "decisions.json"
        entry = {"id": "inline_note", "status": "reviewed", "card_sha256": records["inline_note"]["card_sha256"],
                 "reviewer": "测试复核人", "note": "核对来源", "reviewed_at": datetime.now(timezone.utc).isoformat(),
                 "genre": "memorate"}
        decisions.write_text(json.dumps({"version": 1, "decisions": [entry]}, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, "-X", "utf8", "-m", "pipeline.review_approval", str(decisions),
               "--vault", str(self.vault), "--code-table", str(self.table), "--output", str(graph)]
        check = subprocess.run([*cmd, "--check"], capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertFalse(graph.exists())
        signed = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(signed.returncode, 0, signed.stdout + signed.stderr)
        self.assertEqual([node["id"] for node in json.loads(graph.read_text(encoding="utf-8"))["nodes"]], ["inline_note"])
        self.assertFalse((self.vault / "00_drafts/inline_note.md").exists())
        self.assertTrue((self.vault / "00_drafts/local_text.md").exists())
        self.assertEqual(self.build_review()["records"], 3)

    def test_default_vault_refreshes_review_and_preserves_draft_if_refresh_fails(self):
        args = Namespace(source=None, text="原始文本", encoding=None, id="first_note", title=None,
                         citation="测试来源", source_url=None, doi=None, node_type="case", genre=None,
                         tier=None, code_table=self.table)
        with patch("pipeline.ingest_agent.DEFAULT_VAULT", self.vault), \
             patch("pipeline.review_queue.export", return_value={"records": 1}) as refresh:
            self.assertEqual(draft(args, self.vault, load_code_table(self.table)), 0)
            self.assertEqual(refresh.call_count, 1)
            self.assertTrue((self.vault / "00_drafts/first_note.md").is_file())
        args.id = "second_note"
        with patch("pipeline.ingest_agent.DEFAULT_VAULT", self.vault), \
             patch("pipeline.review_queue.export", side_effect=ValueError("源数据不可用")), \
             redirect_stderr(StringIO()) as error:
            self.assertEqual(draft(args, self.vault, load_code_table(self.table)), 0)
            self.assertTrue((self.vault / "00_drafts/second_note.md").is_file())
            self.assertIn("草稿已保存，但复核清单未更新", error.getvalue())

    def test_missing_or_uncached_sources_are_flagged(self):
        self.draft("--id", "no_source", "--text", "待补来源")
        self.draft("--id", "remote_only", "--text", "待回查网页")
        no_source = self.vault / "00_drafts/no_source.md"
        metadata, body = parse_card(no_source.read_text(encoding="utf-8"))
        no_source.write_bytes(serialize_card(metadata.model_copy(update={"sources": []}), body))
        remote = self.vault / "00_drafts/remote_only.md"
        metadata, body = parse_card(remote.read_text(encoding="utf-8"))
        source = Source.model_validate({"citation": "示例网页", "type": "web_page",
                                        "url": "https://example.org/archive", "locator": "第 1 段"})
        remote.write_bytes(serialize_card(metadata.model_copy(update={"sources": [source]}), body))
        self.build_review()
        records = {record["id"]: record for record in self.records()}
        self.assertTrue(any(flag["code"] == "source_missing" and flag["urgent"]
                            for flag in records["no_source"]["issues"]))
        self.assertTrue({"source_hash_missing", "source_remote_uncached"}.issubset(
            {flag["code"] for flag in records["remote_only"]["issues"]}))

    def test_existing_snapshot_is_never_overwritten(self):
        self.draft("--id", "first_note", "--text", "固定文本")
        card, _ = parse_card((self.vault / "00_drafts/first_note.md").read_text(encoding="utf-8"))
        snapshot = Path(card.sources[0].local_path)
        snapshot.write_text("用户修改的内容", encoding="utf-8")
        result = self.draft("--id", "second_note", "--text", "固定文本", success=False)
        self.assertIn("同名来源快照内容不一致", result.stderr)
        self.assertEqual(snapshot.read_text(encoding="utf-8"), "用户修改的内容")
        self.assertFalse((self.vault / "00_drafts/second_note.md").exists())


if __name__ == "__main__":
    unittest.main()
