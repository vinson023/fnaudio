(function (global) {
  "use strict";
  const MAX_BATCHES = 4096;
  const MAX_BATCH_ITEMS = 256;
  const DEFAULT_CONCURRENCY = 4;
  const MAX_CONCURRENCY = 32;
  function snapshotBatch(value) {
    if (!Array.isArray(value)) return value;
    // Hydration batches are arrays of IDs. Snapshot them at pool creation so
    // a caller reusing/mutating its working array cannot change an in-flight
    // request after the batch has been scheduled.
    try { return value.slice(0, MAX_BATCH_ITEMS); } catch (_) { return []; }
  }
  function safeConcurrency(value) {
    if (typeof value === "boolean" || value == null) return 1;
    let numeric;
    try { numeric = Number(value); } catch (_) { return 1; }
    if (!Number.isFinite(numeric)) return 1;
    return Math.min(MAX_CONCURRENCY, Math.max(1, Math.floor(numeric) || 1));
  }
  function createBatchRequestPool(batches, concurrency, worker) {
    const list = [];
    if (batches != null) {
      try {
        const iterator = batches[Symbol.iterator]();
        while (list.length < MAX_BATCHES) {
          const step = iterator.next();
          if (step.done) break;
          list.push(snapshotBatch(step.value));
        }
      } catch (_) {
        // Invalid/non-iterable input is treated as an empty batch list.
      }
    }
    const limit = safeConcurrency(concurrency);
    const promises = list.map(() => {
      let resolve;
      let reject;
      const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
      // A cancelled queued batch may be rejected before a caller reaches
      // `get()`. Observe the rejection internally while preserving the same
      // rejected Promise for consumers that do await it.
      promise.catch(() => {});
      return { promise, resolve, reject };
    });
    let next = 0;
    let active = 0;
    let cancelled = false;
    let cancelError = null;
    function launch() {
      while (!cancelled && active < limit && next < list.length) {
        const index = next++;
        active += 1;
        Promise.resolve()
          .then(() => {
            // launch() reserves slots through a microtask. A view can cancel
            // in the gap before that callback runs; do not start stale I/O
            // merely because the slot was already accounted for.
            if (cancelled) throw cancelError || new Error("Batch request cancelled");
            return worker(list[index], index);
          })
          .then(promises[index].resolve, promises[index].reject)
          .finally(() => { active -= 1; launch(); });
      }
    }
    launch();
    const pool = {
      length: list.length,
      get: index => promises[index]?.promise || Promise.resolve(undefined),
      // Do not pass the sparse promise array directly to Promise.all: queued
      // batches have no promise until a worker slot opens, and would otherwise
      // be reported as undefined immediately.
      all: () => Promise.all(list.map((_, index) => pool.get(index))),
      cancel(reason = "Batch request cancelled") {
        if (cancelled) return;
        cancelled = true;
        if (reason instanceof Error) cancelError = reason;
        else if (typeof reason === "string") cancelError = new Error(reason.slice(0, 256));
        else cancelError = new Error("Batch request cancelled");
        for (let index = next; index < promises.length; index += 1) promises[index].reject(cancelError);
      },
    };
    return pool;
  }
  global.fnAudioBatchRequestPool = createBatchRequestPool;
  global.fnAudioBatchRequestPool.DEFAULT_CONCURRENCY = DEFAULT_CONCURRENCY;
  global.fnAudioBatchRequestPoolLimits = { MAX_BATCHES, MAX_BATCH_ITEMS, DEFAULT_CONCURRENCY };
})(typeof window !== "undefined" ? window : globalThis);
