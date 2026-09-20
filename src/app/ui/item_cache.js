(function (global) {
  "use strict";

  const MAX_ITEM_CACHE_ENTRIES = 50000;
  const MAX_ITEM_CACHE_KEY_TEXT = 4096;
  function safeKey(key) {
    return typeof key === "string" && key.length > 0 && key.length <= MAX_ITEM_CACHE_KEY_TEXT ? key : null;
  }

  function createItemCache(limit) {
    let requested = 12000;
    if (typeof limit !== "boolean" && limit != null) {
      try {
        const numericLimit = Number(limit);
        if (Number.isFinite(numericLimit)) requested = numericLimit;
      } catch (_) { /* malformed limits use the safe default */ }
    }
    const max = Math.min(MAX_ITEM_CACHE_ENTRIES, Math.max(1000, Math.floor(requested) || 12000));
    const entries = new Map();
    return {
      get(key) {
        key = safeKey(key);
        if (key === null) return undefined;
        if (!entries.has(key)) return undefined;
        const value = entries.get(key);
        entries.delete(key);
        entries.set(key, value);
        return value;
      },
      has(key) { key = safeKey(key); return key !== null && entries.has(key); },
      set(key, value) {
        key = safeKey(key);
        if (key === null) return this;
        entries.delete(key);
        entries.set(key, value);
        return this;
      },
      delete(key) { key = safeKey(key); return key !== null && entries.delete(key); },
      clear() { entries.clear(); },
      trim(protectedIds = new Set()) {
        const removeCount = entries.size - max;
        if (removeCount <= 0) return;
        const removable = [];
        for (const key of entries.keys()) {
          if (protectedIds.has(key)) continue;
          removable.push(key);
          if (removable.length >= removeCount) break;
        }
        removable.forEach(key => entries.delete(key));
      },
      get size() { return entries.size; }
    };
  }

  global.fnAudioItemCache = createItemCache;
})(typeof window !== "undefined" ? window : globalThis);
