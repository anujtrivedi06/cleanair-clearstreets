"""
Refreshes AI zone briefings for all zones, once/day (see
.github/workflows/refresh-briefings.yml) -- decoupled from the 3-hourly data
pipeline (run_pipeline.py) because the Gemini free tier caps each model at
20 requests/day per project, and 12 zones every 3 hours would need ~96/day.

Reads and writes web/data/hotspots.json directly (the file run_pipeline.py
already publishes), rather than re-running the whole data pipeline.
"""
import json

import generate_briefing
from config import WEB_DATA_DIR


def main():
    path = WEB_DATA_DIR / "hotspots.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    data["hotspots"] = generate_briefing.add_briefings(data["hotspots"])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Refreshed briefings for {len(data['hotspots'])} zones -> {path}")


if __name__ == "__main__":
    main()
