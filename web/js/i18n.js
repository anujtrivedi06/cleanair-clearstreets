// Static UI translations (English/Hindi). Hand-translated once, not via a
// live API -- this is a small, fixed set of strings, so a translation API
// call at runtime would just be a quota risk for zero benefit. AI-generated
// zone briefings are translated separately (see generate_briefing.py, which
// asks the LLM for both languages in a single call, since Cloud Translation
// API requires a billing account even for free-tier usage).
export const translations = {
  en: {
    subtitle: "Live pollution hotspots & 24h spike forecast — Delhi NCR",
    zonesHeader: "Zones",
    zonesSubtitle: "Ranked by AQI, high to low",
    reportToggle: "Report a pollution source",
    photoLabel: "Photo",
    locationLabel: "Location",
    submitButton: "Classify & submit",
    forecastLabel: "24h forecast",
    forecastPending: "pending",
    aiBriefingLabel: "AI briefing",
    firmsLabel: "Satellite fire/smoke detections",
    citizenReportsLabel: "Citizen reports",
    actionSevere: "Deploy water-mist cannon / cleanup crew",
    actionModerate: "Schedule inspection within 24h",
    actionLow: "Monitor",
    loading: "Loading hotspot data…",
    aqiProxyLabel: "AQI proxy",
    hotspotScoreLabel: "hotspot score",
    severityLabel: "severity",
    popupHotspotScore: "Hotspot score",
    popupAqi: "AQI",
    popupPredicted: "Predicted 24h AQI",
    listenLabel: "Listen",
    staleNote: "last known reading, station offline",
    populationLabel: "residents nearby",
    recurrenceTemplate: "Poor air quality (AQI>200) on {days} of last {total} days",
    headlineTemplate: "~{count} citizens currently in poor+ AQI zones",
    schoolsLabel: "schools nearby",
    hospitalsLabel: "hospitals/clinics nearby",
  },
  hi: {
    subtitle: "लाइव प्रदूषण हॉटस्पॉट और 24 घंटे का पूर्वानुमान — दिल्ली एनसीआर",
    zonesHeader: "क्षेत्र",
    zonesSubtitle: "AQI के अनुसार क्रमबद्ध, अधिक से कम",
    reportToggle: "प्रदूषण स्रोत की रिपोर्ट करें",
    photoLabel: "फ़ोटो",
    locationLabel: "स्थान",
    submitButton: "वर्गीकृत करें और सबमिट करें",
    forecastLabel: "24 घंटे का पूर्वानुमान",
    forecastPending: "लंबित",
    aiBriefingLabel: "एआई ब्रीफिंग",
    firmsLabel: "उपग्रह आग/धुआं पहचान",
    citizenReportsLabel: "नागरिक रिपोर्ट",
    actionSevere: "वाटर-मिस्ट कैनन/सफाई दल तैनात करें",
    actionModerate: "24 घंटे के भीतर निरीक्षण निर्धारित करें",
    actionLow: "निगरानी करें",
    loading: "हॉटस्पॉट डेटा लोड हो रहा है…",
    aqiProxyLabel: "AQI प्रॉक्सी",
    hotspotScoreLabel: "हॉटस्पॉट स्कोर",
    severityLabel: "गंभीरता",
    popupHotspotScore: "हॉटस्पॉट स्कोर",
    popupAqi: "AQI",
    popupPredicted: "24 घंटे में अनुमानित AQI",
    listenLabel: "सुनें",
    staleNote: "अंतिम ज्ञात रीडिंग, स्टेशन ऑफ़लाइन है",
    populationLabel: "आस-पास निवासी",
    recurrenceTemplate: "पिछले {total} में से {days} दिन खराब वायु गुणवत्ता (AQI>200) रही",
    headlineTemplate: "वर्तमान में लगभग {count} नागरिक खराब+ AQI क्षेत्रों में हैं",
    schoolsLabel: "आस-पास स्कूल",
    hospitalsLabel: "आस-पास अस्पताल/क्लिनिक",
  },
};

const STORAGE_KEY = "cleanair_lang";
const listeners = [];

export function getLang() {
  return localStorage.getItem(STORAGE_KEY) || "en";
}

export function setLang(lang) {
  localStorage.setItem(STORAGE_KEY, lang);
  applyStaticText();
  listeners.forEach((fn) => fn(lang));
}

export function onLangChange(fn) {
  listeners.push(fn);
}

export function t(key) {
  const lang = getLang();
  return translations[lang][key] ?? translations.en[key];
}

export function tFormat(key, vars) {
  let text = t(key);
  for (const [k, v] of Object.entries(vars)) {
    text = text.replace(`{${k}}`, v);
  }
  return text;
}

export function applyStaticText() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === getLang());
  });
}

document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => setLang(btn.dataset.lang));
});

applyStaticText();
