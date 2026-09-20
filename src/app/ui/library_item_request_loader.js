(function (global) {
  "use strict";

  function loadBatch(options) {
    const opts = options || {};
    const batch = Array.isArray(opts.batch) ? opts.batch.slice(0, 100) : [];
    const inflight = opts.inflight;
    const fetchJson = opts.fetchJson;
    const limit = Number.isFinite(opts.limit) ? Math.max(1, Math.floor(opts.limit)) : 32;
    if (!batch.length || !inflight || typeof inflight.has !== "function" || typeof fetchJson !== "function") {
      return Promise.reject(new TypeError("invalid library item request options"));
    }
    // IDs are opaque strings. A delimiter-based key can collide when an ID
    // itself contains that delimiter, causing one hydration response to be
    // returned for a different batch. Preserve array structure in the key.
    const key = JSON.stringify(batch);
    if (inflight.has(key)) return inflight.get(key);
    // Do not merely skip deduplication at capacity: the old behavior still
    // dispatched untracked requests, so a large client-side playlist could
    // exceed its supposed hydration concurrency ceiling.
    if (inflight.size >= limit) {
      return Promise.reject(new Error("library item request concurrency limit reached"));
    }
    const request = Promise.resolve().then(() => fetchJson(batch, opts.signal));
    inflight.set(key, request);
    request.then(
      () => { if (inflight.get(key) === request) inflight.delete(key); },
      () => { if (inflight.get(key) === request) inflight.delete(key); },
    );
    return request;
  }

  global.fnAudioLibraryItemRequestLoader = { loadBatch };
})(typeof window !== "undefined" ? window : globalThis);
