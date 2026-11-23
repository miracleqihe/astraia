"""Read bibliographic fields from saved Nichibunken catalogue cards."""

from datetime import date
from hashlib import sha256
from pathlib import Path
import re

from bs4 import BeautifulSoup
import yaml

from pipeline.ingest_agent import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

SEARCH_URL = ("https://www.nichibun.ac.jp/cgi-bin/YoukaiDB3/ksearch.cgi?"
              "Area=%E5%8C%97%E6%B5%B7%E9%81%93%E3%83%BB%E6%9D%B1%E5%8C%97&"
              "Name=%E3%82%AB%E3%83%83%E3%83%91&Pref=")
CORPUS = "corpus_nichibun_tohoku_kappa"
INDEX = "index_nichibun_tohoku_kappa"
PLACES = PROJECT_ROOT / "reference/nichibun_places.yaml"


def card_fields(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_bytes()
    soup = BeautifulSoup(raw.decode("utf-8-sig"), "html.parser")
    fields = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            continue
        label = cells[1].get_text(" ", strip=True)
        if label in {"番号", "呼称（ヨミ）", "呼称（漢字）", "執筆者", "論文名", "書名・誌名",
                     "巻・号／通巻・号", "発行年（西暦）", "掲載箇所・開始頁", "掲載箇所・終了頁",
                     "地域（都道府県名）", "地域（市・郡名）", "地域（区町村名）", "話者（引用文献）"}:
            if label in fields:
                raise IntakeError(f"馆藏卡片字段重复。{path.name} · {label}")
            fields[label] = cells[2].get_text(" ", strip=True)
    identifier = fields.get("番号", "")
    if not re.fullmatch(r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)*", identifier) or identifier != path.stem:
        raise IntakeError(f"馆藏卡片编号与文件名不符。{path}")
    return fields, sha256(raw).hexdigest()


def local_path(path: Path) -> str:
    absolute = path.resolve()
    return absolute.relative_to(PROJECT_ROOT).as_posix() if absolute.is_relative_to(PROJECT_ROOT) else str(absolute)


def node_id(identifier: str) -> str:
    return f"case_nichibun_{re.sub(r'[^a-z0-9]+', '_', identifier.casefold()).strip('_')}"


def nichibun_cards(paths: list[Path], *, include_groups: bool = True):
    place_document = yaml.safe_load(PLACES.read_text(encoding="utf-8"))
    if not isinstance(place_document, dict) or place_document.get("version") != 1 or not isinstance(place_document.get("places"), dict):
        raise IntakeError("日文研地名参考表格式不正确。")
    places = place_document["places"]
    audit = {"created_at": date.today(), "reviewed_by_human": False}
    source = {"citation": "国际日本文化研究中心，怪異・妖怪伝承データベース，北海道・東北・カッパ检索。",
              "type": "archival_catalogue", "url": SEARCH_URL, "locator": "北海道・東北 / カッパ"}
    common = {"genre": "academic_model", "credibility_tier": "A", "is_fictional_quarantine": False,
              "spatial": None, "temporal": None, "standards": {}, "sources": [source], "audit": audit}
    if include_groups:
        yield NodeMetadata.model_validate({"id": CORPUS, "title": "日文研东北与北海道河童检索档案",
                                            "node_type": "myth_corpus", "z_layer": 2, **common}), (
            "\n## 馆藏范围\n\n此组汇集日文研怪异·妖怪传承数据库中，按北海道与东北地区、"
            "カッパ称呼检索得到的馆藏卡片。每项保留原卡编号、出版资料和地域，供逐项回查。\n"
        )
        yield NodeMetadata.model_validate({"id": INDEX, "title": "日文研东北与北海道河童称谓索引",
                                            "node_type": "motif_index", "z_layer": 3, **common}), (
            "\n## 馆藏称谓\n\n索引表示日文研检索结果的共同称呼。各条叙事的用词、地域与文化背景"
            "可循馆藏卡片及其所引文献分别核对。\n"
        )
    for path in sorted(paths):
        fields, digest = card_fields(path)
        identifier = fields["番号"]
        if ("カッパ" not in fields.get("呼称（ヨミ）", "")
                or fields.get("地域（都道府県名）") not in {"北海道", "青森県", "岩手県", "秋田県", "宮城県", "山形県", "福島県"}):
            raise IntakeError(f"馆藏卡不符合北海道·东北地区的カッパ称呼检索范围。{identifier}")
        names = list(dict.fromkeys(filter(None, (fields.get("呼称（漢字）"), fields.get("呼称（ヨミ）")))))
        location = " ".join(filter(None, (fields.get("地域（都道府県名）"), fields.get("地域（市・郡名）"),
                                          fields.get("地域（区町村名）"))))
        year = re.search(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)", fields.get("発行年（西暦）", ""))
        pages = "–".join(dict.fromkeys(filter(None, (fields.get("掲載箇所・開始頁"), fields.get("掲載箇所・終了頁")))))
        citation = "，".join(filter(None, (
            "国际日本文化研究中心，怪異・妖怪伝承数据库，记录 " + identifier,
            fields.get("執筆者"), fields.get("論文名"), fields.get("書名・誌名"),
            fields.get("巻・号／通巻・号"), fields.get("発行年（西暦）"), f"引用页 {pages}" if pages else "",
        )))
        raw_source = {
            "citation": citation, "type": "archival_catalogue",
            "url": f"https://www.nichibun.ac.jp/cgi-bin/YoukaiDB3/youkai_card.cgi?ID={identifier}",
            "locator": f"馆藏卡 {identifier}" + (f" / 引用页 {pages}" if pages else ""),
            "local_path": local_path(path), "content_sha256": digest,
        }
        spatial = ({"precision": "city" if fields.get("地域（市・郡名）") else "province",
                    "location_name": location, "culture_region": "Asia · Japan"} if location else None)
        place = places.get(location)
        sources = [raw_source]
        if place and spatial:
            spatial.update(lat=place["lat"], lng=place["lng"], precision="city",
                           location_name=f"{location}（{place['label']}）")
            sources.append({"citation": place["citation"], "type": "gazetteer",
                            "url": place["url"], "locator": place["label"]})
        temporal = ({"year_start": int(year[1]), "year_end": int(year[1]), "era_label": "资料出版",
                     "uncertainty_note": "年份为所引刊物的出版时间，传承发生时间未定。"} if year else None)
        label = " / ".join(names) or identifier
        record = NodeMetadata.model_validate({
            "id": node_id(identifier), "title": f"日文研 {identifier} · {label}",
            "aliases": [identifier, *names], "node_type": "case", "z_layer": 1, "genre": "unclassified",
            "credibility_tier": "A", "is_fictional_quarantine": False, "spatial": spatial, "temporal": temporal,
            "standards": {}, "sources": sources, "audit": audit,
            "relations": [
                {"type": "PART_OF_MACRO_TREND", "target": CORPUS, "note": "日文研北海道·东北地区检索结果。"},
                {"type": "HAS_MOTIF", "target": INDEX, "note": "馆藏卡出现在カッパ称呼检索结果。"},
            ],
        })
        lines = ["", "## 馆藏与所引资料", "", f"日文研馆藏编号 {identifier}，称呼为 {label}。"]
        if location:
            lines.append(f"馆藏登记地域为 {location}。")
        if place:
            lines.append(f"地图坐标采用 {place['label']}，具体采录位置待核。")
        if fields.get("話者（引用文献）"):
            lines.append(f"馆藏卡记录的讲述者或引文对象为 {fields['話者（引用文献）']}。")
        lines.extend(["", citation + "。", "", "年份对应所引资料的出版时间。正文与摘要可通过馆藏链接回查。", ""])
        yield record, "\n".join(lines)
