"""Stage the motif and area tables published with Liu et al. (2022)."""

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import date
from hashlib import file_digest, sha256
import json
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from bs4 import BeautifulSoup
import yaml

from pipeline.intake_sources import IntakeError
from pipeline.local_standards import CodeEdition, CodeEntry, CodeTable
from pipeline.node_model import Audit, NodeMetadata, Relation, Source, Spatial, Standards

SYSTEM = "berezkin_codes"
CATALOGUE_URL = "https://www.ruthenia.ru/folklore/berezkin/eng.html"
CATALOGUE = "Yu. E. Berezkin and E. N. Duvakin, World mythology and folklore: Analytical catalogue"
DOI = "10.1017/ehs.2022.15"
SUPPLEMENT = ("https://static.cambridge.org/content/id/urn:cambridge.org:id:article:S2513843X22000159"
              "/resource/name/S2513843X22000159sup003.zip")
STUDY = "Liu, X., Rosenberg, N. A., & Greenbaum, G. (2022). Extracting hierarchical features of cultural variation using network-based clustering. Evolutionary Human Sciences, 4, e18."
MOTIF_CODE = re.compile(r"[a-z][0-9]+[a-z0-9]*")
REGIONAL_HUBS = {"a37b": "index_berezkin_a37b", "b3a": "index_berezkin_b3a"}
MOTIF_FILE = "myth_motifs.csv"
REGION_FILE = "myth_regions.csv"
REGION_REVIEW = Path(__file__).resolve().parent.parent / "reference/berezkin_region_review_notes.yaml"
REGION_REVIEW_MARKER = "<!-- astraia:berezkin-region-crosscheck-v1 -->"


@dataclass(frozen=True)
class Motif:
    label: str
    areas: tuple[int, ...]


@dataclass(frozen=True)
class StudyData:
    path: Path
    digest: str
    motifs: dict[str, Motif]
    regions: dict[int, Spatial]

    def source(self, locator: str, *, direct: bool = True) -> Source:
        return Source.model_validate({
            "citation": STUDY, "type": "research_dataset" if direct else "peer_reviewed",
            "doi": DOI, "url": SUPPLEMENT if direct else f"https://doi.org/{DOI}",
            "locator": locator, "local_path": self.path.as_posix() if direct else None,
            "content_sha256": self.digest if direct else None,
        })

    def manifest(self, table: dict[tuple[str, str], CodeEntry]) -> dict:
        return {
            "study": f"https://doi.org/{DOI}", "supplement": SUPPLEMENT,
            "supplement_sha256": self.digest, "catalogue": CATALOGUE_URL,
            "motifs": len(self.motifs), "regions": len(self.regions),
            "distinct_motif_region_links": sum(len(set(motif.areas) & self.regions.keys()) for motif in self.motifs.values()),
            "unknown_region_ids": {code: sorted(set(motif.areas) - self.regions.keys())
                                   for code, motif in self.motifs.items() if set(motif.areas) - self.regions.keys()},
            "duplicate_region_assignments": sum(len(motif.areas) - len(set(motif.areas)) for motif in self.motifs.values()),
            "standard_codes_unmatched": sorted(code for code in self.motifs if (SYSTEM, code) not in table),
            "shared_pending_cards": list(REGIONAL_HUBS.values()),
        }


def read_csv(archive: ZipFile, name: str) -> list[dict[str, str]]:
    paths = [member for member in archive.namelist() if PurePosixPath(member).name == name]
    if len(paths) != 1:
        raise IntakeError(f"附件中须有唯一的 {name}。")
    return list(csv.DictReader(archive.read(paths[0]).decode("utf-8-sig").splitlines()))


def read_study(path: Path) -> StudyData:
    with path.open("rb") as archive_file:
        digest = file_digest(archive_file, "sha256").hexdigest()
    with ZipFile(path) as archive:
        regions, motifs = {}, {}
        for row in read_csv(archive, REGION_FILE):
            area_id = int(row["code"])
            if area_id <= 0 or area_id in regions:
                raise IntakeError(f"地区编号无效或重复。{area_id}")
            regions[area_id] = Spatial(lat=float(row["latitude"]), lng=float(row["longitude"]),
                                       precision="culture_region", location_name=row["area"], culture_region=row["area"])
        for row in read_csv(archive, MOTIF_FILE):
            code, label = row["motif_code"].strip().lower(), row["description"].strip()
            areas = json.loads(row["areas"])
            if (not MOTIF_CODE.fullmatch(code) or code in motifs or not label
                    or not isinstance(areas, list) or not all(type(area) is int for area in areas)):
                raise IntakeError(f"母题数据行无效或重复。{code}")
            motifs[code] = Motif(label, tuple(areas))
    if not motifs or not regions:
        raise IntakeError("论文附件缺少母题或地区资料。")
    return StudyData(path, digest, motifs, regions)


def region_crosschecks(study: StudyData, path: Path = REGION_REVIEW) -> dict[int, dict]:
    """Apply documented cautions only to the exact supplement that was checked."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("regions"), dict):
        raise IntakeError("地区参考点复核记录格式不正确。")
    if document.get("supplement_sha256") != study.digest:
        return {}
    result = {}
    for area, note in document["regions"].items():
        expected = study.regions.get(area)
        if (type(area) is not int or not isinstance(note, dict) or expected is None
                or (note.get("name"), note.get("lat"), note.get("lng"))
                != (expected.location_name, expected.lat, expected.lng)
                or not isinstance(note.get("finding"), str) or not note["finding"].strip()
                or not isinstance(note.get("sources"), list) or not note["sources"]
                or any(not isinstance(source, dict) or not source.get("title") or not source.get("url")
                       for source in note["sources"])):
            raise IntakeError(f"地区参考点复核记录与研究附件不一致。{area}")
        result[area] = {"area_id": area, **note, "checked_at": document["checked_at"], "method": document["method"]}
    return result


def region_review_section(areas: list[int], notes: dict[int, dict], *, is_region: bool) -> str:
    """Keep the caution and the original values with both regions and dependent motifs."""
    if not areas:
        return ""
    lines = [REGION_REVIEW_MARKER, "## 地区参考点待复核", ""]
    for area in sorted(set(areas)):
        note = notes[area]
        lines.append(f"- 地区 {area} · {note['name']}：研究附件原值为纬度 {note['lat']}、经度 {note['lng']}。{note['finding']}")
        if is_region:
            lines.append("  对照来源：" + "；".join(f"[{source['title']}]({source['url']})" for source in note["sources"]) + "。")
    lines += ["", "文化分析区参考点不是原始采录地点。以上坐标暂不作为地图点位；需结合研究区划、原始资料和复核依据确认。", ""]
    return "\n" + "\n".join(lines)


def update_code_table(path: Path, catalogue: Path, study: StudyData) -> int:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    raw = catalogue.read_bytes()
    page = BeautifulSoup(raw, "html.parser")
    definitions = defaultdict(set)
    for paragraph in page.find_all("p"):
        match = re.match(r"^([a-z][0-9]+[a-z0-9]*)\.\s+(.+)$", paragraph.get_text(" ", strip=True), re.I)
        if match:
            code, label = match.groups()
            definitions[code.lower()].add(label.split(". ", 1)[0].strip().rstrip(".").casefold())
    codes = sorted(code for code in study.motifs if len(definitions.get(code, ())) == 1)
    if not codes:
        raise IntakeError("本地目录快照未找到可唯一核对的编号。")
    edition = CodeEdition.model_validate({
        "system": SYSTEM, "citation": f"{CATALOGUE}, English catalogue entry",
        "url": CATALOGUE_URL, "content_sha256": sha256(raw).hexdigest(), "codes": codes,
    })
    editions = [item for item in data.get("editions", []) if item.get("url") != CATALOGUE_URL]
    data["editions"] = [*editions, edition.model_dump(mode="json")]
    CodeTable.model_validate_json(json.dumps(data, ensure_ascii=False))
    with TemporaryDirectory(prefix=".astraia-code-table-", dir=path.resolve().parent) as directory:
        temporary = Path(directory) / "standards.json"
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    return len(codes)


def distribution_cards(study: StudyData, table: dict[tuple[str, str], CodeEntry]):
    audit = Audit(created_at=date.today(), reviewed_by_human=False)
    review = region_crosschecks(study)
    distribution = defaultdict(list)
    for code, motif in study.motifs.items():
        known = sorted(set(motif.areas) & study.regions.keys())
        node_id = REGIONAL_HUBS.get(code, f"index_berezkin_{code}")
        for area in known:
            distribution[area].append(Relation(type="ATTESTS_MOTIF", target=node_id, weight=1.0,
                note=f"论文附件 3 · {MOTIF_FILE} 编号 {code} · {REGION_FILE} 地区 {area}"))
        if code in REGIONAL_HUBS:
            continue
        entry = table.get((SYSTEM, code))
        sources = [study.source(f"附件 3 / {MOTIF_FILE} / motif_code={code}"),
                   study.source("Methods / Folklore variation", direct=False)]
        if entry is not None:
            sources.append(Source(citation=entry.citation, type="official_standard", url=entry.url, locator=code))
        body = (f"\n## 附件原始条目\n\n**{code} · {motif.label}**\n\n"
                f"研究附件为此条标记了 {len(known)} 个已定义的文化分析区。地点采用论文附件中的参考点。"
                "连线展示母题在编码地区的共现。各地的具体文本与采录可循原目录和书目回查。\n")
        unknown = sorted(set(motif.areas) - study.regions.keys())
        if unknown:
            body += f"\n附件中的地区编号 {', '.join(map(str, unknown))} 缺少对应地区定义，待核。\n"
        if entry is None:
            body += "\n原研究编号已保留。现行本地目录缺少可唯一匹配的标准码，等待人工对照版本。\n"
        body += region_review_section([area for area in known if area in review], review, is_region=False)
        yield NodeMetadata(id=node_id, title=f"别列兹金 {code} · {motif.label}", node_type="motif_index",
                           z_layer=3, genre="academic_model", credibility_tier="A", is_fictional_quarantine=False,
                           spatial=None, temporal=None, standards=Standards(berezkin_codes=[entry.code] if entry else []),
                           sources=sources, audit=audit), body

    for area, spatial in sorted(study.regions.items()):
        related = distribution[area]
        sources = [study.source(f"附件 3 / {REGION_FILE} / code={area}"),
                   study.source("Methods / Folklore variation", direct=False)]
        body = (f"\n## 文化分析区\n\n论文附件用 **{spatial.location_name}** 登记编号 {area}。"
                f"数据表中有 {len(related)} 个母题与本区关联。地图坐标是研究作者提供的区域参考点。\n\n"
                "关联页可循母题编号回查研究表与目录。研究表的地区编码用于比较收录范围。"
                "原采录点、年代和传播判断应结合原始资料核查。\n")
        if area in review:
            body += region_review_section([area], review, is_region=True)
            spatial = spatial.model_copy(update={"lat": None, "lng": None})
        yield NodeMetadata(id=f"corpus_berezkin_region_{area}", title=f"母题分布区 · {spatial.location_name}",
                           aliases=[f"Berezkin region {area}"], node_type="myth_corpus", z_layer=2,
                           genre="academic_model", credibility_tier="A", is_fictional_quarantine=False,
                           spatial=spatial, temporal=None, standards=Standards(), relations=related,
                           sources=sources, audit=audit), body
