"""Append verified Pangloss detail snapshots to unchanged, pending recordings."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

from pipeline.ingest_agent import DEFAULT_VAULT, literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import Source
from pipeline.pangloss_japhug import recording_evidence
from pipeline.pangloss_na import json_object, load_snapshots
from pipeline.pangloss_supplement import CONFIG, MARKER, OLD_CITATION, NEW_CITATION, validate_selection
from pipeline.source_frontmatter import append_sources
from pipeline.vault import parse_card
from pipeline.vault_write import vault_writer


def enrich(vault: Path, corpus: Path, initial: Path, folder: Path, kind: str, *, check: bool = False) -> dict:
    # Imported lazily to avoid a module cycle while the review exporter uses our selection validator.
    from pipeline.review_queue import json_block_preserved

    if kind not in CONFIG:
        raise IntakeError('不支持的 Pangloss 语料。')
    config = CONFIG[kind]
    selection_path, manifest_path = folder/'selection.json', folder/'manifest.json'
    selection = json_object(selection_path)
    catalog, group = validate_selection(selection, corpus, initial, kind)
    loaded_catalog, loaded_selection, details = load_snapshots(folder, corpus, selection_path,
        corpus_name=config['name'], corpus_url=config['url'])
    if loaded_catalog != catalog or loaded_selection != selection or set(details) != set(group['ids']):
        raise IntakeError('补充详情清单与选取范围不符。')
    manifest = json_object(manifest_path)
    detail_hashes = {entry['id']:entry['sha256'] for entry in manifest['records']}
    selection_hash, manifest_hash = sha256(selection_path.read_bytes()).hexdigest(), sha256(manifest_path.read_bytes()).hexdigest()
    corpus_hash, initial_hash = sha256(corpus.read_bytes()).hexdigest(), sha256(initial.read_bytes()).hexdigest()
    plans, skipped, already = [], [], 0
    cards = vault/'00_drafts'/config['folder']
    with vault_writer(vault):
        for number in group['ids']:
            row, fields = catalog[number], details[number]
            path = cards/f"{config['prefix']}{number}.md"
            if not path.is_file() or path.is_symlink():
                skipped.append({'id':number,'reason':'待审草稿不存在或是符号链接'})
                continue
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            metadata, _ = parse_card(text.replace('\r\n','\n'))
            if metadata.audit.reviewed_by_human or metadata.audit.is_sample:
                skipped.append({'id':number,'reason':'已签核或为示例'})
                continue
            detail_path = folder/'records'/number/'page.html'
            detail_hash = sha256(detail_path.read_bytes()).hexdigest()
            if detail_hash != detail_hashes[number]:
                raise IntakeError(f'详情快照在补充期间与清单不符：{number}')
            existing = [source for source in metadata.sources if source.type == f"{config['source']}_supplement_detail"]
            if existing:
                selection_sources = [source for source in metadata.sources if source.type == f"{config['source']}_supplement_selection"]
                manifest_sources = [source for source in metadata.sources if source.type == f"{config['source']}_supplement_manifest"]
                if (len(existing) == len(selection_sources) == len(manifest_sources) == 1
                        and existing[0].content_sha256 == detail_hash and str(existing[0].url) == row['url']
                        and selection_sources[0].content_sha256 == selection_hash and manifest_sources[0].content_sha256 == manifest_hash
                        and MARKER in text and json_block_preserved(text.replace('\r\n','\n'),
                                                                   {'详情补充':recording_evidence(row,fields,group)})):
                    already += 1
                else:
                    skipped.append({'id':number,'reason':'已有不同或不完整的补充详情'})
                continue
            if MARKER in text:
                skipped.append({'id':number,'reason':'已有补充标记但缺少来源'})
                continue
            if sha256(raw).hexdigest() != selection['card_sha256'][number]:
                skipped.append({'id':number,'reason':'选取后草稿发生变化；保留现有修改'})
                continue
            originals = [source for source in metadata.sources if source.type == f"{config['source']}_original"]
            if (metadata.id != path.stem or len(originals) != 1 or originals[0].citation != OLD_CITATION
                    or str(originals[0].url) != row['url'] or originals[0].doi != row['doi'].removeprefix('https://doi.org/')
                    or originals[0].locator != f'录音 {number}' or originals[0].local_path or originals[0].content_sha256
                    or text.count(OLD_CITATION) != 1 or text.count('## 馆方录音目录字段') != 1
                    or not json_block_preserved(text.replace('\r\n','\n'),recording_evidence(row,None,None))):
                skipped.append({'id':number,'reason':'原始来源或目录字段已变化；保留现有修改'})
                continue
            additions = [
                Source.model_validate({'citation':'CNRS-LACITO，馆方单条录音详情后续补充；具体许可见原字段。',
                    'type':f"{config['source']}_supplement_detail",'url':row['url'],
                    'doi':row['doi'].removeprefix('https://doi.org/'),'locator':f'录音 {number} / 补充详情',
                    'local_path':display_path(detail_path),'content_sha256':detail_hash}),
                Source.model_validate({'citation':'Astraia 后续详情选取清单；保存采集前草稿哈希。',
                    'type':f"{config['source']}_supplement_selection",'url':config['url'],
                    'locator':f'录音 {number} / 补充选取','local_path':display_path(selection_path),'content_sha256':selection_hash}),
                Source.model_validate({'citation':'Astraia 馆方详情快照清单；记录逐条来源哈希。',
                    'type':f"{config['source']}_supplement_manifest",'url':config['url'],
                    'locator':f'录音 {number} / 补充清单','local_path':display_path(manifest_path),'content_sha256':manifest_hash}),
            ]
            revised = append_sources(text,additions).replace(OLD_CITATION,NEW_CITATION,1)
            revised = revised.replace('## 馆方录音目录字段','## 首轮馆方录音目录字段（历史状态）',1)
            data = recording_evidence(row,fields,group)
            note = ('\n\n'+MARKER+'\n## 馆方详情补充（待复核）\n\n'
                    +literal_block(json.dumps({'详情补充':data},ensure_ascii=False,indent=2))
                    +'\n\n上述字段来自后续馆方详情快照；原有目录字段与人工备注保留。'
                     '录音地点、讲述者来源地和叙事发生地须区分；许可、体裁及相关社区要求仍须逐项核对。\n')
            linebreak = '\r\n' if '\r\n' in text else '\n'
            revised += note.replace('\n',linebreak)
            encoded = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + revised.encode('utf-8')
            updated, _ = parse_card(encoded.decode('utf-8-sig').replace('\r\n','\n'))
            if (updated.id != metadata.id or updated.audit != metadata.audit or updated.spatial != metadata.spatial
                    or updated.temporal != metadata.temporal or updated.standards != metadata.standards
                    or updated.relations != metadata.relations or updated.genre != metadata.genre):
                raise IntakeError(f'详情补充改变了草稿标识、复核状态或研究字段：{path}')
            plans.append((path,raw,encoded,detail_path,detail_hash))
        if not check:
            if (sha256(selection_path.read_bytes()).hexdigest() != selection_hash
                    or sha256(manifest_path.read_bytes()).hexdigest() != manifest_hash
                    or sha256(corpus.read_bytes()).hexdigest() != corpus_hash
                    or sha256(initial.read_bytes()).hexdigest() != initial_hash):
                raise IntakeError('详情清单或基础目录在补充期间发生变化。')
            for path, original, revised, detail_path, detail_hash in plans:
                with NamedTemporaryFile(dir=path.parent,prefix='.pangloss-detail-',delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(revised)
                try:
                    if path.read_bytes() != original or sha256(detail_path.read_bytes()).hexdigest() != detail_hash:
                        raise IntakeError(f'草稿或详情快照在补充时发生变化：{path}')
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
    return {'cards_to_update':len(plans),'already_enriched':already,'skipped':skipped,'check':check,
            'changes':[{'id':path.stem,'before_sha256':sha256(original).hexdigest(),'after_sha256':sha256(revised).hexdigest()}
                       for path,original,revised,_,_ in plans]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=sorted(CONFIG),required=True)
    parser.add_argument('--vault',type=Path,default=DEFAULT_VAULT)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--initial',type=Path,required=True)
    parser.add_argument('--supplement',type=Path,required=True)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    try:
        result = enrich(args.vault.resolve(),args.corpus.resolve(),args.initial.resolve(),args.supplement.resolve(),args.kind,check=args.check)
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(f'详情补充未完成；已完成条目及其余草稿均保留，可核对后续跑：{error}',file=sys.stderr)
        return 1
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
