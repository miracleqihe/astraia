"""Index selected Yongning Na recordings from Pangloss, retaining source roles.

The local snapshots are catalogue and recording metadata, not audio or a transcript.
"""
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup, NavigableString

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError, _challenge_page, one_line
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

CORPUS_URL = "https://pangloss.cnrs.fr/corpus/Yongning_Na"
DETAIL_BASE = "https://pangloss.cnrs.fr/corpus/show"
DOI_BASE = "https://doi.org/10.24397/pangloss-"
ROOT_ID = "corpus_cn_yongning_na_pangloss"
LOCATION_PAPER = "https://citeseerx.ist.psu.edu/document?doi=55ad721735d2bfa33fd34a89f57959ff225f16a6&repid=rep1&type=pdf"


def json_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"永宁纳语研究索引无法读取：{path}：{error}") from error
    if not isinstance(value, dict):
        raise IntakeError("永宁纳语研究索引须为 JSON 对象。")
    return value


def load_selection(path: Path, corpus_url: str = CORPUS_URL) -> dict:
    data = json_object(path)
    if (data.get("version") != 1 or data.get("corpus_url") != corpus_url
            or not all(isinstance(data.get(key), str) and data[key].strip() for key in ("selection_method", "limits"))
            or not isinstance(data.get("groups"), list) or not data["groups"]):
        raise IntakeError("永宁纳语选取清单结构不符。")
    groups, numbers = set(), set()
    for group in data["groups"]:
        if (not isinstance(group, dict) or not re.fullmatch(r"[a-z][a-z0-9_]*", str(group.get("id", "")))
                or group["id"] in groups or not isinstance(group.get("label"), str) or not group["label"].strip()
                or not isinstance(group.get("ids"), list) or not group["ids"]):
            raise IntakeError("永宁纳语选取主题无效或重复。")
        groups.add(group["id"])
        for number in group["ids"]:
            if not isinstance(number, str) or not re.fullmatch(r"\d{7}", number) or number in numbers:
                raise IntakeError("永宁纳语档号无效或重复。")
            numbers.add(number)
    return data


def _soup(raw: bytes) -> BeautifulSoup:
    if b"SQLSTATE[" in raw and b"Connection refused" in raw:
        raise IntakeError("Pangloss 返回数据库连接错误，不能当作馆藏详情。")
    soup = BeautifulSoup(raw, "html.parser", from_encoding="utf-8")
    if soup.contains_replacement_characters or _challenge_page(soup):
        raise IntakeError("Pangloss 页面编码不可靠或返回访问验证。")
    return soup


def catalogue_rows(raw: bytes, corpus_name: str = "Yongning Na") -> dict[str, dict]:
    """Parse a named Pangloss catalogue without changing the existing Na default."""
    if not isinstance(corpus_name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]*", corpus_name):
        raise IntakeError("Pangloss 馆藏名称无效。")
    soup = _soup(raw)
    table = soup.select_one("table#m_resources-table")
    expected_title = corpus_name.lower().replace(" ", "_")
    if not table or not soup.title or not soup.title.get_text(" ", strip=True).lower().endswith("corpus " + expected_title):
        raise IntakeError(f"页面不是 {corpus_name} 的 Pangloss 馆藏目录。")
    rows = {}
    for tr in table.select("tr[data-corpus]"):
        if tr.get("data-corpus") != corpus_name:
            raise IntakeError("Pangloss 目录行的馆藏名称不符。")
        cells = tr.find_all("td", recursive=False)
        button = tr.select_one("button[data-doi][data-title]")
        if len(cells) != 8 or not button:
            raise IntakeError("Pangloss 目录行的列结构发生变化。")
        doi = button.get("data-doi", "")
        match = re.fullmatch(re.escape(DOI_BASE) + r"(\d{7})", doi)
        title = one_line(cells[4].get_text(" ", strip=True))
        anchor = cells[4].find("a", href=True)
        if not match or not title or not anchor or title != one_line(button.get("data-title", "")):
            raise IntakeError("Pangloss 目录的 DOI、题名或链接不符。")
        number = match.group(1)
        parts = urlsplit(anchor["href"])
        query = parse_qs(parts.query, strict_parsing=True)
        if (parts.scheme != "https" or parts.netloc != "pangloss.cnrs.fr" or parts.path != "/corpus/show"
                or parts.fragment or set(query) != {"oai_primary", "corpus"} or query["corpus"] != [corpus_name]
                or len(query["oai_primary"]) != 1
                or not re.fullmatch(r"cocoon-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", query["oai_primary"][0])
                or number in rows):
            raise IntakeError("Pangloss 馆藏编号或目录链接无效。")
        url = DETAIL_BASE + "?" + urlencode({"oai_primary": query["oai_primary"][0], "corpus": corpus_name})
        duration = one_line(cells[3].get_text(" ", strip=True))
        recorded = one_line(cells[7].get_text(" ", strip=True))
        rows[number] = {"id": number, "doi": doi, "url": url, "title": title,
                        "researchers": one_line(cells[5].get_text(" ", strip=True)),
                        "speakers": one_line(cells[6].get_text(" ", strip=True)), "recorded": recorded,
                        "duration": duration, "formats": sorted({svg.get("name") for svg in cells[1].select("svg[name]")}),
                        "transcription_icon": bool(cells[2].select_one("svg"))}
    if not rows:
        raise IntakeError("Pangloss 目录没有可核验的馆藏行。")
    return rows


def detail_fields(raw: bytes, expected: dict) -> dict:
    soup = _soup(raw)
    button = soup.select_one("h1 button[data-doi][data-title]")
    if not button or button.get("data-doi") != expected["doi"] or one_line(button.get("data-title", "")) != expected["title"]:
        raise IntakeError(f"Pangloss 详情页与目录 DOI 或题名不符：{expected['id']}")
    titles = []
    for alt in button.parent.select("span.alt-title"):
        small = alt.find("small")
        label = one_line(small.get_text(" ", strip=True)) if small else ""
        value = one_line(" ".join(str(child) for child in alt.children if isinstance(child, NavigableString)))
        if label and value:
            titles.append({"language_as_displayed": label, "title": value})
    sections = {}
    aside = soup.select_one("aside#aside")
    if not aside:
        raise IntakeError(f"Pangloss 详情缺少馆方元数据：{expected['id']}")
    for section in aside.find_all("section", recursive=False):
        heading = section.find("h1", recursive=False)
        if not heading:
            continue
        label = one_line(heading.get_text(" ", strip=True))
        heading.extract()
        if label in sections:
            raise IntakeError(f"Pangloss 元数据字段重复：{label}")
        sections[label] = one_line(section.get_text(" ", strip=True))
    return {"alternate_titles": titles, "researchers": sections.get("Chercheur(s)"),
            "speakers": sections.get("Locuteur(s)"), "recorded": sections.get("Date d'enregistrement"),
            "recording_location": sections.get("Lieu d'enregistrement"),
            "deposit_affiliation": sections.get("Affiliation du déposant"), "license": sections.get("Licence")}


def compare_dates(catalogue: str, detail: str | None) -> bool | None:
    if not detail:
        return None
    def normalize(value: str) -> str | None:
        try:
            if re.fullmatch(r"\d{4}", value):
                return value if 1 <= int(value) <= 9999 else None
            if re.fullmatch(r"\d{4}-\d{2}", value):
                return datetime.strptime(value, "%Y-%m").strftime("%Y-%m")
            if re.fullmatch(r"\d{2}/\d{4}", value):
                return datetime.strptime(value, "%m/%Y").strftime("%Y-%m")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return date.fromisoformat(value).isoformat()
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
                return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
        except ValueError:
            pass
        return None
    first, second = normalize(catalogue), normalize(detail)
    if first is None or second is None:
        return None
    if first[:min(len(first), len(second))] != second[:min(len(first), len(second))]:
        return False
    return True if len(first) == len(second) else None


def compare_credits(catalogue: str | None, detail: str | None) -> bool | None:
    if not catalogue or not detail:
        return None
    def fields(value: str) -> set[str]:
        return {one_line(part).casefold() for part in re.split(r"[—;]", value) if one_line(part)}
    return fields(catalogue) == fields(detail)


def evidence(row: dict, detail: dict, group: dict) -> dict:
    return {"馆方目录题名": row["title"], "馆方其他语言题名": detail["alternate_titles"],
            "馆方目录研究者字段": row["researchers"], "馆方详情研究者字段": detail["researchers"],
            "馆方目录讲述者字段": row["speakers"], "馆方详情讲述者字段": detail["speakers"],
            "两处讲述者字段显示是否对应": compare_credits(row["speakers"], detail["speakers"]),
            "两处研究者字段显示是否对应": compare_credits(row["researchers"], detail["researchers"]),
            "馆方目录录音日期": row["recorded"], "馆方详情录音日期原字段": detail["recorded"],
            "两处日期是否一致": compare_dates(row["recorded"], detail["recorded"]),
            "馆方详情录音地点原字段": detail["recording_location"], "馆方时长": row["duration"],
            "馆方媒介图标": row["formats"], "馆方转写图标": row["transcription_icon"],
            "馆方详情许可原字段": detail["license"], "本项目题名对照分组": group["label"]}


def load_snapshots(folder: Path, corpus: Path, selection: Path, *, corpus_name: str = "Yongning Na",
                   corpus_url: str = CORPUS_URL) -> tuple[dict, dict, dict]:
    manifest = json_object(folder / "manifest.json")
    catalog = catalogue_rows(corpus.read_bytes(), corpus_name)
    selected = load_selection(selection, corpus_url)
    ids = [number for group in selected["groups"] for number in group["ids"]]
    if (manifest.get("version") != 1 or manifest.get("corpus_sha256") != sha256(corpus.read_bytes()).hexdigest()
            or manifest.get("selection_sha256") != sha256(selection.read_bytes()).hexdigest()
            or manifest.get("selected_ids") != ids or not isinstance(manifest.get("records"), list)
            or len(manifest["records"]) != len(ids) or any(number not in catalog for number in ids)):
        raise IntakeError("Pangloss 批次清单与馆方目录或选取范围不符。")
    details = {}
    for number, entry in zip(ids, manifest["records"], strict=True):
        if not isinstance(entry, dict) or entry.get("id") != number or entry.get("path") != f"records/{number}/page.html":
            raise IntakeError("Pangloss 详情快照路径或顺序不符。")
        path = folder / "records" / number / "page.html"
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != entry.get("sha256"):
            raise IntakeError(f"Pangloss 详情快照哈希不符：{number}")
        details[number] = detail_fields(raw, catalog[number])
    return catalog, selected, details


def pangloss_cards(folder: Path, corpus: Path, selection: Path, *, include_root: bool = True):
    catalog, selected, details = load_snapshots(folder, corpus, selection)
    selected_ids = [number for group in selected["groups"] for number in group["ids"]]
    corpus_hash, selection_hash = sha256(corpus.read_bytes()).hexdigest(), sha256(selection.read_bytes()).hexdigest()
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "spatial": {"precision": "culture_region", "location_name": "中国云南（录音地点见馆方原字段；行政范围待核）",
                          "culture_region": "East Asia · China"},
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}

    def source_catalogue(locator: str) -> dict:
        return {"citation": "CNRS-LACITO，Pangloss 永宁纳语馆藏目录；本地保留目录网页。",
                "type": "pangloss_na_catalogue", "url": CORPUS_URL, "locator": locator,
                "local_path": display_path(corpus), "content_sha256": corpus_hash}

    def source_selection(locator: str) -> dict:
        return {"citation": "Astraia 目的性题名选取索引；分组是待复核的比较线索。",
                "type": "pangloss_na_selection", "url": CORPUS_URL, "locator": locator,
                "local_path": display_path(selection), "content_sha256": selection_hash}

    root = {**common, "id": ROOT_ID, "title": "云南永宁纳语口述资料 · Pangloss 馆藏选取",
            "node_type": "myth_corpus", "z_layer": 2,
            "sources": [source_catalogue("Yongning Na / 资源目录"), source_selection("目的性题名选取 / 对照分组")]}
    root_body = (f"\n## 馆藏与选取范围\n\n本批从馆方目录中的 {len(catalog)} 条资源里，"
                 f"按题名选出 {len(selected_ids)} 个与叙事、鬼神观念及仪式有关的录音。"
                 "目录还包括语言调查及生活记录，本批不是全部叙事，也不是随机样本。"
                 "馆方的研究者与讲述者字段分别保留；同题记录按来源日期、讲述人及版本分开。"
                 "录音日期不等于故事发生年代，录音地点原字段与行政名称须再核；坐标及标准码留空。"
                 "音频与转写文本未下载，复用须遵守单条许可并考虑相关社区要求。\n")
    if include_root:
        yield NodeMetadata.model_validate(root), root_body
    for group in selected["groups"]:
        anchor = group["ids"][0]
        for number in group["ids"]:
            row, detail = catalog[number], details[number]
            detail_path = folder / "records" / number / "page.html"
            text_fields = evidence(row, detail, group)
            alternatives = [item["title"] for item in detail["alternate_titles"] if item["title"] != row["title"]]
            relations = [{"type": "PART_OF_MACRO_TREND", "target": ROOT_ID,
                          "note": "同一馆藏中的目的性选取；不表示同一讲述者或录音地点。"}]
            if number != anchor:
                relations.append({"type": "COMPARED_WITH", "target": f"case_cn_yongning_na_{anchor}",
                                  "note": "按目录题名供人工对照；不表示已证实同源、同一次演述或迁徙路径。"})
            model = {**common, "id": f"case_cn_yongning_na_{number}",
                     "title": f"永宁纳语录音 · {row['title']}", "aliases": [row["title"], *alternatives],
                     "node_type": "case", "z_layer": 1, "relations": relations,
                     "sources": [{"citation": "CNRS-LACITO，Pangloss 单条录音元数据；具体许可见馆方原字段。",
                                  "type": "pangloss_na_detail", "url": row["url"],
                                  "doi": row["doi"].removeprefix("https://doi.org/"), "locator": f"录音 {number}",
                                  "local_path": display_path(detail_path), "content_sha256": sha256(detail_path.read_bytes()).hexdigest()},
                                 source_catalogue(f"Yongning Na / DOI {number}"), source_selection(group["label"])]}
            body = ("\n## 馆方录音目录字段\n\n" + literal_block(json.dumps(text_fields, ensure_ascii=False, indent=2))
                    + "\n\n## 原音、转写与复核\n\n上列为馆方目录及单条详情元数据，未复制音频和转写正文；"
                      "转写图标仅反映目录显示，具体文本、语言及译本请回查单条页面。"
                      "研究者与讲述者是不同角色，录音日期不是叙事年代；录音地点和行政称谓仍须核对。"
                      "题名对照分组供人工比较，不自动判定同源或历史传播；请逐条核对许可和相关社区要求。\n")
            yield NodeMetadata.model_validate(model), body
