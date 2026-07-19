# VayuKavach — Delhi NCR

Built for **Build with AI: Code for Communities** (Track 2 — CleanAir & Clear Streets).

Detects and predicts neighbourhood-level pollution hotspots across Delhi NCR by fusing
CPCB ground-station air quality data, NASA FIRMS fire/smoke detections, and
citizen-uploaded photos (classified with Gemini Vision) — then surfaces a 24h AQI spike
forecast, an AI-written situational briefing, and a recommended municipal action per
zone, in both English and Hindi.

**Live at: https://gen-lang-client-0882700239.web.app**

## Problem

City-level AQI apps miss hyper-local pollution events (a garbage fire, an industrial
cluster, a smog-trapping junction). These go unnoticed while directly harming nearby
residents, and municipal teams have no way to know where to deploy cleanup crews or
water-mist cannons before a spike happens — or which schools and hospitals are actually
at risk when it does.

## How it works

1. **Citizen intake** — a web form accepts a photo + location (self-seeded sample photos
   for this prototype, standing in for real citizen submissions).
2. **Vision classification** — Gemini, called from the browser via **Firebase AI Logic**
   (Gemini Developer API backend), classifies each photo into pollution type + severity
   (smoke, dust, garbage burning, haze, none). We deliberately moved off a raw
   client-side Generative Language API key: that key type cannot be restricted by
   domain once bound to a service account (confirmed empirically — the "Websites"
   restriction option is disabled for it in Cloud Console), so it would stay
   permanently exposed to anyone who viewed the page source. Firebase AI Logic's
   `firebaseConfig` is meant to be public — access control is enforced by
   Firebase/Firestore rules, not by keeping a secret hidden client-side.
3. **Citizen report storage** — classified reports are written to **Firestore** (public
   `create`, single-document `get` only, no `list`/`update`/`delete` — see
   `firestore.rules`). Only the backend pipeline (a service-account key that bypasses
   these rules) can bulk-read and update reports.
4. **Citizen status view ("My Reports")** — after submitting, a citizen's browser
   remembers the Firestore-generated document ID (a long, unguessable string) in
   `localStorage` and can look up that one report's status later — "Pending review" vs.
   "✓ Included in live map" — without any login system. The ID itself acts as a
   capability token: nobody can browse/list other citizens' reports, only fetch a report
   whose exact ID they already have.
5. **Hotspot fusion** — `scripts/fuse_hotspots.py` combines CPCB station AQI (50%), NASA
   FIRMS fire/smoke detections (30%), and citizen photo severity (20%) into a single
   0–1 hotspot score per zone across a 12-zone Delhi NCR grid. If a CPCB station reports
   nothing this cycle (offline, or its PM sensors specifically report "NA"), the last
   known reading is shown instead of a misleading "n/a" — flagged as stale, with an age.
6. **24h spike prediction** — a lightweight regression model forecasts next-day AQI per
   zone, trained on live CPCB + Open-Meteo weather data (accumulated every 3 hours) plus
   a ~90-day historical bootstrap from Open-Meteo's Air Quality Archive (a CAMS
   reanalysis model, clearly tagged `"source": "open_meteo_backfill"` in
   `data/processed/history_*.json` — CPCB's live feed itself retains no history, so
   there is no real historical CPCB series to pull instead).
7. **AI situational briefing** — once/day, Gemini (falling back to Groq/Llama if
   Gemini's free-tier daily quota is exhausted) writes a one-sentence, plain-language
   briefing per zone reasoning about *likely cause* — traffic baseline, stubble burning,
   or a citizen-reported local source — in English **and** Hindi, generated together in
   a single call. This is decoupled from the 3-hourly data refresh specifically because
   Gemini's free tier caps each model at 20 requests/day/project; running it for all 12
   zones every 3 hours would need ~96 requests/day.
8. **Historical recurrence view** — each zone shows "poor air quality on N of the last
   30 days" plus a small sparkline, so the dashboard shows a recurring problem, not a
   one-off reading.
9. **Population-impact + vulnerable-facility overlay** — each zone shows an approximate
   resident count and nearby schools/hospitals (pulled from OpenStreetMap's Overpass
   API, refreshed weekly), so a hotspot reads as "AQI 250, and 3 schools + a hospital
   are within 1km" rather than a bare number.
10. **Dashboard** — a Leaflet/OpenStreetMap view (mobile-responsive) shows current
    hotspots, predicted spikes, facility markers, and a municipal action list, with a
    language toggle (English/Hindi) and browser-based text-to-speech for low-literacy
    access.

## Stack

- **Firebase AI Logic** (Gemini Developer API backend) — photo vision classification,
  called directly from the browser with no exposed raw API key
- **Gemini API + Groq (Llama, free-tier fallback)** — server-side AI zone briefings,
  bilingual (English/Hindi) in a single call
- **Firestore** — citizen report storage (public create + single-doc read, backend-only
  bulk read/update)
- **Firebase Hosting** — static site hosting (free Spark plan)
- **GitHub Actions** — three scheduled Python pipelines: data refresh (3-hourly),
  AI briefings (daily), facility data (weekly) — replacing a billed Cloud Run backend
- **Leaflet.js + OpenStreetMap** — map rendering + Overpass API for schools/hospitals
- **Browser `SpeechSynthesis` API** — text-to-speech, no external service
- **Data sources**: data.gov.in / CPCB (air quality), NASA FIRMS (fire/smoke
  detections), Open-Meteo (weather + historical archive), OpenStreetMap Overpass
  (schools/hospitals) — all free, no card required anywhere in this stack

No Google Cloud billing account is used anywhere in this build.

## Repo structure

```
data/           zone/grid definitions (data/zones.json), raw + processed pipeline data
scripts/        Python pipeline:
                  fetch_cpcb.py, fetch_firms.py, fetch_weather.py       -- live data
                  fetch_photo_reports.py                                -- Firestore reports
                  fetch_facilities.py                                   -- Overpass schools/hospitals
                  backfill_history.py, append_history.py                -- historical training data
                  fuse_hotspots.py                                      -- hotspot scoring
                  predict_spike.py                                      -- 24h AQI regression
                  generate_briefing.py, refresh_briefings.py            -- bilingual AI briefings
                  run_pipeline.py                                       -- orchestrates the above
web/            static frontend: map dashboard, report form, My Reports,
                i18n (English/Hindi), TTS -- mobile-responsive
.github/workflows/  update-data.yml (3h), refresh-briefings.yml (daily),
                    refresh-facilities.yml (weekly)
```

## Status

Prototype built for hackathon submission (deadline: July 8). Live and running on its
own automated schedule — see `.github/workflows/` for what runs when.

## Setup

See inline TODOs in `scripts/` and `web/` — API keys are read from environment
variables / GitHub Actions secrets, never committed. `firestore.rules` documents the
citizen-report access model.
