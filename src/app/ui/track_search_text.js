(function (global) {
  "use strict";

  const MAX_FIELD_TEXT = 4096;
  const MAX_SEARCH_TEXT = 16384;
  const SEARCH_FIELDS = ["title", "artist", "album", "album_artist", "composer", "genre", "folder", "library_root", "format"];

  function safeFieldText(value) {
    if (typeof value === "string") return value.slice(0, MAX_FIELD_TEXT).toLowerCase();
    if (typeof value === "number" && Number.isFinite(value)) return String(value).toLowerCase();
    return "";
  }

  function trackSearchText(item) {
    if (!item || (typeof item !== "object" && typeof item !== "function")) return "";
    const parts = [];
    for (const field of SEARCH_FIELDS) {
      let value;
      try { value = item[field]; } catch (_) { value = ""; }
      const text = safeFieldText(value);
      if (text) parts.push(text);
    }
    return parts.join(" ").slice(0, MAX_SEARCH_TEXT);
  }

  global.fnAudioTrackSearchText = { MAX_FIELD_TEXT, MAX_SEARCH_TEXT, trackSearchText };
})(typeof window !== "undefined" ? window : globalThis);
