(() => {
  const MAX_VISIBLE_ITEMS = 500;

  function safeItems(value) {
    return Array.isArray(value) ? value.slice(0, MAX_VISIBLE_ITEMS) : [];
  }

  function safeCount(value) {
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) return value;
    if (typeof value === "string" && /^\d{1,9}$/.test(value.trim())) return Number(value);
    return 0;
  }

  function shouldRetainSnapshot(data = {}, previousItems = [], options = {}) {
    if (!options || options.refresh || options.guardUsed || options.snapshotHit !== true) return false;
    const previous = safeItems(previousItems);
    const current = safeItems(data?.items);
    return previous.length > 0 && current.length === 0 && safeCount(data?.count) === 0;
  }

  function shouldRetryAfterRetention(data = {}) {
    return safeItems(data?.items).length === 0 && safeCount(data?.count) === 0;
  }

  globalThis.fnAudioLibraryEmptyResponsePolicy = { shouldRetainSnapshot, shouldRetryAfterRetention };
})();
