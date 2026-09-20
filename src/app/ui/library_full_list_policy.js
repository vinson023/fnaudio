(function (global) {
  "use strict";
  const MAX_ITEMS = 200000;
  const MAX_NUMERIC_TEXT = 64;

  function boundedCount(value, maximum = MAX_ITEMS) {
    if (typeof value === "string" && value.length > MAX_NUMERIC_TEXT) return 0;
    if (typeof value !== "string" && typeof value !== "number") return 0;
    let numeric;
    try { numeric = Number(value); } catch (_) { return 0; }
    if (!Number.isFinite(numeric)) return 0;
    let bound;
    try { bound = Number(maximum); } catch (_) { bound = MAX_ITEMS; }
    if (!Number.isFinite(bound)) bound = MAX_ITEMS;
    bound = Math.max(0, Math.min(MAX_ITEMS, Math.floor(bound)));
    return Math.max(0, Math.min(bound, Math.floor(numeric)));
  }

  function shouldStopMerge(mergedLength, total, pageLength, maximum = MAX_ITEMS) {
    const merged = boundedCount(mergedLength);
    const count = boundedCount(total, maximum);
    const page = boundedCount(pageLength, maximum);
    return merged >= count || merged >= boundedCount(maximum) || page === 0;
  }

  global.fnAudioLibraryFullListPolicy = { boundedCount, shouldStopMerge, MAX_ITEMS };
})(typeof window !== "undefined" ? window : globalThis);
