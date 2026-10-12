(function (global) {
  "use strict";

  const DEFAULT_TTL_MS = 750;
  const DEFAULT_MAX_ENTRIES = 64;

  function boundedPositive(value, fallback, maximum) {
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) return fallback;
    return Math.min(maximum, Math.floor(number));
  }

  function abortError() {
    const error = new Error("metadata request aborted");
    error.name = "AbortError";
    return error;
  }

  function create(options = {}) {
    const now = typeof options.now === "function" ? options.now : () => Date.now();
    const ttlMs = boundedPositive(options.ttlMs, DEFAULT_TTL_MS, 30000);
    const maxEntries = Math.max(1, boundedPositive(options.maxEntries, DEFAULT_MAX_ENTRIES, 256));
    const cache = new Map();
    const inflight = new Map();
    let epoch = 0;

    function trim() {
      while (cache.size > maxEntries) cache.delete(cache.keys().next().value);
    }
    function detach(entry) {
      entry.subscribers = Math.max(0, entry.subscribers - 1);
      if (entry.subscribers === 0 && !entry.settled) {
        try { entry.controller?.abort(); } catch (_) {}
      }
    }
    function subscribe(entry, signal) {
      if (signal?.aborted === true) return Promise.reject(abortError());
      entry.subscribers += 1;
      return new Promise((resolve, reject) => {
        let done = false;
        const finish = (callback, value) => {
          if (done) return;
          done = true;
          signal?.removeEventListener?.("abort", onAbort);
          detach(entry);
          callback(value);
        };
        const onAbort = () => finish(reject, abortError());
        signal?.addEventListener?.("abort", onAbort, { once: true });
        entry.promise.then(value => finish(resolve, value), error => finish(reject, error));
      });
    }
    function load(key, request, signal) {
      const url = typeof key === "string" ? key : "";
      if (!url || typeof request !== "function") return Promise.reject(new TypeError("invalid metadata request"));
      if (signal?.aborted === true) return Promise.reject(abortError());
      const current = now();
      const cached = cache.get(url);
      if (cached && cached.expiresAt > current) {
        cache.delete(url);
        cache.set(url, cached);
        if (!signal) return Promise.resolve(cached.value);
        return new Promise((resolve, reject) => {
          const onAbort = () => reject(abortError());
          signal.addEventListener?.("abort", onAbort, { once: true });
          Promise.resolve(cached.value).then(value => {
            signal.removeEventListener?.("abort", onAbort);
            resolve(value);
          }, error => {
            signal.removeEventListener?.("abort", onAbort);
            reject(error);
          });
        });
      }
      if (cached) cache.delete(url);
      let entry = inflight.get(url);
      if (entry?.controller?.signal?.aborted === true) {
        inflight.delete(url);
        entry = null;
      }
      if (!entry) {
        const controller = typeof AbortController === "function" ? new AbortController() : null;
        entry = { controller, promise: null, subscribers: 0, settled: false, epoch };
        const ownedRequest = Promise.resolve().then(() => request({
          signal: controller?.signal,
          abort: () => { try { controller?.abort(); } catch (_) {} },
        }));
        entry.promise = ownedRequest.then(value => {
          entry.settled = true;
          if (inflight.get(url) === entry) inflight.delete(url);
          if (entry.epoch === epoch) cache.set(url, { value, expiresAt: now() + ttlMs });
          trim();
          return value;
        }, error => {
          entry.settled = true;
          if (inflight.get(url) === entry) inflight.delete(url);
          throw error;
        });
        inflight.set(url, entry);
      }
      return subscribe(entry, signal);
    }
    return {
      load,
      clear() {
        epoch += 1;
        cache.clear();
        for (const entry of inflight.values()) {
          try { entry.controller?.abort(); } catch (_) {}
        }
        inflight.clear();
      },
      snapshot() { return { cache: cache.size, inflight: inflight.size, ttlMs, maxEntries }; },
    };
  }

  global.fnAudioMetadataRequestLoader = { create, DEFAULT_TTL_MS, DEFAULT_MAX_ENTRIES };
})(typeof window !== "undefined" ? window : globalThis);
