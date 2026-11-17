(function (global) {
  "use strict";

  // 「上一首放完」到「下一首出声」的空档。
  //
  // P1-2（预热下一首）和 P2-1（安卓衔接）都靠这个数说话，但它在浏览器里从来没人
  // 量过——之前只能靠猜。这里只做两件事：收样本、算中位数与 p95，纯函数，可单测。
  const MAX_SAMPLES = 50;

  function push(samples, value, max) {
    const list = Array.isArray(samples) ? samples.slice() : [];
    const limit = Math.max(1, Number(max) || MAX_SAMPLES);
    // `Number(null)` 是 0：不显式挡掉，空白样本会被记成"零空档"，把中位数带偏。
    const ms = typeof value === "number"
      ? value
      : (typeof value === "string" && value.trim() ? Number(value) : NaN);
    if (!Number.isFinite(ms) || ms < 0) return list;
    list.push(Math.round(ms));
    return list.length > limit ? list.slice(list.length - limit) : list;
  }

  function percentile(sorted, ratio) {
    if (!sorted.length) return null;
    const index = Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * ratio)));
    return sorted[index];
  }

  function summarize(samples) {
    const list = (Array.isArray(samples) ? samples : [])
      .map(Number)
      .filter(value => Number.isFinite(value) && value >= 0)
      .sort((a, b) => a - b);
    if (!list.length) return { count: 0, median: null, p95: null, max: null };
    return {
      count: list.length,
      median: percentile(list, 0.5),
      p95: percentile(list, 0.95),
      max: list[list.length - 1],
    };
  }

  global.fnAudioGapStats = { MAX_SAMPLES, push, summarize };
})(typeof window !== "undefined" ? window : globalThis);
