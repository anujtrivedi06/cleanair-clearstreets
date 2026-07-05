"""
Combine CPCB AQI + FIRMS fire/smoke detections + (optional) citizen photo
severity into a single hotspot score per zone.

Scoring is intentionally simple and explainable for a hackathon demo: a
weighted sum, not a black box. Weights can be tuned once real data is in.
"""
import csv
import json
from pathlib import Path

from config import PROCESSED_DIR, RAW_DIR, load_zones

AQI_WEIGHT = 0.5
FIRMS_WEIGHT = 0.3
PHOTO_WEIGHT = 0.2

# CPCB's public "Poor" AQI category starts at 201 -- a recognizable, citable
# threshold for "how many days was this genuinely bad," rather than an
# arbitrary internal cutoff.
POOR_AQI_THRESHOLD = 200
RECURRENCE_WINDOW_DAYS = 30


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_firms_csv(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize_pm_proxy(pm_avg_value):
    # PM2.5/PM10 average used as an AQI-scale (0-500) severity proxy -- see
    # fetch_cpcb.py docstring for why we don't compute the official sub-index.
    try:
        return min(max(float(pm_avg_value), 0), 500) / 500
    except (TypeError, ValueError):
        return 0.0


def nearest_zone_firms_count(zone, firms_rows, radius_deg=0.05):
    count = 0
    for row in firms_rows:
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except (KeyError, ValueError):
            continue
        if abs(lat - zone["lat"]) < radius_deg and abs(lon - zone["lon"]) < radius_deg:
            count += 1
    return count


def last_known_aqi(zone_id):
    """
    Fallback when a CPCB station reports nothing this cycle (station offline,
    or its PM2.5/PM10 sensors specifically report "NA" while other pollutants
    still work -- both observed in practice). Without this, an offline
    station makes its zone look artificially clean (aqi=None -> score 0),
    which is the opposite of the truth: we just don't know its current state.
    Returns (aqi, timestamp) from the most recent history point, or
    (None, None) if there's no history at all yet.
    """
    history = load_json(PROCESSED_DIR / f"history_{zone_id}.json", [])
    for entry in reversed(history):
        if entry.get("aqi") is not None:
            return entry["aqi"], entry["timestamp"]
    return None, None


def daily_aqi_series(zone_id, days=RECURRENCE_WINDOW_DAYS):
    """
    Aggregates history entries (a mix of ~3-hourly live points and daily
    backfill points -- see append_history.py / backfill_history.py) down to
    one average-AQI point per calendar day, so live and backfilled data are
    comparable on the same daily granularity.
    """
    history = load_json(PROCESSED_DIR / f"history_{zone_id}.json", [])
    by_day = {}
    for entry in history:
        if entry.get("aqi") is None:
            continue
        day = entry["timestamp"][:10]  # "YYYY-MM-DDT..." -> "YYYY-MM-DD"
        by_day.setdefault(day, []).append(entry["aqi"])

    daily_avgs = {day: sum(vals) / len(vals) for day, vals in by_day.items()}
    recent_days = sorted(daily_avgs)[-days:]
    return [round(daily_avgs[d], 1) for d in recent_days]


def recurrence_stats(zone_id):
    series = daily_aqi_series(zone_id)
    poor_days = sum(1 for v in series if v > POOR_AQI_THRESHOLD)
    return {
        "recurrence_days_observed": len(series),
        "recurrence_poor_days": poor_days,
        "sparkline_30d": series,
    }


def fuse():
    zones = load_zones()
    cpcb_records = load_json(RAW_DIR / "cpcb_latest.json", [])
    firms_rows = load_firms_csv(RAW_DIR / "firms_latest.csv")
    photo_scores = load_json(PROCESSED_DIR / "photo_severity.json", {})
    facilities = load_json(PROCESSED_DIR / "facilities.json", {})

    cpcb_by_station = {r.get("station"): r for r in cpcb_records}

    hotspots = []
    for zone in zones:
        cpcb = cpcb_by_station.get(zone["cpcb_station"], {})
        aqi = cpcb.get("pollutant_avg")
        aqi_stale, aqi_as_of = False, None
        if aqi is None:
            aqi, aqi_as_of = last_known_aqi(zone["id"])
            aqi_stale = aqi is not None

        pm_score = normalize_pm_proxy(aqi)
        firms_count = nearest_zone_firms_count(zone, firms_rows)
        firms_score = min(firms_count / 5, 1.0)  # 5+ detections = max score
        photo_entry = photo_scores.get(zone["id"], {})
        photo_score = photo_entry.get("severity", 0.0)

        hotspot_score = (
            AQI_WEIGHT * pm_score + FIRMS_WEIGHT * firms_score + PHOTO_WEIGHT * photo_score
        )

        hotspots.append(
            {
                "zone_id": zone["id"],
                "name": zone["name"],
                "name_hi": zone.get("name_hi", zone["name"]),
                "lat": zone["lat"],
                "lon": zone["lon"],
                "population": zone.get("population", 0),
                "aqi": aqi,
                "aqi_stale": aqi_stale,
                "aqi_as_of": aqi_as_of,
                "firms_detections": firms_count,
                "photo_severity": photo_score,
                "photo_count": photo_entry.get("count", 0),
                "photo_type": photo_entry.get("type", "none"),
                "hotspot_score": round(hotspot_score, 3),
                **recurrence_stats(zone["id"]),
                "schools_count": facilities.get(zone["id"], {}).get("schools_count", 0),
                "hospitals_count": facilities.get(zone["id"], {}).get("hospitals_count", 0),
            }
        )

    out_path = PROCESSED_DIR / "hotspots.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"hotspots": hotspots}, f, indent=2)
    print(f"Wrote {len(hotspots)} zone hotspot scores to {out_path}")
    return hotspots


if __name__ == "__main__":
    fuse()
