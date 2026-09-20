/* Pure helpers for assembling ordered large-library page results. */
(function (root) {
  const MAX_MERGED_ITEMS = 200000;
  const MAX_NUMERIC_TEXT = 64;
  function safeTotal(total) {
    if (typeof total === "string") {
      if (total.length > MAX_NUMERIC_TEXT) return null;
    } else if (typeof total !== "number") return null;
    try {
      const value = Number(total);
      return Number.isFinite(value) && value >= 0 ? value : null;
    } catch (_) {
      return null;
    }
  }
  function mergePagedItems(firstItems, pageItems, total) {
    const result = Array.isArray(firstItems) ? firstItems.slice(0, MAX_MERGED_ITEMS) : [];
    const pages = Array.isArray(pageItems) ? pageItems : [];
    const totalCount = safeTotal(total);
    for (const page of pages) {
      if (!Array.isArray(page) || page.length === 0) break;
      for (const item of page) {
        if (result.length >= MAX_MERGED_ITEMS) return result;
        result.push(item);
      }
      if (totalCount !== null && result.length >= totalCount) {
        return result.slice(0, totalCount);
      }
    }
    return result;
  }
  function appendPageItems(result, page, total) {
    if (!Array.isArray(result)) result = [];
    if (!Array.isArray(page) || !page.length || result.length >= MAX_MERGED_ITEMS) return result;
    const totalCount = safeTotal(total);
    const remaining = Math.min(MAX_MERGED_ITEMS - result.length, totalCount === null ? MAX_MERGED_ITEMS : Math.max(0, totalCount - result.length));
    for (let index = 0; index < page.length && index < remaining; index += 1) result.push(page[index]);
    return result;
  }
  root.fnAudioLibraryPageMerge = { mergePagedItems, appendPageItems };
})(typeof window !== "undefined" ? window : globalThis);
