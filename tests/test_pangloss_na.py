import csv
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from pipeline.fetch_pangloss_na import download_detail, fetch
from pipeline.import_datasets import stage_batch
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_na import (CORPUS_URL, DOI_BASE, catalogue_rows, compare_credits, compare_dates,
                                   load_snapshots, pangloss_cards)
from pipeline.review_queue import export


def catalogue():
    lines = ['<html><title>Collection Pangloss | corpus yongning_na</title><body>',
             '<table id="m_resources-table">']
    for number, suffix, title, date in [('0004341', '3dd9341b-647a-33d3-b0fd-2b0ab0e7f638', 'Le mariage de la sœur', '2006-11-08'),
                                        ('0004487', 'ff347c68-8747-3516-b2b5-e7b20b5e7774', 'Sister wedding: another speaker', '2009-08-12')]:
        url = f'https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-{suffix}&amp;corpus=Yongning Na'
        lines.append(f'<tr data-corpus="Yongning Na"><td><button data-doi="{DOI_BASE}{number}" data-title="{title}"></button></td>'
                     f'<td class="formats"><svg name="audio"></svg></td><td class="transcr"><svg></svg></td>'
                     f'<td>00:05:12</td><td class="resource-title"><a href="{url}"></a>{title}</td>'
                     f'<td>Michaud, Alexis</td><td>Latami, Dashilame — 拉它米打史拉么</td><td>{date}</td></tr>')
    return ''.join(lines) + '</table></body></html>'


def detail(number, title, date, speaker='Latami, Dashilame; 拉它米打史拉么'):
    return (f'<html><body><h1>{title}<span class="altTitles"><span class="alt-title">中文题名 <small>(zh)</small></span></span>'
            f'<button data-doi="{DOI_BASE}{number}" data-title="{title}"></button></h1><aside id="aside">'
            f'<section><h1>Chercheur(s)</h1>Michaud, Alexis</section><section><h1>Locuteur(s)</h1>{speaker}</section>'
            f'<section><h1>Date d\'enregistrement</h1>{date}</section><section><h1>Lieu d\'enregistrement</h1>'
            f'Chine, province du Yunnan, comté de Yongning</section><section><h1>Licence</h1>'
            f'<a href="http://spdx.org/licenses/CC-BY-NC-SA-2.5">http://spdx.org/licenses/CC-BY-NC-SA-2.5</a>'
            f'</section></aside></body></html>')


class PanglossNaTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.table = self.root / "standards.json"
        self.table.write_text(json.dumps({"version": 1, "entries": [], "editions": []}), encoding="utf-8")
        self.corpus = self.root / "corpus.html"
        self.corpus.write_text(catalogue(), encoding="utf-8")
        self.selection = self.root / "selection.json"
        self.selection.write_text(json.dumps({"version": 1, "corpus_url": CORPUS_URL, "selection_method": "目的性选取",
            "limits": "题名对照待核", "groups": [{"id":"sister", "label":"姐妹出嫁", "ids":["0004341", "0004487"]}]}, ensure_ascii=False), encoding="utf-8")
        entries = []
        for number, title, when in [('0004341', 'Le mariage de la sœur', '08/11/2006'),
                                    ('0004487', 'Sister wedding: another speaker', '12/08/2009')]:
            path = self.root / f'record-{number}.html'
            path.write_text(detail(number, title, when), encoding="utf-8")
            entries.append({"id": number, "path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()})
        self.seed = self.root / "seed.json"
        self.seed.write_text(json.dumps({"version": 1, "records": entries}), encoding="utf-8")
        self.snapshots = self.root / "snapshots"
        self.output = self.root / "review"
        self.absent = self.root / "absent"

    def prepare(self):
        with patch('pipeline.fetch_pangloss_na.robot_rules', return_value=(None, '404')):
            fetch(self.corpus, self.selection, self.snapshots, self.seed)
        return stage_batch(self.vault, 'asia_cn_pangloss_na',
                           pangloss_cards(self.snapshots, self.corpus, self.selection), self.table, {})

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent,
                      self.absent, self.absent, self.table, self.absent)

    def test_versions_credits_dates_and_licenses_remain_distinct(self):
        result = self.prepare()
        self.assertEqual(result["counts"], {"records": 3, "with_coordinates": 0, "with_years": 0, "fiction": 0, "indexed": 0})
        catalog, _, details = load_snapshots(self.snapshots, self.corpus, self.selection)
        self.assertEqual(len(catalog), 2)
        self.assertEqual(details['0004341']['alternate_titles'][0]['title'], '中文题名')
        summary = self.review()
        self.assertEqual(summary['collections'], {'asia': 3})
        self.assertEqual(summary['flags']['pangloss_codes_unassigned'], 3)
        self.assertEqual(summary['flags']['pangloss_license_per_record'], 2)
        self.assertNotIn('pangloss_fields_changed', summary['flags'])
        self.assertNotIn('pangloss_snapshot_invalid', summary['flags'])
        with (self.output / 'pangloss_yongning_na_review.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['馆方详情录音日期原字段'], '08/11/2006')
        self.assertEqual(rows[0]['馆方详情研究者字段'], 'Michaud, Alexis')
        self.assertIn('拉它米打史拉么', rows[0]['馆方详情讲述者字段'])
        self.assertIn('55ad721735d2bfa33fd34a89f57959ff225f16a6', rows[0]['地点对照依据'])
        self.assertTrue(all('CC-BY-NC-SA-2.5' in row['馆方许可原字段'] and not row['坐标'] and not row['标准码']
                            and row['人工复核'] == '待复核' for row in rows))
        self.assertIsNone(compare_dates('2006', '08/11/2006'))
        self.assertEqual(compare_dates('2007', '08/11/2006'), False)
        self.assertEqual(compare_dates('2006-11-08', '09/11/2006'), False)
        self.assertIsNone(compare_dates('2006', 'unknown'))
        self.assertTrue(compare_credits('Latami — 拉它米', 'Latami; 拉它米'))
        self.assertFalse(compare_credits('Latami', 'Lamu'))
        self.assertIsNone(compare_credits('', 'Lamu'))

    def test_tampering_is_flagged_and_resume_does_not_overwrite(self):
        self.prepare()
        with patch('pipeline.fetch_pangloss_na.robot_rules', return_value=(None, '404')):
            fetch(self.corpus, self.selection, self.snapshots, self.seed)
        card = self.vault / '00_drafts/asia_cn_pangloss_na/case_cn_yongning_na_0004341.md'
        raw = card.read_text(encoding='utf-8')
        card.write_text(raw.replace('"馆方详情录音日期原字段": "08/11/2006"',
                                    '"馆方详情录音日期原字段": "09/11/2006"'), encoding='utf-8')
        self.assertEqual(self.review()['flags']['pangloss_fields_changed'], 1)
        page = self.snapshots / 'records/0004341/page.html'
        page.write_bytes(page.read_bytes() + b'changed')
        with self.assertRaises(IntakeError):
            load_snapshots(self.snapshots, self.corpus, self.selection)
        self.assertGreaterEqual(self.review()['flags']['source_hash_mismatch'], 1)

    def test_invalid_record_urls_and_duplicate_ids_fail(self):
        with self.assertRaises(IntakeError):
            catalogue_rows(catalogue().replace('pangloss.cnrs.fr/corpus/show', 'example.com/corpus/show').encode('utf-8'))
        selected = json.loads(self.selection.read_text(encoding='utf-8'))
        selected['groups'][0]['ids'].append('0004341')
        self.selection.write_text(json.dumps(selected,ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(IntakeError):
            list(pangloss_cards(self.snapshots, self.corpus, self.selection))

    def test_database_error_is_retried_and_never_saved_as_metadata(self):
        row = catalogue_rows(self.corpus.read_bytes())['0004341']
        good = (self.root / 'record-0004341.html').read_bytes()
        class FakeResponse(BytesIO):
            status = 200
            headers = type('Headers', (), {'get_content_type': lambda self: 'text/html'})()
            def geturl(self):
                return row['url']
        with patch('pipeline.fetch_pangloss_na.urlopen', side_effect=[FakeResponse(b'Erreur:SQLSTATE[HY000] [2002] Connection refused'),
                                                                      FakeResponse(good)]), patch('pipeline.fetch_pangloss_na.time.sleep') as sleep:
            self.assertEqual(download_detail(row), good)
            sleep.assert_called_once_with(10)
        with (patch('pipeline.fetch_pangloss_na.urlopen', side_effect=lambda *a, **k: FakeResponse(b'SQLSTATE[HY000] Connection refused')),
              patch('pipeline.fetch_pangloss_na.time.sleep')):
            with self.assertRaises(IntakeError):
                download_detail(row)

    def test_rate_limit_stops_without_retry(self):
        row = catalogue_rows(self.corpus.read_bytes())['0004341']
        error = HTTPError(row['url'], 429, 'Too Many Requests', None, None)
        with patch('pipeline.fetch_pangloss_na.urlopen', side_effect=error) as request, patch('pipeline.fetch_pangloss_na.time.sleep') as sleep:
            with self.assertRaisesRegex(IntakeError, '429'):
                download_detail(row)
            request.assert_called_once()
            sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
