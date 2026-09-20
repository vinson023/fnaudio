(function (global) {
  "use strict";

  const MAX_SEARCH_CHARS = 4096;

  function text(value, max = 512) {
    if (typeof value !== "string") return "";
    return value.trim().slice(0, max);
  }

  function numberText(value, fallback) {
    try {
      const number = Number(value);
      return Number.isFinite(number) ? String(number) : String(fallback);
    } catch (_) {
      return String(fallback);
    }
  }

  function safeNumber(value, fallback) {
    try {
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function safePageNumber(value, fallback = 1) {
    const number = safeNumber(value, fallback);
    return Number.isInteger(number) && number >= 1 ? number : fallback;
  }

  function buildLibraryQueryParams(options) {
    const source = options && typeof options === "object" ? options : {};
    const params = new URLSearchParams();
    const page = safePageNumber(source.page, 1);
    const pageSize = Math.max(1, safeNumber(source.pageSize, 1) || 1);
    const view = text(source.view);
    params.set("paged", "1");
    params.set("limit", numberText(pageSize, 1));
    params.set("offset", numberText((page - 1) * pageSize, 0));
    params.set("view", view);
    params.set("sort", text(source.sortKey, 128) || "title");
    params.set("dir", text(source.sortDir, 16) || "asc");
    const search = text(source.search, MAX_SEARCH_CHARS);
    if (search) params.set("search", search);
    if (view === "folders" && text(source.folderRoot, MAX_SEARCH_CHARS)) {
      params.set("root", text(source.folderRoot, MAX_SEARCH_CHARS));
    }
    if (view === "folders" && text(source.folderPath, MAX_SEARCH_CHARS)) {
      params.set("folder", text(source.folderPath, MAX_SEARCH_CHARS));
    }
    const creatorName = text(source.creatorName, MAX_SEARCH_CHARS);
    const groupName = text(source.groupName, MAX_SEARCH_CHARS);
    if (source.creatorView && creatorName) {
      params.set("group", creatorName);
      if (groupName) params.set("album", groupName);
    } else if (source.groupView && groupName) {
      params.set("group", groupName);
    }
    if (source.playlistView) params.set("view", view);
    return params;
  }

  global.fnAudioLibraryQueryParams = { buildLibraryQueryParams, MAX_SEARCH_CHARS };
})(typeof window !== "undefined" ? window : globalThis);
