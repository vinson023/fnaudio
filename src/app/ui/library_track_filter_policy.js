(function (global) {
  "use strict";

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function safeMatches(matches, item, search) {
    if (!search) return true;
    if (typeof matches !== "function") return false;
    try { return Boolean(matches(item, search)); } catch (_) { return false; }
  }

  function selectTracks(options = {}) {
    const source = options && typeof options === "object" ? options : {};
    if (source.pagedTrackListing) return safeArray(source.pageItems);

    let list = safeArray(source.items);
    const view = typeof source.view === "string" ? source.view : "";
    const groupKey = typeof source.groupKey === "string" ? source.groupKey : "";
    const groupName = typeof source.groupName === "string" ? source.groupName : "";
    if (groupKey && groupName) {
      list = list.filter(item => {
        try { return (item?.[groupKey] || "未分类") === groupName; } catch (_) { return false; }
      });
    } else if (view === "dsd") {
      list = list.filter(item => {
        try { return item?.is_dsd === true; } catch (_) { return false; }
      });
    } else if (view === "queue") {
      list = safeArray(source.queue);
    } else if (view === "random100") {
      list = safeArray(source.random100);
    } else if (view === "recent") {
      list = safeArray(source.recent);
    } else if (view === "favorites") {
      list = safeArray(source.favorites);
    } else if (view === "playlist") {
      list = safeArray(source.playlist);
    }

    const search = typeof source.search === "string" ? source.search.toLowerCase() : "";
    if (search) list = list.filter(item => safeMatches(source.matches, item, search));
    if (typeof source.sort === "function") {
      try { return source.sort(list); } catch (_) { /* return a stable copy below */ }
    }
    return list.slice();
  }

  global.fnAudioLibraryTrackFilterPolicy = { selectTracks };
})(typeof window !== "undefined" ? window : globalThis);
