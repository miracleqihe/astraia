"""Add source-checked project-comparison links to pending 2011 extensions.

Only appends a relation. Existing body, notes, sources and user edits are
preserved; changed source fields, missing targets and signed cards are skipped.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from pipeline.chinese_heritage import SOURCE_URL as URL_2006, register_rows as rows_2006
from pipeline.chinese_heritage_2011 import (SOURCE_URL as URL_2011, evidence as evidence_2011,
                                            register_rows as rows_2011, row_id as id_2011)
from pipeline.chinese_heritage_batches import (CONFIG, base_identity, project_number,
                                                register_rows as rows_batch, row_id as id_batch)
from pipeline.ingest_agent import DEFAULT_VAULT, PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import Relation
from pipeline.source_frontmatter import append_relations
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer

NOTE = '扩展名录沿用原项目序号和行政编号；名称与申报地区须分别核对，不表示单篇故事或传播关系。'


def source_rows(metadata, year: int, cache: dict) -> list[dict]:
    kind = 'heritage_register' if year == 2006 else f'heritage_register_{year}'
    url = URL_2006 if year == 2006 else URL_2011 if year == 2011 else CONFIG[year]['url']
    sources = [s for s in metadata.sources if s.type == kind]
    if len(sources) != 1 or not sources[0].local_path or not sources[0].content_sha256 or str(sources[0].url) != url:
        raise IntakeError(f'{year} 年原表来源不完整。')
    source = sources[0]
    path = Path(source.local_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve(strict=True)
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != source.content_sha256:
        raise IntakeError(f'{year} 年原表哈希不符。')
    key = (path, year, source.content_sha256)
    if key not in cache:
        cache[key] = rows_2006(raw) if year == 2006 else rows_2011(raw) if year == 2011 else rows_batch(raw, year)
    return cache[key]


def enrich(vault: Path, *, check: bool = False) -> dict:
    vault = vault.resolve(strict=True)
    queue = vault / '00_drafts/asia_chinese_heritage_2011'
    cache, plans, skipped, already = {}, [], [], []
    with vault_writer(vault):
        for path in sorted(queue.glob('corpus_cn_ich_2011_ext_*.md')):
            if path.is_symlink():
                skipped.append({'id': path.stem, 'reason': '待审草稿是符号链接'})
                continue
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            try:
                metadata, body = parse_card(text.replace('\r\n', '\n'))
                if metadata.id != path.stem or metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                    raise IntakeError('草稿已签核、为示例或编号不符。')
                found = [row for row in source_rows(metadata, 2011, cache) if id_2011(row) == metadata.id]
                if len(found) != 1 or found[0]['kind'] != '扩展项目':
                    raise IntakeError('2011 年原表行不唯一。')
                row = found[0]
                expected_json = json.dumps(evidence_2011(row), ensure_ascii=False, indent=2)
                if metadata.title != f"2011 年国家级非遗扩展项目 · {row['title']}" or expected_json not in body:
                    raise IntakeError('草稿题名或原表字段已改变。')
                target_id = base_identity(row['index'], project_number(row['project_number']))
                if any(rel.type == 'COMPARED_WITH' and rel.target == target_id for rel in metadata.relations):
                    already.append(metadata.id)
                    continue
                candidates = [p for p in vault.rglob(target_id + '.md') if p.is_file() and not p.is_symlink()]
                if len(candidates) != 1:
                    raise IntakeError('原项目卡片缺失或不唯一。')
                target, _ = parse_card(candidates[0].read_text(encoding='utf-8-sig').replace('\r\n', '\n'))
                if target.id != target_id:
                    raise IntakeError('原项目卡片编号不符。')
                target_year = 2006 if target_id.startswith('corpus_cn_ich_2006_') else 2008
                candidates = source_rows(target, target_year, cache)
                if target_year == 2006:
                    matches = [x for x in candidates if x['index'] == row['index'] and project_number(x['code']) == project_number(row['project_number'])]
                    expected_title = f"国家级非遗名录 · {matches[0]['title']}" if len(matches) == 1 else None
                else:
                    matches = [x for x in candidates if id_batch(x) == target_id and x['kind'] == '新增项目'
                               and x['index'] == row['index'] and x['number'] == project_number(row['project_number'])]
                    expected_title = f"2008 年国家级非遗新增项目 · {matches[0]['title']}" if len(matches) == 1 else None
                if len(matches) != 1 or target.title != expected_title:
                    raise IntakeError('原项目与原表字段不符。')
                relation = Relation.model_validate({'type': 'COMPARED_WITH', 'target': target_id, 'note': NOTE})
                revised = append_relations(text, [relation])
                encoded = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + revised.encode('utf-8')
                checked, _ = parse_card(encoded.decode('utf-8-sig').replace('\r\n', '\n'))
                if checked.id != metadata.id or checked.audit.reviewed_by_human:
                    raise IntakeError('添加关联后的草稿无效。')
                plans.append((path, raw, encoded, target_id))
            except (ValueError, OSError, KeyError, TypeError) as error:
                skipped.append({'id': path.stem, 'reason': str(error)})
        if not check:
            for path, original, revised, _ in plans:
                with NamedTemporaryFile(dir=path.parent, prefix='.heritage-link-', delete=False) as stream:
                    temp = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original:
                        raise IntakeError(f'草稿添加关联时发生变化：{path}')
                    temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)
    return {'check': check, 'updated' if not check else 'to_update': [
        {'id': p.stem, 'target': target, 'before_sha256': sha256(old).hexdigest(), 'after_sha256': sha256(new).hexdigest()}
        for p, old, new, target in plans], 'already_linked': already, 'skipped': skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        raise IntakeError('关联补充报告已存在，不覆盖。')
    result = enrich(args.vault, check=args.check)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
