from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from pipeline.berezkin_distribution import Motif, StudyData, region_crosschecks
from pipeline.enrich_berezkin_coordinates import enrich
from pipeline.ingest_agent import serialize_card
from pipeline.node_model import Audit, NodeMetadata, Source, Spatial, Standards
from pipeline.vault import parse_card


class BerezkinCoordinateReviewTests(unittest.TestCase):
    def test_crosscheck_is_bound_to_original_source_and_coordinates(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            spatial = Spatial(lat=21.2, lng=-66.8, precision="culture_region",
                              location_name="Northern Andes", culture_region="Northern Andes")
            study = StudyData(root / "study.zip", "a" * 64, {}, {55: spatial})
            review = root / "notes.yaml"
            review.write_text("\n".join([
                "version: 1", "checked_at: '2026-11-22'", "method: 示例", "supplement_sha256: " + "a" * 64,
                "regions:", "  55:", "    name: Northern Andes", "    lat: 21.2", "    lng: -66.8",
                "    finding: 待核", "    sources:", "      - title: 测试", "        url: https://example.org",
            ]), encoding="utf-8")
            self.assertEqual(set(region_crosschecks(study, review)), {55})
            different = StudyData(study.path, "b" * 64, {}, study.regions)
            self.assertEqual(region_crosschecks(different, review), {})
            review.write_text(review.read_text(encoding="utf-8").replace("lat: 21.2", "lat: 20.0"), encoding="utf-8")
            with self.assertRaises(ValueError):
                region_crosschecks(study, review)

    def test_notes_preserve_user_edits_and_withhold_only_the_original_point(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "00_drafts" / "berezkin_distribution"
            folder.mkdir(parents=True)
            original = Spatial(lat=21.2, lng=-66.8, precision="culture_region",
                               location_name="Northern Andes", culture_region="Northern Andes")
            edited = Spatial(lat=5.0, lng=-75.0, precision="culture_region",
                             location_name="Reviewer supplied", culture_region="Reviewer supplied")
            llanos = Spatial(lat=18.6, lng=-69.5, precision="culture_region",
                             location_name="Llanos", culture_region="Llanos")
            study = StudyData(root / "study.zip", "a" * 64, {"a1": Motif("example", (55,))},
                              {55: original, 56: llanos})
            notes = {
                55: {"name": "Northern Andes", "lat": 21.2, "lng": -66.8,
                     "finding": "需要对照。", "sources": [{"title": "原始研究", "url": "https://example.org/a"}]},
                56: {"name": "Other", "lat": 18.6, "lng": -69.5,
                     "finding": "需要对照。", "sources": [{"title": "原始研究", "url": "https://example.org/b"}]},
            }

            def write_card(card_id, node_type, spatial):
                metadata = NodeMetadata(
                    id=card_id, title=card_id, node_type=node_type, z_layer=2 if node_type == "myth_corpus" else 3,
                    genre="academic_model", credibility_tier="A", is_fictional_quarantine=False,
                    spatial=spatial, temporal=None, standards=Standards(), sources=[Source(citation="测试", type="research_dataset")],
                    audit=Audit(created_at=date(2026, 1, 1), reviewed_by_human=False),
                )
                path = folder / f"{card_id}.md"
                path.write_bytes(serialize_card(metadata, "\n原有人工笔记。\n"))
                return path

            first = write_card("corpus_berezkin_region_55", "myth_corpus", original)
            second = write_card("corpus_berezkin_region_56", "myth_corpus", edited)
            motif = write_card("index_berezkin_a1", "motif_index", None)
            with patch("pipeline.enrich_berezkin_coordinates.read_study", return_value=study), \
                 patch("pipeline.enrich_berezkin_coordinates.region_crosschecks", return_value=notes):
                result = enrich(root, root / "study.zip")
                self.assertEqual(result["cards_updated"], 3)
                self.assertEqual(result["original_points_withheld"], 1)
                self.assertEqual(result["independently_edited_points_preserved"], 1)
                first_card, first_body = parse_card(first.read_text(encoding="utf-8"))
                second_card, _ = parse_card(second.read_text(encoding="utf-8"))
                _, motif_body = parse_card(motif.read_text(encoding="utf-8"))
                self.assertIsNone(first_card.spatial.lat)
                self.assertEqual(second_card.spatial.lat, 5.0)
                self.assertIn("原有人工笔记。", first_body)
                self.assertIn("21.2", first_body)
                self.assertIn("原始研究", first_body)
                self.assertIn("Northern Andes", motif_body)
                after_first = [path.read_bytes() for path in (first, second, motif)]
                self.assertEqual(enrich(root, root / "study.zip")["cards_updated"], 0)
                self.assertEqual(after_first, [path.read_bytes() for path in (first, second, motif)])


if __name__ == "__main__":
    unittest.main()
