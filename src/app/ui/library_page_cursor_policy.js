(function (global) {
  "use strict";

  const MAX_ENTRIES = 64;
  const MAX_TOKEN_CHARS = 768;

  function validPage(value) {
    try {
      return Number.isFinite(value) && Number.isInteger(value) && value >= 1 ? value : 0;
    } catch (_) {
      return 0;
    }
  }

  function clearQuery(store, queryKey) {
    if (!(store instanceof Map) || typeof queryKey !== "string" || !queryKey) return;
    const prefix = `${queryKey}:`;
    for (const key of store.keys()) {
      if (typeof key === "string" && key.startsWith(prefix)) store.delete(key);
    }
  }

  function remember(store, queryKey, page, token) {
    if (!(store instanceof Map) || typeof queryKey !== "string" || !queryKey) return false;
    const numericPage = validPage(page);
    if (!numericPage) return false;
    if (numericPage === 1) clearQuery(store, queryKey);
    if (typeof token === "string") {
      const bounded = token.trim();
      if (bounded && bounded.length <= MAX_TOKEN_CHARS) store.set(`${queryKey}:${numericPage}`, bounded);
    }
    while (store.size > MAX_ENTRIES) {
      const oldest = store.keys().next().value;
      if (oldest === undefined) break;
      store.delete(oldest);
    }
    return true;
  }

  function get(store, queryKey, page) {
    if (!(store instanceof Map) || typeof queryKey !== "string" || !queryKey) return "";
    const numericPage = validPage(page);
    if (numericPage <= 1) return "";
    const token = store.get(`${queryKey}:${numericPage - 1}`);
    return typeof token === "string" && token.length <= MAX_TOKEN_CHARS ? token : "";
  }

  global.fnAudioLibraryPageCursorPolicy = { MAX_ENTRIES, MAX_TOKEN_CHARS, clearQuery, remember, get };
})(typeof window !== "undefined" ? window : globalThis);
