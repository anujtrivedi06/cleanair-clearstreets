"""
Patches schools_count/hospitals_count into the already-published
web/data/hotspots.json, without re-running the full data pipeline. Used by
.github/workflows/refresh-facilities.yml, which runs in a fresh checkout
that doesn't have the CPCB/FIRMS raw data files (gitignored) needed to run
fuse_hotspots.py properly -- this only touches the two facility fields and
leaves everything else in the published file untouched.
"""
import json

from config import PROCESSED_DIR, WEB_DATA_DIR


def main():
    facilities_path = PROCESSED_DIR / "facilities.json"
    hotspots_path = WEB_DATA_DIR / "hotspots.json"

    with open(facilities_path, encoding="utf-8") as f:
        facilities = json.load(f)
    with open(hotspots_path, encoding="utf-8") as f:
        data = json.load(f)

    for hotspot in data["hotspots"]:
        entry = facilities.get(hotspot["zone_id"], {})
        hotspot["schools_count"] = entry.get("schools_count", 0)
        hotspot["hospitals_count"] = entry.get("hospitals_count", 0)

    with open(hotspots_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Merged facility counts into {len(data['hotspots'])} zones -> {hotspots_path}")


if __name__ == "__main__":
    main()
