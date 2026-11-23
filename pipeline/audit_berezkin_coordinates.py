"""Save a reproducible country-overlay check for documented doubtful points."""
import argparse
import json
from pathlib import Path
import subprocess

from pipeline.berezkin_distribution import read_study, region_crosschecks
from pipeline.ingest_agent import PROJECT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=PROJECT_ROOT / ".local/import-sources/liu-2022-supplement-3.zip")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".local/intake-qa/berezkin-coordinate-map-check.json")
    args = parser.parse_args()
    study = read_study(args.study)
    checks = region_crosschecks(study)
    if not checks:
        raise ValueError("当前附件与地区复核记录的哈希不一致。")
    points = [{"area_id": area, "lat": note["lat"], "lng": note["lng"]} for area, note in sorted(checks.items())]
    completed = subprocess.run(
        ["node", str(PROJECT_ROOT / "web/scripts/check-coordinate-countries.mjs")],
        input=json.dumps(points), capture_output=True, text=True, encoding="utf-8", check=True,
    )
    output = json.loads(completed.stdout)
    output["supplement_sha256"] = study.digest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
