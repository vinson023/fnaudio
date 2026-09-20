(function (global) {
  "use strict";

  function safeId(value) {
    return typeof value === "string" && value.length > 0 ? value : null;
  }

  const indexes = new WeakMap();
  function indexFor(rows) {
    if (!Array.isArray(rows)) return null;
    const existing = indexes.get(rows);
    if (existing) return existing;
    const index = new Map();
    for (const item of rows) {
      if (index.size >= 5000) break;
      if (!item || typeof item !== "object") continue;
      try {
        if (typeof item.id === "string" && item.id && !index.has(item.id)) index.set(item.id, item);
      } catch (_) { /* malformed row is ignored */ }
    }
    indexes.set(rows, index);
    return index;
  }

  function findInRows(rows, key) {
    if (!Array.isArray(rows)) return undefined;
    const indexed = indexFor(rows);
    if (indexed && indexed.has(key)) return indexed.get(key);
    for (const item of rows) {
      if (!item || typeof item !== "object") continue;
      try {
        if (item.id === key) return item;
      } catch (_) { /* malformed row is ignored */ }
    }
    return undefined;
  }

  function lookupItem(id, cache, pageItems, items) {
    const key = safeId(id);
    if (key === null) return undefined;
    try {
      const cached = cache && typeof cache.get === "function" ? cache.get(key) : undefined;
      if (cached) return cached;
    } catch (_) { /* cache failures fall through to page data */ }
    return findInRows(pageItems, key) || findInRows(items, key);
  }

  global.fnAudioItemLookup = { lookupItem };
})(typeof window !== "undefined" ? window : globalThis);
