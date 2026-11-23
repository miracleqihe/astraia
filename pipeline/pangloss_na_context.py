"""Stage a separately selected Yongning Na context batch without changing prior cards."""
from hashlib import sha256
from pathlib import Path

from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata
from pipeline.pangloss_na import CORPUS_URL, catalogue_rows, load_selection, pangloss_cards


def validate_selection(corpus: Path, previous: Path, selection: Path) -> dict:
    catalog=catalogue_rows(corpus.read_bytes())
    prior=load_selection(previous)
    selected=load_selection(selection)
    previous_ids={number for group in prior['groups'] for number in group['ids']}
    groups=selected['groups']
    ids=[number for group in groups for number in group['ids']]
    titles=selected.get('selected_titles')
    if (selected.get('catalogue_sha256')!=sha256(corpus.read_bytes()).hexdigest()
            or selected.get('previous_selection_sha256')!=sha256(previous.read_bytes()).hexdigest()
            or not previous_ids.issubset(catalog) or set(ids)&previous_ids
            or not set(ids).issubset(catalog) or any(len(group['ids'])!=1 for group in groups)
            or not isinstance(titles,dict) or set(titles)!=set(ids)
            or any(titles[number]!=catalog[number]['title'] for number in ids)):
        raise IntakeError('永宁背景补充的目录、题名、分组或原始选取不符。')
    return selected


def context_cards(folder: Path, corpus: Path, previous: Path, selection: Path):
    validate_selection(corpus,previous,selection)
    for model,body in pangloss_cards(folder,corpus,selection,include_root=False):
        raw=model.model_dump(mode='python')
        raw['spatial']={'precision':'culture_region',
                        'location_name':'永宁纳语（馆藏语言范围；单条录音地点见馆方字段）',
                        'culture_region':'East Asia · China'}
        manifest=folder/'manifest.json'
        raw['sources'] += [
            {'citation':'Astraia 首轮选取索引，用于核验补充批次不重复原有录音。',
             'type':'pangloss_na_context_previous','url':CORPUS_URL,'locator':'首轮选取对照',
             'local_path':display_path(previous),'content_sha256':sha256(previous.read_bytes()).hexdigest()},
            {'citation':'Astraia 补充详情快照清单，单条许可及社区要求仍需复核。',
             'type':'pangloss_na_context_manifest','url':CORPUS_URL,'locator':'口述背景补充详情清单',
             'local_path':display_path(manifest),'content_sha256':sha256(manifest.read_bytes()).hexdigest()},
        ]
        yield NodeMetadata.model_validate(raw),body
