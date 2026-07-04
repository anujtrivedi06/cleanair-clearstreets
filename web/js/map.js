// Renders the Delhi NCR hotspot map from the static JSON published by the
// GitHub Actions pipeline (scripts/run_pipeline.py -> web/data/hotspots.json).

const map = L.map("map").setView([28.6139, 77.209], 10); // Delhi NCR center

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
  maxZoom: 18,
}).addTo(map);

function severityColor(score) {
  if (score >= 0.7) return "#d0342c"; // severe
  if (score >= 0.4) return "#e0a021"; // moderate
  return "#3a9d5d"; // low
}

function renderAlert(zone) {
  const li = document.createElement("li");
  const severe = zone.hotspot_score >= 0.7;
  li.className = severe ? "severe" : "";
  const spikeText =
    zone.predicted_aqi_24h != null
      ? `predicted AQI ${zone.predicted_aqi_24h} in ~24h`
      : "prediction pending (needs more history)";
  const action = severe ? "Deploy water-mist cannon / cleanup crew" : "Monitor";
  li.textContent = `${zone.name} — score ${zone.hotspot_score} — ${spikeText} — ${action}`;
  return li;
}

async function loadHotspots() {
  const res = await fetch("data/hotspots.json", { cache: "no-store" });
  const { hotspots } = await res.json();

  const alertList = document.getElementById("alert-list");
  alertList.innerHTML = "";

  const zoneSelect = document.getElementById("zone-select");
  zoneSelect.innerHTML = "";

  hotspots
    .sort((a, b) => b.hotspot_score - a.hotspot_score)
    .forEach((zone) => {
      L.circleMarker([zone.lat, zone.lon], {
        radius: 10 + zone.hotspot_score * 12,
        color: severityColor(zone.hotspot_score),
        fillColor: severityColor(zone.hotspot_score),
        fillOpacity: 0.6,
      })
        .addTo(map)
        .bindPopup(
          `<strong>${zone.name}</strong><br/>Hotspot score: ${zone.hotspot_score}<br/>AQI: ${zone.aqi ?? "n/a"}<br/>Predicted 24h AQI: ${zone.predicted_aqi_24h ?? "n/a"}`
        );

      alertList.appendChild(renderAlert(zone));

      const opt = document.createElement("option");
      opt.value = zone.zone_id;
      opt.textContent = zone.name;
      zoneSelect.appendChild(opt);
    });
}

loadHotspots().catch((err) => {
  console.error("Failed to load hotspot data", err);
  document.getElementById("alert-list").innerHTML =
    '<li class="placeholder">No data yet — run the pipeline (scripts/run_pipeline.py) at least once.</li>';
});
