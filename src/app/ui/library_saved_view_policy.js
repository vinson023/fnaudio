(function (global) {
  "use strict";

  // A saved view is the library's filter, nothing else: no page, no scroll
  // position, no queue. That is what makes "最近添加的 DSD" one click instead of
  // five. The server validates and stores the record
  // (library_saved_view_policy.py); this module only captures the current filter
  // and projects a stored one back into the query parameters /api/library takes.
  const MAX_NAME_CHARS = 48;
  const MAX_VIEWS = 24;
  const SORT_KEYS = Object.freeze(["title", "artist", "album", "format", "added", "track_no"]);
  const VIEW_NAMES = Object.freeze([
    "all", "dsd", "recent", "random100", "favorites", "queue",
    "folders", "albums", "artists", "composers", "genres",
  ]);
  const SORT_LABELS = Object.freeze({
    title: "按标题", artist: "按歌手", album: "按专辑",
    format: "按格式", added: "按加入时间", track_no: "按歌曲序号",
  });

  function text(value, limit) {
    return typeof value === "string" ? value.trim().slice(0, limit) : "";
  }

  function isView(value) {
    return VIEW_NAMES.indexOf(String(value || "")) >= 0;
  }

  // The search box is the one filter that lives in the DOM rather than in state,
  // so the caller passes its text in and this stays pure.
  function capture(state, searchText) {
    const source = state || {};
    const view = isView(source.view) ? String(source.view) : "all";
    const folder = text(source.folderPath, 4096);
    return {
      view,
      group: text(source.groupName, 256),
      album: text(source.albumName, 256),
      folder,
      root: folder ? text(source.folderRoot, 4096) : "",
      search: text(searchText, 512),
      sort: SORT_KEYS.indexOf(String(source.sortKey || "")) >= 0 ? String(source.sortKey) : "title",
      dir: String(source.sortDir || "") === "desc" ? "desc" : "asc",
      subtree: source.subtree === true,
    };
  }

  function toQueryParams(criteria) {
    const source = criteria || {};
    const params = {
      view: isView(source.view) ? String(source.view) : "all",
      sort: SORT_KEYS.indexOf(String(source.sort || "")) >= 0 ? String(source.sort) : "title",
      dir: String(source.dir || "") === "desc" ? "desc" : "asc",
    };
    ["group", "album", "folder", "root", "search"].forEach(key => {
      const value = text(source[key], key === "folder" || key === "root" ? 4096 : 512);
      if (value) params[key] = value;
    });
    if (source.subtree === true) params.subtree = "1";
    return params;
  }

  function validateName(value) {
    const name = text(value, MAX_NAME_CHARS);
    return name || "";
  }

  // One line, because it sits under a 30-character sidebar row.
  function summary(criteria) {
    const source = criteria || {};
    const parts = [];
    if (source.search) parts.push(`搜索：${text(source.search, 32)}`);
    if (source.group) parts.push(text(source.group, 24));
    if (source.album) parts.push(text(source.album, 24));
    if (source.folder) parts.push(text(source.folder, 24));
    parts.push(SORT_LABELS[source.sort] || SORT_LABELS.title);
    if (source.dir === "desc") parts.push("降序");
    return parts.join(" · ");
  }

  function merge(list, view) {
    const items = Array.isArray(list) ? list.slice() : [];
    if (!view || !view.id) return items;
    const next = items.filter(item => item && item.id !== view.id);
    next.unshift(view);
    return next.slice(0, MAX_VIEWS);
  }

  function remove(list, id) {
    const key = String(id || "");
    return (Array.isArray(list) ? list : []).filter(item => item && item.id !== key);
  }

  global.fnAudioLibrarySavedViewPolicy = Object.freeze({
    MAX_NAME_CHARS, MAX_VIEWS, SORT_KEYS, VIEW_NAMES,
    capture, isView, merge, remove, summary, toQueryParams, validateName,
  });
})(typeof window !== "undefined" ? window : globalThis);
