(function (global) {
  "use strict";

  // Keep diagnostics safe to expose from a browser/WebView console.  The
  // policy never mutates counters and deliberately omits the session start
  // timestamp so callers cannot infer wall-clock information from a report.
  const COUNTER_KEYS = [
    "renders", "listCommits", "coverHydrations",
    "coverRequests", "coverLoads", "coverFailures", "coverRetries",
    "snapshotMarkupReuses", "listMarkupNoops",
    "metadataPrefetchRequests", "metadataPrefetchSuccesses", "metadataPrefetchFailures", "metadataPrefetchNoMatches",
  ];
  const TIMING_KEYS = ["firstListCommitMs", "firstCoverHydrationMs", "metadataPrefetchFirstMs", "metadataPrefetchLastMs", "metadataPrefetchMaxMs", "metadataPrefetchTotalMs"];
  const MAX_COUNTER = 1000000;
  const MAX_TIMING = 3600000;

  function boundedNumber(value, maximum) {
    // Diagnostics are callable from a WebView console and may receive a
    // hostile/corrupt metrics object. Do not invoke arbitrary valueOf/
    // toString hooks while projecting a supposedly read-only snapshot.
    if (typeof value !== "number" && typeof value !== "string") return 0;
    if (typeof value === "string" && value.length > 32) return 0;
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < 0) return 0;
    return Math.min(maximum, Math.floor(numeric));
  }

  function snapshot(metrics) {
    const source = metrics && typeof metrics === "object" ? metrics : {};
    const result = {};
    for (const key of COUNTER_KEYS) result[key] = boundedNumber(source[key], MAX_COUNTER);
    for (const key of TIMING_KEYS) result[key] = boundedNumber(source[key], MAX_TIMING);
    return result;
  }

  global.fnAudioUiMetricsPolicy = { snapshot };
})(typeof window !== "undefined" ? window : globalThis);
