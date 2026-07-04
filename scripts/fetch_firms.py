"""
Pull active fire/smoke hotspot detections over Delhi NCR from NASA FIRMS.

Day 1 TODO: get a free MAP_KEY from https://firms.modaps.eosdis.nasa.gov/api/
and set FIRMS_MAP_KEY as an environment variable.
"""
import json

import requests

from config import DEFAULT_HEADERS, FIRMS_MAP_KEY, NCR_BBOX, RAW_DIR

# VIIRS_SNPP_NRT = near-real-time VIIRS active fire product.
FIRMS_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/"
    "{min_lon},{min_lat},{max_lon},{max_lat}/1"
)


def fetch_ncr_fire_hotspots():
    url = FIRMS_URL.format(key=FIRMS_MAP_KEY, **NCR_BBOX)
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text  # CSV


def main():
    csv_text = fetch_ncr_fire_hotspots()
    out_path = RAW_DIR / "firms_latest.csv"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(csv_text)
    print(f"Saved FIRMS hotspot CSV to {out_path}")


if __name__ == "__main__":
    main()
