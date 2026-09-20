(function (root) {
  "use strict";

  const SORT_AFFECTING_FIELDS = new Set([
    "title", "artist", "album", "album_artist", "date", "genre", "track_no", "composer",
  ]);

  function safeText(value) {
    return typeof value === "string" ? value.trim().slice(0, 4096) : "";
  }

  function safeFields(value) {
    if (!Array.isArray(value)) return [];
    return value.map(safeText).filter(Boolean).slice(0, 32);
  }

  function sameListIdentity(expected, current) {
    if (!expected || typeof expected !== "object" || !current || typeof current !== "object") return false;
    return expected.requestSeq === current.requestSeq
      && expected.view === current.view
      && expected.page === current.page
      && expected.pageItems === current.pageItems;
  }

  function canPatchRow(options = {}) {
    const source = options && typeof options === "object" ? options : {};
    if (source.pagedTrackListing !== true || source.queueView === true) return false;
    if (source.groupRoot === true || source.folderView === true || source.albumDetail === true || source.creatorAllTracks === true) return false;
    if (safeText(source.search)) return false;
    const fields = safeFields(source.changedFields);
    if (!fields.length) return true;
    const sortKey = safeText(source.sortKey);
    return fields.every(field => !SORT_AFFECTING_FIELDS.has(field))
      || !SORT_AFFECTING_FIELDS.has(sortKey);
  }

  root.fnAudioMetadataRowPatchPolicy = Object.freeze({ canPatchRow, safeFields, sameListIdentity });
})(globalThis);
