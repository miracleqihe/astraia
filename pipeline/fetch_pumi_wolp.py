"""Snapshot the Wangjiagou Pumi catalogue and terms without fetching audio."""
import argparse
from hashlib import sha256
from pathlib import Path

from bs4 import BeautifulSoup

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.fetch_minyag_wolp import HOST, TERMS_URL
from pipeline.intake_sources import IntakeError

CATALOGUE_URL = f'https://{HOST}/collections/huqianma001.html'


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    entries = []
    for name, url in [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)]:
        raw, observed = request_html(url, HOST, robots, delay)
        text = BeautifulSoup(raw.decode('utf-8'), 'html.parser').get_text(' ', strip=True)
        needed = ('personal non-commercial use', 'prior written permission', 'proprietary notices') if name == 'terms.html' else (
            'Hu Qianma', 'Wangjiagou', 'forty-five audio files', 'Pumi', 'February 2008', 'February 2011')
        if not all(value in text for value in needed):
            raise IntakeError(f'普米语馆藏来源或条款关键字段变化：{name}')
        exclusive_write(folder / name, raw)
        entries.append({'path': name, 'url': url, 'sha256': sha256(raw).hexdigest(),
                        'observed_at': observed, 'bytes': len(raw)})
    manifest = {'version': 1, 'robots_status': status, 'pages': entries,
                'scope': '项目目录及网站条款；本地个人或内部非商业研究；不请求音频或其他附件。',
                'rights': '保留原网页版权通知；进一步使用及单件权利与社区要求须另核。'}
    exclusive_write(folder / 'manifest.json', json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    result = fetch(args.output, args.delay)
    print(f"已保存 {len(result['pages'])} 份原始网页；未获取音频和附件。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
