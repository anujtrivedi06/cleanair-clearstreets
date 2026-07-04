"""
One-time (or occasional) backfill of historical training data for
predict_spike.py, using Open-Meteo's Air Quality Archive (CAMS reanalysis
model, not raw CPCB ground-station data) + Weather Archive.

IMPORTANT: this is a model-based historical PROXY, not the same CPCB ground
feed used for live/current readings (fetch_cpcb.py). CPCB's live API has no
retained history (confirmed empirically -- see project notes), so there is no
real "past CPCB data" to pull. This backfill exists purely to bootstrap the
regression in predict_spike.py with enough points to train on quickly, rather
than waiting ~1-2 days for live 3-hourly accumulation to cross the minimum.
Label this data source explicitly as a proxy in any write-up/demo.

Aggregates to one point per day (mean of that day's hourly values), matching
the same aqi-proxy formula used elsewhere: average of PM2.5 + PM10.
"""
import json
from collections import defaultdict
from datetime import date, timedelta

import requests

from config import DEFAULT_HEADERS, OPEN_METEO_ARCHIVE_URL, PROCESSED_DIR, load_zones

AIR_QUALITY_ARCHIVE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
BACKFILL_DAYS = 90
MAX_HISTORY_POINTS = 500


def fetch_air_quality_history(lat, lon, start_date, end_date):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "pm10,pm2_5",
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(AIR_QUALITY_ARCHIVE_URL, params=params, headers=DEFAULT_HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_weather_history(lat, lon, start_date, end_date):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,relative_humidity_2m",
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, headers=DEFAULT_HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()


def aggregate_daily(hourly, value_keys):
    """Group hourly series by calendar date, return {date: {key: mean}}."""
    by_date = defaultdict(lambda: defaultdict(list))
    times = hourly.get("time", [])
    for i, ts in enumerate(times):
        day = ts[:10]  # "YYYY-MM-DDTHH:MM" -> "YYYY-MM-DD"
        for key in value_keys:
            values = hourly.get(key, [])
            if i < len(values) and values[i] is not None:
                by_date[day][key].append(values[i])

    daily_means = {}
    for day, series in by_date.items():
        if all(series.get(k) for k in value_keys):
            daily_means[day] = {k: sum(series[k]) / len(series[k]) for k in value_keys}
    return daily_means


def backfill_zone(zone, days=BACKFILL_DAYS):
    end_date = date.today() - timedelta(days=1)  # yesterday: today may be incomplete
    start_date = end_date - timedelta(days=days)

    aq = fetch_air_quality_history(zone["lat"], zone["lon"], start_date.isoformat(), end_date.isoformat())
    weather = fetch_weather_history(zone["lat"], zone["lon"], start_date.isoformat(), end_date.isoformat())

    aq_daily = aggregate_daily(aq.get("hourly", {}), ["pm2_5", "pm10"])
    weather_daily = aggregate_daily(weather.get("hourly", {}), ["wind_speed_10m", "relative_humidity_2m"])

    common_days = sorted(set(aq_daily) & set(weather_daily))
    entries = [
        {
            "timestamp": f"{day}T12:00:00+00:00",
            "aqi": round((aq_daily[day]["pm2_5"] + aq_daily[day]["pm10"]) / 2, 1),
            "wind_speed": round(weather_daily[day]["wind_speed_10m"], 1),
            "humidity": round(weather_daily[day]["relative_humidity_2m"], 1),
            "source": "open_meteo_backfill",
        }
        for day in common_days
    ]

    history_path = PROCESSED_DIR / f"history_{zone['id']}.json"
    existing = []
    if history_path.exists():
        with open(history_path, encoding="utf-8") as f:
            existing = json.load(f)

    # Backfilled days are older than anything already recorded live; merge and
    # dedupe by timestamp in case a date somehow appears in both.
    merged = {e["timestamp"]: e for e in entries}
    for e in existing:
        merged[e["timestamp"]] = e
    combined = sorted(merged.values(), key=lambda e: e["timestamp"])[-MAX_HISTORY_POINTS:]

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    return len(entries)


def main():
    zones = load_zones()
    for zone in zones:
        try:
            count = backfill_zone(zone)
            print(f"{zone['id']}: backfilled {count} daily points")
        except Exception as e:
            print(f"[warn] backfill failed for {zone['id']}: {e}")


if __name__ == "__main__":
    main()
