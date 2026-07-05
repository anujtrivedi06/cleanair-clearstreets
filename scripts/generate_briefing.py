"""
Generates a one-sentence AI situational briefing per zone using Gemini
(server-side call -- see config.py for why this key never touches the
browser). We compute the historical comparison (7-day / 30-day average AQI)
ourselves with plain arithmetic -- LLMs are unreliable at math -- and only
ask Gemini to reason about likely cause and write the natural-language
summary. That keeps the AI doing synthesis/reasoning work, not decoration.
"""
import statistics
import time

import requests

from config import DEFAULT_HEADERS, GEMINI_API_KEY, PROCESSED_DIR
from fuse_hotspots import load_json

# Deliberately NOT gemini-2.5-flash: that model's free tier is capped at 20
# requests/day for this project and is shared with the browser's citizen
# photo-classification path (Firebase AI Logic). flash-lite is tracked under
# a separate, much higher free-tier quota, so this feature doesn't compete
# with citizen submissions for the same daily budget.
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

BRIEFING_PROMPT_TEMPLATE = """You are writing a one-sentence situational briefing for a municipal
official about air quality in {zone_name}, Delhi NCR.

Current AQI proxy: {current_aqi}
7-day average AQI proxy: {avg_7d}
30-day average AQI proxy: {avg_30d}
Predicted AQI in 24h: {predicted_aqi}
Active fire/smoke satellite detections nearby: {firms_detections}
Recent citizen photo reports: {photo_count} (worst severity {photo_severity}, type: {photo_type})

Write ONE short sentence (max 25 words) explaining the current situation and
most likely cause (e.g. traffic/industrial baseline, fire/stubble burning,
citizen-reported local source, or normal/improving). Be concrete and specific
to the numbers given. Do not just repeat the raw numbers -- interpret them."""


def historical_averages(zone_id):
    history = load_json(PROCESSED_DIR / f"history_{zone_id}.json", [])
    if not history:
        return None, None
    recent_7d = [h["aqi"] for h in history[-7:] if h.get("aqi") is not None]
    recent_30d = [h["aqi"] for h in history[-30:] if h.get("aqi") is not None]
    avg_7d = round(statistics.mean(recent_7d), 1) if recent_7d else None
    avg_30d = round(statistics.mean(recent_30d), 1) if recent_30d else None
    return avg_7d, avg_30d


def call_gemini(prompt, max_retries=3):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(max_retries):
        resp = requests.post(
            GEMINI_URL, params={"key": GEMINI_API_KEY}, json=body, headers=DEFAULT_HEADERS, timeout=30
        )
        if resp.status_code in (429, 503) and attempt < max_retries - 1:
            time.sleep(5 * (attempt + 1))  # backoff: 5s, 10s
            continue
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def briefing_for_zone(hotspot):
    avg_7d, avg_30d = historical_averages(hotspot["zone_id"])
    prompt = BRIEFING_PROMPT_TEMPLATE.format(
        zone_name=hotspot["name"],
        current_aqi=hotspot.get("aqi", "n/a"),
        avg_7d=avg_7d if avg_7d is not None else "insufficient history",
        avg_30d=avg_30d if avg_30d is not None else "insufficient history",
        predicted_aqi=hotspot.get("predicted_aqi_24h", "n/a"),
        firms_detections=hotspot.get("firms_detections", 0),
        photo_count=hotspot.get("photo_count", 0),
        photo_severity=hotspot.get("photo_severity", 0),
        photo_type=hotspot.get("photo_type", "none"),
    )
    return call_gemini(prompt)


def add_briefings(hotspots):
    for hotspot in hotspots:
        try:
            hotspot["ai_briefing"] = briefing_for_zone(hotspot)
        except Exception as e:
            print(f"[warn] briefing failed for {hotspot['zone_id']}: {e}")
            hotspot["ai_briefing"] = None
        time.sleep(4)  # stay comfortably under free-tier RPM limits
    return hotspots
