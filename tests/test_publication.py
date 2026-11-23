from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from pipeline.ingest_agent import DEFAULT_CODE_TABLE, serialize_card
from pipeline.catalogue import build_catalogue
from pipeline.node_model import Relation
from pipeline.publication import build_public_graph
from pipeline.vault import parse_card


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        for card_id, node_type in (('test_corpus', 'myth_corpus'), ('test_case', 'case')):
            result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pipeline.ingest_agent', 'draft',
                '--vault', str(self.vault), '--id', card_id, '--node-type', node_type,
                '--genre', 'historical_archive', '--text', '用于验证的资料', '--citation', '测试来源'],
                capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path = self.vault / '00_drafts/test_case.md'
        card, body = parse_card(path.read_text(encoding='utf-8'))
        card.relations = [Relation(type='PART_OF_MACRO_TREND', target='test_corpus')]
        path.write_bytes(serialize_card(card, body))

    def decision(self, card_id, *, public=False):
        path = self.vault / '00_drafts' / f'{card_id}.md'
        return {'id': card_id, 'status': 'reviewed', 'card_sha256': sha256(path.read_bytes()).hexdigest(),
                'reviewer': '测试复核人', 'reviewed_at': datetime.now(timezone.utc).isoformat(),
                'note': '内部复核备注', 'public_release': public,
                'public_rights_note': '测试许可依据' if public else None}

    def approve(self, decisions, *, success=True):
        path = self.root / 'decisions.json'
        path.write_text(json.dumps({'version': 1, 'decisions': decisions}, ensure_ascii=False), encoding='utf-8')
        result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pipeline.review_approval', str(path),
            '--vault', str(self.vault), '--output', str(self.root / 'local.json')],
            capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def test_only_cleared_cards_publish_without_private_dependencies_or_review_notes(self):
        self.approve([self.decision('test_corpus'), self.decision('test_case', public=True)])
        local = json.loads((self.root / 'local.json').read_text(encoding='utf-8'))
        self.assertEqual(len(local['nodes']), 2)
        public = build_public_graph(self.vault, DEFAULT_CODE_TABLE)
        self.assertEqual([node['id'] for node in public['nodes']], ['test_case'])
        self.assertEqual(public['links'], [])
        node = public['nodes'][0]
        self.assertEqual(node['relations'], [])
        self.assertEqual(node['audit']['public_rights_note'], '测试许可依据')
        self.assertIsNone(node['audit']['review_note'])
        self.assertTrue(all(source['local_path'] is None for source in node['sources']))
        self.assertEqual(node['source_path'], '公开资料/test_case')

    def test_post_approval_edits_block_publication(self):
        self.approve([self.decision('test_corpus'), self.decision('test_case', public=True)])
        path = self.vault / '01_cases/test_case.md'
        path.write_text(path.read_text(encoding='utf-8') + '\n变更后的资料\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '签核后卡片内容发生变化'):
            build_public_graph(self.vault, DEFAULT_CODE_TABLE)

    def test_public_permission_needs_a_review_and_a_rights_explanation(self):
        bad = self.decision('test_case', public=True)
        bad['public_rights_note'] = '   '
        result = self.approve([bad], success=False)
        self.assertIn('填写许可依据', result.stderr)
        self.assertTrue((self.vault / '00_drafts/test_case.md').exists())

    def test_public_catalogue_preserves_review_state_and_omits_uncleared_text(self):
        graph = build_catalogue(self.vault, DEFAULT_CODE_TABLE)
        self.assertEqual({node['id'] for node in graph['nodes']}, {'test_case', 'test_corpus'})
        self.assertTrue(all(not node['audit']['reviewed_by_human'] for node in graph['nodes']))
        self.assertTrue(all('用于验证的资料' not in node['markdown'] for node in graph['nodes']))
        self.assertTrue(all(source['local_path'] is None for node in graph['nodes'] for source in node['sources']))
        self.assertEqual(len(graph['links']), 1)


if __name__ == '__main__':
    unittest.main()
