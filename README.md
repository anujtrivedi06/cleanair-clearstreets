# CleanAir & Clear Streets — Delhi NCR

Built for **Build with AI: Code for Communities** (Track 2 — CleanAir & Clear Streets).

Detects and predicts neighbourhood-level pollution hotspots across Delhi NCR by fusing
citizen-uploaded photos (classified with Gemini Vision), CPCB ground-station air quality
data, NASA FIRMS fire/smoke detections, and weather data — then surfaces a 24h AQI spike
forecast and recommended municipal action on a live map.

## Problem

City-level AQI apps miss hyper-local pollution events (a garbage fire, an industrial
cluster, a smog-trapping junction). These go unnoticed while directly harming nearby
residents, and municipal teams have no way to know where to deploy cleanup crews or
water-mist cannons before a spike happens.

## How it works

1. **Citizen intake** — a web form accepts a photo + location (self-seeded sample photos
   for this prototype, standing in for real citizen submissions).
2. **Vision classification** — Gemini (via Google AI Studio API) classifies each photo
   into pollution type + severity (smoke, dust, garbage burning, haze).
3. **Hotspot fusion** — a scheduled script combines photo classifications, CPCB
   station AQI, and NASA FIRMS fire/smoke detections into a per-zone hotspot score
   across a Delhi NCR grid.
4. **24h spike prediction** — a lightweight regression model forecasts next-day AQI
   per zone using historical AQI + weather (wind, humidity, temperature from
   Open-Meteo/NASA POWER).
5. **Dashboard** — a Leaflet/OpenStreetMap view shows current hotspots, predicted
   spikes, and a municipal action list (e.g. "Zone X — spike predicted in 18h — deploy
   water-mist cannon").

## Stack

- **Gemini API** (Google AI Studio) — vision classification + reasoning
- **Firebase Hosting** — static site hosting (free Spark plan)
- **GitHub Actions** — scheduled Python pipeline (fetch data → fuse → predict → write
  static JSON), replacing a billed Cloud Run backend
- **Leaflet.js + OpenStreetMap** — map rendering (no billing account required)
- **Data sources**: data.gov.in / CPCB (air quality), NASA FIRMS (fire/smoke
  detections), Open-Meteo / NASA POWER (weather) — all free, no card required

No Google Cloud billing account is used anywhere in this build.

## Repo structure

```
data/           raw + processed data, zone/grid definitions
scripts/        Python pipeline: fetch data, fuse hotspots, predict spikes
web/            static frontend (map dashboard + submission form)
.github/workflows/  scheduled pipeline runner
```

## Status

Prototype built for hackathon submission (deadline: July 8). See `scripts/` for the
data pipeline and `web/` for the live dashboard.

## Setup

See inline TODOs in `scripts/` and `web/` — API keys are read from environment
variables / GitHub Actions secrets, never committed.
