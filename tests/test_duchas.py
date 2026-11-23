from pathlib import Path
from hashlib import sha256
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from pydantic import HttpUrl

from pipeline.duchas import CORPUS, INDEX, duchas_cards
from pipeline.enrich_duchas_pages import enrich as enrich_pages
from pipeline.intake_sources import IntakeError
from pipeline.ingest_agent import DEFAULT_CODE_TABLE, serialize_card
from pipeline.node_model import Source
from pipeline.review_queue import duchas_records, other_records
from pipeline.vault import parse_card


class DuchasIntakeTests(unittest.TestCase):
    def test_continuation_pages_extend_sources_without_overwriting_review_edits(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault, snapshots = root / "vault", root / "snapshots"
            folder = vault / "00_drafts/duchas_test"
            folder.mkdir(parents=True)
            snapshots.mkdir()
            (snapshots / "school-123.xml").write_text(
                '<lChapter entryID="123"><schoolName default="Test"/>'
                '<schoolLocation nameEN="Test" lat="53.1" lon="-7.2"/></lChapter>', encoding="utf-8")
            story = snapshots / "story-123-456-789.xml"
            story.write_text('<lStory entryID="789"><chapter default="123" volumeNumber="1"/>'
                             '<page default="456"/><page default="457"/><title default="Fairy Forts"/></lStory>', encoding="utf-8")
            (snapshots / "page-123-456.xml").write_text(
                '<pPage entryID="456"><pageNumber default="1"/><story default="789"/></pPage>', encoding="utf-8")
            case, body = next(duchas_cards([story], include_groups=False))
            case.genre = "memorate"
            case.relations = []
            path = folder / f"{case.id}.md"
            path.write_bytes(serialize_card(case, body + "\n人工笔记保留。\n").replace(
                b"relations: []", b"relations: [] # original comment"))
            initial_flags = {flag["code"] for flag in duchas_records(vault)[0]["issues"]}
            self.assertIn("story_pages_not_cached", initial_flags)
            (snapshots / "page-123-457.xml").write_text(
                '<pPage entryID="457"><pageNumber default="2"/><story default="789"/></pPage>', encoding="utf-8")
            before = path.read_bytes()
            without_groups = enrich_pages(vault, snapshots, check=True)
            self.assertEqual(set(without_groups["missing_groups"]), {CORPUS, INDEX})
            self.assertEqual(without_groups["additional_relations"], 0)
            for group, group_body in list(duchas_cards([story]))[:2]:
                (folder / f"{group.id}.md").write_bytes(serialize_card(group, group_body))
            preview = enrich_pages(vault, snapshots, check=True)
            self.assertEqual((preview["cards"], preview["additional_page_sources"]), (1, 1))
            self.assertEqual(preview["missing_groups"], [])
            self.assertEqual(path.read_bytes(), before)
            result = enrich_pages(vault, snapshots)
            self.assertEqual(result["uncached_pages"], {})
            self.assertEqual(result["additional_relations"], 2)
            updated, text = parse_card(path.read_text(encoding="utf-8"))
            self.assertEqual(updated.genre, "memorate")
            self.assertIn("人工笔记保留。", text)
            self.assertIn("# original comment", path.read_text(encoding="utf-8"))
            self.assertEqual({relation.target for relation in updated.relations}, {CORPUS, INDEX})
            self.assertTrue(any(source.locator and "馆藏页 457" in source.locator for source in updated.sources))
            final = duchas_records(vault)[0]
            self.assertEqual({page["entryID"] for page in final["evidence"]["page_snapshots"]}, {"456", "457"})
            self.assertNotIn("story_pages_not_cached", {flag["code"] for flag in final["issues"]})
            self.assertEqual(enrich_pages(vault, snapshots)["cards"], 0)
            supplemental = root / "补充笔记.txt"
            supplemental.write_text("人工补充笔记", encoding="utf-8")
            updated.sources.append(Source(citation="补充笔记", type="plain_text", local_path=str(supplemental),
                                          content_sha256=sha256(supplemental.read_bytes()).hexdigest()))
            path.write_bytes(serialize_card(updated, text))
            final = duchas_records(vault)[0]
            self.assertEqual(len(final["evidence"]["other_local_sources"]), 1)
            self.assertNotIn("source_snapshot_invalid", {flag["code"] for flag in final["issues"]})

    def test_school_point_and_unknown_story_date(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "school-123.xml").write_text(
                '<lChapter entryID="123"><schoolName default="Example School"/>'
                '<schoolLocation nameEN="Example" lat="53.1" lon="-7.2"/></lChapter>', encoding="utf-8")
            path = folder / "story-123-456-789.xml"
            path.write_text(
                '<lStory entryID="789"><chapter default="123" volumeNumber="0123"/>'
                '<page default="456"/><page default="457"/><title default="Fairy Forts"/></lStory>', encoding="utf-8")
            page = folder / "page-123-456.xml"
            page.write_text('<pPage entryID="456"><pageNumber default="009"/>'
                            '<story default="789"><transcript>' + ' '.join(f"word{i}" for i in range(30))
                            + '</transcript></story></pPage>', encoding="utf-8")
            (folder / "page-123-457.xml").write_text('<pPage entryID="457"><pageNumber default="010"/>'
                                                      '<story default="789"><transcript>later words</transcript></story></pPage>', encoding="utf-8")
            cards = list(duchas_cards([path]))
            self.assertEqual(len(cards), 3)
            case, body = cards[2]
            self.assertEqual(case.genre, "unclassified")
            self.assertFalse(case.audit.reviewed_by_human)
            self.assertEqual((case.spatial.lat, case.spatial.lng), (53.1, -7.2))
            self.assertIn("学校登记地点参照", case.spatial.location_name)
            self.assertEqual((case.temporal.year_start, case.temporal.year_end), (1937, 1939))
            self.assertIn("单条日期", case.temporal.uncertainty_note)
            self.assertEqual({relation.target for relation in case.relations}, {CORPUS, INDEX})
            self.assertTrue(all("CC BY-NC 4.0" in source.citation for source in case.sources))
            self.assertEqual(case.standards.ocm_codes, [])
            self.assertIn("原文", body)
            self.assertIn("word19", body)
            self.assertNotIn("word20", body)
            self.assertTrue(any("印页 009" in source.locator for source in case.sources if source.locator))
            self.assertTrue(any("印页 010" in source.locator for source in case.sources if source.locator))
            self.assertIn("跨 2 页", body)
            path.write_text('<lStory entryID="789"><chapter default="123"/><page default="456"/>'
                            '<title default="Unrelated"/></lStory>', encoding="utf-8")
            with self.assertRaises(IntakeError):
                list(duchas_cards([path]))

            (folder / "school-123.xml").write_text(
                '<lChapter entryID="123"><schoolName default="Example School"/>'
                '<schoolLocation nameEN="Example" lat="NaN" lon="-7.2"/></lChapter>', encoding="utf-8")
            path.write_text('<lStory entryID="789"><chapter default="123"/><page default="456"/>'
                            '<title default="Fairy Forts" date="1938-13-01"/></lStory>', encoding="utf-8")
            case, body = list(duchas_cards([path], include_groups=False))[0]
            self.assertIsNone(case.spatial.lat)
            self.assertIn("1938-13-01", case.temporal.uncertainty_note)
            vault = folder / "vault"
            queue = vault / "00_drafts/duchas_test"
            queue.mkdir(parents=True)
            (queue / f"{case.id}.md").write_bytes(serialize_card(case, body))
            flags = {flag["code"] for flag in duchas_records(vault)[0]["issues"]}
            self.assertIn("school_coordinates_invalid", flags)
            self.assertIn("story_date_invalid", flags)

    def test_incremental_import_reuses_groups_and_skips_existing_story(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            vault.mkdir()
            snapshots = root / "snapshots"
            snapshots.mkdir()

            def make_story(chapter, page, story):
                (snapshots / f"school-{chapter}.xml").write_text(
                    f'<lChapter entryID="{chapter}"><schoolName default="School {chapter}"/>'
                    '<schoolLocation nameEN="Example" lat="53.1" lon="-7.2"/></lChapter>', encoding="utf-8")
                path = snapshots / f"story-{chapter}-{page}-{story}.xml"
                path.write_text(f'<lStory entryID="{story}"><chapter default="{chapter}" volumeNumber="01"/>'
                                f'<page default="{page}"/><title default="Fairy Forts"/></lStory>', encoding="utf-8")
                return path

            first = make_story("123", "456", "789")
            second = make_story("124", "457", "790")

            def run(batch, *paths, success=True, selection=None):
                command = [sys.executable, "-X", "utf8", "-m", "pipeline.import_datasets", "duchas",
                           "--vault", str(vault), "--batch", batch]
                if selection:
                    command += ["--selection", str(selection)]
                result = subprocess.run([*command, "--stories", *map(str, paths)],
                    encoding="utf-8", capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
                return result

            run("duchas_first", first)
            selection = root / "selection.yaml"
            selection.write_text("version: 1\ncandidates:\n  - url: https://www.duchas.ie/en/cbes/124/457/790\n", encoding="utf-8")
            run("duchas_next", first, second, selection=selection)
            manifest = json.loads((vault / "00_drafts/duchas_next/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["counts"]["records"], 1)
            self.assertEqual(manifest["source"]["selection_register"], str(selection.resolve()))
            self.assertEqual(len(manifest["source"]["selection_sha256"]), 64)
            self.assertEqual([path.name for path in (vault / "00_drafts/duchas_next").glob("*.md")], ["case_duchas_790.md"])
            records = duchas_records(vault)
            self.assertEqual(len(records), 4)
            next_case = next(record for record in records if record["id"] == "case_duchas_790")
            self.assertEqual(set(next_case["dependencies"]), {CORPUS, INDEX})
            self.assertFalse(any(flag["code"] == "source_hash_mismatch" for flag in next_case["issues"]))
            duplicate = run("duchas_duplicate", second, second, success=False)
            self.assertIn("多个输入文件", duplicate.stderr)
            self.assertFalse((vault / "00_drafts/duchas_duplicate").exists())
            third = make_story("125", "458", "791")
            manually_named, body = list(duchas_cards([third], include_groups=False))[0]
            manually_named = manually_named.model_copy(update={"id": "case_duchas_custom"})
            manually_named.sources[0] = manually_named.sources[0].model_copy(update={"url": HttpUrl("https://duchas.ie/en/cbes/125/458/791")})
            manually_named.sources[1] = manually_named.sources[1].model_copy(update={"url": HttpUrl("https://duchas.ie/xml/cbes/125/458/791")})
            regional = vault / "00_drafts/regional_sources"
            regional.mkdir()
            (regional / "case_duchas_custom.md").write_bytes(serialize_card(manually_named, body))
            custom = next(record for record in duchas_records(vault) if record["id"] == "case_duchas_custom")
            self.assertEqual(custom["collection"], "duchas")
            self.assertEqual(custom["evidence"]["lStory"]["entryID"], "791")
            self.assertFalse(any(record["id"] == "case_duchas_custom" for record in other_records(vault, DEFAULT_CODE_TABLE)))
            duplicate = run("duchas_duplicate_source", third, success=False)
            self.assertIn("均已入库", duplicate.stderr)
            self.assertFalse((vault / "00_drafts/duchas_duplicate_source").exists())


if __name__ == "__main__":
    unittest.main()
