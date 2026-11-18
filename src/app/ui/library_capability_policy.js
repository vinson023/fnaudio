(function (global) {
  "use strict";

  // Audio Station gates features on each endpoint's maxVersion, so an old NAS
  // loses a button instead of erroring. fnAudio ships one bundle for both sides,
  // which used to mean the UI could not know that this particular SQLite build
  // lacks FTS5, or that the server does not have saved views yet.
  //
  // The server now reports what it can do (library_capability_policy.py, surfaced
  // as status.capabilities). This module is the only place the UI reads it, and
  // its defaults are deliberately the *old* behaviour: a missing block means
  // "no field syntax, no saved views", never "assume yes".
  function object(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function features(status) {
    const capabilities = object(object(status).capabilities);
    const search = object(capabilities.search);
    const saved = object(capabilities.saved_views);
    const fields = Array.isArray(search.fields)
      ? search.fields.filter(field => typeof field === "string" && field)
      : [];
    const minChars = Number(search.min_chars);
    return {
      savedViews: {
        enabled: saved.enabled === true,
        limit: Number.isFinite(Number(saved.limit)) && Number(saved.limit) > 0 ? Math.floor(Number(saved.limit)) : 0,
      },
      search: {
        mode: search.mode === "fts5-trigram" ? "fts5-trigram" : "like",
        fieldSyntax: search.field_syntax === true && fields.length > 0,
        fields,
        minChars: Number.isFinite(minChars) && minChars > 0 ? Math.floor(minChars) : 0,
      },
      sortKeys: Array.isArray(capabilities.sort && capabilities.sort.keys)
        ? capabilities.sort.keys.filter(key => typeof key === "string")
        : [],
      views: Array.isArray(capabilities.views) ? capabilities.views.filter(view => typeof view === "string") : [],
      formats: Array.isArray(capabilities.formats) ? capabilities.formats.filter(item => typeof item === "string") : [],
      version: Number(capabilities.version) || 0,
    };
  }

  function supportsField(capabilityFeatures, field) {
    const search = object(capabilityFeatures).search;
    if (!search || search.fieldSyntax !== true) return false;
    if (field === undefined) return true;
    return Array.isArray(search.fields) && search.fields.indexOf(String(field)) >= 0;
  }

  // Keep the placeholder short. "搜索音乐，可用 artist:歌手 限定字段" was cut off
  // mid-word ("可用 artis") in the library toolbar, so the box now only says what
  // it searches; the syntax hint moved to the tooltip (see searchHint).
  function searchPlaceholder() {
    return "搜索音乐";
  }

  // Only promise the syntax the server will actually honour.
  function searchHint(capabilityFeatures) {
    return supportsField(capabilityFeatures, "artist")
      ? "搜索音乐，可用 artist:歌手 限定字段"
      : "搜索音乐";
  }

  global.fnAudioLibraryCapabilityPolicy = Object.freeze({
    features, searchPlaceholder, searchHint, supportsField,
  });
})(typeof window !== "undefined" ? window : globalThis);
