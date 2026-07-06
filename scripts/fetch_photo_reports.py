"""
Reads citizen photo reports from Firestore (written by web/js/submit.js after
Gemini classification) and aggregates them into data/processed/photo_severity.json,
which fuse_hotspots.py already reads as the "photo_severity" input to the
hotspot score.

Uses a service-account credential, which bypasses the public Firestore
security rules (see firestore.rules) that otherwise deny all reads -- this is
the only part of the system allowed to see raw citizen reports.

Aggregation: within RECENT_WINDOW_HOURS, take the MAX severity per zone (a
single credible severe report should raise that zone's score immediately,
rather than being averaged down by older/milder reports).
"""
import json
from datetime import datetime, timedelta, timezone

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.oauth2 import service_account

from config import (
    FIREBASE_PROJECT_ID,
    FIREBASE_SERVICE_ACCOUNT_PATH,
    PROCESSED_DIR,
)

RECENT_WINDOW_HOURS = 24


def get_client():
    credentials = service_account.Credentials.from_service_account_file(
        FIREBASE_SERVICE_ACCOUNT_PATH
    )
    return firestore.Client(project=FIREBASE_PROJECT_ID, credentials=credentials)


def fetch_recent_reports(client):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_WINDOW_HOURS)
    cutoff_iso = cutoff.isoformat()
    docs = (
        client.collection("reports")
        .where(filter=FieldFilter("timestamp", ">=", cutoff_iso))
        .stream()
    )
    reports = []
    for doc in docs:
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        reports.append(data)
    return reports


def mark_acknowledged(client, reports):
    """
    Flips status "pending" -> "acknowledged" once a report has actually been
    folded into this cycle's hotspot fusion, so a citizen checking "My
    Reports" (see web/js/myReports.js) sees their report mattered, not just
    that it was received.
    """
    updated = 0
    for r in reports:
        doc_id = r.get("_doc_id")
        if not doc_id or r.get("zoneId") is None or r.get("severity") is None:
            continue
        if r.get("status") == "acknowledged":
            continue
        client.collection("reports").document(doc_id).update({"status": "acknowledged"})
        updated += 1
    return updated


def aggregate_by_zone(reports):
    by_zone = {}
    for r in reports:
        zone_id = r.get("zoneId")
        severity = r.get("severity")
        if not zone_id or severity is None:
            continue
        entry = by_zone.setdefault(zone_id, {"severity": 0.0, "count": 0, "type": "none"})
        if float(severity) >= entry["severity"]:
            entry["severity"] = float(severity)
            entry["type"] = r.get("type", "none")
        entry["count"] += 1
    return by_zone


def main():
    client = get_client()
    reports = fetch_recent_reports(client)
    aggregated = aggregate_by_zone(reports)

    out_path = PROCESSED_DIR / "photo_severity.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2)
    print(f"Aggregated {len(reports)} reports into {len(aggregated)} zones -> {out_path}")

    updated = mark_acknowledged(client, reports)
    print(f"Marked {updated} report(s) as acknowledged")


if __name__ == "__main__":
    main()
