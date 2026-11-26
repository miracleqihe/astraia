"""A batch can be checked without importing or silently merging records."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from pipeline.check_regional_batch import check_batches
from pipeline.import_regional_folklore import format_source
from pipeline.node_model import Source


class RegionalBatchCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.graph = {'nodes': [{'id': 'case_existing', 'title': '已有个案',
                                  'aliases': ['相同传闻']},
                                 {'id': 'motif_existing', 'title': '已有母题'}]}
        self.book = {'entries': [{'id': 'BOOK-1', 'body': '知识正文'}]}
        self.record = {
            'id': 'case_new', 'title': '城市｜新故事', 'aliases': ['相同传闻'],
            'genre': 'urban_legend', 'credibility_tier': 'C',
            'location': {'lat': 22.3, 'lng': 114.1, 'precision': 'city', 'location_name': '城市'},
            'location_note': '城市参考点。', 'paragraphs': ['故事第一段。', '故事第二段。'],
            'sources': [{'citation': '口述记录', 'type': 'oral_archive',
                         'url': 'https://example.org/story', 'locator': '正文'}],
            'compare': ['case_existing'],
            'bridge': {'entry': 'BOOK-1', 'cluster': 'sid_liminal', 'trail': 'all',
                       'label': '知识对读', 'rationale': '比较空间叙事。'},
        }

    def write_batch(self, name, records):
        path = self.root / name
        path.write_text(yaml.safe_dump({'records': records}, allow_unicode=True), encoding='utf-8')
        return path

    def test_alias_collision_is_reported_for_human_review(self):
        batch = self.write_batch('one.yaml', [self.record])
        result = check_batches([batch], self.graph, self.book)
        self.assertEqual(result['errors'], [])
        self.assertTrue(any('case_existing' in warning for warning in result['warnings']))
        self.assertEqual(result['records'], 1)

    def test_rejects_duplicates_missing_sources_and_unresolved_bridge(self):
        broken = deepcopy(self.record)
        broken['sources'] = []
        broken['bridge']['entry'] = 'BOOK-MISSING'
        broken['location']['lat'] = None
        broken['location']['lng'] = None
        first = self.write_batch('one.yaml', [self.record])
        second = self.write_batch('two.yaml', [broken])
        result = check_batches([first, second], self.graph, self.book)
        self.assertTrue(any('编号重复' in error for error in result['errors']))
        self.assertTrue(any('缺少出处' in error for error in result['errors']))
        self.assertTrue(any('知识星桥目标' in error for error in result['errors']))
        self.assertTrue(any('地图坐标缺失' in error for error in result['errors']))

    def test_print_source_keeps_locator_without_a_fake_link(self):
        entry = deepcopy(self.record)
        entry['sources'] = [{'citation': '《中国鬼文化大辞典》', 'type': 'book', 'locator': '第 472 页'}]
        result = check_batches([self.write_batch('print.yaml', [entry])], self.graph, self.book)
        self.assertFalse(result['errors'])
        formatted = format_source(1, Source.model_validate(entry['sources'][0]))
        self.assertIn('第 472 页', formatted)
        self.assertNotIn('None', formatted)
        self.assertNotIn('[来源]', formatted)


if __name__ == '__main__':
    unittest.main()
