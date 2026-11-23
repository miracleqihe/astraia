from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.chinese_heritage import heritage_cards, register_rows
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.review_queue import export


def fixture() -> bytes:
    lines = ["<div class='gsj_htmlcon_bot'>", "第一批国家级非物质文化遗产名录<br>", "一、民间文学 （共计31项）<br>",
             "序号 编号 项目名称 申报地区或单位<br>"]
    for i in range(1, 32):
        title = "苗族古歌" if i == 1 else "青林寺谜语" if i == 31 else f"项目{i}"
        lines.append(f"{i}　Ⅰ—{i}　　 {title}　　 地区{i}<br>")
        if i == 1:
            lines.append("第二个申报地区<br>")
    lines.append("二、民间音乐<br></div>")
    return "".join(lines).encode("utf-8")


class ChineseHeritageTests(unittest.TestCase):
    def test_register_rows_require_complete_bounded_section(self):
        rows = register_rows(fixture())
        self.assertEqual(len(rows), 31)
        self.assertEqual(rows[0]["area_lines"], ["地区1", "第二个申报地区"])
        with self.assertRaises(IntakeError):
            register_rows(fixture().replace("二、民间音乐".encode(), b""))
        with self.assertRaises(IntakeError):
            register_rows(fixture().replace("Ⅰ—5".encode(), "Ⅰ—6".encode()))

    def test_register_metadata_stays_pending_without_geocoding_or_motif_codes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "register.html"
            source.write_bytes(fixture())
            table = root / "standards.json"
            table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
            vault = root / "vault"
            vault.mkdir()
            manifest = stage_batch(vault, "asia_chinese_heritage_2006", heritage_cards(source), table, {})
            self.assertEqual(manifest["counts"]["records"], 31)
            self.assertEqual(manifest["counts"]["with_coordinates"], 0)
            self.assertEqual(manifest["counts"]["indexed"], 0)
            absent = root / "no-dataset"
            output = root / "review"
            summary = export(vault, output, absent, absent, absent, absent, absent, table, absent)
            self.assertEqual(summary["collections"], {"asia": 31})
            script = (output / "data.js").read_text(encoding="utf-8")
            records = json.loads(script.removeprefix("window.ASTRAIA_REVIEW_DATA=").rstrip()[:-1])["records"]
            first = next(record for record in records if record["id"] == "corpus_cn_ich_2006_01")
            self.assertIsNone(first["spatial"]["lat"])
            self.assertIn("第二个申报地区", first["spatial"]["location_name"])
            self.assertEqual(first["standards"]["atu_types"], [])
            self.assertEqual(first["standards"]["berezkin_codes"], [])
            self.assertEqual(first["sources"][0]["content_sha256"], sha256(fixture()).hexdigest())
            self.assertTrue(any(flag["code"] == "coordinate_missing" for flag in first["issues"]))
            self.assertIn("不是单篇采录原文", first["markdown"])
            self.assertTrue((output / "asia.csv").read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
