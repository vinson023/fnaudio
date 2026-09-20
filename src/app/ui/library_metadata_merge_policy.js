(function (global) {
  "use strict";

  const INHERIT_FIELDS = [
    "title", "artist", "album", "cover_url", "cover_thumbnail_url",
    "metadata_artwork_id", "lyrics", "album_artist", "composer", "genre",
    "date", "track_no",
  ];

  function merge(items, previousItems, itemCache) {
    const previous = new Map((Array.isArray(previousItems) ? previousItems : [])
      .map(item => [String(item?.id || ""), item]));
    return (Array.isArray(items) ? items : []).map(item => {
      if (!item || !item.id) return item;
      const id = String(item.id);
      const cached = itemCache && typeof itemCache.get === "function" ? itemCache.get(id) : undefined;
      const old = previous.get(id) || cached;
      if (!old) return item;
      const merged = { ...item };
      INHERIT_FIELDS.forEach(field => {
        if ((merged[field] == null || String(merged[field]).trim() === "")
          && old[field] != null && String(old[field]).trim() !== "") merged[field] = old[field];
      });
      const mergedSource = merged.metadata_source;
      const hasMergedSource = mergedSource && typeof mergedSource === "object"
        ? Object.keys(mergedSource).length > 0
        : Boolean(mergedSource);
      if (!hasMergedSource && old.metadata_source) merged.metadata_source = old.metadata_source;
      return merged;
    });
  }

  global.fnAudioLibraryMetadataMergePolicy = { merge };
})(typeof window !== "undefined" ? window : globalThis);
