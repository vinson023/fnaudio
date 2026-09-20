(function (global) {
  "use strict";

  // Keep the first desktop paint below the old 120-row DOM/JSON burst. User
  // preferences still win, so this only affects new sessions.
  const DESKTOP_DEFAULT = 96;
  const MOBILE_DEFAULT = 60;
  const MAX_PAGE_SIZE = 500;

  function defaultPageSize(viewport) {
    try {
      return viewport?.matchMedia?.("(max-width: 760px)")?.matches
        ? MOBILE_DEFAULT
        : DESKTOP_DEFAULT;
    } catch (_) {
      return DESKTOP_DEFAULT;
    }
  }

  function resolvePageSize(storage, viewport) {
    const fallback = defaultPageSize(viewport);
    let stored = "";
    try { stored = storage?.getItem?.("fnaudio.pageSize") || ""; } catch (_) {}
    const numeric = Number(stored || fallback);
    if (!Number.isFinite(numeric)) return fallback;
    return Math.min(MAX_PAGE_SIZE, Math.max(1, Math.floor(numeric) || fallback));
  }

  global.fnAudioLibraryPageSizePolicy = {
    DESKTOP_DEFAULT, MOBILE_DEFAULT, MAX_PAGE_SIZE, defaultPageSize, resolvePageSize,
  };
})(typeof window !== "undefined" ? window : globalThis);
