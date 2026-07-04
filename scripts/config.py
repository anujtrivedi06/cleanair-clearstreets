"""
Central config: reads all secrets from environment variables (set locally via
.env / shell export, or via GitHub Actions "secrets" in CI). Never hardcode keys.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
WEB_DATA_DIR = ROOT / "web" / "data"

# data.gov.in CPCB resource — sign up free at https://data.gov.in, get an API key,
# and find the correct resource ID for "Real-time / historical Air Quality Index".
DATA_GOV_IN_API_KEY = os.environ.get("DATA_GOV_IN_API_KEY", "")
CPCB_RESOURCE_ID = os.environ.get("CPCB_RESOURCE_ID", "")

# NASA FIRMS — free API key from https://firms.modaps.eosdis.nasa.gov/api/
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")

# Open-Meteo needs no key at all.
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Delhi NCR bounding box, used for FIRMS hotspot queries.
NCR_BBOX = {"min_lon": 76.8, "min_lat": 28.3, "max_lon": 77.6, "max_lat": 28.9}


def load_zones():
    with open(DATA_DIR / "zones.json", encoding="utf-8") as f:
        return json.load(f)["zones"]
