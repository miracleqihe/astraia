"""Snapshot the Temiar collection catalogue for local noncommercial review."""
import argparse
from hashlib import sha256
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.archive_fetch import json_bytes, request_html, robot_rules
from pipeline.fetch_lao_dllm import exclusive_write
from pipeline.fetch_minyag_wolp import HOST, TERMS_URL
from pipeline.intake_sources import IntakeError

CATALOGUE_URL = f'https://{HOST}/collections/probertson001.html'


def catalogue_rows(raw: bytes) -> list[dict]:
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    text = soup.get_text(' ', strip=True)
    if not all(value in text for value in ('Aileen Margaret Robertson', 'ten audio tracks', 'five tracks', '1941', 'Temiar')):
        raise IntakeError('Temiar 馆藏总述变化，须复核来源及数量。')
    rows = []
    for paragraph in soup.find_all('p'):
        content = paragraph.get_text(' ', strip=True)
        match = re.match(r'^(\d+)\.\s', content)
        if not match:
            continue
        number, strong = int(match.group(1)), paragraph.find('strong')
        archive = [a['href'].strip() for a in paragraph.find_all('a', href=True) if a.get_text(strip=True) == '[Archive]']
        audio = [a['href'].strip() for a in paragraph.find_all('a', href=True) if a.get_text(strip=True) == '[Listen to audio]']
        if (strong is None or len(archive) != 1 or not re.fullmatch(r'http://www\.dspace\.cam\.ac\.uk/handle/1810/\d+', archive[0])):
            raise IntakeError(f'Temiar 目录题名或旧档案入口异常：{number}')
        if len(audio) > 1 or (audio and not re.fullmatch(r'http://sms\.cam\.ac\.uk/media/\d+', audio[0])):
            raise IntakeError(f'Temiar 目录音频入口异常：{number}')
        rows.append({'number': number, 'title': strong.get_text(' ', strip=True), 'archive_url': archive[0],
                     'audio_url': audio[0] if audio else None})
    if [row['number'] for row in rows] != list(range(1, 51)):
        raise IntakeError('Temiar 目录编号不完整或重复。')
    return rows


def fetch(folder: Path, delay: float = 2.0) -> dict:
    if delay < 2:
        raise IntakeError('馆藏页面请求间隔至少为 2 秒。')
    folder.mkdir(parents=True, exist_ok=False)
    robots, status = robot_rules(HOST, delay)
    entries = []
    for name, url in [('terms.html', TERMS_URL), ('catalogue.html', CATALOGUE_URL)]:
        raw, observed = request_html(url, HOST, robots, delay)
        if name == 'terms.html':
            text = BeautifulSoup(raw.decode('utf-8'), 'html.parser').get_text(' ', strip=True)
            if not all(v in text for v in ('personal non-commercial use', 'prior written permission', 'proprietary notices')):
                raise IntakeError('站点条款变化，停止采集并复核。')
        else:
            catalogue_rows(raw)
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
    print(f"已保存 {len(result['pages'])} 份原始网页；未获取录音和附件。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
