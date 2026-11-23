import csv
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import quote

from pipeline.archive_fetch import json_bytes
from pipeline.enrich_zibuyu_existing import enrich
from pipeline.fetch_zibuyu import page_url
from pipeline.fetch_zibuyu_talk import fetch as fetch_talk
from pipeline.import_datasets import stage_batch
from pipeline.ingest_agent import serialize_card
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata
from pipeline.review_queue import export
from pipeline.zibuyu import (EXISTING_ID, TALK_URL, card_body, cards, fixed_url, load_snapshot,
                             source_set, volume_id)


class ZibuyuTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshot, self.talk, self.vault = self.root / 'snapshot', self.root / 'talk', self.root / 'vault'
        for path in (self.snapshot, self.talk, self.vault): path.mkdir()
        self.output, self.absent, self.table = self.root / 'review', self.root / 'absent', self.root / 'standards.json'
        self.table.write_text(json.dumps({'version': 1, 'entries': [], 'editions': []}), encoding='utf-8')
        self.prepare_snapshot()

    def prepare_snapshot(self):
        pages, groups = [], []
        for volume in range(1, 25):
            titles = ['李通判', '蔡書生'] if volume == 1 else [f'篇目{volume}']
            indexed = ['李通判', '蔡書生'] if volume == 1 else [f'篇目{volume}']
            if volume == 13: indexed = ['异题13']
            anchors = [f'○{title}' for title in indexed]
            if volume == 8: anchors[0] = '○错误锚点'
            groups.append('<div class="mw-heading"><h3><a href="/wiki/子不語/卷' + str(volume) + '">卷</a></h3></div><table>'
                          + ''.join(f'<a href="/wiki/子不語/卷{volume}#{anchor}">{title}</a>' for title, anchor in zip(indexed, anchors, strict=True))
                          + '</table>')
            note = '<span title="原页提示">□</span>' if volume == 5 else ''
            content = ''.join(f'<div class="mw-heading"><h3 id="○{title}">○{title}</h3></div><p>古文第一行<br/>古文第二行{note}</p>' for title in titles)
            self.write_page(volume, content, pages)
        self.write_page(0, ''.join(groups), pages)
        pages.sort(key=lambda item: item['volume'])
        recheck = {'url': page_url(0), 'revision_id': 100, 'sha256': 'a' * 64, 'bytes': 1,
                   'observed_at': '2026-11-23T00:00:00+00:00'}
        (self.snapshot / 'manifest.json').write_bytes(json_bytes({'version': 1, 'robots_status': '200', 'pages': pages, 'index_recheck': recheck}))
        raw = '<html><script>{"wgRevisionId":335835}</script><p>User:arthursilva 開放文學 2011-12-24</p></html>'.encode('utf-8')
        (self.talk / 'talk.html').write_bytes(raw)
        (self.talk / 'manifest.json').write_bytes(json_bytes({'version': 1, 'url': TALK_URL, 'robots_status': '200',
            'observed_at': '2026-11-23T00:00:00+00:00', 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)}))

    def write_page(self, volume, body, pages):
        title = '子不語' if volume == 0 else f'子不語/卷{volume}'
        rev = 100 + volume
        raw = (f'<html><script>{{"wgRevisionId":{rev}}}</script><h1 id="firstHeading">{title}</h1>'
               f'<div id="mw-content-text"><div class="mw-parser-output">{body}'
               '<table class="ws-footer"></table></div></div></html>').encode('utf-8')
        name = 'index.html' if volume == 0 else f'volume-{volume:02d}.html'
        (self.snapshot / name).write_bytes(raw)
        pages.append({'volume': volume, 'path': name, 'url': page_url(volume), 'sha256': sha256(raw).hexdigest(),
                      'bytes': len(raw), 'observed_at': '2026-11-23T00:00:00+00:00', 'revision_id': rev, 'title': title})

    def prepare_existing(self):
        manifest, _, volumes, _ = load_snapshot(self.snapshot)
        row = volumes[0][0]
        model = NodeMetadata.model_validate({'id': EXISTING_ID, 'title': '《子不语》卷一 · 李通判', 'aliases': ['李通判'],
            'node_type': 'case', 'z_layer': 1, 'genre': 'fabulate', 'credibility_tier': 'A', 'is_fictional_quarantine': False,
            'spatial': {'precision': 'province', 'location_name': '广西（原文所述籍地范围）'}, 'temporal': None,
            'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False},
            'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': volume_id(1)}],
            'sources': source_set(self.snapshot, manifest, row=row)})
        folder = self.vault / '00_drafts/regional_sources'
        folder.mkdir(parents=True)
        (folder / f'{EXISTING_ID}.md').write_bytes(serialize_card(model, card_body(row, manifest)))

    def review(self):
        return export(self.vault, self.output, self.absent, self.absent, self.absent, self.absent, self.absent, self.table, self.absent)

    def test_all_titles_and_existing_card_are_reconciled_without_automatic_identity(self):
        self.prepare_existing()
        result = stage_batch(self.vault, 'asia_cn_zibuyu_wikisource', cards(self.snapshot, self.talk), self.table, {})
        self.assertEqual(result['counts']['records'], 49)
        summary = self.review()
        self.assertEqual(summary['flags']['zibuyu_title_disagreement'], 1)
        self.assertEqual(summary['flags']['zibuyu_anchor_disagreement'], 1)
        self.assertEqual(summary['flags']['zibuyu_inline_annotation'], 1)
        self.assertNotIn('zibuyu_fields_changed', summary['flags'])
        self.assertNotIn('zibuyu_source_changed', summary['flags'])
        with (self.output / 'zibuyu_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 26)  # 25 volume headings and one unmatched directory heading.
        first = next(row for row in rows if row['分卷篇名'] == '李通判')
        self.assertEqual(first['卡片ID'], EXISTING_ID)
        self.assertEqual(first['人工复核'], '待复核')
        self.assertEqual(first['固定修订原文'], fixed_url(1, 101, '○李通判'))
        discrepancy = next(row for row in rows if row['卷次'] == '13' and row['记录类型'] == '分卷标题')
        self.assertEqual(discrepancy['候选方式'], '同序候选，身份待核')
        self.assertEqual(discrepancy['总目录候选题名'], '异题13')
        self.assertEqual(sum(row['记录类型'] == '目录未找到唯一同题' for row in rows), 1)
        self.assertTrue(all(not row['坐标'] and not row['标准码'] for row in rows))
        raw = (self.vault / '00_drafts/asia_cn_zibuyu_wikisource/case_cn_zibuyu_v01_s002.md').read_text(encoding='utf-8')
        self.assertIn('古文第一行\n古文第二行', raw)

    def test_changed_html_or_body_is_not_silently_accepted(self):
        self.prepare_existing()
        stage_batch(self.vault, 'asia_cn_zibuyu_wikisource', cards(self.snapshot, self.talk), self.table, {})
        path = self.vault / '00_drafts/asia_cn_zibuyu_wikisource/case_cn_zibuyu_v01_s002.md'
        path.write_text(path.read_text(encoding='utf-8').replace('古文第二行', '错改'), encoding='utf-8')
        self.assertEqual(self.review()['flags']['zibuyu_fields_changed'], 1)
        with (self.snapshot / 'volume-08.html').open('ab') as stream: stream.write(b' ')
        with self.assertRaises(IntakeError): load_snapshot(self.snapshot)

    def test_new_vault_can_include_first_story(self):
        result = stage_batch(self.vault, 'asia_cn_zibuyu_wikisource',
                             cards(self.snapshot, self.talk, include_existing=True), self.table, {})
        self.assertEqual(result['counts']['records'], 50)
        self.assertTrue((self.vault / '00_drafts/asia_cn_zibuyu_wikisource' / f'{EXISTING_ID}.md').is_file())
        self.assertNotIn('zibuyu_fields_changed', self.review()['flags'])

    def test_existing_card_requires_unchanged_hash_and_retains_backup(self):
        folder = self.vault / '00_drafts/regional_sources'
        folder.mkdir(parents=True)
        model = NodeMetadata.model_validate({'id': EXISTING_ID, 'title': '《子不语》卷一 · 李通判', 'aliases': ['李通判'],
            'node_type': 'case', 'z_layer': 1, 'genre': 'fabulate', 'credibility_tier': 'A', 'is_fictional_quarantine': False,
            'spatial': {'precision': 'province', 'location_name': '广西'}, 'temporal': None, 'standards': {},
            'audit': {'created_at': date.today(), 'reviewed_by_human': False},
            'sources': [{'citation': '旧来源', 'type': 'primary_archive', 'url': 'https://example.org/#李通判', 'locator': '卷一首篇'}]})
        path = folder / f'{EXISTING_ID}.md'
        old = serialize_card(model, '\n## 原有说明\n\n保留。\n')
        path.write_bytes(old)
        expected = sha256(old).hexdigest()
        with self.assertRaises(IntakeError): enrich(self.vault, self.snapshot, '0' * 64, None)
        check = enrich(self.vault, self.snapshot, expected, None)
        self.assertFalse(check['applied'])
        self.assertEqual(path.read_bytes(), old)
        backup = self.root / 'li-backup.md'
        result = enrich(self.vault, self.snapshot, expected, backup, apply=True)
        self.assertTrue(result['applied'])
        self.assertEqual(backup.read_bytes(), old)
        self.assertIn('保留。', path.read_text(encoding='utf-8'))
        self.assertIn('古文第一行\n古文第二行', path.read_text(encoding='utf-8'))
        with self.assertRaises(IntakeError): enrich(self.vault, self.snapshot, expected, backup, apply=True)

    def test_talk_capture_revalidates_and_never_overwrites(self):
        raw = (self.talk / 'talk.html').read_bytes()
        destination = self.root / 'new-talk'
        with patch('pipeline.fetch_zibuyu_talk.robot_rules', return_value=(object(), '200')), \
             patch('pipeline.fetch_zibuyu_talk.request_html', return_value=(raw, '2026-11-23T00:00:00+00:00')):
            receipt = fetch_talk(destination)
            self.assertEqual(receipt['sha256'], sha256(raw).hexdigest())
            with self.assertRaises(FileExistsError): fetch_talk(destination)


if __name__ == '__main__':
    unittest.main()
