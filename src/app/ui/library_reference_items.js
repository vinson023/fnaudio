(function (global) {
  "use strict";

  const MAX_REFERENCE_ITEMS = 200000;

  function projectReferencedItems(ids, itemById, limit = MAX_REFERENCE_ITEMS) {
    if (!Array.isArray(ids) || typeof itemById !== "function") return [];
    let max = Number(limit);
    if (!Number.isFinite(max)) max = MAX_REFERENCE_ITEMS;
    max = Math.max(0, Math.min(MAX_REFERENCE_ITEMS, Math.floor(max)));
    let length;
    try { length = Math.min(MAX_REFERENCE_ITEMS, ids.length); } catch (_) { return []; }
    if (!Number.isFinite(length) || length <= 0) return [];
    const result = [];
    for (let index = 0; index < length && result.length < max; index += 1) {
      let item;
      try { item = itemById(ids[index]); } catch (_) { item = null; }
      if (item) result.push(item);
    }
    return result;
  }

  global.fnAudioLibraryReferenceItems = { MAX_REFERENCE_ITEMS, projectReferencedItems };
})(typeof window !== "undefined" ? window : globalThis);
