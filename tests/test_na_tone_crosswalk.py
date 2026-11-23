import base64
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.fetch_datacite_na_tone import fetch, validate_envelope
from pipeline.enrich_na_tone import enrich, note
from pipeline.intake_sources import IntakeError
from pipeline.na_tone_book import DATACITE_API, parse_doi_uri
from pipeline.na_tone_crosswalk import build, primary_from_url, requires_primary, rights_conflict
from pipeline.node_model import NodeMetadata
from pipeline.ingest_agent import serialize_card
from pipeline.vault import parse_card


class NaToneCrosswalkTests(unittest.TestCase):
    def test_book_links_and_resource_identity_are_strict(self):
        self.assertEqual(parse_doi_uri('https://doi.org/10.24397/pangloss-0004531#S119'), ('0004531', 'S119'))
        self.assertIsNone(parse_doi_uri('https://example.org/10.24397/pangloss-0004531#S119'))
        self.assertIsNone(parse_doi_uri('https://doi.org/10.24397/pangloss-0004531?other=1'))
        primary = 'cocoon-8784cd43-3edf-3396-b026-bd0fd068578b'
        secondary = 'cocoon-fc5c16dc-541c-324c-b25e-040d65fcd0f0'
        base = 'https://pangloss.cnrs.fr/corpus/show?oai_primary=' + primary
        self.assertEqual(primary_from_url(base + '&oai_secondary=' + secondary), (primary, True))
        self.assertEqual(primary_from_url(base + '&oai_primary=' + primary), (None, False))
        self.assertEqual(primary_from_url(base.replace('pangloss.cnrs.fr', 'example.org')), (None, False))
        attrs = {'relatedIdentifiers': [{'relationType': 'Requires', 'relatedIdentifierType': 'PURL',
                                        'relatedIdentifier': 'http://purl.org/poi/crdo.vjf.cnrs.fr/' + primary}]}
        self.assertTrue(requires_primary(attrs, primary))
        self.assertFalse(requires_primary(attrs, primary[:-1] + 'c'))

    def test_registry_receipt_hash_and_license_wording(self):
        number = '0004531'
        obj = {'data': {'id': '10.24397/pangloss-' + number,
                        'attributes': {'doi': '10.24397/pangloss-' + number, 'state': 'findable'}}}
        raw = json.dumps(obj).encode()
        envelope = {'id': number, 'url': DATACITE_API + number, 'status': 200,
                    'observed_at': '2026-11-23T00:00:00+00:00', 'raw_sha256': sha256(raw).hexdigest(),
                    'raw_base64': base64.b64encode(raw).decode()}
        self.assertEqual(validate_envelope(envelope, number)['doi'], '10.24397/pangloss-' + number)
        with self.assertRaisesRegex(IntakeError, '哈希'):
            validate_envelope({**envelope, 'raw_sha256': '0' * 64}, number)
        with self.assertRaisesRegex(IntakeError, 'DOI'):
            validate_envelope({**envelope, 'id': number, 'raw_base64': base64.b64encode(json.dumps(
                {'data': {'id': 'wrong', 'attributes': obj['data']['attributes']}}).encode()).decode(),
                'raw_sha256': sha256(json.dumps({'data': {'id': 'wrong', 'attributes': obj['data']['attributes']}}).encode()).hexdigest()}, number)
        self.assertTrue(rights_conflict([{'rights': 'Creative Commons Attribution-NonCommercial 2.5 Generic',
                                          'rightsUri': 'http://creativecommons.org/licenses/by-nc-sa/2.5'}]))
        self.assertFalse(rights_conflict([{'rights': 'Creative Commons Attribution-NonCommercial-ShareAlike 2.5',
                                           'rightsUri': 'http://creativecommons.org/licenses/by-nc-sa/2.5'}]))

    def test_crosswalk_requires_unique_proven_parent_and_keeps_conflicts(self):
        primary = 'cocoon-8784cd43-3edf-3396-b026-bd0fd068578b'
        secondary = 'cocoon-fc5c16dc-541c-324c-b25e-040d65fcd0f0'
        base = 'https://pangloss.cnrs.fr/corpus/show?oai_primary=' + primary
        catalogue = {'0000001': {'title': 'Example (version 3)', 'url': base}}
        def link(number, fragment):
            return {'pdf_page': 29, 'printed_page': 'xxiii', 'annotation': 1, 'doi_id': number,
                    'fragment': fragment, 'fragment_kind': 'sentence' if fragment.startswith('S') else 'unknown_fragment',
                    'url': f'https://doi.org/10.24397/pangloss-{number}#{fragment}'}
        links = [link('0000001', 'S1'), link('0000002', 'S2'), link('0000003', 'S3'), link('0000001', '123')]
        table = [{'topic': 'Elders', 'title': 'Elders', 'mentions': [{'doi_id': '0000001', 'version_label': '2'}]},
                 {'topic': 'Dog', 'title': 'Dog', 'mentions': [{'doi_id': '0000001', 'version_label': '1'}]}]
        purl = 'http://purl.org/poi/crdo.vjf.cnrs.fr/' + primary
        direct = {'url': base, 'types': {'resourceTypeGeneral': 'Sound'}}
        text = {'url': base + '&oai_secondary=' + secondary, 'types': {'resourceTypeGeneral': 'Text'},
                'relatedIdentifiers': [{'relationType': 'Requires', 'relatedIdentifierType': 'PURL', 'relatedIdentifier': purl}]}
        orphan = {**text, 'relatedIdentifiers': []}
        registered = {'0000001': direct, '0000002': text, '0000003': orphan}
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'manifest.json').write_text('{}', encoding='utf-8')
            with patch('pipeline.na_tone_crosswalk.extract_links', return_value=links), \
                 patch('pipeline.na_tone_crosswalk.extract_narrative_table', return_value=table), \
                 patch('pipeline.na_tone_crosswalk.checked', return_value=b'catalogue'), \
                 patch('pipeline.na_tone_crosswalk.catalogue_rows', return_value=catalogue), \
                 patch('pipeline.na_tone_crosswalk.load_datacite', return_value=({}, {}, registered)):
                data = build(root / 'book', root / 'tex', root / 'catalogue', root)
        mapping = data['mappings']
        self.assertEqual(mapping['0000002']['catalogue_recording_id'], '0000001')
        self.assertIsNone(mapping['0000003']['catalogue_recording_id'])
        flags = data['recordings']['0000001']['flags']
        self.assertIn('book_table_doi_reused_across_topics', flags)
        self.assertIn('book_catalogue_version_label_differs', flags)
        self.assertIn('book_fragment_unclassified', flags)
        self.assertEqual([x['doi_id'] for x in data['recordings']['0000001']['links']], ['0000001', '0000002', '0000001'])

    def test_enrichment_preserves_human_fields_and_rejects_modified_note(self):
        number = '0004530'
        link = {'pdf_page': 29, 'printed_page': 'xxiii', 'annotation': 1, 'doi_id': number, 'fragment': '',
                'fragment_kind': 'resource', 'url': 'https://doi.org/10.24397/pangloss-' + number,
                'catalogue_recording_id': number, 'basis': '书中 DOI 与目录 DOI 一致'}
        recording = {'recording_id': number, 'catalogue_title': 'Caravanes', 'catalogue_url': 'https://example.org/record',
                     'links': [link], 'table_mentions': [], 'flags': []}
        mapping = {'datacite_checked': False}
        index = {'recordings': {number: recording}, 'mappings': {number: mapping}}
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / 'vault'; folder = vault / '00_drafts/asia_cn_pangloss_na_catalogue'
            folder.mkdir(parents=True)
            book, tex, index_path, registry = root / 'book.pdf', root / 'table.tex', root / 'index.json', root / 'registry'
            registry.mkdir()
            for path in (book, tex, index_path, registry / 'manifest.json'):
                path.write_bytes(b'test')
            metadata = NodeMetadata.model_validate({'id': 'case_cn_yongning_na_' + number, 'title': 'Caravanes',
                'node_type': 'case', 'z_layer': 1, 'genre': 'unclassified', 'credibility_tier': 'B',
                'is_fictional_quarantine': False, 'spatial': None, 'temporal': None, 'standards': {},
                'sources': [{'citation': 'catalogue', 'type': 'pangloss_na_candidate_catalogue',
                             'content_sha256': '85f6c91212d4ca5d7ae29bc1e3caa6a35d248911d0173811055f38409295dbaf'}],
                'audit': {'created_at': '2026-11-22', 'reviewed_by_human': False}})
            path = folder / (metadata.id + '.md')
            path.write_bytes(serialize_card(metadata, '\n## 人工备注\n\n保留此备注。\n'))
            before = path.read_bytes()
            self.assertEqual(enrich(vault, index, book, tex, index_path, registry, check=True)['cards_to_update'], 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(enrich(vault, index, book, tex, index_path, registry)['cards_to_update'], 1)
            after, body = parse_card(path.read_text(encoding='utf-8'))
            self.assertEqual(metadata.model_dump(exclude={'sources'}), after.model_dump(exclude={'sources'}))
            self.assertIn('保留此备注。', body)
            self.assertIn(note(index, number).strip(), body)
            self.assertEqual(enrich(vault, index, book, tex, index_path, registry, check=True)['already_enriched'], 1)
            path.write_text(path.read_text(encoding='utf-8').replace('出版专著的录音与分句引用', '人工改过的书目'), encoding='utf-8')
            with self.assertRaisesRegex(IntakeError, '保留原内容'):
                enrich(vault, index, book, tex, index_path, registry)

    def test_registry_resume_retains_first_response(self):
        identifiers = ['0000001', '0000002']
        selected = {'version': 1, 'fetch_ids': identifiers}
        def envelope(number):
            raw = json.dumps({'data': {'id': '10.24397/pangloss-' + number,
                'attributes': {'doi': '10.24397/pangloss-' + number, 'state': 'findable'}}}).encode()
            return {'id': number, 'url': DATACITE_API + number, 'status': 200,
                    'observed_at': '2026-11-23T00:00:00+00:00', 'raw_sha256': sha256(raw).hexdigest(),
                    'raw_base64': base64.b64encode(raw).decode()}
        with TemporaryDirectory() as temporary:
            root = Path(temporary); folder = root / 'data'
            with patch('pipeline.fetch_datacite_na_tone.selection', return_value=selected), \
                 patch('pipeline.fetch_datacite_na_tone.robot_rules', return_value=(object(), '404')):
                with patch('pipeline.fetch_datacite_na_tone.fetch_one', side_effect=[envelope(identifiers[0]), OSError('interrupted')]):
                    with self.assertRaisesRegex(OSError, 'interrupted'):
                        fetch(root / 'book', root / 'tex', root / 'catalogue', folder)
                first = (folder / 'records/0000001.json').read_bytes()
                self.assertFalse((folder / 'manifest.json').exists())
                with patch('pipeline.fetch_datacite_na_tone.fetch_one', return_value=envelope(identifiers[1])) as retried:
                    manifest = fetch(root / 'book', root / 'tex', root / 'catalogue', folder)
                    self.assertEqual(retried.call_count, 1)
                    self.assertEqual(retried.call_args.args[0], identifiers[1])
                self.assertEqual((folder / 'records/0000001.json').read_bytes(), first)
                self.assertEqual(len(manifest['records']), 2)


if __name__ == '__main__': unittest.main()
