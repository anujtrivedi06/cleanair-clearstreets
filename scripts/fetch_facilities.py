"""
Pulls nearby schools and hospitals/clinics per zone from OpenStreetMap's
Overpass API (free, no key, no quota problems -- unlike everything else in
this project today). This turns a bare hotspot score into something more
concrete: "AQI 250, and there are 3 schools and a hospital within 1km" is a
much stronger signal of who's actually at risk than the number alone.

Facility locations don't change day to day, so this is meant to be run
occasionally (manually, or a lightly-scheduled job), not on every 3-hourly
data refresh -- see .github/workflows/ for how often it actually runs.
"""
import json
import time

import requests

from config import PROCESSED_DIR, WEB_DATA_DIR, load_zones

# Overpass mirrors (unlike data.gov.in) want an honest, distinctive User-Agent
# identifying the application -- some (e.g. openstreetmap.fr) return 403 for
# a spoofed-browser UA, treating it as suspected scraping. This is the
# opposite lesson from DEFAULT_HEADERS (see config.py), so it's kept separate.
OVERPASS_HEADERS = {
    "User-Agent": "CleanAirClearStreets-Hackathon/1.0 (github.com/anujtrivedi06/cleanair-clearstreets)"
}

# Public Overpass mirrors are individually flaky (the main overpass-api.de
# instance returned a bare 406 for every request during testing, reproduced
# with plain curl too; overpass.kumi.systems worked once then started timing
# out minutes later) -- try a short list in order rather than hard-coding one.
OVERPASS_URLS = [
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
RADIUS_METERS = 1000
MAX_FACILITIES_PER_ZONE = 25


def build_query(lat, lon, radius=RADIUS_METERS):
    return f"""
    [out:json][timeout:25];
    (
      node["amenity"="school"](around:{radius},{lat},{lon});
      way["amenity"="school"](around:{radius},{lat},{lon});
      node["amenity"="hospital"](around:{radius},{lat},{lon});
      way["amenity"="hospital"](around:{radius},{lat},{lon});
      node["amenity"="clinic"](around:{radius},{lat},{lon});
      way["amenity"="clinic"](around:{radius},{lat},{lon});
    );
    out center;
    """


def fetch_facilities_for_zone(zone):
    query = build_query(zone["lat"], zone["lon"])
    last_error = None
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, headers=OVERPASS_HEADERS, timeout=30)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            break
        except Exception as e:
            last_error = e
            continue
    else:
        raise RuntimeError(f"All Overpass mirrors failed: {last_error}")

    facilities = []
    for el in elements:
        amenity = el.get("tags", {}).get("amenity")
        facility_type = "school" if amenity == "school" else "hospital"
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        facilities.append(
            {
                "type": facility_type,
                "name": el.get("tags", {}).get("name", facility_type.title()),
                "lat": lat,
                "lon": lon,
            }
        )

    return facilities[:MAX_FACILITIES_PER_ZONE]


def main():
    zones = load_zones()
    result = {}

    for zone in zones:
        try:
            facilities = fetch_facilities_for_zone(zone)
            schools = sum(1 for f in facilities if f["type"] == "school")
            hospitals = sum(1 for f in facilities if f["type"] == "hospital")
            result[zone["id"]] = {
                "schools_count": schools,
                "hospitals_count": hospitals,
                "facilities": facilities,
            }
            print(f"{zone['id']}: {schools} schools, {hospitals} hospitals/clinics")
        except Exception as e:
            print(f"[warn] facility fetch failed for {zone['id']}: {e}")
            result[zone["id"]] = {"schools_count": 0, "hospitals_count": 0, "facilities": []}
        time.sleep(2)  # be polite to the free public Overpass instance

    out_path = PROCESSED_DIR / "facilities.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote facility data for {len(result)} zones -> {out_path}")

    # Also publish a flat list for the map to render as markers.
    flat = []
    for zone_id, data in result.items():
        for facility in data["facilities"]:
            flat.append({**facility, "zone_id": zone_id})
    web_out_path = WEB_DATA_DIR / "facilities.json"
    web_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(web_out_path, "w", encoding="utf-8") as f:
        json.dump({"facilities": flat}, f, indent=2)
    print(f"Published {len(flat)} facility markers -> {web_out_path}")


if __name__ == "__main__":
    main()
