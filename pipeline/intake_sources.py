"""Extract literal, locatable passages from one local document or web URL."""

from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from typing import BinaryIO
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bs4 import BeautifulSoup
from pydantic import HttpUrl
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_DOWNLOAD = 64 * 1024 * 1024


class IntakeError(ValueError):
    """An input or draft requires a correction before intake can continue."""


@dataclass(frozen=True)
class Passage:
    locator: str
    text: str


@dataclass(frozen=True)
class Material:
    title: str
    citation: str
    source_type: str
    content_sha256: str
    passages: list[Passage]
    url: str | None = None
    local_path: str | None = None
    doi: str | None = None
    notes: tuple[str, ...] = ()
    raw_bytes: bytes = field(default=b"", repr=False, compare=False)


def one_line(value: str) -> str:
    return " ".join(value.split())


def _decode(raw: bytes, encoding: str) -> str:
    try:
        text = raw.decode(encoding)
    except (UnicodeError, LookupError) as error:
        raise IntakeError("无法按指定编码读取文本。请检查 UTF-8 或通过 --encoding 指定原编码。") from error
    if "\ufffd" in text or "\0" in text:
        raise IntakeError("文本含有替代字符或空字节，请核对原文件与编码。")
    return text


def _text_passages(text: str) -> list[Passage]:
    passages: list[Passage] = []
    lines: list[str] = []
    start = 0
    for index, line in enumerate([*text.splitlines(), ""], 1):
        if line.strip():
            if not lines:
                start = index
            lines.append(line)
        elif lines:
            end = index - 1
            locator = f"文本第 {start} 行" if start == end else f"文本第 {start}–{end} 行"
            passages.append(Passage(locator, "\n".join(lines)))
            lines.clear()
    return passages


def _from_text(raw: bytes, *, title: str, encoding: str, path: str | None = None) -> Material:
    passages = _text_passages(_decode(raw, encoding))
    if not passages:
        raise IntakeError("纯文本没有可供引用的内容。")
    return Material(title, title, "plain_text", sha256(raw).hexdigest(), passages, local_path=path, raw_bytes=raw)


def _readable_pdf_text(text: str) -> bool:
    return (any(character.isalnum() for character in text) and "\ufffd" not in text
            and not re.search(r"\(cid:\d+\)|[\ue000-\uf8ff]", text))


def _from_pdf(raw: bytes, title: str, *, path: str | None = None, url: str | None = None) -> Material:
    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted and not reader.decrypt(""):
            raise IntakeError("PDF 需要访问密码。请提供可以读取的本地副本。")
        metadata = reader.metadata
        if metadata and metadata.title and "\ufffd" not in metadata.title:
            title = one_line(metadata.title) or title
        author = one_line(metadata.author) if metadata and metadata.author else ""
        if author.casefold() in {"anonymous", "unknown"} or "\ufffd" in author:
            author = ""

        passages, unavailable = [], []
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if _readable_pdf_text(text):
                passages.append(Passage(f"PDF 第 {number} 页", text))
            else:
                unavailable.append(str(number))
    except IntakeError:
        raise
    except (PdfReadError, UnicodeError, ValueError) as error:
        raise IntakeError(f"PDF 读取失败。{error}") from error

    if not passages:
        raise IntakeError("PDF 未提取到可靠文字。扫描件需先在本地 OCR，再导入含文字层的 PDF 或纯文本。")
    citation = f"{author}，《{title}》" if author else title
    notes = (f"以下 PDF 页未提取到可靠文字，复核时请查看原页。{', '.join(unavailable)}。",) if unavailable else ()
    return Material(title, citation, "pdf", sha256(raw).hexdigest(), passages, url=url, local_path=path, notes=notes, raw_bytes=raw)


def _meta(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        for attribute in ("name", "property"):
            tag = soup.find("meta", attrs={attribute: key})
            if tag is not None and isinstance(tag.get("content"), str):
                content = one_line(tag["content"])
                if content:
                    return content
    return ""


def _challenge_page(soup: BeautifulSoup) -> bool:
    title = one_line(soup.title.get_text(" ", strip=True)).casefold() if soup.title else ""
    heading = soup.find("h1")
    heading_text = one_line(heading.get_text(" ", strip=True)).casefold() if heading else ""
    visible = one_line(soup.get_text(" ", strip=True)).casefold()
    structural = str(soup).casefold()
    security_heading = "security verification" in title or "security verification" in heading_text
    return ((security_heading and "security service" in visible and "bot" in visible)
            or (("just a moment" in title or "attention required" in title)
                and ("cf-chl" in structural or "challenge-platform" in structural or "cf-turnstile" in structural)))


def _from_html(raw: bytes, title: str, *, path: str | None = None, url: str | None = None,
               encoding: str | None = None) -> Material:
    soup = BeautifulSoup(raw, "html.parser", from_encoding=encoding)
    if soup.contains_replacement_characters:
        raise IntakeError("网页正文含有替代字符。可保存网页并指定正确编码后重新导入。")
    if _challenge_page(soup):
        raise IntakeError("网页返回了访问验证页面，未生成资料草稿。请使用可访问的原始资料或本地副本。")
    candidate_title = _meta(soup, "citation_title", "og:title")
    if not candidate_title and soup.title:
        candidate_title = one_line(soup.title.get_text(" ", strip=True))
    title = candidate_title or title
    author = _meta(soup, "citation_author", "author")
    published = _meta(soup, "citation_publication_date", "article:published_time")
    doi = _meta(soup, "citation_doi").removeprefix("https://doi.org/")
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        doi = ""

    for element in soup.select("script, style, noscript, template, nav, footer, aside, form"):
        element.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    tags = {"h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote", "tr"}
    blocks = []
    for element in main.find_all(list(tags)):
        if any(parent.name in tags for parent in element.parents if parent is not main):
            continue
        text = element.get_text(" ", strip=True)
        if text:
            blocks.append(text)
    if not blocks:
        blocks = [part for part in main.stripped_strings if part.strip()]
    if not blocks or any("\ufffd" in block for block in blocks):
        raise IntakeError("没有取得可引用的网页正文。可提供保存后的 HTML 或正文纯文本。")
    passages = [Passage(f"网页正文第 {index} 段", block) for index, block in enumerate(blocks, 1)]
    citation = "，".join(value for value in (author, title, published) if value)
    return Material(title, citation, "web_page", sha256(raw).hexdigest(), passages,
                    url=url, local_path=path, doi=doi or None, raw_bytes=raw)


def _web_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise IntakeError("网页地址须为有效的 HTTP 或 HTTPS URL，且不含登录凭据。")
    return str(HttpUrl(value))


class _WebRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, _web_url(newurl))


def read_url(url: str) -> Material:
    request = Request(_web_url(url), headers={"User-Agent": "Astraia/0.1 (local document intake)", "Accept-Encoding": "identity"})
    with build_opener(_WebRedirect()).open(request, timeout=25) as response:
        raw = response.read(MAX_DOWNLOAD + 1)
        if len(raw) > MAX_DOWNLOAD:
            raise IntakeError("网页响应超过 64 MiB。请保存需要引用的文件后在本地导入。")
        final_url = response.geturl()
        media_type = response.headers.get_content_type()
        encoding = response.headers.get_content_charset()

    parsed = urlsplit(final_url)
    title = unquote(parsed.path.rstrip("/").split("/")[-1]) or parsed.hostname or "网页资料"
    if media_type == "application/pdf" or raw.lstrip().startswith(b"%PDF-"):
        return _from_pdf(raw, title, url=final_url)
    if media_type in {"text/html", "application/xhtml+xml"}:
        return _from_html(raw, title, url=final_url, encoding=encoding)
    if media_type == "text/plain":
        text = _decode(raw, encoding or "utf-8-sig")
        passages = _text_passages(text)
        if not passages:
            raise IntakeError("网页返回了空白文本。")
        return Material(title, title, "plain_text", sha256(raw).hexdigest(), passages, url=final_url, raw_bytes=raw)
    raise IntakeError(f"网页返回 {media_type}。请提供可读取的 HTML、PDF 或纯文本。")


def read_material(source: str | None, inline: str | None, encoding: str | None,
                  stdin: BinaryIO) -> Material:
    if inline is not None:
        return _from_text(inline.encode("utf-8"), title="用户提供的文本", encoding="utf-8")
    if source == "-":
        return _from_text(stdin.read(), title="用户提供的文本", encoding=encoding or "utf-8-sig")
    if source is None:
        raise IntakeError("请提供文件、网页 URL、--text 或标准输入 -。")
    if source.lower().startswith(("http://", "https://")):
        return read_url(source)

    path = Path(source).resolve(strict=True)
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(raw, path.name, path=str(path))
    if suffix in {".html", ".htm"}:
        return _from_html(raw, path.name, path=str(path), encoding=encoding)
    return _from_text(raw, title=path.name, encoding=encoding or "utf-8-sig", path=str(path))
