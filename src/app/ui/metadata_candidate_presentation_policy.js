(function (global) {
  "use strict";

  const FIELDS = ["title", "artist", "album", "album_artist", "image_url", "date", "genre", "track_no"];

  function hasDisplayValue(value) {
    if (typeof value === "string") return value.trim().length > 0;
    return typeof value === "number" && Number.isFinite(value);
  }

  function completeness(candidate) {
    if (!candidate || typeof candidate !== "object") return 0;
    try {
      return FIELDS.reduce((score, field) => score + (hasDisplayValue(candidate[field]) ? 1 : 0), 0);
    } catch (_) {
      return 0;
    }
  }

  // Do not inspect provider object keys: a malformed response may be a Proxy
  // whose ownKeys trap throws. The presentation layer only needs to know
  // whether one of the bounded display fields is readable.
  function hasCandidateData(candidate) {
    if (!candidate || typeof candidate !== "object") return false;
    return completeness(candidate) > 0 || confidence(candidate) > 0;
  }

  function confidence(candidate) {
    if (!candidate || typeof candidate !== "object") return 0;
    try {
      const value = candidate.confidence;
      return typeof value === "number" && Number.isFinite(value) && value >= 0
        ? value
        : (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : 0);
    } catch (_) {
      return 0;
    }
  }

  function confidencePercent(value) {
    const number = typeof value === "number" || typeof value === "string" ? Number(value) : NaN;
    if (!Number.isFinite(number) || number < 0) return "0%";
    return `${Math.round(Math.min(1, number) * 100)}%`;
  }

  function selectDisplayCandidate(best, candidates) {
    const pool = [];
    try {
      if (hasCandidateData(best)) pool.push(best);
    } catch (_) {}
    (Array.isArray(candidates) ? candidates : []).forEach(candidate => {
      try {
        if (hasCandidateData(candidate)) pool.push(candidate);
      } catch (_) {}
    });
    let selected = null;
    let selectedCompleteness = -1;
    let selectedConfidence = -1;
    pool.forEach(candidate => {
      const candidateCompleteness = completeness(candidate);
      const candidateConfidence = confidence(candidate);
      if (!selected || candidateCompleteness > selectedCompleteness
        || (candidateCompleteness === selectedCompleteness && candidateConfidence > selectedConfidence)) {
        selected = candidate;
        selectedCompleteness = candidateCompleteness;
        selectedConfidence = candidateConfidence;
      }
    });
    // Null is meaningful to callers: it distinguishes “no candidate yet”
    // from an empty object projection and keeps pending/no-match recovery
    // branches reachable.
    return selected;
  }

  function selectDisplayArtwork(best, candidates, fallback = "") {
    const values = [];
    try { if (hasDisplayValue(best?.image_url)) values.push(best.image_url); } catch (_) {}
    (Array.isArray(candidates) ? candidates : []).forEach(candidate => {
      try { if (hasDisplayValue(candidate?.image_url)) values.push(candidate.image_url); } catch (_) {}
    });
    try { if (hasDisplayValue(fallback)) values.push(fallback); } catch (_) {}
    const selected = values.find(value => typeof value === "string" ? value.trim() : Number.isFinite(value));
    return selected == null ? "" : selected;
  }

  global.fnAudioMetadataCandidatePresentationPolicy = { selectDisplayCandidate, selectDisplayArtwork, confidencePercent };
})(typeof window !== "undefined" ? window : globalThis);
