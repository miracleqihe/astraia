import unittest

from pipeline.fetch_palue_sample import ITEMS, selected_fields
from pipeline.intake_sources import IntakeError


class PalueMetadataTests(unittest.TestCase):
    def sample(self):
        name, identifier = ITEMS[0]
        metadata = {'dc.title': [{'value': name}], 'dc.contributor.speaker': [{'value': 'Speaker A'}],
                    'dc.contributor.recorder': [{'value': 'Recorder B'}], 'dc.date.begin': [{'value': '2015-06-18'}],
                    'dc.description': [{'value': 'a long cultural account that must not be copied'}]}
        return {'type': 'item', 'uuid': identifier, 'name': name, 'handle': '10125/38948', 'metadata': metadata}

    def test_metadata_summary_keeps_roles_separate_without_copying_description(self):
        name, identifier = ITEMS[0]
        summary = selected_fields(self.sample(), name, identifier)
        self.assertEqual(summary['fields']['dc.contributor.speaker'], ['Speaker A'])
        self.assertEqual(summary['fields']['dc.contributor.recorder'], ['Recorder B'])
        self.assertNotIn('dc.description', summary['fields'])
        self.assertEqual(summary['fields']['dc.rights'], [])

    def test_changed_identity_or_missing_speaker_fails_closed(self):
        name, identifier = ITEMS[0]
        item = self.sample()
        item['uuid'] = 'another-item'
        with self.assertRaises(IntakeError): selected_fields(item, name, identifier)
        item = self.sample()
        item['metadata']['dc.contributor.speaker'] = []
        with self.assertRaises(IntakeError): selected_fields(item, name, identifier)


if __name__ == '__main__':
    unittest.main()
