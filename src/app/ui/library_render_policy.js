(function (global) {
  "use strict";

  const MAX_RENDER_ROWS = 500;
  function boundedRows(value, limit = MAX_RENDER_ROWS) {
    if (!Array.isArray(value)) return [];
    let max = MAX_RENDER_ROWS;
    try {
      if (typeof limit === "number" && Number.isFinite(limit)) max = Math.max(0, Math.min(MAX_RENDER_ROWS, Math.floor(limit)));
    } catch (_) { /* retain the safe default */ }
    try { return value.slice(0, max); } catch (_) { return []; }
  }

  function boundedTrackRows(value, limit = MAX_RENDER_ROWS) {
    if (!Array.isArray(value)) return [];
    let max = MAX_RENDER_ROWS;
    try {
      if (typeof limit === "number" && Number.isFinite(limit)) max = Math.max(0, Math.min(MAX_RENDER_ROWS, Math.floor(limit)));
    } catch (_) { /* retain the safe default */ }
    const result = [];
    // Keep the scan bounded, but do not let malformed early snapshot rows
    // consume slots that valid later rows could have used.
    for (let index = 0; index < value.length && index < MAX_RENDER_ROWS && result.length < max; index += 1) {
      const item = value[index];
      if (!item || typeof item !== "object" || Array.isArray(item)) continue;
      try {
        if (typeof item.id === "string" && item.id.trim().length > 0) result.push(item);
      } catch (_) { /* ignore one malformed row */ }
    }
    return result;
  }

  function shouldDeferListCommit(options) {
    const source = options && typeof options === "object" ? options : {};
    return source.libraryLoading === true
      && source.hasVisiblePresentation === true
      && source.hasRenderedMarkup === true
      && source.listLength === 0;
  }

  function hasVisiblePresentation(snapshot) {
    const source = snapshot && typeof snapshot === "object" ? snapshot : {};
    const positive = value => typeof value === "number" && Number.isFinite(value) && value > 0;
    return source.librarySnapshotHit === true
      || positive(source.libraryLoaded)
      || positive(source.pageItemsLength)
      || positive(source.groupRowsLength)
      || positive(source.folderRowsLength)
      || positive(source.folderRootRowsLength);
  }

  global.fnAudioLibraryRenderPolicy = { MAX_RENDER_ROWS, boundedRows, boundedTrackRows, hasVisiblePresentation, shouldDeferListCommit };
})(typeof window !== "undefined" ? window : globalThis);
