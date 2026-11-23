from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pipeline.fetch_minyag_wolp import TERMS_URL
from pipeline.fetch_pumi_wolp import CATALOGUE_URL, HOST, fetch
from pipeline.intake_sources import IntakeError


class PumiFetchTests(unittest.TestCase):
    def test_saves_only_two_pages_with_matching_receipts_and_no_overwrite(self):
        terms = b'personal non-commercial use prior written permission proprietary notices'
        catalogue = b'Hu Qianma Wangjiagou forty-five audio files Pumi February 2008 February 2011'
        with TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'snapshot'
            with patch('pipeline.fetch_pumi_wolp.robot_rules', return_value=(object(), '404')) as robots, \
                 patch('pipeline.fetch_pumi_wolp.request_html', side_effect=[(terms, '2026-11-23T00:00:00+00:00'),
                                                                            (catalogue, '2026-11-23T00:00:02+00:00')]) as request:
                manifest = fetch(folder, 2)
            robots.assert_called_once_with(HOST, 2)
            self.assertEqual([call.args[0] for call in request.call_args_list], [TERMS_URL, CATALOGUE_URL])
            self.assertEqual({p.name for p in folder.iterdir()}, {'terms.html', 'catalogue.html', 'manifest.json'})
            self.assertEqual(manifest['pages'][1]['sha256'], sha256(catalogue).hexdigest())
            self.assertEqual(json.loads((folder / 'manifest.json').read_text(encoding='utf-8')), manifest)
            with self.assertRaises(FileExistsError):
                fetch(folder, 2)

    def test_changed_terms_stop_before_catalogue_request(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'snapshot'
            with patch('pipeline.fetch_pumi_wolp.robot_rules', return_value=(object(), '404')), \
                 patch('pipeline.fetch_pumi_wolp.request_html', return_value=(b'changed terms', '2026-11-23T00:00:00+00:00')) as request:
                with self.assertRaises(IntakeError):
                    fetch(folder, 2)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(list(folder.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
