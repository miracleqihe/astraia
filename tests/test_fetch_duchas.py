from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from pipeline.fetch_duchas import candidates, fetch
from pipeline.intake_sources import IntakeError


class DuchasFetchTests(unittest.TestCase):
    def test_public_xml_validation_and_cached_snapshots(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = {"url": "https://www.duchas.ie/en/cbes/123/456/789", "context": "Example",
                         "chapter": "123", "page": "456", "story": "789"}
            payloads = {
                "https://www.duchas.ie/robots.txt": b"User-agent: *\nCrawl-delay: 2\n",
                "https://www.duchas.ie/xml/cbes/123/456/789":
                    b'<lStory entryID="789"><chapter default="123"/><page default="456"/><page default="457"/><title default="Fairy Forts"/></lStory>',
                "https://www.duchas.ie/xml/cbes/123": b'<lChapter entryID="123"/>',
                "https://www.duchas.ie/xml/cbes/123/456": b'<pPage entryID="456"><story default="789"/></pPage>',
                "https://www.duchas.ie/xml/cbes/123/457": b'<pPage entryID="457"><story default="789"/></pPage>',
            }
            calls = []

            def remote(url):
                calls.append(url)
                return payloads[url]

            with patch("pipeline.fetch_duchas.read_remote", side_effect=remote), \
                 patch("pipeline.fetch_duchas.time.sleep"):
                result = fetch([candidate], root, include_all_pages=True)
                self.assertEqual(result["ready"], 1)
                self.assertGreaterEqual(result["crawl_delay_seconds"], 2)
                self.assertEqual(len(calls), 5)
                self.assertEqual(result["results"][0]["files"]["story"]["state"], "downloaded")
                self.assertTrue((root / "page-123-457.xml").is_file())
                calls.clear()
                result = fetch([candidate], root, include_all_pages=True)
                self.assertEqual(result["ready"], 1)
                self.assertEqual(calls, ["https://www.duchas.ie/robots.txt"])
                self.assertEqual(result["results"][0]["files"]["story"]["state"], "cached")
                story = root / "story-123-456-789.xml"
                story.write_text('<lStory entryID="999"/>', encoding="utf-8")
                result = fetch([candidate], root)
                self.assertEqual(result["ready"], 0)
                self.assertEqual(result["results"][0]["status"], "stopped")
                self.assertIn('entryID="999"', story.read_text(encoding="utf-8"))

    def test_candidate_urls_require_official_host_and_unique_story(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "candidates.yaml"
            path.write_text("version: 1\ncandidates:\n  - url: https://example.com/en/cbes/1/2/3\n", encoding="utf-8")
            with self.assertRaises(IntakeError):
                candidates(path)
            path.write_text("version: 1\ncandidates:\n  - url: https://www.duchas.ie/en/cbes/1/2/3\n"
                            "  - url: https://www.duchas.ie/en/cbes/1/4/3\n", encoding="utf-8")
            with self.assertRaises(IntakeError):
                candidates(path)


if __name__ == "__main__":
    unittest.main()
