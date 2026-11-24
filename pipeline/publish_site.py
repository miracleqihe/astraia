"""Deploy the public catalogue to the existing GitHub Pages subdirectory."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from pipeline.build_graph import PROJECT_ROOT
from pipeline.catalogue import build_catalogue
from pipeline.graph_output import publish_graph
from pipeline.ingest_agent import DEFAULT_CODE_TABLE, DEFAULT_VAULT
from pipeline.publication import build_public_graph
from pipeline.review_coverage import DEFAULT_DATA, DEFAULT_REGIONS, build_coverage, ensure_coverage_current
from pipeline.vault_write import vault_writer

PUBLIC_REPOSITORY = 'https://github.com/miracleqihe/miracleqihe.github.io.git'
PUBLIC_PATH = 'astraia'


def run(args: list[str], cwd: Path, *, env: dict | None = None, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace',
                            capture_output=capture, check=False)
    if result.returncode:
        raise ValueError(f"命令未完成：{args[0]}\n{(result.stderr or '').strip()}")
    return result.stdout if capture else ''


def deploy(vault: Path, code_table: Path, *, reviewed_only: bool = False) -> None:
    root = PROJECT_ROOT.resolve()
    with vault_writer(vault):
        graph = build_public_graph(vault, code_table) if reviewed_only else build_catalogue(vault, code_table)
        coverage = build_coverage(DEFAULT_DATA, DEFAULT_REGIONS)
        if vault == DEFAULT_VAULT.resolve():
            ensure_coverage_current(vault, coverage, DEFAULT_REGIONS)
    if not graph['nodes']:
        raise ValueError('没有可发布的资料；没有修改线上网站。')

    work = root / '.local/publication-work'
    work.mkdir(parents=True, exist_ok=True)
    if not work.resolve().is_relative_to(root):
        raise ValueError('临时发布目录不在项目中。')
    with TemporaryDirectory(prefix='site-', dir=work) as temporary:
        stage = Path(temporary).resolve()
        if not stage.is_relative_to(work.resolve()):
            raise ValueError('临时发布目录不在预期位置。')
        checkout, built = stage / 'homepage', stage / 'built'
        run(['git', 'clone', '--single-branch', '--branch', 'main', PUBLIC_REPOSITORY, str(checkout)], root)
        site = checkout / PUBLIC_PATH
        if site.is_symlink() or not site.is_dir() or site.resolve() != checkout.resolve() / PUBLIC_PATH:
            raise ValueError('公开网站目录不在独立检出的预期位置。')
        run(['git', 'ls-files', '--error-unmatch', f'{PUBLIC_PATH}/index.html'], checkout, capture=True)

        env = os.environ.copy()
        env['VITE_PUBLIC_DEMO'] = '1'
        npm = 'npm.cmd' if os.name == 'nt' else 'npm'
        run([npm, 'run', 'build', '--', '--base=/astraia/', '--outDir', str(built), '--emptyOutDir'], root / 'web', env=env)
        for name in ('index.html', 'ui-review/index.html', 'assets', 'fonts', 'knowledge/index.json', 'knowledge/data.json',
                     'knowledge/handbook.pdf', 'knowledge/inline-figures/manifest.json',
                     'knowledge/figures/font-report.json'):
            if not (built / name).exists():
                raise ValueError(f'网页构建缺少 {name}。')

        # This removes only the verified path in a fresh disposable checkout.
        run(['git', 'rm', '-rq', '--', PUBLIC_PATH], checkout)
        site.mkdir()
        shutil.copy2(built / 'index.html', site / 'index.html')
        for name in ('assets', 'fonts', 'ui-review', 'knowledge'):
            shutil.copytree(built / name, site / name)
        (site / 'data').mkdir()
        (site / 'data/graph_data.json').write_text(json.dumps(graph, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8', newline='\n')
        # Build the first-paint index from the exact graph just published, not
        # from a potentially older local development snapshot.
        run(['node', str(root / 'web/scripts/build-graph-index.mjs'), str(site / 'data/graph_data.json')], root)
        publish_graph(site / 'data/asia_coverage.json', coverage, 'json')
        # A Windows checkout may otherwise normalize SVG newlines when staging,
        # breaking the image hashes and embedded-font verification on Pages.
        (site / '.gitattributes').write_text(
            '# Preserve the exact bytes of generated assets and their manifests.\n* -text\n',
            encoding='utf-8', newline='\n')
        if (site / 'review').exists():
            raise ValueError('公开构建包含本地复核目录。')
        run(['git', 'add', '--', PUBLIC_PATH], checkout)
        paths = run(['git', 'diff', '--cached', '--name-only', '-z'], checkout, capture=True).split('\0')
        if not any(paths) or any(path and not path.startswith(PUBLIC_PATH + '/') for path in paths):
            raise ValueError('公开变更为空或超出图谱目录，未推送。')
        run(['git', 'commit', '-m', f'Publish {len(graph["nodes"])} Astraia catalogue records'], checkout)
        env['GH_PROMPT_DISABLED'] = '1'
        run(['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
             'push', 'origin', 'HEAD:main'], checkout, env=env)
        print(f'已推送 {len(graph["nodes"])} 条目录资料；GitHub Pages 随后部署。')
        print('https://miracleqihe.github.io/astraia/')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--code-table', type=Path, default=DEFAULT_CODE_TABLE)
    parser.add_argument('--publish', action='store_true', help='将目录与已许可正文推送到 GitHub Pages')
    parser.add_argument('--reviewed-only', action='store_true', help='只发布已复核且确认公开许可的资料')
    args = parser.parse_args()
    try:
        if args.publish:
            deploy(args.vault.resolve(), args.code_table, reviewed_only=args.reviewed_only)
        else:
            with vault_writer(args.vault.resolve()):
                graph = (build_public_graph(args.vault.resolve(), args.code_table) if args.reviewed_only
                         else build_catalogue(args.vault.resolve(), args.code_table))
            print(f'可展示的目录资料：{len(graph["nodes"])} 条；尚未推送。')
    except (OSError, ValueError) as error:
        print(f'网站发布未完成：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
