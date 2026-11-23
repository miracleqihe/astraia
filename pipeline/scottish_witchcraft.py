"""Adapt Edinburgh DataShare's Survey of Scottish Witchcraft and the map team's residence data."""

from collections import defaultdict
import csv
from datetime import date
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from zipfile import ZipFile

from pipeline.intake_sources import IntakeError, one_line
from pipeline.local_standards import normalized_text
from pipeline.node_model import NodeMetadata

DATASET_URL = "https://doi.org/10.7488/ds/100"
MAP_URL = "https://witches.is.ed.ac.uk/resources/"
CITATION = "Goodare, J., Yeoman, L., Martin, L., & Miller, J. Survey of Scottish Witchcraft, 1563–1736. Edinburgh DataShare. CC BY 4.0."
CORPUS = "corpus_scottish_witchcraft_survey"
RESIDENCES = "ArcGIS Online Files/Accused witch residence and gender.csv"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def snapshot_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def historical_reference(row: dict[str, str], archive_hash: str) -> dict:
    parts = [one_line(row[field]) for field in ("SourceRef", "Reference", "Notes") if row[field]]
    return {
        "citation": "爱丁堡调查库登记的史料线索 · " + (" · ".join(parts) or "原表未填写史料名称或位置"),
        "type": "historical_reference", "url": DATASET_URL, "doi": "10.7488/ds/100",
        "locator": f"WDB_Reference · {row['ReferenceRef']} · 案件 {row['CaseRef']}",
        "content_sha256": archive_hash,
    }


def _archive_table(archive: ZipFile, schema: str, name: str) -> list[dict[str, str]]:
    definition = re.search(rf"CREATE TABLE WDB_{name}\s*\((.*?)\n\);", schema, re.S)
    if definition is None:
        raise IntakeError(f"原始 SQL 模式缺少 WDB_{name}。")
    fields = [line.split()[0] for line in definition[1].splitlines() if line.strip()]
    raw = archive.read(f"WDB_{name}.txt").decode("cp1252")
    return [dict(zip(fields, row, strict=True)) for row in csv.reader(StringIO(raw, newline=""))]


def _residence_index(path: Path | None) -> dict[str, tuple[float, float]]:
    if path is None:
        return {}
    with ZipFile(path) as archive:
        raw = archive.read(RESIDENCES).decode("utf-8-sig")
    by_name = defaultdict(set)
    for row in csv.DictReader(StringIO(raw, newline="")):
        try:
            lat, lng = float(row["Latitude"]), float(row["Longitude"])
        except ValueError:
            continue
        name = normalized_text(row["Residence"])
        if name and 54 <= lat <= 61 and -9 <= lng <= -0.5:
            by_name[name].add((lat, lng))
    return {name: next(iter(points)) for name, points in by_name.items() if len(points) == 1}


def _grid_coordinates(row: dict[str, str], prefix: str, transform) -> tuple[float, float] | None:
    letters = row.get(f"{prefix}_NGR_Letters", "").upper().strip()
    east = row.get(f"{prefix}_NGR_Easting", "")
    north = row.get(f"{prefix}_NGR_Northing", "")
    if not re.fullmatch(r"[A-HJ-Z]{2}", letters) or not east.isdecimal() or not north.isdecimal():
        return None
    if int(east) > 999 or int(north) > 999:
        return None
    first, second = (ord(letter) - ord("A") - (letter > "I") for letter in letters)
    easting = ((first - 2) % 5 * 5 + second % 5) * 100000 + int(east) * 100
    northing = (19 - first // 5 * 5 - second // 5) * 100000 + int(north) * 100
    lng, lat = transform(easting, northing)
    return (round(lat, 5), round(lng, 5)) if 54 <= lat <= 61 and -9 <= lng <= -0.5 else None


def _identifier(source_ref: str) -> str:
    return "scot_" + "_".join(part.lower() for part in source_ref.split("/"))


def _choose_location(accused, parish, residence_index, transform):
    town = accused.get("Res_settlement", "")
    county = accused.get("Res_county", "")
    parish_name = parish.get("Parish_Name", "")
    named_location = ", ".join(dict.fromkeys(filter(None, (town, parish_name, county)))) or "苏格兰"
    coordinates = _grid_coordinates(accused, "Res", transform)
    method, precision = "被告表居住地英国国家格网", "city"
    if coordinates is None:
        coordinates = residence_index.get(normalized_text(town))
        method = "爱丁堡地图资料中同名住地的唯一坐标"
    if coordinates is None:
        coordinates = _grid_coordinates(parish, "Parish", transform)
        method, precision = "教区参考表英国国家格网", "province"
    lat, lng = coordinates or (None, None)
    return {"lat": lat, "lng": lng, "precision": precision if coordinates else "culture_region",
            "location_name": named_location, "culture_region": "Europe · Scotland"}, method if coordinates else None


def _temporal(cases: list[dict[str, str]], trials: list[dict[str, str]]) -> dict:
    dates = [record[key] for record in cases for key in ("CaseStart_date", "Case_date")]
    dates.extend(record["TrialDate"] for record in trials)
    years = [int(year) for value in dates for year in re.findall(r"(?<!\d)(1[5-7]\d{2})(?!\d)", value)]
    return {"year_start": min(years, default=None), "year_end": max(years, default=None),
            "era_label": "近代早期苏格兰", "uncertainty_note": "年份来自调查或审判登记，不代表当事人的生卒时间。"}


def _base(node_id, title, node_type, locator, archive_hash, archive_path):
    return {"id": node_id, "title": title, "node_type": node_type, "z_layer": 1 if node_type == "case" else 2,
            "genre": "historical_archive", "credibility_tier": "A", "is_fictional_quarantine": False,
            "spatial": None, "temporal": None, "standards": {"ocm_codes": ["754"]},
            "sources": [{"citation": CITATION, "type": "scholarly_database", "url": DATASET_URL,
                         "doi": "10.7488/ds/100", "locator": locator, "content_sha256": archive_hash,
                         "local_path": snapshot_path(archive_path)}],
            "audit": {"created_at": date.today(), "reviewed_by_human": False}}


def scottish_cards(archive_path: Path, schema_path: Path, map_path: Path | None):
    try:
        from pyproj import Transformer
    except ImportError as error:
        raise IntakeError("转换英国国家格网需要安装项目的 datasets 依赖。") from error

    transform = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True).transform
    schema = schema_path.read_text(encoding="utf-8-sig")
    archive_hash = sha256(archive_path.read_bytes()).hexdigest()
    map_hash = sha256(map_path.read_bytes()).hexdigest() if map_path else None
    with ZipFile(archive_path) as archive:
        accused_rows = _archive_table(archive, schema, "Accused")
        case_rows = _archive_table(archive, schema, "Case")
        trial_rows = _archive_table(archive, schema, "Trial")
        references = _archive_table(archive, schema, "Reference")
        parishes = {row["Parishref"]: row for row in _archive_table(archive, schema, "Ref_Parish")}

    by_accused, by_case, reference_by_case = defaultdict(list), defaultdict(list), defaultdict(list)
    for case in case_rows:
        by_accused[case["AccusedRef"]].append(case)
    for trial in trial_rows:
        by_case[trial["CaseRef"]].append(trial)
    for reference in references:
        reference_by_case[reference["CaseRef"]].append(reference)
    official_refs = {row["AccusedRef"] for row in accused_rows}
    separate_cases = [case for case in case_rows if case["AccusedRef"] not in official_refs]
    residence_index = _residence_index(map_path)

    corpus = _base(CORPUS, "爱丁堡大学苏格兰猎巫调查库（1563–1736）", "myth_corpus", "WDB_Accused、WDB_Case、WDB_Trial", archive_hash, archive_path)
    corpus["temporal"] = {"year_start": 1563, "year_end": 1736, "era_label": "近代早期苏格兰"}
    body = (f"\n## 调查库范围\n\n本批依据 Edinburgh DataShare 原始表，整理 {len(accused_rows):,} 条被告登记，"
            f"另保留 {len(separate_cases):,} 条没有可联接被告登记的案件。每条记录保留档号和表名。\n\n"
            "项目 FAQ 统计涉及 3,837 人或无名组。批次按实际档号组织，组数和人数保持原始登记口径。"
            " [项目 FAQ](https://witches.hca.ed.ac.uk/faq/)\n\n"
            "住址点来自原表格网、同名地点对应的唯一地图坐标或教区格网。点位记录居住地或教区。\n")
    yield NodeMetadata.model_validate(corpus), body

    for accused, cases in [*((row, by_accused[row["AccusedRef"]]) for row in accused_rows),
                           *(({}, [case]) for case in separate_cases)]:
        reference = accused.get("AccusedRef") or cases[0]["CaseRef"]
        name = one_line(" ".join((accused.get("FirstName", ""), accused.get("LastName", ""))))
        group_name = one_line(cases[0]["CaseCommonName"]) if cases else ""
        title = f"苏格兰猎巫档案 · {name or group_name or reference}"
        source_table = "WDB_Accused" if accused else "WDB_Case"
        data = _base(_identifier(reference), title, "case", f"{source_table} · {reference}", archive_hash, archive_path)
        if name:
            data["aliases"] = [name, reference]
        trials = [trial for case in cases for trial in by_case[case["CaseRef"]]]
        for case in cases:
            data["sources"].extend(historical_reference(row, archive_hash) for row in reference_by_case[case["CaseRef"]])
        data["spatial"], method = _choose_location(accused, parishes.get(accused.get("Res_parish"), {}), residence_index, transform)
        data["temporal"] = _temporal(cases, trials)
        data["relations"] = [{"type": "PART_OF_MACRO_TREND", "target": CORPUS, "note": "归于爱丁堡大学调查库档案组。"}]
        if method and method.startswith("爱丁堡"):
            data["sources"].append({"citation": "University of Edinburgh Map of Accused Witches. Residence CSV derived from Wikidata.",
                                    "type": "gazetteer", "url": MAP_URL,
                                    "locator": f"{RESIDENCES} · {accused['Res_settlement']}", "content_sha256": map_hash,
                                    "local_path": snapshot_path(map_path)})

        lines = ["", "## 原始登记", "", f"- 档号 `{reference}`", f"- 数据表 `{source_table}`"]
        for label, value in (("姓名", name), ("性别", accused.get("Sex")), ("住址", accused.get("Res_settlement")),
                             ("郡", accused.get("Res_county")), ("定位依据", method)):
            if value:
                lines.append(f"- {label}　{one_line(value)}")
        for case in cases:
            date_label = one_line(case["CaseStart_date"] or case["Case_date"])
            lines.append(f"- 调查 `{case['CaseRef']}`" + (f"　{date_label}" if date_label else ""))
            if not accused and case["Suspects_text"]:
                lines.append(f"- 原表中登记的涉案人数　{case['Suspects_text']}")
        for trial in trials:
            fields = " · ".join(one_line(trial[key]) for key in ("TrialDate", "TrialPlace", "Verdict") if trial[key])
            lines.append(f"- 审判 `{trial['Trialref']}`" + (f"　{fields}" if fields else ""))
        lines.extend(["", "OCM 754 用于检索巫术指控及其司法语境。入库内容由原始表转写。", ""])
        yield NodeMetadata.model_validate(data), "\n".join(lines)
