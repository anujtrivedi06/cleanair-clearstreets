# Architecture — Deep Reference

This document explains the system end-to-end: every layer, why it was chosen, what the
alternatives were, exactly where data lives, and how it moves. Written for judge Q&A
prep — if asked "why not X," the answer is probably here.

---

## 1. The two independent flows

Everything in this system is one of two flows. Keep these separate in your head —
conflating them is the easiest way to get confused mid-Q&A.

**Flow A — Citizen submission (client-driven, happens the instant someone reports)**
```
Citizen's browser
  → photo captured/selected
  → Gemini (via Firebase AI Logic) classifies it directly from the browser
  → result written to Firestore (public create, no auth)
  → doc ID saved in the browser's localStorage (citizen's "receipt")
```

**Flow B — Data pipeline (server-driven, runs on a schedule, no human involved)**
```
GitHub Actions (cron)
  → pulls CPCB, NASA FIRMS, Open-Meteo, Firestore reports, OSM Overpass
  → fuses them into a hotspot score per zone
  → predicts 24h AQI
  → (daily only) asks Gemini/Groq for a bilingual briefing
  → writes JSON files, commits them to the git repo
```

**The join point**: the live website is a static site that just reads the JSON files
Flow B produces. Flow A's only connection to the dashboard is indirect — a citizen
report sits in Firestore until the *next* Flow B run reads it and folds it into the
score. That's why the UI says "will be reflected on the map within the next pipeline
run" rather than updating instantly.

---

## 2. Layer by layer

### 2.1 Data sources (external, all free, no card anywhere)

| Source | What we pull | Why this one | Alternative considered |
|---|---|---|---|
| **CPCB** (via data.gov.in API) | Live PM2.5/PM10 per station | Only source of real, government ground-truth AQI | Buying a private sensor network (cost) |
| **NASA FIRMS** | Active fire/smoke satellite detections | Free, real-time, purpose-built for exactly "is something burning here" | Google Earth Engine (approval-wait risk killed this for a 4-day build — see §5) |
| **Open-Meteo** | Live weather + historical archive | Free, no key, has both live *and* historical endpoints (rare) | IMD (India Meteorological Dept) — less accessible API |
| **OpenStreetMap Overpass** | Schools/hospitals near each zone | Free, no key, real crowdsourced data | Google Places API (needs billing) |
| **Firestore** | Citizen photo reports | Already in the Firebase ecosystem we use for hosting | A custom backend (unnecessary infra for this scale) |

**Non-obvious lesson baked into the code**: three of these five sources *silently
blocked or hung* on default HTTP client behavior during development — data.gov.in
rejects the default Python `requests` User-Agent (needs a browser-like one),
Overpass mirrors reject a *spoofed* browser UA (needs an honest, identifying one,
opposite problem), and one Overpass mirror is just flaky regardless. `fetch_cpcb.py`
and `fetch_facilities.py` both encode these fixes with comments explaining why —
worth reading if asked "what was actually hard about this."

### 2.2 The vision AI (Flow A)

**Gemini via Firebase AI Logic**, called directly from the browser (`web/js/submit.js`).
Classifies a photo into `smoke | dust | garbage_burning | haze | none`, a severity
0–1, and a one-sentence reasoning.

**Why Firebase AI Logic and not a raw Gemini API key in the browser**: a raw
Generative Language API key embedded in client-side JS is visible to anyone who views
page source. Normally you'd restrict such a key to your domain — but the key type
this project's Cloud Console issued is *bound to a service account*, and that key
type has the "Websites" restriction option permanently disabled (confirmed by testing
it, not assumed). An unrestrictable key sitting in public JS is a real liability.
Firebase AI Logic sidesteps the problem structurally: its `firebaseConfig` is *meant*
to be public (it just identifies the project), and Firebase's own infrastructure
brokers the actual Gemini call — there's no secret to leak in the first place.

**Alternative considered**: Vertex AI Vision — rejected because it requires the
Vertex AI backend, which needs a billing account (contradicts the no-card build).

### 2.3 The reasoning AI (Flow B, server-side)

**Gemini `gemini-2.5-flash-lite`**, with **Groq (Llama 3.3 70B) as an automatic
fallback**, called from `scripts/generate_briefing.py`. Once a day (not every pipeline
run — see §4), it writes a one-sentence, plain-language briefing per zone reasoning
about *likely cause*, in English and Hindi, in a single call.

**Why a fallback provider at all**: Gemini's free tier caps each model at **20
requests/day per project**. That was discovered empirically mid-build (see git
history around the "Groq fallback" commit) — 12 zones once/day fits inside 20 with
room to spare, but repeated manual/demo testing on the same day can burn through it.
Groq hosts open-source models with a much higher free ceiling, so it exists purely as
insurance for demo-day, not because Gemini alone is insufficient.

**Why compute the historical comparison ourselves instead of asking the model to**:
LLMs are unreliable at arithmetic. `generate_briefing.py` computes the 7-day/30-day
AQI averages in plain Python and only asks the model to *interpret* the comparison and
write prose — this is a deliberate "AI does reasoning, not math" design choice, worth
stating explicitly if asked "is the AI doing real work."

**Why bilingual-in-one-call instead of a separate translation step**: Google Cloud
Translation API requires a billing account even for its free-tier usage (discovered by
trying to enable it — hit a "billing required" wall). A second LLM call per language
would also double the already-tight Gemini quota. Asking the same model to emit both
languages in one JSON response costs nothing extra.

### 2.4 The prediction model (Flow B)

`scripts/predict_spike.py` — a linear regression (scikit-learn) forecasting each
zone's AQI 24h ahead, trained on lagged AQI + wind speed + humidity.

**Training data has two sources, clearly tagged**:
- **Live**: real CPCB + weather, accumulated every 3 hours (`"source": "cpcb_live"`
  in `data/processed/history_*.json`)
- **Backfill**: ~90 days of daily data from Open-Meteo's Air Quality Archive (a CAMS
  atmospheric reanalysis *model*, not raw ground sensor data), tagged
  `"source": "open_meteo_backfill"`

**Why the backfill exists**: CPCB's live API retains *no history at all* — every
station reports the exact same `last_update` timestamp, and querying a past date
returns zero rows (confirmed empirically, not assumed). Waiting for live-only
accumulation would mean ~1-2 days with no working predictions. The backfill is
explicitly labeled as a proxy so it's never confused with real CPCB data if a judge
asks "is this real."

**Why linear regression and not something fancier**: an intentional choice for
explainability under judge questioning — a simple, inspectable model beats a
black-box one when you have 4 days and need to defend it live.

### 2.5 Hotspot fusion (Flow B)

`scripts/fuse_hotspots.py` — the core scoring logic. For each of 12 zones:

```
hotspot_score = 0.5 × normalize(CPCB PM2.5/PM10)
              + 0.3 × normalize(nearby FIRMS fire detections)
              + 0.2 × normalize(citizen photo severity)
```

A deliberate weighted sum, not a trained model — explainable to a non-technical
MP's office in one sentence, which directly serves the "Presentation & Clarity"
criterion.

**Resilience built in**: if a CPCB station reports nothing this cycle (offline, or
its PM sensors specifically return `"NA"` while other pollutants still work — both
observed in practice), the fusion falls back to the last known reading rather than
silently showing "n/a" (which would make an offline station look artificially clean).
The fallback value is flagged `aqi_stale: true` with a timestamp so the frontend can
show "⚠ last known reading, 4h old."

### 2.6 Storage — exactly what lives where

| Location | What's stored | Who can write | Who can read |
|---|---|---|---|
| **Firestore `reports` collection** | Citizen photo reports (zoneId, type, severity, reasoning, timestamp, status) | Anyone (public `create`, schema-validated) | Single doc by exact ID (public `get`); bulk read/update only via service account |
| **`data/raw/*.json`** (gitignored) | Latest CPCB/FIRMS/weather API responses | Pipeline scripts | Pipeline scripts (ephemeral, not committed) |
| **`data/processed/*.json`** (git-committed) | Fused hotspots, predictions, per-zone history, facilities | Pipeline scripts, committed by GitHub Actions | Anyone with repo access |
| **`web/data/hotspots.json` / `facilities.json`** (git-committed, also deployed) | The actual published data the live site reads | Pipeline scripts + manual `firebase deploy` | Public, served by Firebase Hosting |
| **Browser `localStorage`** | Citizen's own report IDs (`cleanair_my_reports`), language preference | Client JS | Client JS only (never leaves the browser) |

**The Firestore security model, precisely**: `create` is open but schema-validated
(must have the right fields, severity must be a number 0–1). `get` (single document,
by ID) is open — this is what lets "My Reports" work without a login system, using
the long random document ID as a de facto capability token. `list` (querying/browsing
the whole collection) is denied to everyone except the service account. So a citizen
can check *their own* report by ID, but cannot enumerate or browse anyone else's.

### 2.7 Automation — three independent GitHub Actions schedules

| Workflow | Cadence | Does | Needs these secrets |
|---|---|---|---|
| `update-data.yml` | Every 3 hours | Fetch CPCB/FIRMS/weather/Firestore reports → fuse → predict → **commit** | `DATA_GOV_IN_API_KEY`, `CPCB_RESOURCE_ID`, `FIRMS_MAP_KEY`, `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_B64` |
| `refresh-briefings.yml` | Once daily | Generate bilingual AI briefings for all 12 zones → **commit** | `GEMINI_API_KEY`, `GROQ_API_KEY` |
| `refresh-facilities.yml` | Weekly | Pull schools/hospitals from Overpass → **commit** | none (Overpass is keyless) |

**Why three separate schedules instead of one**: each is rate-limited by a different
real constraint. Data refresh is cheap and citizens benefit from freshness (3h).
Briefings cost LLM quota (daily, because 12 zones × 8 runs/day would blow the 20/day
cap). Facilities barely change at all (weekly is already overkill).

**⚠ None of the three call `firebase deploy`.** They all end at `git push`. The live
site's data only updates when someone runs `firebase deploy --only hosting` by hand.
See §5 for the fix.

### 2.8 Frontend / hosting

- **Firebase Hosting** (free Spark plan) serves the static `web/` directory —
  `index.html`, `css/style.css`, and ES modules (`map.js`, `submit.js`, `i18n.js`,
  `myReports.js`).
- **Leaflet.js + OpenStreetMap** tiles render the map — chosen specifically over
  Google Maps Platform because it needs no billing account and no API key at all.
- **i18n**: a hand-maintained English/Hindi dictionary (`i18n.js`) for static UI text
  + AI-generated bilingual briefings from the pipeline. No live translation API call
  ever happens client-side (cost/quota risk avoided entirely).
- **TTS**: the browser's native `SpeechSynthesis` API — zero cost, zero quota, works
  offline-capable once the page is loaded.
- **Responsive layout**: a single CSS media query breakpoint (900px) switches from a
  3-column desktop layout to a stacked mobile one; a `resize` listener calls
  `map.invalidateSize()` so Leaflet redraws correctly after orientation changes.

---

## 3. Full data-flow narrative (read this section if you need the "walk me through
what happens" answer)

**When a citizen submits a report:**
1. Browser captures/selects a photo (`<input capture="environment">` opens the
   camera directly on mobile).
2. `submit.js` base64-encodes it, sends it to Gemini via the Firebase AI Logic SDK
   (`getGenerativeModel().generateContent()`), in-browser, no server involved.
3. Gemini returns `{type, severity, reasoning}` as JSON.
4. `submit.js` POSTs this + `status: "pending"` to Firestore's REST API
   (`projects/.../databases/(default)/documents/reports`) — no auth header, allowed
   by the `create` rule.
5. Firestore's response includes the auto-generated document ID; `submit.js` saves
   `{id, zoneId, submittedAt}` into `localStorage`.
6. The citizen can reopen "My Reports" any time — it re-fetches each stored ID via
   Firestore's single-doc `GET` endpoint and shows `status`.

**When the 3-hourly pipeline runs (GitHub Actions):**
1. `fetch_cpcb.py`, `fetch_firms.py`, `fetch_weather.py` hit their respective free
   APIs, write to `data/raw/*.json`.
2. `fetch_photo_reports.py` authenticates to Firestore with the **service-account**
   key (bypasses all security rules), queries reports from the last 24h, aggregates
   max-severity-per-zone into `data/processed/photo_severity.json`, and — critically —
   **writes back** to each processed report's `status` field, flipping
   `"pending" → "acknowledged"`. This is the other half of the citizen-status loop.
3. `append_history.py` appends today's live reading to each zone's
   `data/processed/history_<zone>.json`.
4. `fuse_hotspots.py` combines everything into `hotspot_score` per zone.
5. `predict_spike.py` trains the regression on history, forecasts 24h AQI.
6. `run_pipeline.py` (the orchestrator) merges predictions in, **carries forward**
   whatever AI briefing was last generated (since briefings aren't regenerated every
   cycle), and writes the final `web/data/hotspots.json`.
7. The workflow commits and pushes this file to the git repo.
8. *(Currently a manual step, not automated — see §5)* Someone runs
   `firebase deploy --only hosting`, which uploads `web/` to Firebase's CDN, and
   **only then** does the public URL actually reflect the new data.

**When a citizen opens the dashboard:**
1. Firebase Hosting serves `index.html` + JS/CSS (static, cached at the edge).
2. `map.js` fetches `data/hotspots.json` and `data/facilities.json` (also static
   files on the same CDN — no live API call happens on page load).
3. Everything renders client-side: Leaflet markers, ranked tiles, sparklines
   (hand-rolled inline SVG, no charting library), language toggle, TTS.

---

## 4. Why the pipeline is split the way it is (the quota story)

This is worth understanding cold, because it's the single most "we actually debugged
a real production constraint" story in the whole project, and it's very
Q&A-friendly.

Gemini's free tier caps `gemini-2.5-flash-lite` (and every other model) at **20
requests/day per Google Cloud project**. Early in the build, `generate_briefing.py`
was called from *inside* `run_pipeline.py` — meaning every 3-hourly data refresh also
regenerated all 12 zones' AI briefings. That's `12 × 8 runs/day = 96 requests/day`,
nearly 5× the quota. It failed visibly (429 errors) the first time it ran on a
schedule.

The fix was architectural, not just "add retries": briefing generation was pulled out
into its own script (`refresh_briefings.py`) on its **own** daily schedule
(`refresh-briefings.yml`), decoupled entirely from the 3-hourly data refresh. The
3-hourly job now just **carries forward** whatever briefing already exists
(`carry_forward_briefings()` in `run_pipeline.py`) so the UI never shows a blank
briefing between daily regenerations. On top of that, a Groq fallback was added so a
single exhausted-quota day during demo prep doesn't produce visibly broken briefings.

---

## 5. What's incomplete / honest gaps (know these before a judge asks)

1. **Live site deploy isn't automated.** GitHub Actions commits fresh data to the
   repo on schedule, but nothing calls `firebase deploy`. **Fix**: add a step to
   `update-data.yml` using the official
   [`FirebaseExtended/action-hosting-deploy`](https://github.com/FirebaseExtended/action-hosting-deploy)
   action, authenticated with a Firebase CI token (`firebase login:ci` generates one)
   stored as a GitHub secret. This is the highest-value fix before finals — it's the
   difference between "automated" being true in the repo vs. true in production.
2. **No proactive push alerts.** Municipal teams currently have to check the
   dashboard; nothing pushes a WhatsApp/SMS/email when a zone newly crosses severe.
   Scoped but not built (discussed and deliberately deferred).
3. **No low-connectivity intake channel.** Citizen reporting requires a smartphone +
   browser + data connection; no WhatsApp/SMS submission path exists.
4. **Satellite imagery is FIRMS (fire detection), not Earth Engine** (general
   aerosol/visual imagery) — a documented Day-1 trade-off to avoid Earth Engine's
   approval-wait risk in a short build window.
5. **Population figures are estimates**, not census-audited — stated as such
   everywhere they appear.
6. **The PM-proxy isn't the official CPCB AQI sub-index** — it's the average of
   PM2.5/PM10 readings, deliberately chosen over implementing the official
   multi-pollutant breakpoint formula (out of scope for the timeline), and labeled
   as a proxy in the code and docs.

---

## 6. Future improvements, organized by what they'd actually buy you

**Close the deploy gap (do this first, cheap, high-value)**
- Automate `firebase deploy` inside `update-data.yml` (see §5.1). Turns "the pipeline
  runs itself" from a repo-level truth into a production-level truth.

**Deepen the AI (raises "AI/Technical Execution" ceiling)**
- Earth Engine integration for real aerosol/visual satellite layers, once there's
  time to wait out the approval process.
- A second model pass that correlates wind speed/humidity against AQI history to
  surface genuine environmental patterns ("this zone worsens sharply when wind drops
  below X km/h") — cheap, reuses data already being collected, no new quota.
- Replace the linear regression with a slightly richer model (e.g. gradient boosting)
  once there's enough accumulated live history to justify it without overfitting.

**Close the intake/outreach loop (raises "Deployability" + "Problem-Solution Fit")**
- WhatsApp/SMS citizen intake (e.g. Twilio, or a lighter-weight service) for citizens
  without a smartphone/data plan.
- Proactive municipal alerts (WhatsApp via a free-tier service like CallMeBot, or
  email) fired specifically on a zone's *state change* into severe — not on every
  cycle, to avoid alert fatigue.

**Scale beyond Delhi NCR (raises "Deployability & Scalability")**
- The architecture already supports this cheaply: `data/zones.json` is the only file
  that encodes "what to monitor" — a new city means adding its CPCB stations there,
  no code changes to fusion/prediction/dashboard logic. Worth actually demonstrating
  (even with 2-3 zones in a second city) if there's time before finals — a live
  second-city demo is a very strong scalability proof.

**Operational maturity (small, cheap, judge-visible polish)**
- A pipeline health indicator already exists for stale CPCB readings (`aqi_stale`) —
  extend the same idea to flag if the *entire pipeline* hasn't run recently (e.g. a
  "last updated Xh ago" banner), which also indirectly surfaces the deploy-gap issue
  if it recurs.
- Basic uptime/error monitoring on the GitHub Actions workflows (GitHub already
  emails on failure by default — worth confirming that's actually being watched).
