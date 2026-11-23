from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from pypdf import PdfWriter

from pipeline.build_graph import compile_graph
from pipeline.graph_output import publish_graph
from pipeline.ingest_agent import serialize_card
from pipeline.node_model import Relation
from pipeline.vault import parse_card


class IntakeTests(unittest.TestCase):
    def setUp(self):
        work = TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.vault = self.root / "vault"
        destination = self.vault / "03_motifs_standards"
        destination.mkdir(parents=True)
        index = Path(__file__).resolve().parents[1] / "vault" / destination.name / "index_ocm_754.md"
        shutil.copyfile(index, destination / index.name)
        self.output = self.root / "graph.json"
        publish_graph(self.output, compile_graph(self.vault, include_samples=True), "json")

    def cli(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "pipeline.ingest_agent", *args, "--vault", str(self.vault)],
            encoding="utf-8", capture_output=True, check=False, timeout=30,
        )
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def approve(self, name, *args, success=True):
        return self.cli("approve", name, "--output", str(self.output), *args, success=success)

    def path(self, name):
        return self.vault / "00_drafts" / f"{name}.md"

    def test_review_gate_and_code_table_provenance(self):
        baseline = self.output.read_bytes()
        self.cli("draft", "--id", "field_note", "--title", "中文田野记录", "--citation", "访谈记录 W23",
                 "--text", "本页涉及 ATU 425A、汤普森 C611、别列兹金 a37b 与 ＯＣＭ ７５４。本页另列 OCM 9999。")
        path = self.path("field_note")
        card, body = parse_card(path.read_text(encoding="utf-8"))
        self.assertEqual(card.standards.atu_types, ["425A"])
        self.assertEqual(card.standards.thompson_motifs, ["C611"])
        self.assertEqual(card.standards.berezkin_codes, ["a37b"])
        self.assertEqual(card.standards.ocm_codes, ["754"])
        self.assertEqual(card.sources[0].citation, "访谈记录 W23")
        cached = Path(card.sources[0].local_path)
        self.assertTrue(cached.is_file())
        self.assertIn("OCM 9999", cached.read_text(encoding="utf-8"))
        self.assertIn("未匹配的原文编码", body)
        self.assertIn("OCM `9999`", body)
        self.assertIn("文本第 1 行", body)
        self.assertEqual([node["id"] for node in compile_graph(self.vault, include_samples=True)["nodes"]], ["index_ocm_754"])
        self.assertFalse(card.audit.reviewed_by_human)
        self.assertEqual(self.output.read_bytes(), baseline)

        result = self.approve("field_note", success=False)
        self.assertIn("genre", result.stderr)
        self.approve("field_note", "--genre", "memorate", "--check")
        self.assertTrue(path.is_file())
        self.assertEqual(self.output.read_bytes(), baseline)

        self.approve("field_note", "--genre", "memorate")
        self.assertFalse(path.exists())
        graph = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertTrue(graph["visibility"]["include_samples"])
        self.assertTrue(graph["nodes"][0]["audit"]["reviewed_by_human"])
        self.assertEqual(graph["nodes"][0]["source_path"], "01_cases/field_note.md")
        self.assertEqual(graph["links"][0]["target"], "index_ocm_754")
        self.assertEqual(graph, compile_graph(self.vault, include_samples=True))

    def test_unknown_codes_and_failed_publish_preserve_draft(self):
        baseline = self.output.read_bytes()
        self.cli("draft", "--id", "unmatched", "--text", "没有命中可用的标引。OCM 7547、ATU 425AB 和年份 754。")
        path = self.path("unmatched")
        original = path.read_text(encoding="utf-8")
        card, _ = parse_card(original)
        self.assertEqual(card.standards.model_dump(exclude_none=True), {
            "atu_types": [], "thompson_motifs": [], "berezkin_codes": [], "ocm_codes": [],
        })
        self.cli("draft", "--id", "unmatched", "--text", "尝试覆盖草稿。", success=False)
        self.assertEqual(path.read_text(encoding="utf-8"), original)

        path.write_text(original.replace("ocm_codes: []", "ocm_codes: ['9999']"), encoding="utf-8")
        result = self.approve("unmatched", "--genre", "folktale", success=False)
        self.assertIn("未登记", result.stderr)
        self.assertEqual(self.output.read_bytes(), baseline)
        path.write_text(original, encoding="utf-8")

        blocked_output = self.root / "locked-output"
        blocked_output.mkdir()
        self.cli("approve", "unmatched", "--genre", "folktale", "--output", str(blocked_output), success=False)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertFalse((self.vault / "01_cases" / path.name).exists())
        self.assertEqual(self.output.read_bytes(), baseline)

    def test_linked_batches_publish_together_after_check(self):
        baseline = self.output.read_bytes()
        batches = {}
        for batch, card_id in (("region", "record_region"), ("motif", "record_motif")):
            self.cli("draft", "--id", card_id, "--genre", "folktale", "--text", "来源内容。")
            folder = self.path(card_id).parent / batch
            folder.mkdir()
            batches[batch] = self.path(card_id).rename(folder / f"{card_id}.md")
            (folder / "manifest.json").write_text(json.dumps({"batch": batch, "review_state": "pending"}), encoding="utf-8")
        path = batches["region"]
        card, body = parse_card(path.read_text(encoding="utf-8"))
        card.relations = [Relation(type="COMPARED_WITH", target="record_motif")]
        path.write_bytes(serialize_card(card, body))

        self.cli("approve-batch", "region", "--output", str(self.output), "--check", success=False)
        self.cli("approve-batch", "region", "motif", "--output", str(self.output), "--check")
        self.assertEqual(self.output.read_bytes(), baseline)
        self.assertTrue(all(path.is_file() for path in batches.values()))

        self.cli("approve-batch", "region", "motif", "--output", str(self.output))
        graph = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(graph["links"][0]["target"], "record_motif")
        for path in batches.values():
            manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["review_state"], "review_closed")
            self.assertEqual(manifest["remaining_drafts"], 0)
            self.assertFalse(path.exists())

    def test_web_body_keeps_final_url_and_text_encoding(self):
        body = ('<html><head><title>网页采录</title><meta name="author" content="采录者">'
                '</head><body><nav>OCM 754</nav><article><p>网页正文涉及 OCM 776。</p>'
                '<script>ATU 425A</script></article></body></html>').encode("gb18030")

        class Page(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", "/article")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=gb18030")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Page) as server:
            thread = Thread(target=partial(server.serve_forever, poll_interval=0.05), daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                self.cli("draft", f"{base}/start", "--id", "web_note")
            finally:
                server.shutdown()
                thread.join()
        card, markdown = parse_card(self.path("web_note").read_text(encoding="utf-8"))
        self.assertEqual(str(card.sources[0].url), f"{base}/article")
        self.assertEqual(card.sources[0].citation, "采录者，网页采录")
        self.assertEqual(Path(card.sources[0].local_path).read_bytes(), body)
        self.assertEqual(card.standards.ocm_codes, ["776"])
        self.assertEqual(card.standards.atu_types, [])
        self.assertIn("网页正文第 1 段", markdown)

    def test_pdf_without_text_layer_returns_clear_error(self):
        pdf = self.root / "blank.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=400, height=600)
        writer.write(str(pdf))
        result = self.cli("draft", str(pdf), "--id", "empty_pdf", success=False)
        self.assertIn("OCR", result.stderr)
        self.assertFalse(self.path("empty_pdf").exists())

    def test_access_challenge_is_not_saved_as_source_material(self):
        challenge = self.root / "challenge.html"
        challenge.write_text('<html><title>Security verification | Archive</title><body>'
                             '<h1>Security verification</h1><p>This website uses a security service '
                             'to protect against malicious bots.</p></body></html>', encoding="utf-8")
        result = self.cli("draft", str(challenge), "--id", "challenge", success=False)
        self.assertIn("访问验证页面", result.stderr)
        self.assertFalse(self.path("challenge").exists())
        legitimate = self.root / "article.html"
        legitimate.write_text('<html><title>Security verification</title><body>'
                              '<article><p>Historical archive access practices.</p></article></body></html>', encoding="utf-8")
        self.cli("draft", str(legitimate), "--id", "legitimate")
        self.assertTrue(self.path("legitimate").is_file())
