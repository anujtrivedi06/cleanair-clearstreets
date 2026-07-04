"""
Pull weather (wind speed, humidity, temperature) per zone from Open-Meteo.
No API key required.
"""
import json

import requests

from config import OPEN_METEO_BASE_URL, RAW_DIR, load_zones


def fetch_weather_for_zone(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
        "forecast_days": 2,
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(OPEN_METEO_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    zones = load_zones()
    all_weather = {}
    for zone in zones:
        all_weather[zone["id"]] = fetch_weather_for_zone(zone["lat"], zone["lon"])
    out_path = RAW_DIR / "weather_latest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_weather, f, indent=2)
    print(f"Saved weather for {len(all_weather)} zones to {out_path}")


if __name__ == "__main__":
    main()
