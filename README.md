# CleanAir & Clear Streets — Delhi NCR

Built for **Build with AI: Code for Communities** (Track 2 — CleanAir & Clear Streets).

Detects and predicts neighbourhood-level pollution hotspots across Delhi NCR by fusing
citizen-uploaded photos (classified with Gemini Vision), CPCB ground-station air quality
data, NASA FIRMS fire/smoke detections, and weather data — then surfaces a 24h AQI spike
forecast and recommended municipal action on a live map.

**Live at: https://gen-lang-client-0882700239.web.app**

## Problem

City-level AQI apps miss hyper-local pollution events (a garbage fire, an industrial
cluster, a smog-trapping junction). These go unnoticed while directly harming nearby
residents, and municipal teams have no way to know where to deploy cleanup crews or
water-mist cannons before a spike happens.

## How it works

1. **Citizen intake** — a web form accepts a photo + location (self-seeded sample photos
   for this prototype, standing in for real citizen submissions).
2. **Vision classification** — Gemini, called from the browser via **Firebase AI Logic**
   (Gemini Developer API backend), classifies each photo into pollution type + severity
   (smoke, dust, garbage burning, haze). We deliberately moved off a raw client-side
   Generative Language API key: that key type cannot be restricted by domain once bound
   to a service account (confirmed empirically — the "Websites" restriction option is
   disabled for it in Cloud Console), so it would stay permanently exposed and usable by
   anyone who viewed the page source. Firebase AI Logic's `firebaseConfig` is meant to be
   public — access control is enforced by Firebase/Firestore rules, not by keeping a
   secret hidden client-side.
3. **Citizen report storage** — classified reports are written to **Firestore** (public
   `create`, no read/update/delete — see `firestore.rules`). Only the backend pipeline,
   using a service-account key that bypasses these rules, can read them back
   (`scripts/fetch_photo_reports.py`).
4. **Hotspot fusion** — a scheduled script combines photo severity (from Firestore), CPCB
   station AQI, and NASA FIRMS fire/smoke detections into a per-zone hotspot score
   across a Delhi NCR grid.
5. **24h spike prediction** — a lightweight regression model forecasts next-day AQI
   per zone, trained on:
   - **Live data (source of truth)**: real CPCB ground-station PM2.5/PM10 readings +
     Open-Meteo weather, accumulated every 3 hours via a scheduled GitHub Action.
   - **Historical bootstrap (proxy, clearly labeled)**: ~90 days of daily AQI-proxy +
     weather per zone from Open-Meteo's Air Quality Archive (a CAMS reanalysis
     model, not raw CPCB data) via `scripts/backfill_history.py`. CPCB's live feed
     retains no historical records (confirmed empirically — every station reports
     the same single `last_update` timestamp, and querying a past date returns zero
     rows), so there is no real historical CPCB series to pull. This backfill exists
     purely to give the regression enough points to train on immediately rather than
     waiting ~1-2 days for live accumulation; every point is tagged
     `"source": "open_meteo_backfill"` in `data/processed/history_*.json` so it's
     always distinguishable from genuine live CPCB readings.
6. **Dashboard** — a Leaflet/OpenStreetMap view shows current hotspots, predicted
   spikes, and a municipal action list (e.g. "Zone X — spike predicted in 18h — deploy
   water-mist cannon").

## Stack

- **Firebase AI Logic** (Gemini Developer API backend) — vision classification + reasoning,
  called directly from the browser with no exposed raw API key
- **Firestore** — citizen report storage (public create, backend-only read)
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
