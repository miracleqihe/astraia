from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipeline.check_lexicon_batch import check_batches


class LexiconBatchCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lexicon = self.root / 'lexicon'
        self.lexicon.mkdir()
        (self.lexicon / 'existing.json').write_text(json.dumps({
            'entries': [{'id': 'lex_old', 'term': '守护之石', 'aliases': ['镇石']}]},
            ensure_ascii=False), encoding='utf-8')
        self.taxonomy = {'domains': [{'id': 'objects', 'groups': [{'hub_ids': ['motif_guard']}]}]}
        self.graph = {'nodes': [{'id': 'motif_guard'}, {'id': 'motif_other'}]}
        self.entry = {'id': 'lex_new', 'hub_id': 'motif_guard', 'term': '镇石',
                      'aliases': [], 'category': '镇物', 'summary': '解释这一民俗器物。',
                      'primary_sources': [{'citation': '馆藏记录', 'url': 'https://example.org/object'}],
                      'secondary_ref': '《中国镇物》第 45 页'}

    def write(self, entry):
        path = self.root / 'candidate.json'
        path.write_text(json.dumps({'domain_id': 'objects', 'entries': [entry]},
                                   ensure_ascii=False), encoding='utf-8')
        return path

    def test_flags_possible_existing_entry_without_overwriting_it(self):
        result = check_batches([self.write(self.entry)], self.lexicon, self.taxonomy, self.graph)
        self.assertFalse(result['errors'])
        self.assertTrue(any('lex_old' in warning for warning in result['warnings']))

    def test_rejects_missing_source_and_hub_outside_domain(self):
        invalid = deepcopy(self.entry)
        invalid['hub_id'] = 'motif_other'
        invalid['primary_sources'] = []
        result = check_batches([self.write(invalid)], self.lexicon, self.taxonomy, self.graph)
        self.assertTrue(any('枢纽' in error for error in result['errors']))
        self.assertTrue(any('原典' in error for error in result['errors']))

    def test_print_source_requires_precise_locator(self):
        book = deepcopy(self.entry)
        book['primary_sources'] = [{'citation': '《中国镇物》', 'locator': '第 45 页'}]
        result = check_batches([self.write(book)], self.lexicon, self.taxonomy, self.graph)
        self.assertFalse(result['errors'])
        book['primary_sources'][0].pop('locator')
        invalid = check_batches([self.write(book)], self.lexicon, self.taxonomy, self.graph)
        self.assertTrue(any('无网址的纸本来源须有页码或章节' in error for error in invalid['errors']))


if __name__ == '__main__':
    unittest.main()
