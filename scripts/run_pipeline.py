"""
Orchestrates the full pipeline: fetch -> fuse -> predict -> merge -> publish
to web/data/hotspots.json for the frontend to read as a static file.

Run manually during development:  python scripts/run_pipeline.py
Run in CI: see .github/workflows/update-data.yml
"""
import json
import shutil

import append_history
import fetch_cpcb
import fetch_firms
import fetch_weather
import fuse_hotspots
import predict_spike
from config import PROCESSED_DIR, WEB_DATA_DIR


def merge_predictions_into_hotspots(hotspots):
    with open(PROCESSED_DIR / "predictions.json", encoding="utf-8") as f:
        predictions = json.load(f)
    for h in hotspots:
        pred = predictions.get(h["zone_id"], {})
        h["predicted_aqi_24h"] = pred.get("predicted_aqi_24h")
    return hotspots


def publish(hotspots):
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WEB_DATA_DIR / "hotspots.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"hotspots": hotspots}, f, indent=2)
    print(f"Published {len(hotspots)} zones to {out_path}")


def main():
    try:
        fetch_cpcb.main()
    except Exception as e:
        print(f"[warn] CPCB fetch failed, continuing with stale/empty data: {e}")
    try:
        fetch_firms.main()
    except Exception as e:
        print(f"[warn] FIRMS fetch failed, continuing with stale/empty data: {e}")
    try:
        fetch_weather.main()
    except Exception as e:
        print(f"[warn] Weather fetch failed, continuing: {e}")

    try:
        append_history.append_all()
    except Exception as e:
        print(f"[warn] History append failed, continuing: {e}")

    hotspots = fuse_hotspots.fuse()
    predict_spike.main()
    hotspots = merge_predictions_into_hotspots(hotspots)
    publish(hotspots)


if __name__ == "__main__":
    main()
