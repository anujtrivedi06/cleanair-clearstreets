"""
Orchestrates the frequent data refresh: fetch -> fuse -> predict -> merge ->
publish to web/data/hotspots.json for the frontend to read as a static file.

AI zone briefings are deliberately NOT generated here -- see
generate_briefings.py and .github/workflows/refresh-briefings.yml. The
Gemini free tier caps each model at 20 requests/day per project; running all
12 zones' briefings on this pipeline's 3-hourly cadence would need ~96
requests/day, far over budget. Briefings are refreshed once/day instead
(12/day, comfortable buffer left for manual triggers), and this script
carries forward whatever briefing was last generated so the UI never loses
it between briefing refreshes.

Run manually during development:  python scripts/run_pipeline.py
Run in CI: see .github/workflows/update-data.yml
"""
import json

import append_history
import fetch_cpcb
import fetch_firms
import fetch_photo_reports
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


def carry_forward_briefings(hotspots):
    existing_path = WEB_DATA_DIR / "hotspots.json"
    if not existing_path.exists():
        return hotspots
    with open(existing_path, encoding="utf-8") as f:
        existing = {h["zone_id"]: h for h in json.load(f).get("hotspots", [])}
    for h in hotspots:
        prev = existing.get(h["zone_id"], {})
        h["ai_briefing"] = prev.get("ai_briefing")
        h["ai_briefing_hi"] = prev.get("ai_briefing_hi")
        h["ai_briefing_source"] = prev.get("ai_briefing_source")
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
        fetch_photo_reports.main()
    except Exception as e:
        print(f"[warn] Photo reports fetch failed, continuing with stale/empty data: {e}")

    try:
        append_history.append_all()
    except Exception as e:
        print(f"[warn] History append failed, continuing: {e}")

    hotspots = fuse_hotspots.fuse()
    predict_spike.main()
    hotspots = merge_predictions_into_hotspots(hotspots)
    hotspots = carry_forward_briefings(hotspots)
    publish(hotspots)


if __name__ == "__main__":
    main()
