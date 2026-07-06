// Tracks which citizen reports THIS browser submitted, using the Firestore
// document ID as a capability token (see firestore.rules) rather than any
// login system. Pure localStorage helpers -- no DOM, no Firestore calls
// here; those live in map.js (rendering) and submit.js (recording).
const STORAGE_KEY = "cleanair_my_reports";
const MAX_STORED = 20;

export function recordReport(reportId, zoneId) {
  const reports = getStoredReports();
  reports.unshift({ id: reportId, zoneId, submittedAt: new Date().toISOString() });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(reports.slice(0, MAX_STORED)));
}

export function getStoredReports() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}
