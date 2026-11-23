import csv
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.korea_aks_cards import korea_cards
from pipeline.korea_aks_crosswalk import crosswalk, load_catalogue, load_search
from pipeline.korea_aks_detail import fetch as fetch_details
from pipeline.korea_aks_inventory import FIELDS, MEMBER, SOURCE_URL
from pipeline.korea_aks_reconcile import load_details, reconcile
from pipeline.korea_aks_search import fetch as fetch_search
from pipeline.review_queue import export
from tests.test_korea_aks_search import FakeResponse, html_page
from tests.test_korea_aks_detail import detail_html


class KoreaAKSCardsTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.archive = self.root / 'catalogue.zip'
        self.receipt = self.root / 'receipt.json'
        self.search = self.root / 'search'
        self.details = self.root / 'details'
        self.base = self.root / 'crosswalk.csv'
        self.enriched = self.root / 'detail.csv'
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.table = self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.absent = self.root / 'absent'
        rows = [
            {'서명':'이야기 1','구연자':'김장수','채록지':'서울시-도봉구-미아1동','유형':'설화','텍스트':'tsu_1'},
            {'서명':'알 수 없는 자료','구연자':'','채록지':'서울시-도봉구-미아1동','유형':'기타','텍스트':''},
            {'서명':'다른 지역','구연자':'김장수','채록지':'서울시-종로구','유형':'설화','텍스트':'tsu_3'},
        ]
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator='\r\n')
        writer.writeheader()
        writer.writerows(rows)
        with ZipFile(self.archive, 'w') as zipped:
            zipped.writestr(MEMBER, buffer.getvalue().encode('utf-8-sig'))
        raw = self.archive.read_bytes()
        self.receipt.write_text(json.dumps({'datasetId':'15070383','pageUrl':SOURCE_URL,
            'bytes':len(raw),'sha256':sha256(raw).hexdigest()}), encoding='utf-8')
        rules = type('Rules', (), {'can_fetch':lambda self, *args: True})()
        with patch('pipeline.korea_aks_search._read_robots', return_value=(rules, 'a'*64)), \
             patch('pipeline.korea_aks_search.urlopen', side_effect=lambda req, timeout: FakeResponse(req.full_url, html_page(1, 2))), \
             patch('pipeline.korea_aks_search.time.sleep'), patch('sys.stdout', new_callable=io.StringIO):
            fetch_search(self.search, expected_total=2, delay=3)
        catalogue, archive_hash, member_hash = load_catalogue(self.archive, self.receipt)
        sources, search_hash = load_search(self.search)
        base, _ = crosswalk(catalogue, sources, archive_hash, member_hash)
        self.base.write_bytes(base)
        with patch('pipeline.korea_aks_detail._read_robots', return_value=(rules, 'b'*64)), \
             patch('pipeline.korea_aks_detail.urlopen', side_effect=lambda req, timeout: FakeResponse(req.full_url, detail_html())), \
             patch('pipeline.korea_aks_detail.time.sleep'), patch('sys.stdout', new_callable=io.StringIO):
            fetch_details(self.archive, self.receipt, self.search, self.base, self.details, delay=3)
        details, _ = load_details(self.details, sources, base, archive_hash, member_hash, search_hash)
        enriched, _ = reconcile(base, details)
        self.enriched.write_bytes(enriched)

    def cards(self):
        return korea_cards(self.archive, self.receipt, self.search, self.base, self.details, self.enriched)

    def review(self):
        return export(self.vault, self.root/'review', self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_stages_only_scope_as_pending_and_flags_real_disagreement(self):
        cards = list(self.cards())
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(not card.audit.reviewed_by_human and not card.standards.model_dump()['atu_types'] for card, _ in cards))
        self.assertTrue(all(card.spatial.lat is None and card.spatial.lng is None and card.temporal is None for card, _ in cards))
        self.assertIn('이야기 1', cards[1][1])
        self.assertNotIn('TRANSCRIPTION MUST NOT BE STORED', cards[1][1])
        staged = stage_batch(self.vault, 'asia_kr_aks_dobong', iter(cards), self.table, {})
        self.assertEqual(staged['counts']['records'], 3)
        summary = self.review()
        self.assertEqual(summary['flags']['korea_aks_candidate_unverified'], 1)
        self.assertEqual(summary['flags']['korea_aks_no_candidate'], 1)
        self.assertEqual(summary['flags']['korea_aks_listing_detail_disagreement'], 1)
        self.assertNotIn('korea_aks_snapshot_invalid', summary['flags'])
        self.assertNotIn('korea_aks_fields_changed', summary['flags'])
        with self.assertRaises((IntakeError, FileExistsError)):
            stage_batch(self.vault, 'asia_kr_aks_dobong', self.cards(), self.table, {})

    def test_changed_card_or_snapshot_is_detected_without_overwriting(self):
        stage_batch(self.vault, 'asia_kr_aks_dobong', self.cards(), self.table, {})
        card = self.vault/'00_drafts/asia_kr_aks_dobong/case_kr_aks_dobong_000001.md'
        text = card.read_text(encoding='utf-8')
        card.write_text(text.replace('"서명": "이야기 1"', '"서명": "다른 이야기"'), encoding='utf-8')
        self.assertEqual(self.review()['flags']['korea_aks_fields_changed'], 1)
        page = self.details/'records/POKS.GUBI.GUBI.1_1.json'
        page.write_bytes(page.read_bytes() + b' ')
        summary = self.review()
        self.assertGreaterEqual(summary['flags']['source_hash_mismatch'], 1)
        self.assertGreaterEqual(summary['flags']['korea_aks_snapshot_invalid'], 1)


if __name__ == '__main__':
    unittest.main()
