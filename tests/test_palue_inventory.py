from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.fetch_palue_inventory import fetch, genre_hint, parse_page, selected_item
from pipeline.intake_sources import IntakeError


def item(number: int) -> dict:
    name = f'SD1-{number:03d}'
    return {'type': 'item', 'uuid': f'00000000-0000-0000-0000-{number:012d}', 'name': name,
            'handle': f'10125/{number+10000}', 'metadata': {'dc.title': [{'value': name}],
                'dc.contributor.speaker': [{'value': 'Speaker A'}], 'dc.contributor.recorder': [{'value': 'Recorder B'}],
                'dc.description': [{'value': 'Genre: Folk tale. Title: Cultural content that must not be copied.'}]}}


def document(objects: list[dict]) -> dict:
    return {'sort': {'by': 'dc.title', 'order': 'ASC'}, '_embedded': {'searchResult': {
        'page': {'number': 0, 'size': 50, 'totalElements': len(objects), 'totalPages': 1},
        '_embedded': {'objects': [{'_embedded': {'indexableObject': value}} for value in objects]}}}}


class PalueInventoryTests(unittest.TestCase):
    def test_explicit_genre_and_fields_do_not_copy_narrative(self):
        value = selected_item(item(1))
        self.assertEqual(value['genre_hint'], 'Folk tale')
        self.assertNotIn('dc.description', value['fields'])
        self.assertEqual(value['fields']['dc.contributor.speaker'], ['Speaker A'])
        self.assertEqual(value['fields']['dc.contributor.recorder'], ['Recorder B'])
        self.assertEqual(value['fields']['dc.rights'], [])
        self.assertNotIn('Cultural content', str(value))

    def test_invalid_genre_is_not_saved_and_metadata_can_be_missing(self):
        result, scope = genre_hint({'dc.description': [{'value': 'Genre: medicine: a detailed sensitive procedure'}]})
        self.assertIsNone(result)
        self.assertIn('无法安全提取', scope)
        value = item(1)
        value['metadata']['dc.contributor.speaker'] = []
        self.assertEqual(selected_item(value)['fields']['dc.contributor.speaker'], [])

    def test_sorted_page_and_changed_boundaries_are_checked(self):
        first = document([item(1), item(2)])
        rows, total, pages = parse_page(first, 0)
        self.assertEqual((len(rows), total, pages), (2, 2, 1))
        with self.assertRaises(IntakeError): parse_page(document([item(2), item(1)]), 0)
        changed = document([item(1), item(3)])
        receipt = {'url': 'https://example.invalid', 'sha256': '0' * 64, 'bytes': 1, 'observed_at': '2026-11-23T00:00:00+00:00'}
        with TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'snapshot'
            with patch('pipeline.fetch_palue_inventory.robot_rules', return_value=(object(), '200')), \
                 patch('pipeline.fetch_palue_inventory.request_page', side_effect=[(first, receipt), (changed, receipt)]):
                with self.assertRaisesRegex(IntakeError, '采集期间变化'):
                    fetch(folder, 2)
            self.assertFalse((folder / 'manifest.json').exists())
            self.assertTrue((folder / 'page-000.json').exists())


if __name__ == '__main__':
    unittest.main()
