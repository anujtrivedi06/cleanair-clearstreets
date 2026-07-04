"""
Appends one snapshot per zone (current AQI proxy + weather) to
data/processed/history_<zone_id>.json on every pipeline run. This is what
predict_spike.py trains on -- it needs a handful of runs spaced out over time
before predictions turn non-null, so this script should run every time the
pipeline runs (manually now, on the GitHub Actions schedule later).

History files are capped at MAX_HISTORY_POINTS so they don't grow unbounded
over a long-running scheduled job.
"""
import json
from datetime import datetime, timezone

from config import PROCESSED_DIR, RAW_DIR, load_zones

MAX_HISTORY_POINTS = 500
# Don't append more than once within this window, so re-running the pipeline
# by hand a few times in a row doesn't pollute history with near-duplicate points.
MIN_GAP_MINUTES = 30


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def nearest_hourly_index(hourly_times):
    """Index into an Open-Meteo hourly series closest to the current hour."""
    now = datetime.now().strftime("%Y-%m-%dT%H:00")
    if now in hourly_times:
        return hourly_times.index(now)
    # Fall back to the last past timestamp if the exact hour isn't listed.
    past = [i for i, t in enumerate(hourly_times) if t <= now]
    return past[-1] if past else 0


def current_weather_for_zone(zone_id, weather_data):
    entry = weather_data.get(zone_id)
    if not entry or "hourly" not in entry:
        return None
    hourly = entry["hourly"]
    idx = nearest_hourly_index(hourly["time"])
    return {
        "wind_speed": hourly["wind_speed_10m"][idx],
        "humidity": hourly["relative_humidity_2m"][idx],
    }


def append_all():
    zones = load_zones()
    cpcb_records = load_json(RAW_DIR / "cpcb_latest.json", [])
    weather_data = load_json(RAW_DIR / "weather_latest.json", {})
    cpcb_by_station = {r.get("station", "").strip(): r for r in cpcb_records}

    now_iso = datetime.now(timezone.utc).isoformat()
    appended, skipped = 0, 0

    for zone in zones:
        cpcb = cpcb_by_station.get(zone["cpcb_station"].strip())
        weather = current_weather_for_zone(zone["id"], weather_data)
        if not cpcb or not weather:
            skipped += 1
            continue

        history_path = PROCESSED_DIR / f"history_{zone['id']}.json"
        history = load_json(history_path, [])

        if history:
            last_time = datetime.fromisoformat(history[-1]["timestamp"])
            minutes_since_last = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
            if minutes_since_last < MIN_GAP_MINUTES:
                skipped += 1
                continue

        history.append(
            {
                "timestamp": now_iso,
                "aqi": cpcb["pollutant_avg"],
                "wind_speed": weather["wind_speed"],
                "humidity": weather["humidity"],
            }
        )
        history = history[-MAX_HISTORY_POINTS:]

        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        appended += 1

    print(f"History updated: {appended} zones appended, {skipped} skipped")


if __name__ == "__main__":
    append_all()
