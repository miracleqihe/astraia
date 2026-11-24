from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from pipeline.enrich_yuhuan_readings import (
    BATCH, MARKER, NEW_LOCATION, NEW_PUBLICATION, OLD_LOCATION, OLD_PUBLICATION,
    apply_updates, plan_updates,
)
from pipeline.ingest_agent import DEFAULT_VAULT, serialize_card
from pipeline.node_model import NodeMetadata
from pipeline.vault import parse_card


class YuhuanReadingImportTest(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.vault = root / 'vault'
        cards = self.vault / '00_drafts/asia_yuhuan_2008'
        cards.mkdir(parents=True)
        self.scan = root / 'scan.pdf'
        self.scan.write_bytes(b'synthetic scan fixture')
        digest = sha256(self.scan.read_bytes()).hexdigest()
        batch = yaml.safe_load(BATCH.read_text(encoding='utf-8'))
        record = batch['records'][0]
        self.card = cards / (record['id'] + '.md')
        metadata, body = parse_card((DEFAULT_VAULT / '00_drafts/asia_yuhuan_2008' / self.card.name)
                                    .read_text(encoding='utf-8'))
        data = metadata.model_dump(mode='json')
        data['genre'] = 'unclassified'
        data['spatial'] = {'lat': None, 'lng': None, 'precision': 'culture_region',
                           'location_name': '测试地区', 'culture_region': 'East Asia'}
        data['sources'] = [source for source in data['sources'] if source['type'] != 'map_reference']
        for source in data['sources']:
            if source['type'] == 'yuhuan_scan':
                source['content_sha256'] = digest
        body = body.split(MARKER, 1)[0].rstrip() + '\n'
        body = body.replace(NEW_LOCATION, OLD_LOCATION).replace(NEW_PUBLICATION, OLD_PUBLICATION)
        self.card.write_bytes(serialize_card(NodeMetadata.model_validate(data), body))
        (cards / 'corpus_cn_yuhuan_2008.md').write_bytes(
            (DEFAULT_VAULT / '00_drafts/asia_yuhuan_2008/corpus_cn_yuhuan_2008.md').read_bytes())
        self.notes = root / 'notes.yaml'
        self.notes.write_text('{}\n', encoding='utf-8')
        record['original_sha256'] = sha256(self.card.read_bytes()).hexdigest()
        batch['pdf_sha256'], batch['records'] = digest, [record]
        self.batch = root / 'batch.yaml'
        self.batch.write_text(yaml.safe_dump(batch, allow_unicode=True, sort_keys=False), encoding='utf-8')
        self.node_id = record['id']

    def plan(self):
        return plan_updates(self.batch, self.vault, self.notes, self.scan)

    def test_reading_and_regional_anchor_preserve_audit_and_sources(self):
        original, _ = parse_card(self.card.read_text(encoding='utf-8'))
        updates = self.plan()
        self.assertEqual(len(updates), 2)
        apply_updates(updates)
        revised, body = parse_card(self.card.read_text(encoding='utf-8'))
        notes = yaml.safe_load(self.notes.read_text(encoding='utf-8'))
        self.assertFalse(revised.audit.reviewed_by_human)
        self.assertEqual(revised.standards, original.standards)
        self.assertEqual(revised.sources[:len(original.sources)], original.sources)
        self.assertEqual(revised.spatial.precision, 'city')
        self.assertIsNotNone(revised.spatial.lat)
        self.assertIn('不是具体采录地', notes[self.node_id]['location_note'])
        self.assertIn(notes[self.node_id]['paragraphs'][0], body)
        self.assertIn('corpus_cn_yuhuan_2008', notes)
        with self.assertRaises(ValueError):
            self.plan()  # Reapplying cannot overwrite an existing editorial note.

    def test_unexpected_card_or_source_does_not_write(self):
        original = self.card.read_bytes()
        self.scan.write_bytes(b'changed scan')
        with self.assertRaisesRegex(ValueError, '哈希'):
            self.plan()
        self.assertEqual(self.card.read_bytes(), original)
        self.assertEqual(self.notes.read_text(encoding='utf-8'), '{}\n')


if __name__ == '__main__':
    unittest.main()
