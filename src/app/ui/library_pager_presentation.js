/* Pure pagination markup policy for library views. */
(function (global) {
  const MAX_PAGER_TOTAL = 100000000;
  const MAX_PAGER_PAGES = 1000000;
  function safeNumber(value, fallback) {
    if (typeof value === "boolean" || value == null) return fallback;
    try {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : fallback;
    } catch (_) { return fallback; }
  }
  function renderPager({ total = 0, page = 1, pages = 1, unit = "首" } = {}) {
    const safeTotal = Math.min(MAX_PAGER_TOTAL, Math.max(0, safeNumber(total, 0)));
    const safePages = Math.min(MAX_PAGER_PAGES, Math.max(1, Math.floor(safeNumber(pages, 1))));
    if (safePages <= 1) return "";
    const safePage = Math.min(Math.max(1, safeNumber(page, 1) || 1), safePages);
    const prevDisabled = safePage <= 1 ? "disabled" : "";
    const nextDisabled = safePage >= safePages ? "disabled" : "";
    const safeUnit = typeof unit === "string" && unit.length <= 8 ? unit : "首";
    return `<div class="pager-inner"><div class="pager-nav"><button class="pager-nav-button" type="button" data-page-go="1" title="首页" aria-label="首页" ${prevDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 12 12l6 6"/><path d="m11 6-5 6 6 6"/></svg></button><button class="pager-nav-button" type="button" data-page-step="-1" title="上一页" aria-label="上一页" ${prevDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg></button><span class="pager-page-summary" aria-label="当前页">第 ${safePage} / ${safePages} 页</span><button class="pager-nav-button" type="button" data-page-step="1" title="下一页" aria-label="下一页" ${nextDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button><button class="pager-nav-button" type="button" data-page-go="${safePages}" title="尾页" aria-label="尾页" ${nextDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 6 6-6 6"/><path d="m13 6 6 6-6 6"/></svg></button></div><div class="pager-status"><span>共 ${safeTotal} ${safeUnit}</span><button class="pager-refresh-button" type="button" data-refresh-library title="刷新音乐库" aria-label="刷新音乐库"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.4 9A7 7 0 0 0 6.2 6.8L4 9"/><path d="M5.6 15a7 7 0 0 0 12.2 2.2L20 15"/></svg></button></div></div>`;
  }
  global.fnAudioLibraryPagerPresentation = { renderPager };
})(globalThis);
