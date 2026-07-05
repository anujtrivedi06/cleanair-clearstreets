// Renders the Delhi NCR hotspot map + zone tile list from the static JSON
// published by the GitHub Actions pipeline (scripts/run_pipeline.py ->
// web/data/hotspots.json).
import { applyStaticText, getLang, onLangChange, t } from "./i18n.js";

const map = L.map("map").setView([28.6139, 77.209], 10); // Delhi NCR center

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
  maxZoom: 18,
}).addTo(map);

let cachedHotspots = null;
let markers = [];

function severityLevel(score) {
  if (score >= 0.7) return "severe";
  if (score >= 0.4) return "moderate";
  return "low";
}

function severityColor(level) {
  return { severe: "#d0342c", moderate: "#e0a021", low: "#3a9d5d" }[level];
}

function recommendedAction(level) {
  if (level === "severe") return t("actionSevere");
  if (level === "moderate") return t("actionModerate");
  return t("actionLow");
}

function briefingText(zone) {
  return getLang() === "hi" ? zone.ai_briefing_hi ?? zone.ai_briefing : zone.ai_briefing;
}

function displayName(zone) {
  return getLang() === "hi" ? zone.name_hi ?? zone.name : zone.name;
}

function relativeTime(isoTimestamp) {
  const diffMs = Date.now() - new Date(isoTimestamp).getTime();
  const hours = Math.round(diffMs / 3600000);
  if (hours < 1) return "<1h";
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

function forecastBadge(zone) {
  if (zone.predicted_aqi_24h == null) {
    return { text: t("forecastPending"), className: "pending" };
  }
  const delta = zone.predicted_aqi_24h - (zone.aqi ?? zone.predicted_aqi_24h);
  const trendClass = delta > 5 ? "up" : delta < -5 ? "down" : "steady";
  const arrow = delta > 5 ? "↑" : delta < -5 ? "↓" : "→";
  return { text: `${arrow} ${zone.predicted_aqi_24h}`, className: trendClass };
}

function speak(text) {
  if (!text || !window.speechSynthesis) return;
  window.speechSynthesis.cancel(); // stop any previous utterance
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = getLang() === "hi" ? "hi-IN" : "en-US";
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find((v) => v.lang === utterance.lang);
  if (match) utterance.voice = match;
  window.speechSynthesis.speak(utterance);
}

function buildTile(zone, markersByZone) {
  const level = severityLevel(zone.hotspot_score);
  const forecast = forecastBadge(zone);
  const briefing = briefingText(zone);

  const tile = document.createElement("div");
  tile.className = `zone-tile severity-${level}`;
  tile.style.setProperty("--severity-color", severityColor(level));
  tile.dataset.zoneId = zone.zone_id;

  const photoNote =
    zone.photo_severity > 0
      ? `<dt>${t("citizenReportsLabel")}</dt><dd>${t("severityLabel")} ${zone.photo_severity}</dd>`
      : "";

  const staleNote = zone.aqi_stale
    ? `<span class="stale-note">⚠ ${t("staleNote")} (${relativeTime(zone.aqi_as_of)})</span>`
    : "";

  const briefingBlock = briefing
    ? `<p class="tile-briefing">
         <span class="briefing-label">${t("aiBriefingLabel")}</span>
         <button type="button" class="tts-btn" title="${t("listenLabel")}" aria-label="${t("listenLabel")}">🔊</button>
         ${briefing}
       </p>`
    : "";

  tile.innerHTML = `
    <div class="tile-summary">
      <span class="severity-dot"></span>
      <div class="tile-main">
        <div class="tile-name">${displayName(zone)}</div>
        <div class="tile-current">${t("aqiProxyLabel")} ${zone.aqi ?? "n/a"} · ${t("hotspotScoreLabel")} ${zone.hotspot_score}</div>
        ${staleNote}
      </div>
      <div class="tile-forecast">
        <span>${t("forecastLabel")}</span>
        <span class="forecast-value ${forecast.className}">${forecast.text}</span>
      </div>
      <span class="expand-icon">▾</span>
    </div>
    <div class="tile-details">
      <p class="tile-action">${recommendedAction(level)}</p>
      ${briefingBlock}
      <dl>
        <dt>${t("firmsLabel")}</dt><dd>${zone.firms_detections}</dd>
        ${photoNote}
      </dl>
    </div>
  `;

  tile.querySelector(".tile-summary").addEventListener("click", () => {
    const wasExpanded = tile.classList.contains("expanded");
    document.querySelectorAll(".zone-tile.expanded").forEach((el) => el.classList.remove("expanded"));
    if (!wasExpanded) {
      tile.classList.add("expanded");
      const marker = markersByZone.get(zone.zone_id);
      if (marker) {
        map.flyTo([zone.lat, zone.lon], 12, { duration: 0.6 });
        marker.openPopup();
      }
    }
  });

  const ttsBtn = tile.querySelector(".tts-btn");
  if (ttsBtn) {
    ttsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      speak(briefing);
    });
  }

  return tile;
}

function renderZones(hotspots) {
  const tilesContainer = document.getElementById("zone-tiles");
  tilesContainer.innerHTML = "";

  const zoneSelect = document.getElementById("zone-select");
  zoneSelect.innerHTML = "";

  markers.forEach((m) => map.removeLayer(m));
  markers = [];
  const markersByZone = new Map();

  hotspots
    .slice()
    .sort((a, b) => (b.aqi ?? -1) - (a.aqi ?? -1))
    .forEach((zone) => {
      const level = severityLevel(zone.hotspot_score);
      const marker = L.circleMarker([zone.lat, zone.lon], {
        radius: 10 + zone.hotspot_score * 12,
        color: severityColor(level),
        fillColor: severityColor(level),
        fillOpacity: 0.6,
      })
        .addTo(map)
        .bindPopup(
          `<strong>${displayName(zone)}</strong><br/>${t("popupHotspotScore")}: ${zone.hotspot_score}<br/>${t("popupAqi")}: ${zone.aqi ?? "n/a"}<br/>${t("popupPredicted")}: ${zone.predicted_aqi_24h ?? "n/a"}`
        );
      markers.push(marker);
      markersByZone.set(zone.zone_id, marker);

      tilesContainer.appendChild(buildTile(zone, markersByZone));

      const opt = document.createElement("option");
      opt.value = zone.zone_id;
      opt.textContent = displayName(zone);
      zoneSelect.appendChild(opt);
    });
}

async function loadHotspots() {
  const res = await fetch("data/hotspots.json", { cache: "no-store" });
  const { hotspots } = await res.json();
  cachedHotspots = hotspots;
  renderZones(hotspots);
}

loadHotspots().catch((err) => {
  console.error("Failed to load hotspot data", err);
  document.getElementById("zone-tiles").innerHTML =
    '<div class="placeholder-tile">No data yet — run the pipeline (scripts/run_pipeline.py) at least once.</div>';
});

onLangChange(() => {
  if (cachedHotspots) renderZones(cachedHotspots);
});

document.getElementById("report-toggle").addEventListener("click", () => {
  const body = document.getElementById("report-body");
  const icon = document.querySelector("#report-toggle .toggle-icon");
  const open = body.classList.toggle("open");
  icon.textContent = open ? "−" : "+";
});
