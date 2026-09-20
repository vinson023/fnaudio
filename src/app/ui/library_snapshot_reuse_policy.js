(function (global) {
  "use strict";

  // A restored first-page snapshot is useful only if the later authoritative
  // page will paint exactly the same visible rows. Keep the comparison small
  // and primitive-only: this is a fast guard before list HTML is regenerated,
  // not a general-purpose object equality helper.
  const MAX_ROWS = 500;
  const MAX_SIGNATURE_CHARS = 2048;

  function normalizedSignatures(value) {
    if (!Array.isArray(value) || value.length > MAX_ROWS) return null;
    const result = [];
    for (const entry of value) {
      if (typeof entry !== "string" || entry.length > MAX_SIGNATURE_CHARS) return null;
      result.push(entry);
    }
    return result;
  }

  function canReuseMarkup(previous, next) {
    const left = normalizedSignatures(previous);
    const right = normalizedSignatures(next);
    if (!left || !right || left.length === 0 || left.length !== right.length) return false;
    for (let index = 0; index < left.length; index += 1) {
      if (left[index] !== right[index]) return false;
    }
    return true;
  }

  global.fnAudioLibrarySnapshotReusePolicy = {
    MAX_ROWS,
    MAX_SIGNATURE_CHARS,
    canReuseMarkup,
  };
})(typeof window !== "undefined" ? window : globalThis);
