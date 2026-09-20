(function (global) {
  "use strict";
  const MAX_PAGE_OFFSETS = 8192;
  const MAX_PAGE_SIZE = 500;
  const MAX_NUMERIC_TEXT = 64;
  function safeNumber(value) {
    if (typeof value === "string") {
      if (value.length > MAX_NUMERIC_TEXT) return NaN;
    } else if (typeof value !== "number") return NaN;
    try {
      return Number(value);
    } catch (_) {
      return NaN;
    }
  }
  function normalizedPlan(total, pageSize, firstCount, maxItems) {
    const totalValue = safeNumber(total);
    const pageValue = safeNumber(pageSize);
    const firstValue = safeNumber(firstCount);
    const totalCount = Number.isFinite(totalValue) ? Math.max(0, totalValue) : 0;
    const size = Number.isFinite(pageValue) ? Math.max(1, Math.min(MAX_PAGE_SIZE, Math.floor(pageValue || 1))) : 1;
    const first = Number.isFinite(firstValue) ? Math.max(0, firstValue) : 0;
    const budgetValue = safeNumber(maxItems);
    const budget = Number.isFinite(budgetValue) ? Math.max(0, Math.min(200000, Math.floor(budgetValue))) : 200000;
    return { size, first, target: Math.min(totalCount, budget) };
  }
  function pageOffsetBatches(total, pageSize, firstCount, maxItems = 200000, batchSize = 32) {
    const plan = normalizedPlan(total, pageSize, firstCount, maxItems);
    const batchValue = safeNumber(batchSize);
    const size = Number.isFinite(batchValue) ? Math.max(1, Math.min(128, Math.floor(batchValue || 1))) : 32;
    return (function* () {
      if (!plan.first || plan.first >= plan.target) return;
      let batch = [];
      let count = 0;
      for (let offset = plan.size; offset < plan.target && count < MAX_PAGE_OFFSETS; offset += plan.size) {
        batch.push(offset);
        count += 1;
        if (batch.length >= size) {
          yield batch;
          batch = [];
        }
      }
      if (batch.length) yield batch;
    })();
  }
  function remainingPageOffsets(total, pageSize, firstCount, maxItems = 200000) {
    const offsets = [];
    for (const batch of pageOffsetBatches(total, pageSize, firstCount, maxItems, 128)) offsets.push(...batch);
    return offsets;
  }
  global.fnAudioLibraryPagePlan = { remainingPageOffsets, pageOffsetBatches };
})(typeof window !== "undefined" ? window : globalThis);
