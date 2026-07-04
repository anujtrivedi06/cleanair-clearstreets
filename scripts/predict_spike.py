"""
Simple, explainable 24h AQI spike predictor: linear regression on lagged AQI
+ weather (wind speed, humidity) per zone. Intentionally simple so it stays
defensible under judge questioning -- swap in something fancier later if time
allows, but a transparent model beats a fragile black box for a 4-day build.
"""
import json

import numpy as np
from sklearn.linear_model import LinearRegression

from config import PROCESSED_DIR, RAW_DIR, load_zones


def load_history(zone_id):
    """
    TODO (Day 2): replace with real historical CPCB+weather series per zone,
    loaded from data/processed/history_<zone_id>.json once Day 1 data pull is
    in place. Expected shape: list of {aqi, wind_speed, humidity} ordered by
    day, oldest first.
    """
    path = PROCESSED_DIR / f"history_{zone_id}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def predict_next_aqi(history):
    if len(history) < 5:
        return None  # not enough data to fit a model yet
    X = np.array([[h["wind_speed"], h["humidity"], h["aqi"]] for h in history[:-1]])
    y = np.array([h["aqi"] for h in history[1:]])
    model = LinearRegression().fit(X, y)
    latest = history[-1]
    pred = model.predict([[latest["wind_speed"], latest["humidity"], latest["aqi"]]])[0]
    return round(float(pred), 1)


def main():
    zones = load_zones()
    predictions = {}
    for zone in zones:
        history = load_history(zone["id"])
        predictions[zone["id"]] = {
            "predicted_aqi_24h": predict_next_aqi(history),
            "history_points": len(history),
        }
    out_path = PROCESSED_DIR / "predictions.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2)
    print(f"Wrote predictions for {len(predictions)} zones to {out_path}")


if __name__ == "__main__":
    main()
