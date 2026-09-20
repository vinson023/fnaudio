(function (global) {
  "use strict";

  const MAX_COLUMNS = 16;

  function safeText(value, limit = 4096) {
    if (typeof value !== "string" && typeof value !== "number") return "";
    const text = String(value);
    return text.length > limit ? text.slice(0, limit) : text;
  }

  function safeIndex(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) return 0;
    return Math.max(0, Math.min(1000000, Math.floor(value)));
  }

  // The server page and a locally restored snapshot may represent the same
  // visible cell with different raw JSON types (for example `180` versus
  // `"180"`).  Build the reconciliation key from presentation values only,
  // so that transport-only differences cannot replace decoded cover nodes.
  function signature(input) {
    const source = input && typeof input === "object" ? input : {};
    const columns = Array.isArray(source.columns) ? source.columns.slice(0, MAX_COLUMNS) : [];
    const values = source.values && typeof source.values === "object" ? source.values : {};
    const cells = columns.map(key => {
      const name = safeText(key, 64);
      if (name === "title") return [name, safeText(source.title), safeText(source.artist), safeText(source.album)];
      return [name, safeText(values[name] || "—"), name === "format" && source.isDsd === true ? 1 : 0];
    });
    return JSON.stringify([
      safeIndex(source.index),
      safeText(source.cover),
      cells,
    ]);
  }

  global.fnAudioLibraryRowSignaturePolicy = { signature };
})(typeof window !== "undefined" ? window : globalThis);
