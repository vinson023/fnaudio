(function (global) {
  "use strict";

  const MAX_RESPONSE_WEIGHT = 6000;

  function responseWeight(data) {
    if (!data || typeof data !== "object") return 1;
    const collections = [data.items, data.groups, data.folders];
    const weight = Math.max(1, ...collections.map(value => Array.isArray(value) ? value.length : 0));
    return Math.min(MAX_RESPONSE_WEIGHT, weight);
  }

  global.fnAudioLibraryResponsePolicy = { MAX_RESPONSE_WEIGHT, responseWeight };
})(typeof window !== "undefined" ? window : globalThis);
