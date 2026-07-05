// Citizen photo submission -> Gemini Vision classification via Firebase AI
// Logic (Gemini Developer API backend). Unlike a raw Generative Language API
// key, this firebaseConfig is meant to be public -- it identifies the Firebase
// project, but access control is enforced by Firebase, not by keeping this
// secret. See README for why we moved off a raw client-side Gemini key.
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.15.0/firebase-app.js";
import {
  getAI,
  getGenerativeModel,
  GoogleAIBackend,
} from "https://www.gstatic.com/firebasejs/12.15.0/firebase-ai.js";

const firebaseConfig = {
  apiKey: "AIzaSyCGJQ3Xl2_hTloRhyLAV-prVgBzpgngtnU",
  authDomain: "gen-lang-client-0882700239.firebaseapp.com",
  projectId: "gen-lang-client-0882700239",
  storageBucket: "gen-lang-client-0882700239.firebasestorage.app",
  messagingSenderId: "568172456241",
  appId: "1:568172456241:web:1dd51495a6cbbc017d2810",
};

const firebaseApp = initializeApp(firebaseConfig);
const ai = getAI(firebaseApp, { backend: new GoogleAIBackend() });
const model = getGenerativeModel(ai, { model: "gemini-2.5-flash" });

// Firestore "reports" collection: public create only (see firestore.rules) --
// no API key or auth needed for a create request the rules allow.
const FIREBASE_PROJECT_ID = "gen-lang-client-0882700239";
const FIRESTORE_REPORTS_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT_ID}/databases/(default)/documents/reports`;

const CLASSIFY_PROMPT = `You are classifying a photo reported by a citizen for a
neighbourhood pollution monitoring system. Respond ONLY with compact JSON of the
form {"type": "smoke"|"dust"|"garbage_burning"|"haze"|"none", "severity": 0.0-1.0,
"reasoning": "one short sentence"}. severity 1.0 = extreme/hazardous, 0.0 = no
visible pollution.`;

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function classifyPhoto(file) {
  const base64Data = await fileToBase64(file);
  const result = await model.generateContent([
    CLASSIFY_PROMPT,
    { inlineData: { mimeType: file.type, data: base64Data } },
  ]);
  const text = result.response.text();
  // Model may wrap JSON in a code fence; strip it defensively.
  const cleaned = text.replace(/```json|```/g, "").trim();
  return JSON.parse(cleaned);
}

async function saveReportToFirestore(zoneId, result) {
  const body = {
    fields: {
      zoneId: { stringValue: zoneId },
      type: { stringValue: result.type },
      severity: { doubleValue: result.severity },
      reasoning: { stringValue: result.reasoning },
      timestamp: { stringValue: new Date().toISOString() },
    },
  };
  const resp = await fetch(FIRESTORE_REPORTS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Firestore write error: ${resp.status} ${await resp.text()}`);
}

document.getElementById("submit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById("photo-input");
  const zoneId = document.getElementById("zone-select").value;
  const resultDiv = document.getElementById("classification-result");

  if (!fileInput.files.length) return;

  resultDiv.textContent = "Classifying…";
  try {
    const result = await classifyPhoto(fileInput.files[0]);
    resultDiv.innerHTML = `<strong>${result.type}</strong> — severity ${result.severity}<br/><em>${result.reasoning}</em>`;
    await saveReportToFirestore(zoneId, result);
    resultDiv.innerHTML += `<br/><small>Report submitted — will be reflected on the map within the next pipeline run.</small>`;
  } catch (err) {
    console.error(err);
    resultDiv.textContent = "Classification/submission failed — check console for details.";
  }
});
