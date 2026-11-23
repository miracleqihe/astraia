"""Candidate community landmarks from the Council of Indigenous Peoples GIS dataset."""
import json
from pathlib import Path
import re
import unicodedata

from pipeline.intake_sources import IntakeError

GIS_URL = "https://data.gov.tw/dataset/156632"
DATA_URL = "https://data.cip.gov.tw/API/v1/dump/datastore/A53000000A-111027-001"
ALIAS_URL = "https://mioe.openmuseum.tw/digipub_article/73"
RESOURCE_ID = "A53000000A-111027-001"
FIELDS = ("Seq", "DateListed", "縣市", "鄉鎮市區", "村里", "部落名稱", "部落傳統名制_羅馬拼音",
          "定位點", "緯度", "經度", "族別")


def load_gis(path: Path) -> list[dict]:
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"部落 GIS 数据无法读取：{error}") from error
    if (not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict)
            or document[0].get("success") is not True or not isinstance(document[0].get("result"), dict)
            or document[0]["result"].get("resource_id") != RESOURCE_ID
            or not isinstance(document[0]["result"].get("records"), list)
            or not document[0]["result"]["records"]):
        raise IntakeError("部落 GIS 数据的资源编号或结构不符。")
    result, seen = [], set()
    for row in document[0]["result"]["records"]:
        if (not isinstance(row, dict) or type(row.get("Seq")) is not int or row["Seq"] in seen
                or any(not isinstance(row.get(key), str) for key in FIELDS if key != "Seq")):
            raise IntakeError("部落 GIS 数据存在重复编号或缺失字段。")
        seen.add(row["Seq"])
        result.append({key: row[key] for key in FIELDS})
    return result


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).replace("臺", "台").casefold()
    return "".join(char for char in text if char.isalnum())


def _admin(value: str) -> str:
    return re.sub(r"[縣市鄉鎮區]$", "", _normalize(value))


def locator(matches: list[dict]) -> str:
    return "、".join(f"Seq {item['seq']} · {item['部落名称']} · {item['地标']}" for item in matches)


def candidates(location: str, rows: list[dict]) -> list[dict]:
    """Require county, township and a separate community name in the source location."""
    original = _normalize(location)
    if not original:
        return []
    matches = []
    for row in rows:
        county, town = _admin(row["縣市"]), _admin(row["鄉鎮市區"])
        name = re.sub(r"部落$", "", _normalize(row["部落名稱"]))
        if not county or not town or len(name) < 2 or county not in original:
            continue
        after_county = original.split(county, 1)[1]
        if town not in after_county:
            continue
        remainder = after_county.split(town, 1)[1]
        alias = (row["縣市"] == "花蓮縣" and row["鄉鎮市區"] == "光復鄉"
                 and row["部落名稱"] == "馬太鞍部落" and "馬太安" in remainder)
        if name not in remainder and not alias:
            continue
        try:
            lat, lng = float(row["緯度"]), float(row["經度"])
        except ValueError:
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
            continue
        matches.append({"seq": row["Seq"], "登记日期": row["DateListed"], "县市": row["縣市"],
                        "乡镇": row["鄉鎮市區"], "村里": row["村里"], "部落名称": row["部落名稱"],
                        "传统名": row["部落傳統名制_羅馬拼音"], "地标": row["定位點"],
                        "纬度": lat, "经度": lng, "登记族别": row["族別"],
                        "名称对照": "马太安／马太鞍名称对应待复核" if alias else "采集地文字与部落名、县市和乡镇对应待复核",
                        "名称对照依据": ALIAS_URL if alias else None,
                        "坐标范围": "政府资料中的社区地标；非具体采录点或故事发生地",
                        "坐标参考系": "数据提供经纬度；参考系与定位误差待核"})
    return sorted(matches, key=lambda item: item["seq"])
