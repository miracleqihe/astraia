from email.message import Message
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from pipeline.fetch_lao_dllm import fetch, parse_page
from pipeline.intake_sources import IntakeError


def item(identifier, category="Folk Tale"):
    return {"resource_id": f"urn:madoc:manifest:{identifier}", "resource_type": "Manifest",
            "metadata": [{"label": {"en": ["dc:subject"]}, "value": {"en": [category]}}]}


def page(number, entries, *, total=3, total_pages=2, size=2):
    return json.dumps({"pagination": {"page": number, "pageSize": size, "totalPages": total_pages,
                                     "totalResults": total}, "results": entries, "facets": {}}, ensure_ascii=False).encode()


class Response:
    def __init__(self, content, content_type="application/json"):
        self.content = content
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, maximum): return self.content[:maximum]


class LaoFetchTests(unittest.TestCase):
    def test_fetch_validates_pages_and_never_overwrites_completed_snapshot(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            responses = {1: page(1, [item(11), item(12)]), 2: page(2, [item(13)])}
            (folder / "page-001.json").write_bytes(responses[1])
            def request(req, timeout):
                number = int(parse_qs(urlsplit(req.full_url).query)["page"][0])
                self.assertEqual(req.get_method(), "POST")
                self.assertEqual(json.loads(req.data)["facets"][0]["value"], "Folk Tale")
                return Response(responses[number])
            with patch("pipeline.fetch_lao_dllm.urlopen", side_effect=request) as network, \
                 patch("pipeline.fetch_lao_dllm.time.sleep"):
                manifest = fetch(folder)
                self.assertEqual(network.call_count, 1)
            self.assertEqual((manifest["total_results"], manifest["total_pages"]), (3, 2))
            self.assertEqual((folder / "page-001.json").read_bytes(), responses[1])
            self.assertIsNone(manifest["pages"][0]["retrieved_at"])
            with self.assertRaisesRegex(IntakeError, "已有完整批次"):
                fetch(folder)

    def test_rejects_mixed_categories_and_duplicate_identifiers(self):
        with self.assertRaisesRegex(IntakeError, "不属于"):
            parse_page(page(1, [item(11, "Medicine"), item(12)]), 1)
        with TemporaryDirectory() as temporary, \
             patch("pipeline.fetch_lao_dllm.urlopen", side_effect=[Response(page(1, [item(11), item(12)])),
                                                                    Response(page(2, [item(11)]))]), \
             patch("pipeline.fetch_lao_dllm.time.sleep"):
            folder = Path(temporary)
            with self.assertRaisesRegex(IntakeError, "重复馆藏编号"):
                fetch(folder)
            self.assertFalse((folder / "manifest.json").exists())
            self.assertTrue((folder / "page-001.json").exists())


if __name__ == "__main__":
    unittest.main()
