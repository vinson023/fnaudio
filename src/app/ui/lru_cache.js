(function (global) {
  "use strict";
  const MAX_ENTRIES = 50000;
  const MAX_WEIGHT = 1000000;

  function finiteNumber(value) {
    if (typeof value === "boolean" || value == null) return null;
    try {
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    } catch (_) {
      return null;
    }
  }

  function createLruCache(limit, options = {}) {
    const requestedLimit = finiteNumber(limit);
    const max = Math.min(MAX_ENTRIES, Math.max(1, Math.floor(requestedLimit === null ? 1 : requestedLimit)));
    const requestedWeight = finiteNumber(options.maxWeight);
    const maxWeight = Math.min(MAX_WEIGHT, Math.max(0, Math.floor(requestedWeight === null ? 0 : requestedWeight)));
    const weightOf = typeof options.weightOf === "function" ? options.weightOf : () => 1;
    const entries = new Map();
    let totalWeight = 0;

    function entryWeight(value) {
      try {
        const weight = finiteNumber(weightOf(value));
        return weight === null ? 0 : Math.max(0, weight);
      } catch (_) {
        return 0;
      }
    }

    function drop(key) {
      const entry = entries.get(key);
      if (!entry) return false;
      entries.delete(key);
      totalWeight = Math.max(0, totalWeight - entry.weight);
      return true;
    }

    return {
      get(key) {
        if (!entries.has(key)) return undefined;
        const entry = entries.get(key);
        entries.delete(key);
        entries.set(key, entry);
        return entry.value;
      },
      has(key) { return entries.has(key); },
      set(key, value) {
        drop(key);
        const weight = entryWeight(value);
        // A single oversized response should render for this request, but
        // must not evict every useful page only to remain uncached.
        if (maxWeight && weight > maxWeight) return this;
        entries.set(key, { value, weight });
        totalWeight += weight;
        while (entries.size > max || (maxWeight && totalWeight > maxWeight)) {
          drop(entries.keys().next().value);
        }
        return this;
      },
      delete(key) { return drop(key); },
      deleteWhere(predicate) {
        if (typeof predicate !== "function") return 0;
        let removed = 0;
        for (const [key, entry] of entries) {
          let match = false;
          try { match = Boolean(predicate(entry.value, key)); } catch (_) { match = false; }
          if (match && drop(key)) removed += 1;
        }
        return removed;
      },
      clear() {
        entries.clear();
        totalWeight = 0;
      },
      get size() { return entries.size; },
      get weight() { return totalWeight; }
    };
  }

  global.fnAudioLruCache = createLruCache;
})(typeof window !== "undefined" ? window : globalThis);
