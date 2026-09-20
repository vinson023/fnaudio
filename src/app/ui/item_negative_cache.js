(function (global) {
  "use strict";

  const MAX_ENTRIES = 2048;
  const MAX_AGE_MS = 5 * 60 * 1000;

  function create(limit = MAX_ENTRIES, maxAgeMs = MAX_AGE_MS, now = () => Date.now()) {
    const requestedLimit = Number(limit);
    const requestedAge = Number(maxAgeMs);
    const max = Number.isFinite(requestedLimit)
      ? Math.min(MAX_ENTRIES, Math.max(1, Math.floor(requestedLimit)))
      : MAX_ENTRIES;
    const age = Number.isFinite(requestedAge)
      ? Math.min(MAX_AGE_MS, Math.max(1000, Math.floor(requestedAge)))
      : MAX_AGE_MS;
    const entries = new Map();

    function validKey(value) {
      return typeof value === "string" && value.length > 0 && value.length <= 512;
    }

    function timestamp() {
      try {
        const value = Number(now());
        return Number.isFinite(value) ? value : Date.now();
      } catch (_) {
        return Date.now();
      }
    }

    function prune(current = timestamp()) {
      for (const [key, savedAt] of entries) {
        if (!Number.isFinite(savedAt) || current - savedAt >= age || current < savedAt) entries.delete(key);
      }
      while (entries.size > max) {
        const oldest = entries.keys().next().value;
        if (oldest === undefined) break;
        entries.delete(oldest);
      }
    }

    return {
      has(key) {
        if (!validKey(key)) return false;
        prune();
        return entries.has(key);
      },
      remember(key) {
        if (!validKey(key)) return false;
        prune();
        entries.delete(key);
        entries.set(key, timestamp());
        prune();
        return true;
      },
      delete(key) { return validKey(key) && entries.delete(key); },
      clear() { entries.clear(); },
      get size() { prune(); return entries.size; },
    };
  }

  global.fnAudioItemNegativeCache = { MAX_ENTRIES, MAX_AGE_MS, create };
})(typeof window !== "undefined" ? window : globalThis);
