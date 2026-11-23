import csv
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import tests.test_pangloss_na as fixture
from pipeline.enrich_pangloss_annotations import MARKER, enrich
from pipeline.fetch_pangloss_annotations import collect
from pipeline.intake_sources import IntakeError
from pipeline.pangloss_annotations import API, parse_annotations, parse_primary, parse_xml, read_index, viewer_url


P1 = 'cocoon-3dd9341b-647a-33d3-b0fd-2b0ab0e7f638'
P2 = 'cocoon-ff347c68-8747-3516-b2b5-e7b20b5e7774'
MEDIA = 'cocoon-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
ANNOTATION = 'cocoon-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
TEXT = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE TEXT SYSTEM "https://cocoon.huma-num.fr/schemas/Archive.dtd">
<TEXT id="synthetic" xml:lang="nru"><NOTE xml:lang="en">private sample note</NOTE>
 <S id="original-A"><AUDIO start="0.1" end="1.2"/><FORM kindOf="phono">private sample utterance</FORM><TRANSL xml:lang="zh">私有样本文字</TRANSL></S>
 <S id="original-B"><AUDIO start="2" end="3"/><FORM kindOf="ortho">sample second sentence</FORM><TRANSL xml:lang="fr">sample translation</TRANSL></S>
 <S id="original-C"><AUDIO start="bad" end="0"/></S>
</TEXT>'''


def primary(oai):
    prefix = 'oai:crdo.vjf.cnrs.fr:'
    def resource(identifier, links):
        return {'oai': identifier, 'format': 'audio', 'licence': 'audio license only',
                'related_resources': json.dumps(links)}
    if oai == P1:
        objects = [resource(P1, {'primary': [prefix + MEDIA]}),
                   resource(MEDIA, {'primary': [prefix + P1], 'secondary': [prefix + ANNOTATION]})]
    elif oai == P2:
        objects = [resource(P2, {})]
    else:
        raise AssertionError(oai)
    return json.dumps({'success': True, 'object': objects}).encode('utf-8')


def annotations(oai=ANNOTATION, content=TEXT):
    return json.dumps([{'oai': oai, 'type': 'xml', 'doi': 'https://doi.org/10.24397/pangloss-0000001',
                        'content': content}], ensure_ascii=False).encode('utf-8')


def fake_api(params, delay):
    assert delay >= 2
    if params['action'] == 'getresourcesByOAI':
        raw = primary(params['oai'])
    elif params['action'] == 'getAnnotations':
        assert json.loads(params['oais']) == [ANNOTATION]
        raw = annotations()
    else:
        raise AssertionError(params)
    return raw, API + '?' + urlencode(params)


class PanglossAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.PanglossNaTests('test_invalid_record_urls_and_duplicate_ids_fail')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.prepare()
        self.folder = self.fixture.root / 'annotation-index'

    def collect(self):
        with (patch('pipeline.fetch_pangloss_annotations.robot_rules', return_value=(None, '404')),
              patch('pipeline.fetch_pangloss_annotations.request_api', side_effect=fake_api)):
            return collect(self.fixture.vault, self.fixture.corpus, self.fixture.selection,
                           self.fixture.snapshots, self.folder)

    def enrich(self, check=False):
        return enrich(self.fixture.vault, self.fixture.corpus, self.fixture.selection,
                      self.fixture.snapshots, self.folder, check=check)

    def test_structural_index_preserves_resource_ownership_without_copying_text(self):
        resources = parse_primary(primary(P1), P1)
        self.assertEqual(resources[1]['secondary'], [ANNOTATION])
        item = parse_annotations(annotations(), [ANNOTATION], MEDIA)[0]
        self.assertEqual(item['segments'][0]['xml_id'], 'original-A')
        self.assertEqual(item['segments'][0]['translation_languages'], ['zh'])
        self.assertEqual(item['segments'][2]['time_status'], 'invalid')
        self.assertIsNone(item['license'])
        target = viewer_url(MEDIA, ANNOTATION, 2)
        self.assertIn('oai_primary=' + MEDIA, target)
        self.assertTrue(target.endswith('#S2'))
        self.assertNotIn('original-B', target)
        structural = json.dumps(item, ensure_ascii=False)
        self.assertNotIn('private sample utterance', structural)
        self.assertNotIn('私有样本文字', structural)
        self.assertNotIn('private sample note', structural)
        with self.assertRaises(IntakeError):
            parse_primary(primary(P1), P2)
        with self.assertRaises(IntakeError):
            parse_annotations(annotations(), [], MEDIA)
        with self.assertRaises(IntakeError):
            viewer_url('bad-resource', ANNOTATION, 1)

    def test_unsafe_xml_is_rejected(self):
        with self.assertRaises(IntakeError):
            parse_xml('<!DOCTYPE TEXT [<!ENTITY a SYSTEM "file:///secret">]><TEXT>&a;</TEXT>')
        with self.assertRaises(IntakeError):
            parse_xml('<!DOCTYPE TEXT SYSTEM "https://example.org/other.dtd"><TEXT/>')

    def test_collection_enrichment_review_and_changed_card_protection(self):
        manifest = self.collect()
        self.assertEqual(len(manifest['records']), 2)
        indexed = (self.folder / 'record-0004341.json').read_text(encoding='utf-8')
        for protected in ('private sample utterance', '私有样本文字', 'private sample note', 'sample translation'):
            self.assertNotIn(protected, indexed)
        altered = json.loads(indexed)
        altered['resources'][1]['annotations'][0]['segments'][0]['time_status'] = 'invalid'
        altered_path = self.folder / 'altered.json'
        altered_path.write_text(json.dumps(altered), encoding='utf-8')
        selection = json.loads((self.folder / 'selection.json').read_text(encoding='utf-8'))
        with self.assertRaises(IntakeError):
            read_index(altered_path, selection['records'][0])
        self.assertEqual(self.enrich(check=True)['cards_to_update'], 2)
        changed = self.fixture.vault / '00_drafts/asia_cn_pangloss_na/case_cn_yongning_na_0004487.md'
        changed.write_text(changed.read_text(encoding='utf-8') + '\n用户手工补充\n', encoding='utf-8')
        result = self.enrich()
        self.assertEqual(result['cards_to_update'], 1)
        self.assertEqual(result['skipped'][0]['id'], '0004487')
        self.assertIn('用户手工补充', changed.read_text(encoding='utf-8'))
        card = self.fixture.vault / '00_drafts/asia_cn_pangloss_na/case_cn_yongning_na_0004341.md'
        text = card.read_text(encoding='utf-8')
        self.assertIn(MARKER, text)
        self.assertIn('原始响应和转写正文', text)
        self.assertNotIn('private sample utterance', text)
        self.assertEqual(self.enrich()['already_enriched'], 1)
        summary = self.fixture.review()
        self.assertEqual(summary['flags']['pangloss_annotation_license_unverified'], 1)
        self.assertNotIn('pangloss_annotation_fields_changed', summary['flags'])
        with (self.fixture.output / 'pangloss_yongning_na_segments.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3)
        self.assertIn('oai_primary=' + MEDIA, rows[1]['原站分句链接'])
        self.assertTrue(rows[1]['原站分句链接'].endswith('#S2'))
        self.assertEqual(rows[1]['附件单独许可'], '尚未核明')
        self.assertTrue(rows[1]['接口观察时间'].endswith('+00:00'))
        index_file = self.folder / 'record-0004341.json'
        index_file.write_text(index_file.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        with self.assertRaises(IntakeError):
            self.collect()
        with self.assertRaises(IntakeError):
            self.enrich()
        self.assertGreaterEqual(self.fixture.review()['flags']['source_hash_mismatch'], 1)


if __name__ == '__main__':
    unittest.main()
