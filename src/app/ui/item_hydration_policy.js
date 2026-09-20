(function (global) {
  "use strict";
  const MAX_ITEM_IDS = 2048;
  const MAX_ITEM_ID_CHARS = 512;
  const BATCH_SIZE = 100;
  const MAX_BATCH_CHARS = 8192;
  function encodedLength(value) {
    try {
      return encodeURIComponent(value).length;
    } catch (_) {
      return value.length;
    }
  }
  function normalizeItemIds(values) {
    if (!Array.isArray(values)) return [];
    const result = [];
    const seen = new Set();
    for (let index = 0; index < values.length && result.length < MAX_ITEM_IDS; index += 1) {
      const value = values[index];
      if (typeof value !== "string") continue;
      const id = value.trim();
      if (!id || id.length > MAX_ITEM_ID_CHARS || seen.has(id)) continue;
      seen.add(id);
      result.push(id);
    }
    return result;
  }
  function batchesForItemIds(values) {
    const ids = normalizeItemIds(values);
    const batches = [];
    let batch = [];
    let batchChars = 0;
    ids.forEach(id => {
      const separatorChars = batch.length ? 1 : 0;
      const encodedChars = encodedLength(id);
      if (batch.length >= BATCH_SIZE || (batch.length && batchChars + separatorChars + encodedChars > MAX_BATCH_CHARS)) {
        batches.push(batch);
        batch = [];
        batchChars = 0;
      }
      batch.push(id);
      batchChars += (batch.length > 1 ? 1 : 0) + encodedChars;
    });
    if (batch.length) batches.push(batch);
    return batches;
  }
  global.fnAudioItemHydrationPolicy = { normalizeItemIds, batchesForItemIds, MAX_ITEM_IDS, MAX_ITEM_ID_CHARS, BATCH_SIZE, MAX_BATCH_CHARS };
})(typeof window !== "undefined" ? window : globalThis);
