(function (global) {
  "use strict";

  const DEFAULT_INFLIGHT_LIMIT = 32;
  const MAX_INFLIGHT_LIMIT = 32;

  function safeInflightLimit(value) {
    if (typeof value === "boolean" || value == null) return DEFAULT_INFLIGHT_LIMIT;
    // Number("") and Number("   ") are both 0, and a blank value can only ever mean "unset".
    if (typeof value === "string" && !value.trim()) return DEFAULT_INFLIGHT_LIMIT;
    let numeric;
    try { numeric = Number(value); } catch (_) { return DEFAULT_INFLIGHT_LIMIT; }
    if (!Number.isFinite(numeric)) return DEFAULT_INFLIGHT_LIMIT;
    // A budget has to be either a number somebody typed or nothing at all. `Number([])` is 0 even
    // though nobody configured anything, and the old `Math.max(0, ...)` clamp turned every negative
    // into that same value, so both silently inherited the "zero means no budget at all" rule and
    // rejected every library page. An explicit `0` keeps meaning "disabled" (pinned by the
    // regression suite); only the accidental collapse falls back (TODO.md:107).
    if (typeof value === "object") return DEFAULT_INFLIGHT_LIMIT;
    if (numeric < 0) return DEFAULT_INFLIGHT_LIMIT;
    return Math.min(MAX_INFLIGHT_LIMIT, Math.max(0, Math.floor(numeric)));
  }

  function loadLibraryResponse(options) {
    const opts = options || {};
    const url = typeof opts.url === "string" ? opts.url : "";
    const refresh = Boolean(opts.refresh);
    const cache = opts.cache;
    const inflight = opts.inflight;
    const fetchJson = opts.fetchJson;
    const limit = safeInflightLimit(opts.inflightLimit);
    const active = opts.active && typeof opts.active === "object" ? opts.active : null;
    const activeCount = () => active && Number.isFinite(active.value) ? Math.max(0, active.value) : inflight.size;
    const epoch = opts.epoch;
    const getEpoch = typeof opts.getEpoch === "function" ? opts.getEpoch : () => epoch;
    // A request can be superseded for its own URL (see the takeover below) and
    // still settle successfully on a transport that ignores `signal`. Epoch
    // ownership cannot catch that: the replacement inherits the same generation,
    // so the abandoned response would overwrite the fresher cache entry after the
    // newer one landed. This per-request flag voids exactly that write.
    let cacheWriteVoided = false;
    if (!url || !cache || !inflight || typeof fetchJson !== "function") {
      return Promise.reject(new TypeError("invalid library response loader options"));
    }
    if (opts.signal?.aborted === true) {
      const error = new Error("library response aborted");
      error.name = "AbortError";
      return Promise.reject(error);
    }
    if (!refresh && cache.has(url)) return Promise.resolve(cache.get(url));
    // Refresh bypasses the response cache, but overlapping refreshes for the
    // same page should still share one active request. This prevents a
    // double-click or status-triggered refresh from producing duplicate list
    // commits and visible flashes in older WebViews.
    if (inflight.has(url)) {
      const existing = inflight.get(url);
      // A view switch aborts the previous fetch before starting its successor.
      // Its rejection can arrive a turn later, so do not let the old promise
      // capture the new page through the URL-level dedupe map.
      if (existing?.__fnAudioAbortSignal?.aborted === true) {
        inflight.delete(url);
        // The owner already abandoned this request, so its admission slot
        // belongs to the replacement now. A WebView whose transport ignores
        // `signal` would otherwise hold the only free slot until the dead
        // fetch settles, which turns a page switch at the ceiling into a
        // rejected load. The release is idempotent and a later settle must
        // not free the neighbour slot (regression tested).
        existing.__fnAudioRelease?.();
        // Handover also voids the abandoned request's right to publish: it no
        // longer owns the URL, so a late body from it must never reach the cache.
        existing.__fnAudioVoidCacheWrite?.();
      } else {
        return existing;
      }
    }
    if (activeCount() >= limit) {
      return Promise.reject(new Error("library response concurrency limit reached"));
    }
    if (active) active.value = activeCount() + 1;
    const internalController = typeof AbortController === "function" ? new AbortController() : null;
    const externalSignal = opts.signal;
    let removeExternalAbort = null;
    if (internalController && externalSignal) {
      const abortFromOwner = () => internalController.abort();
      if (externalSignal.aborted) {
        internalController.abort();
      } else if (typeof externalSignal.addEventListener === "function") {
        externalSignal.addEventListener("abort", abortFromOwner, { once: true });
        removeExternalAbort = () => externalSignal.removeEventListener("abort", abortFromOwner);
      }
    }
    const requestSignal = internalController ? internalController.signal : externalSignal;
    const request = Promise.resolve().then(() => fetchJson(url, opts.message, requestSignal)).then(data => {
      // Refreshes bypass reads, but stale overlapping refresh responses must
      // still obey generation ownership or they can resurrect old rows.
      if (!cacheWriteVoided && getEpoch() === epoch) cache.set(url, data);
      return data;
    });
    request.__fnAudioAbortSignal = requestSignal || null;
    request.__fnAudioAbort = () => {
      if (internalController) internalController.abort();
    };
    let released = false;
    const release = () => {
      if (released) return;
      released = true;
      if (active) active.value = Math.max(0, activeCount() - 1);
    };
    request.__fnAudioRelease = release;
    request.__fnAudioVoidCacheWrite = () => { cacheWriteVoided = true; };
    inflight.set(url, request);
    request.then(
      () => {
        if (inflight.get(url) === request) inflight.delete(url);
        removeExternalAbort?.();
        release();
      },
      () => {
        if (inflight.get(url) === request) inflight.delete(url);
        removeExternalAbort?.();
        release();
      },
    );
    return request;
  }

  global.fnAudioLibraryResponseLoader = { loadLibraryResponse };
})(typeof window !== "undefined" ? window : globalThis);
