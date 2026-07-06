CleanAir & Clear Streets is a real-time pollution hotspot detection and forecasting
platform for Delhi NCR. It fuses three independent signals — live CPCB ground-station
air quality readings, NASA FIRMS satellite fire/smoke detections, and citizen-submitted
photos classified by Gemini (via Firebase AI Logic) — into a single hotspot score per
zone, then forecasts each zone's AQI 24 hours ahead using a regression model trained on
live and historical data. Gemini also generates a plain-language situational briefing
per zone, in English and Hindi in a single call, reasoning about likely cause — traffic
baseline, stubble burning, or a citizen-reported local source — rather than just
repeating numbers back at the reader.

Beyond detection, the platform is built for real-world deployability and inclusivity:
it runs entirely on free-tier infrastructure (Firebase Hosting, Firestore, GitHub
Actions, with a Groq/Llama fallback if Gemini's daily quota is exhausted) with no
billing account required anywhere; supports Hindi alongside English with browser-based
text-to-speech for low-literacy accessibility; overlays nearby schools and hospitals
(via OpenStreetMap) so a hotspot reads as "who's actually at risk," not just a number;
estimates population impact per zone; and lets citizens check whether their own photo
report was acknowledged and folded into the live map — closing the feedback loop that
keeps citizen reporting worth doing. It is live at
https://gen-lang-client-0882700239.web.app, mobile-responsive, and runs on its own
automated schedule via GitHub Actions (data refresh every 3 hours, AI briefings daily,
facility data weekly).
