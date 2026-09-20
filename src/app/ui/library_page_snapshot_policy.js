(function (global) {
  "use strict";

  const MAX_TOTAL = 1000000000;

  function boundedPage(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) return 1;
    return Math.max(1, Math.floor(value));
  }

  function boundedTotal(value, itemCount) {
    const floor = Math.max(0, Number(itemCount) || 0);
    if (typeof value !== "number" || !Number.isFinite(value)) return floor;
    return Math.max(floor, Math.min(MAX_TOTAL, Math.floor(value)));
  }

  function restore(raw, options = {}) {
    const source = options && typeof options === "object" ? options : {};
    const maxBytes = Number(source.maxBytes);
    const now = Number(source.now);
    const ttlMs = Number(source.ttlMs);
    const key = typeof source.key === "string" ? source.key : "";
    const boundItems = typeof source.boundItems === "function" ? source.boundItems : () => [];
    if (typeof raw !== "string" || !raw || !Number.isFinite(maxBytes) || maxBytes < 1 || raw.length > maxBytes) {
      return { status: "miss", savedAt: 0, items: [], total: 0 };
    }
    try {
      const snapshot = JSON.parse(raw);
      if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)
        || snapshot.key !== key || !Array.isArray(snapshot.items) || !snapshot.items.length) {
        return { status: "miss", savedAt: 0, items: [], total: 0 };
      }
      const savedAt = Number(snapshot.savedAt);
      const age = now - savedAt;
      if (!Number.isFinite(now) || !Number.isFinite(ttlMs) || ttlMs < 0
        || !Number.isFinite(savedAt) || age < 0 || age > ttlMs) {
        return { status: "stale", savedAt: Number.isFinite(savedAt) ? savedAt : 0, items: [], total: 0 };
      }
      const items = boundItems(snapshot.items);
      if (!Array.isArray(items) || !items.length) return { status: "miss", savedAt: 0, items: [], total: 0 };
      return { status: "hit", savedAt, items, total: boundedTotal(snapshot.total, items.length) };
    } catch (_) {
      return { status: "miss", savedAt: 0, items: [], total: 0 };
    }
  }

  function encode(options = {}) {
    const source = options && typeof options === "object" ? options : {};
    const key = typeof source.key === "string" ? source.key : "";
    const items = Array.isArray(source.items) ? source.items : [];
    const savedAt = Number(source.savedAt);
    const maxBytes = Number(source.maxBytes);
    if (!key || !items.length || !Number.isFinite(savedAt) || !Number.isFinite(maxBytes) || maxBytes < 1) return "";
    try {
      const encoded = JSON.stringify({
        key,
        savedAt,
        total: boundedTotal(source.total, items.length),
        items,
      });
      return encoded.length <= maxBytes ? encoded : "";
    } catch (_) {
      return "";
    }
  }

  global.fnAudioLibraryPageSnapshotPolicy = Object.freeze({ MAX_TOTAL, boundedPage, boundedTotal, restore, encode });
})(typeof window !== "undefined" ? window : globalThis);
