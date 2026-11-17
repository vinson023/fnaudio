(function (global) {
  "use strict";

  // Both defaults are 50 now (R569). The old 96/60 split came from keeping the
  // first desktop paint below a 120-row burst, which made the song list disagree
  // with folder browsing (100) for no reason a user could see. 50 is also the
  // cheapest first paint, and the setting below raises it per installation.
  const DESKTOP_DEFAULT = 50;
  const MOBILE_DEFAULT = 50;
  const MAX_PAGE_SIZE = 500;
  // What the 高级 settings select offers; `normalizePageSize` snaps anything else
  // (an older stored value, a hand-edited localStorage) onto the nearest one.
  const PAGE_SIZE_OPTIONS = [50, 100, 150, 200, 500];

  function defaultPageSize(viewport) {
    try {
      return viewport?.matchMedia?.("(max-width: 760px)")?.matches
        ? MOBILE_DEFAULT
        : DESKTOP_DEFAULT;
    } catch (_) {
      return DESKTOP_DEFAULT;
    }
  }

  // Any value in 1..500 is honoured: the select only offers five steps, but a
  // caller (and the end-to-end fixture) may legitimately ask for 2. Snapping to
  // the nearest step here silently rewrote those requests to 50.
  function normalizePageSize(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return DESKTOP_DEFAULT;
    return Math.min(MAX_PAGE_SIZE, Math.max(1, Math.floor(numeric)));
  }

  // Only for the settings select: which step should appear chosen.
  function nearestOption(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return PAGE_SIZE_OPTIONS[0];
    let best = PAGE_SIZE_OPTIONS[0];
    for (const option of PAGE_SIZE_OPTIONS) {
      if (Math.abs(option - numeric) < Math.abs(best - numeric)) best = option;
    }
    return best;
  }

  function resolvePageSize(storage, viewport) {
    const fallback = defaultPageSize(viewport);
    let stored = "";
    try { stored = storage?.getItem?.("fnaudio.pageSize") || ""; } catch (_) {}
    if (!stored) return fallback;
    return normalizePageSize(stored);
  }

  global.fnAudioLibraryPageSizePolicy = {
    DESKTOP_DEFAULT, MOBILE_DEFAULT, MAX_PAGE_SIZE, PAGE_SIZE_OPTIONS,
    defaultPageSize, nearestOption, normalizePageSize, resolvePageSize,
  };
})(typeof window !== "undefined" ? window : globalThis);
