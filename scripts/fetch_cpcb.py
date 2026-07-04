"""
Pull CPCB/DPCC station-wise air quality data from the data.gov.in API.

Day 1 TODO: sign up at https://data.gov.in, generate an API key, and locate the
resource ID for the live/historical AQI dataset (search "Real Time Air Quality
Index"). Set DATA_GOV_IN_API_KEY and CPCB_RESOURCE_ID as environment variables.
"""
import json

import requests

from config import CPCB_RESOURCE_ID, DATA_GOV_IN_API_KEY, RAW_DIR, load_zones

API_URL = "https://api.data.gov.in/resource/{resource_id}"


def fetch_latest_aqi(limit=1000):
    params = {
        "api-key": DATA_GOV_IN_API_KEY,
        "format": "json",
        "limit": limit,
    }
    resp = requests.get(API_URL.format(resource_id=CPCB_RESOURCE_ID), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def filter_to_ncr_zones(records, zones):
    station_names = {z["cpcb_station"] for z in zones}
    return [r for r in records.get("records", []) if r.get("station") in station_names]


def main():
    zones = load_zones()
    raw = fetch_latest_aqi()
    matched = filter_to_ncr_zones(raw, zones)
    out_path = RAW_DIR / "cpcb_latest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(matched, f, indent=2)
    print(f"Saved {len(matched)} matched station records to {out_path}")


if __name__ == "__main__":
    main()
