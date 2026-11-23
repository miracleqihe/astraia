"""Stage Dúchas school collection metadata from locally saved public XML."""

from datetime import date
from hashlib import sha256
import math
from pathlib import Path
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree

from pipeline.ingest_agent import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

CORPUS = "corpus_duchas_fairy_forts"
INDEX = "index_duchas_fairy_forts"
COLLECTION = "https://www.duchas.ie/en/info/cbe-collections"
ATTRIBUTION = "Folklore data by Dúchas © National Folklore Collection, UCD. CC BY-NC 4.0."


def xml_record(path: Path, expected_tag: str, expected_id: str):
    raw = path.read_bytes()
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise IntakeError(f"馆藏 XML 无法解析。{path}") from error
    if root.tag != expected_tag or root.get("entryID") != expected_id:
        raise IntakeError(f"馆藏 XML 的类型或编号不匹配。{path}")
    return root, sha256(raw).hexdigest()


def relative_path(path: Path) -> str:
    absolute = path.resolve()
    return absolute.relative_to(PROJECT_ROOT).as_posix() if absolute.is_relative_to(PROJECT_ROOT) else str(absolute)


def person(element) -> str:
    if element is None:
        return ""
    return " ".join(filter(None, (element.get("pretext"), element.get("text"))))


def school_coordinates(location) -> tuple[float, float] | None:
    if location is None:
        return None
    try:
        latitude, longitude = float(location.get("lat", "")), float(location.get("lon", ""))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not (51 <= latitude <= 56 and -11 <= longitude <= -5):
        return None
    return round(latitude, 5), round(longitude, 5)


def page_source(path: Path, chapter_id: str, page_id: str, story_id: str, volume: str) -> tuple[dict, str, str]:
    page, page_digest = xml_record(path, "pPage", page_id)
    item = next((item for item in page.findall("story") if item.get("default") == story_id), None)
    if item is None:
        raise IntakeError(f"馆藏页未包含该故事。{path}")
    transcript = item.find("transcript")
    excerpt = " ".join(" ".join(transcript.itertext()).split()[:20]) if transcript is not None else ""
    page_number = page.find("pageNumber")
    page_label = page_number.get("default", page_id) if page_number is not None else page_id
    source = {
        "citation": f"{ATTRIBUTION} Transcript, volume {volume}, page {page_label}.",
        "type": "primary_archive", "url": f"https://www.duchas.ie/xml/cbes/{chapter_id}/{page_id}",
        "locator": f"馆藏页 {page_id} / 印页 {page_label} / 故事 {story_id}",
        "local_path": relative_path(path), "content_sha256": page_digest,
    }
    return source, excerpt, page_label


def story_node_id(path: Path) -> str:
    match = re.fullmatch(r"story-(\d+)-(\d+)-(\d+)\.xml", path.name)
    if not match:
        raise IntakeError(f"故事文件名须包含学校、页和故事编号。{path}")
    return f"case_duchas_{match[3]}"


def cited_story_ids(metadata: NodeMetadata) -> set[str]:
    if metadata.node_type != "case":
        return set()
    result = set()
    for source in metadata.sources:
        if not source.url:
            continue
        url = urlsplit(str(source.url))
        match = re.fullmatch(r"/(?:en|ga|xml)/cbes/\d+/\d+/(\d+)/?", url.path)
        if url.hostname in {"duchas.ie", "www.duchas.ie"} and match:
            result.add(match[1])
    return result


def duchas_cards(paths: list[Path], *, include_groups: bool = True):
    audit = {"created_at": date.today(), "reviewed_by_human": False}
    source = {"citation": f"{ATTRIBUTION} The Schools’ Collection, 1937–1939.",
              "type": "archival_catalogue", "url": COLLECTION, "locator": "The Schools’ Collection"}
    common = {"genre": "academic_model", "credibility_tier": "A", "is_fictional_quarantine": False,
              "spatial": None, "temporal": None, "standards": {}, "sources": [source], "audit": audit}
    if include_groups:
        yield NodeMetadata.model_validate({"id": CORPUS, "title": "Dúchas 学校采录 · 仙丘资料组",
                                           "node_type": "myth_corpus", "z_layer": 2, **common}), (
            "\n## 馆藏范围\n\n资料组汇集爱尔兰学校采录馆藏中的仙丘相关故事。"
            "每条保留卷号、学校、馆藏编号和采录元数据，原文可从 Dúchas 馆藏页查看。\n"
        )
        yield NodeMetadata.model_validate({"id": INDEX, "title": "Dúchas 仙丘称谓索引",
                                           "node_type": "motif_index", "z_layer": 3, **common}), (
            "\n## 馆藏称谓\n\n此索引用于关联馆藏中题名为 Fairy Forts 的学校采录。"
            "叙述内容和各地术语须循单条记录核对。\n"
        )
    for path in sorted(paths):
        match = re.fullmatch(r"story-(\d+)-(\d+)-(\d+)\.xml", path.name)
        if not match:
            raise IntakeError(f"故事文件名须包含学校、页和故事编号。{path}")
        chapter_id, page_id, story_id = match.groups()
        school_path = path.parent / f"school-{chapter_id}.xml"
        story, story_digest = xml_record(path, "lStory", story_id)
        school, school_digest = xml_record(school_path, "lChapter", chapter_id)
        chapter = story.find("chapter")
        title = story.find("title")
        pages = [page.get("default") for page in story.findall("page")]
        if chapter is None or chapter.get("default") != chapter_id or page_id not in pages or title is None:
            raise IntakeError(f"馆藏故事与学校或页码不匹配。{path}")
        if any(not page or not re.fullmatch(r"\d+", page) for page in pages) or len(set(pages)) != len(pages):
            raise IntakeError(f"馆藏故事的页面编号无效或重复。{path}")
        if title.get("default", "").casefold() not in {"fairy fort", "fairy forts"}:
            raise IntakeError(f"馆藏故事标题不属于仙丘资料组。{path}")
        school_name = school.find("schoolName")
        location = school.find("schoolLocation")
        school_label = school_name.get("default", "") if school_name is not None else ""
        place_name = location.get("nameEN") or location.get("nameGA") if location is not None else ""
        spatial = None
        if location is not None and place_name:
            spatial = {"precision": "city", "location_name": f"{place_name}（学校登记地点参照）",
                       "culture_region": "Europe · Ireland"}
            coordinates = school_coordinates(location)
            if coordinates:
                spatial.update(lat=coordinates[0], lng=coordinates[1])
        recorded_date = title.get("date", "")
        try:
            parsed_date = date.fromisoformat(recorded_date) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", recorded_date) else None
        except ValueError:
            parsed_date = None
        if parsed_date:
            year = parsed_date.year
            temporal = {"year_start": year, "year_end": year, "era_label": "学校采录",
                        "uncertainty_note": f"故事元数据登记日期为 {recorded_date}，叙事发生时间未定。"}
        else:
            invalid_date = f"原 XML 日期「{recorded_date}」无法按年月日解析；" if recorded_date else ""
            temporal = {"year_start": 1937, "year_end": 1939, "era_label": "学校采录",
                        "uncertainty_note": invalid_date + "学校采录工程整体时间为 1937–1939 年，单条日期及叙事发生时间未定。"}
        html_url = f"https://www.duchas.ie/en/cbes/{chapter_id}/{page_id}/{story_id}"
        sources = [
            {"citation": f"{ATTRIBUTION} Fairy Forts, {school_label}, Schools’ Collection.",
             "type": "primary_archive", "url": html_url, "locator": f"{chapter_id} / {page_id} / {story_id}"},
            {"citation": f"{ATTRIBUTION} Story metadata, {story_id}.", "type": "archival_catalogue",
             "url": f"https://www.duchas.ie/xml/cbes/{chapter_id}/{page_id}/{story_id}",
             "locator": f"故事 XML {story_id}", "local_path": relative_path(path), "content_sha256": story_digest},
            {"citation": f"{ATTRIBUTION} School metadata, {chapter_id}.", "type": "archival_catalogue",
             "url": f"https://www.duchas.ie/xml/cbes/{chapter_id}", "locator": f"学校 XML {chapter_id}",
             "local_path": relative_path(school_path), "content_sha256": school_digest},
            source,
        ]
        excerpt = ""
        page_label = page_id
        for current_page in [page_id, *(page for page in pages if page != page_id)]:
            page_path = path.parent / f"page-{chapter_id}-{current_page}.xml"
            if not page_path.is_file():
                continue
            page_entry, page_excerpt, label = page_source(page_path, chapter_id, current_page, story_id,
                                                         chapter.get("volumeNumber", ""))
            sources.append(page_entry)
            if current_page == page_id:
                excerpt, page_label = page_excerpt, label
        record = NodeMetadata.model_validate({
            "id": story_node_id(path), "title": f"Dúchas {story_id} · Fairy Forts · {school_label}",
            "aliases": list(filter(None, (story_id, school_label))), "node_type": "case", "z_layer": 1, "genre": "unclassified",
            "credibility_tier": "A", "is_fictional_quarantine": False, "spatial": spatial, "temporal": temporal,
            "standards": {}, "sources": sources, "audit": audit,
            "relations": [
                {"type": "PART_OF_MACRO_TREND", "target": CORPUS, "note": "Dúchas 学校采录的仙丘资料。"},
                {"type": "HAS_MOTIF", "target": INDEX, "note": "馆藏故事题名为 Fairy Forts。"},
            ],
        })
        collector = person(story.find("collector/persName"))
        informant = person(story.find("informant/persName"))
        lines = ["", "## 学校采录馆藏", "",
                 f"馆藏故事编号 {story_id}，学校 {school_label}，卷号 {chapter.get('volumeNumber', '')}。"]
        if len(pages) > 1:
            lines.append(f"馆藏登记此故事跨 {len(pages)} 页；已保存页面的出处列于来源，其他页面可从馆藏故事链接查阅。")
        if collector:
            lines.append(f"采录者为 {collector}。")
        if informant:
            lines.append(f"馆藏登记的受访者为 {informant}。")
        if place_name:
            lines.append(f"学校登记地点为 {place_name}，地图坐标用于地点参照。")
        if excerpt:
            lines.extend(["", f"## 馆藏第 {page_label} 页转录摘录", "", f"> {excerpt}", ""])
        lines.extend(["", "原文和手稿图像可通过馆藏链接查看。", "", f"资料署名与许可：{ATTRIBUTION}", ""])
        yield record, "\n".join(lines)
