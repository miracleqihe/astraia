"""Link Scottish archive identifiers to the map export through a dated Wikidata snapshot."""

from collections import defaultdict
import csv
from hashlib import sha256
from io import StringIO
import json
import math
from pathlib import Path
import re
from zipfile import ZipFile

from pyproj import Geod

from pipeline.fetch_scottish_wikidata import parse_snapshot
from pipeline.scottish_witchcraft import MAP_URL, RESIDENCES, snapshot_path

GEOD = Geod(ellps="WGS84")
DISTANCE_REVIEW_KM = 10.0


class ScottishIdentityIndex:
    def __init__(self, snapshot: Path, maps: Path):
        raw = snapshot.read_bytes()
        self.snapshot_sha256 = sha256(raw).hexdigest()
        manifest = json.loads(snapshot.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        if manifest.get("sha256") != self.snapshot_sha256 or manifest.get("property") != "P4478":
            raise ValueError("Wikidata 快照和来源清单的哈希或属性不一致。")
        self.retrieved_at = manifest.get("retrieved_at")
        if not isinstance(self.retrieved_at, str) or not self.retrieved_at:
            raise ValueError("Wikidata 快照缺少获取时间。")
        self.by_ref, self.by_qid = defaultdict(set), defaultdict(set)
        for qid, reference in parse_snapshot(raw):
            self.by_ref[reference].add(qid)
            self.by_qid[qid].add(reference)
        self.map_sha256 = sha256(maps.read_bytes()).hexdigest()
        self.map_path = snapshot_path(maps)
        self.by_map_qid = defaultdict(list)
        with ZipFile(maps) as archive:
            rows = csv.DictReader(StringIO(archive.read(RESIDENCES).decode("utf-8-sig"), newline=""))
            for row in rows:
                match = re.fullmatch(r"https?://www\.wikidata\.org/(?:entity|wiki)/(Q[1-9]\d*)", row["Wikidata Page"])
                try:
                    lat, lng = float(row["Latitude"]), float(row["Longitude"])
                except (TypeError, ValueError):
                    continue
                if not match or not math.isfinite(lat) or not math.isfinite(lng) or not (54 <= lat <= 61 and -9 <= lng <= -0.5):
                    continue
                qid = match[1]
                self.by_map_qid[qid].append({"qid": qid, "name": row["Name"], "residence": row["Residence"],
                    "lat": lat, "lng": lng, "gender": row["Gender"]})

    def lookup(self, reference: str, coordinates: tuple[float, float] | None = None) -> dict:
        qids = sorted(self.by_ref.get(reference, set()))
        entities = [{"qid": qid, "url": f"https://www.wikidata.org/wiki/{qid}",
                     "other_survey_ids": sorted(self.by_qid[qid] - {reference})} for qid in qids]
        candidates = []
        for qid in qids:
            for candidate in self.by_map_qid[qid]:
                entry = dict(candidate)
                if coordinates is not None:
                    lat, lng = coordinates
                    _, _, metres = GEOD.inv(lng, lat, entry["lng"], entry["lat"])
                    entry["distance_km"] = round(metres / 1000, 2)
                    entry["distance_over_threshold"] = metres > DISTANCE_REVIEW_KM * 1000
                candidates.append(entry)
        candidates.sort(key=lambda item: (item["qid"], item["residence"], item["lat"], item["lng"]))
        return {"survey_id": reference, "property": "P4478", "snapshot_sha256": self.snapshot_sha256,
                "retrieved_at": self.retrieved_at, "map_sha256": self.map_sha256, "map_url": MAP_URL,
                "map_locator": RESIDENCES, "map_local_path": self.map_path,
                "entities": entities, "map_candidates": candidates,
                "ambiguous_identity": len(qids) > 1 or any(entity["other_survey_ids"] for entity in entities),
                "coordinate_conflict": bool(coordinates is not None and candidates
                    and all(candidate["distance_over_threshold"] for candidate in candidates))}
