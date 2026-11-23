import unittest

from pipeline.fetch_temiar_wolp import catalogue_rows
from pipeline.intake_sources import IntakeError


def sample() -> str:
    rows = []
    for number in range(1, 51):
        identifier = 100010 if number == 45 else 100000 + number
        rows.append(f'<p>{number}. <strong>Title {number}</strong><br>Sample description.'
                    f'<br><a href="http://www.dspace.cam.ac.uk/handle/1810/{identifier}">[Archive]</a></p>')
    return '<html>Aileen Margaret Robertson ten audio tracks five tracks 1941 Temiar' + ''.join(rows) + '</html>'


class TemiarCatalogueTests(unittest.TestCase):
    def test_repeated_archive_reference_remains_two_catalogue_entries(self):
        rows = catalogue_rows(sample().encode('utf-8'))
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[9]['archive_url'], rows[44]['archive_url'])
        self.assertNotEqual(rows[9]['number'], rows[44]['number'])

    def test_changed_number_or_unexpected_archive_host_is_rejected(self):
        with self.assertRaises(IntakeError):
            catalogue_rows(sample().replace('<p>50.', '<p>51.').encode('utf-8'))
        with self.assertRaises(IntakeError):
            catalogue_rows(sample().replace('www.dspace.cam.ac.uk', 'example.com', 1).encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
