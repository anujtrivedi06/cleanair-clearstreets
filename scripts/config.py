"""
Central config: reads all secrets from environment variables (set locally via
.env / shell export, or via GitHub Actions "secrets" in CI). Never hardcode keys.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
WEB_DATA_DIR = ROOT / "web" / "data"

# data.gov.in CPCB resource -- "Real time Air Quality Index from various locations".
# Sign up free at https://data.gov.in, generate a personal key under "My Account",
# and set it as DATA_GOV_IN_API_KEY. Resource ID is fixed (public dataset).
DATA_GOV_IN_API_KEY = os.environ.get("DATA_GOV_IN_API_KEY", "")
CPCB_RESOURCE_ID = os.environ.get("CPCB_RESOURCE_ID", "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69")

# States covering our Delhi NCR zones (Gurugram=Haryana, Noida/Ghaziabad=Uttar Pradesh).
NCR_STATES = ["Delhi", "Haryana", "Uttar Pradesh"]

# NASA FIRMS — free API key from https://firms.modaps.eosdis.nasa.gov/api/
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")

# Open-Meteo needs no key at all.
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Delhi NCR bounding box, used for FIRMS hotspot queries.
NCR_BBOX = {"min_lon": 76.8, "min_lat": 28.3, "max_lon": 77.6, "max_lat": 28.9}

# Some endpoints (observed: data.gov.in) silently hang/timeout on the default
# "python-requests/x.x" User-Agent, likely blocked by a WAF, but respond
# instantly to a browser-like one. Use this on every outbound request.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def load_zones():
    with open(DATA_DIR / "zones.json", encoding="utf-8") as f:
        return json.load(f)["zones"]
