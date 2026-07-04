// Citizen photo submission -> Gemini Vision classification, called directly
// from the browser via the Google AI Studio API.
//
// SECURITY NOTE: this key is visible in client-side code. Restrict it to your
// deployed domain via HTTP referrer restrictions in Google AI Studio / Cloud
// Console before going live -- see README. Fine for a hackathon prototype,
// not for production use as-is.
const GEMINI_API_KEY = "REPLACE_WITH_YOUR_AI_STUDIO_KEY";
const GEMINI_MODEL = "gemini-2.0-flash";
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;

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
  const body = {
    contents: [
      {
        parts: [
          { text: CLASSIFY_PROMPT },
          { inline_data: { mime_type: file.type, data: base64Data } },
        ],
      },
    ],
  };

  const resp = await fetch(GEMINI_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Gemini API error: ${resp.status}`);
  const data = await resp.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? "{}";
  // Model may wrap JSON in a code fence; strip it defensively.
  const cleaned = text.replace(/```json|```/g, "").trim();
  return JSON.parse(cleaned);
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
    // TODO (Day 3): persist { zoneId, ...result, timestamp } to Firestore so
    // the next pipeline run can fold citizen photo severity into fuse_hotspots.py.
  } catch (err) {
    console.error(err);
    resultDiv.textContent = "Classification failed — check API key / console for details.";
  }
});
