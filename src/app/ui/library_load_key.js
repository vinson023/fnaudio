(function (global) {
  "use strict";

  function safeNumber(value, fallback = 0) {
    try {
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function safeText(value, fallback = "") {
    return typeof value === "string" ? value : fallback;
  }

  function safePage(value, fallback = 1) {
    const number = safeNumber(value, fallback);
    return Number.isInteger(number) && number >= 1 ? number : fallback;
  }

  function buildLibraryLoadKey(state, page, currentCreatorName, isCreatorAllTracks, currentQueryText) {
    const source = state && typeof state === "object" ? state : {};
    const numericPage = safePage(page, 1);
    const key = {
      view: safeText(source.view, "all") || "all",
      page: Math.max(1, numericPage),
      pageSize: safeNumber(source.pageSize),
      folderRoot: safeText(source.folderRoot),
      folderPath: safeText(source.folderPath),
      folderPage: safeNumber(source.folderPage),
      folderPageSize: safeNumber(source.folderPageSize),
      groupName: safeText(source.groupName),
      creator: typeof currentCreatorName === "function" ? safeText(currentCreatorName()) : "",
      creatorAllTracks: typeof isCreatorAllTracks === "function" ? Boolean(isCreatorAllTracks()) : false,
      sortKey: safeText(source.sortKey, "title") || "title",
      sortDir: safeText(source.sortDir, "asc") || "asc",
      search: typeof currentQueryText === "function" ? safeText(currentQueryText()) : "",
    };
    try {
      return JSON.stringify(key);
    } catch (_) {
      return "";
    }
  }

  global.fnAudioLibraryLoadKey = { buildLibraryLoadKey };
})(typeof window !== "undefined" ? window : globalThis);
