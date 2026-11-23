import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from pipeline.fetch_lanna import fetch
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.lanna_manuscripts import lanna_cards, load_snapshot
from pipeline.review_queue import export
from tests.test_lao_dllm_fetch import Response, page
from tests.test_lao_manuscripts import item


class LannaManuscriptsTests(unittest.TestCase):
    def setUp(self):
        temporary=TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.snapshots=self.root/'snapshots'
        self.vault=self.root/'vault';self.vault.mkdir()
        self.table=self.root/'standards.json'
        self.table.write_text(json.dumps({'version':1,'entries':[],'editions':[]}),encoding='utf-8')
        self.absent=self.root/'absent'
        self.responses={1:page(1,[item(11,code='shared'),item(12,license_value=False)]),
                        2:page(2,[item(13,code='shared')])}

    def fake(self,request,timeout):
        number=int(parse_qs(urlsplit(request.full_url).query)['page'][0])
        result=Response(self.responses[number]);result.url=request.full_url
        return result

    def capture(self):
        with patch('pipeline.fetch_lanna.rules',return_value=(None,{'status':404,'sha256':None})), \
             patch('pipeline.fetch_lanna.urlopen',side_effect=self.fake),patch('pipeline.fetch_lanna.time.sleep'), \
             patch('sys.stdout',new_callable=io.StringIO):
            return fetch(self.snapshots,delay=2)

    def review(self):
        return export(self.vault,self.root/'review',self.absent,self.absent,self.absent,
                      self.absent,self.absent,self.table,self.absent)

    def test_pending_cards_preserve_sources_and_flag_shared_shelfmark(self):
        self.capture()
        manifest,records=load_snapshot(self.snapshots)
        self.assertEqual((manifest['total_results'],len(records)),(3,3))
        cards=list(lanna_cards(self.snapshots))
        self.assertEqual(len(cards),4)
        self.assertTrue(all(model.spatial.lat is None and model.spatial.lng is None and model.temporal is None for model,_ in cards))
        self.assertTrue(all(not any(model.standards.model_dump().values()) and not model.audit.reviewed_by_human for model,_ in cards))
        self.assertIn('"相同档号馆藏候选": [',cards[1][1])
        self.assertTrue(str(cards[1][0].sources[1].url).endswith('/manifests/11'))
        self.assertEqual(stage_batch(self.vault,'asia_th_lanna_folktales',iter(cards),self.table,{})['counts']['records'],4)
        flags=self.review()['flags']
        self.assertEqual(flags['lanna_duplicate_shelfmark'],2)
        self.assertEqual(flags['lanna_license_unclear'],1)
        self.assertNotIn('lanna_snapshot_invalid',flags)
        self.assertNotIn('lanna_fields_changed',flags)
        with (self.root/'review/lanna_manuscript_review.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),3)
        self.assertTrue(all(not row['坐标'] and not row['标准码'] and row['人工复核']=='待复核' for row in rows))
        self.assertEqual(rows[0]['馆藏纬度原字段'],'17.9639')
        self.assertEqual(rows[0]['同号馆藏候选'],'13')
        with self.assertRaises((FileExistsError,IntakeError)):
            stage_batch(self.vault,'asia_th_lanna_folktales',lanna_cards(self.snapshots),self.table,{})

    def test_missing_or_changed_receipt_stops_without_overwriting(self):
        self.capture()
        (self.snapshots/'manifest.json').unlink()
        page_path=self.snapshots/'page-001.json';before=page_path.read_bytes()
        page_path.write_bytes(before+b' ')
        with patch('pipeline.fetch_lanna.rules',return_value=(None,{'status':404,'sha256':None})), \
             patch('pipeline.fetch_lanna.urlopen',side_effect=self.fake),patch('pipeline.fetch_lanna.time.sleep'):
            with self.assertRaises(IntakeError):fetch(self.snapshots,delay=2)
        self.assertEqual(page_path.read_bytes(),before+b' ')


if __name__=='__main__':unittest.main()
