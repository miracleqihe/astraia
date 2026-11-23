"""Small, bounded HTTP helpers for public institutional catalogue pages."""
from datetime import datetime, timezone
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from pipeline.intake_sources import IntakeError

AGENT = "Astraia/0.1 (local research intake)"
MAX_HTML = 2 * 1024 * 1024


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def robot_rules(host: str, delay: float) -> tuple[RobotFileParser, str]:
    if delay < 2:
        raise IntakeError("馆藏页面请求间隔至少为 2 秒。")
    url = f"https://{host}/robots.txt"
    time.sleep(delay)
    try:
        with urlopen(Request(url, headers={"User-Agent": AGENT}), timeout=30) as response:
            if response.status != 200 or response.geturl() != url:
                raise IntakeError("馆藏 robots.txt 状态或跳转发生变化。")
            raw = response.read(256 * 1024 + 1)
            if len(raw) > 256 * 1024:
                raise IntakeError("馆藏 robots.txt 过大。")
            lines, status = raw.decode("utf-8-sig").splitlines(), "200"
    except HTTPError as error:
        if error.code != 404:
            raise IntakeError(f"馆藏 robots.txt 返回 HTTP {error.code}。") from error
        lines, status = [], "404"
    parser = RobotFileParser()
    parser.parse(lines)
    return parser, status


def request_html(url: str, host: str, robots: RobotFileParser, delay: float) -> tuple[bytes, str]:
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != host or parts.query or parts.fragment
            or not robots.can_fetch(AGENT, url)):
        raise IntakeError(f"馆藏地址或 robots.txt 不允许访问：{url}")
    time.sleep(delay)
    with urlopen(Request(url, headers={"User-Agent": AGENT, "Accept": "text/html", "Accept-Encoding": "identity"}), timeout=30) as response:
        if response.status != 200 or response.geturl() != url or response.headers.get_content_type() != "text/html":
            raise IntakeError(f"馆藏页面状态、跳转或类型不符：{url}")
        raw = response.read(MAX_HTML + 1)
    if not raw or len(raw) > MAX_HTML:
        raise IntakeError(f"馆藏页面为空或过大：{url}")
    try:
        raw.decode("utf-8")
    except UnicodeError as error:
        raise IntakeError(f"馆藏页面不是有效 UTF-8：{url}") from error
    return raw, datetime.now(timezone.utc).isoformat()
