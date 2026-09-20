(() => {
  const MAX_QUEUE_SCAN = 50000;
  function safeNumber(value, fallback = 0) {
    if (typeof value !== "number" && typeof value !== "string") return fallback;
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }
  function pageForQueueIndex(index, entries = [], pageSize = 120) {
    const targetIndex = safeNumber(index, NaN);
    const size = Math.min(500, Math.max(1, Math.floor(safeNumber(pageSize, 1)) || 1));
    let position = -1;
    if (Array.isArray(entries)) {
      const limit = Math.min(entries.length, MAX_QUEUE_SCAN);
      for (let index = 0; index < limit; index += 1) {
        if (safeNumber(entries[index]?.queueIndex, NaN) === targetIndex) { position = index; break; }
      }
    }
    if (position < 0) return 1;
    return Math.floor(position / size) + 1;
  }

  function queuePresentationPlan(options = {}) {
    if (!options || typeof options !== "object") options = {};
    const { view, previousIndex, currentIndex, previousPage, currentPage } = options;
    const changed = view === "queue" && safeNumber(previousIndex, NaN) !== safeNumber(currentIndex, NaN);
    return {
      changed,
      page: Math.max(1, safeNumber(currentPage, 1)),
      requiresFullRender: changed && safeNumber(previousPage, NaN) !== safeNumber(currentPage, NaN),
      shouldScrollCurrent: changed,
    };
  }

  window.fnAudioQueuePresentation = { pageForQueueIndex, queuePresentationPlan };
})();
