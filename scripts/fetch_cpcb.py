"""
Pull CPCB/DPCC/HSPCB/UPPCB station-wise air quality data from the data.gov.in
"Real time Air Quality Index from various locations" API
(resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69).

This feed is per-pollutant, per-station (each row = one pollutant reading at
one station), not a single composite AQI number. Computing the official CPCB
AQI sub-index formula is out of scope for this build, so we use the average
of PM2.5 + PM10 pollutant_avg (the two dominant pollutants driving Delhi NCR
air quality) as a practical severity proxy -- defensible for a hackathon demo,
not a substitute for the official AQI calculation.
"""
import json
from collections import defaultdict

import requests

from config import (
    CPCB_RESOURCE_ID,
    DATA_GOV_IN_API_KEY,
    DEFAULT_HEADERS,
    NCR_STATES,
    RAW_DIR,
    load_zones,
)

API_URL = f"https://api.data.gov.in/resource/{CPCB_RESOURCE_ID}"
PROXY_POLLUTANTS = {"PM2.5", "PM10"}


def fetch_state_records(state, limit=500):
    params = {
        "api-key": DATA_GOV_IN_API_KEY,
        "format": "json",
        "limit": limit,
        "filters[state]": state,
    }
    resp = requests.get(API_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("records", [])


def fetch_all_ncr_records():
    records = []
    for state in NCR_STATES:
        records.extend(fetch_state_records(state))
    return records


def compute_station_severity(records, zones):
    """Group PM2.5/PM10 readings by station, average them into one proxy score."""
    # CPCB feed occasionally has stray leading/trailing whitespace in station
    # names (observed on "Dwarka-Sector 8, Delhi - DPCC "), so match on the
    # stripped form rather than requiring an exact byte-for-byte match.
    station_names = {z["cpcb_station"].strip() for z in zones}
    by_station = defaultdict(list)

    for r in records:
        station = (r.get("station") or "").strip()
        pollutant = r.get("pollutant_id")
        if station not in station_names or pollutant not in PROXY_POLLUTANTS:
            continue
        try:
            avg_val = float(r.get("pollutant_avg") or r.get("avg_value"))
        except (TypeError, ValueError):
            continue
        by_station[station].append(avg_val)

    return {
        station: {"pollutant_avg": round(sum(vals) / len(vals), 1), "readings": len(vals)}
        for station, vals in by_station.items()
    }


def main():
    zones = load_zones()
    raw_records = fetch_all_ncr_records()
    station_severity = compute_station_severity(raw_records, zones)

    # Reshape into the {station, pollutant_avg} format fuse_hotspots.py expects.
    matched = [
        {"station": station, "pollutant_avg": data["pollutant_avg"]}
        for station, data in station_severity.items()
    ]

    out_path = RAW_DIR / "cpcb_latest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(matched, f, indent=2)
    print(f"Saved {len(matched)} matched station severity scores to {out_path}")
    missing = {z["cpcb_station"] for z in zones} - set(station_severity)
    if missing:
        print(f"[warn] no PM2.5/PM10 data found for stations: {sorted(missing)}")


if __name__ == "__main__":
    main()
