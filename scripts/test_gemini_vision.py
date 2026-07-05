"""
One-off local test of the Gemini vision classification prompt, mirroring
web/js/submit.js exactly, so prompt/response issues are caught here instead
of in the browser. Not part of the pipeline -- run manually:
  python scripts/test_gemini_vision.py path/to/photo.jpg
"""
import base64
import json
import sys

import requests

from config import GEMINI_API_KEY, GEMINI_MODEL

CLASSIFY_PROMPT = """You are classifying a photo reported by a citizen for a
neighbourhood pollution monitoring system. Respond ONLY with compact JSON of the
form {"type": "smoke"|"dust"|"garbage_burning"|"haze"|"none", "severity": 0.0-1.0,
"reasoning": "one short sentence"}. severity 1.0 = extreme/hazardous, 0.0 = no
visible pollution."""


def classify(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "contents": [
            {
                "parts": [
                    {"text": CLASSIFY_PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }
        ]
    }
    resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/sample_smog.jpg"
    result = classify(path)
    print(json.dumps(result, indent=2))
