"""Select and fetch a resumable Pangloss detail supplement for pending cards."""
import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError

from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.fetch_pangloss_na import fetch
from pipeline.ingest_agent import DEFAULT_VAULT
from pipeline.pangloss_supplement import CONFIG, select_targets, validate_selection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=sorted(CONFIG),required=True)
    parser.add_argument('--vault',type=Path,default=DEFAULT_VAULT)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--initial',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=120)
    parser.add_argument('--delay',type=float,default=2.0)
    args = parser.parse_args()
    try:
        args.output.mkdir(parents=True,exist_ok=True)
        selection_path = args.output/'selection.json'
        if selection_path.exists():
            selection = json.loads(selection_path.read_text(encoding='utf-8'))
        else:
            selection = select_targets(args.vault.resolve(),args.corpus.resolve(),args.initial.resolve(),args.kind,args.limit)
            exclusive_write(selection_path,(json.dumps(selection,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        validate_selection(selection,args.corpus.resolve(),args.initial.resolve(),args.kind)
        config = CONFIG[args.kind]
        manifest = fetch(args.corpus,selection_path,args.output,delay=args.delay,
                         corpus_name=config['name'],corpus_url=config['url'])
    except (ValueError,OSError,KeyError,TypeError,HTTPError) as error:
        print(f'详情补充获取停止；同一选取范围下已保存快照可续跑：{error}',file=sys.stderr)
        return 1
    print(f"已保存 {len(manifest['records'])} 条 {config['name']} 补充详情。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
