(function (global) {
  "use strict";

  const DEFAULT_LIMIT = 4096;
  const MAX_TEXT = 1024;
  const MAX_IMAGE = 4096;

  function safeKey(value) {
    return typeof value === "string" && value.length > 0 && value.length <= MAX_TEXT
      ? value
      : "";
  }

  function safeText(value, limit) {
    if (typeof value !== "string") return "";
    return value.length > limit ? value.slice(0, limit) : value;
  }

  function normalizeMetadata(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    return {
      artist: safeText(value.artist, MAX_TEXT),
      release_date: safeText(value.release_date, MAX_TEXT),
      image_url: safeText(value.image_url, MAX_IMAGE),
      source: safeText(value.source, MAX_TEXT),
    };
  }

  function createAlbumMetadataCache(limit = DEFAULT_LIMIT) {
    const numeric = typeof limit === "number" && Number.isFinite(limit) ? Math.floor(limit) : DEFAULT_LIMIT;
    const max = Math.min(10000, Math.max(1, numeric));
    const entries = new Map();
    return {
      get(key) {
        const normalized = safeKey(key);
        if (!normalized || !entries.has(normalized)) return undefined;
        const value = entries.get(normalized);
        entries.delete(normalized);
        entries.set(normalized, value);
        return value;
      },
      set(key, value) {
        const normalized = safeKey(key);
        if (!normalized) return this;
        const metadata = normalizeMetadata(value);
        if (!metadata) return this;
        entries.delete(normalized);
        entries.set(normalized, metadata);
        while (entries.size > max) entries.delete(entries.keys().next().value);
        return this;
      },
      has(key) { return entries.has(safeKey(key)); },
      delete(key) { return entries.delete(safeKey(key)); },
      clear() { entries.clear(); },
      get size() { return entries.size; },
      get limit() { return max; }
    };
  }

  global.fnAudioAlbumMetadataCache = createAlbumMetadataCache;
})(typeof window !== "undefined" ? window : globalThis);
