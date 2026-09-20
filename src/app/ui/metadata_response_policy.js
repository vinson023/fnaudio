(function (global) {
  "use strict";

  function boundedLowerText(value, limit = 64) {
    if (typeof value !== "string") return "";
    return value.trim().slice(0, limit).toLowerCase();
  }

  const ENVELOPE_KEYS = ["data", "result", "payload", "metadata"];
  const METADATA_PROJECTION_KEYS = ["status", "best", "candidates", "image_url", "lyrics", "pending", "retryable"];

  function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function hasRejectedOk(value) {
    if (!isRecord(value)) return false;
    try {
      return Object.prototype.hasOwnProperty.call(value, "ok") && value.ok !== true;
    } catch (_) {
      return true;
    }
  }

  // Do not unwrap a response that is already a usable metadata projection.
  // In particular, a provider result can legitimately contain a `metadata`
  // property of its own; treating every object as a transport envelope would
  // lose its top-level status/pending semantics.
  function hasMetadataProjection(value) {
    if (!isRecord(value)) return false;
    for (const key of METADATA_PROJECTION_KEYS) {
      try {
        if (Object.prototype.hasOwnProperty.call(value, key)) return true;
      } catch (_) {
        return false;
      }
    }
    return false;
  }

  function nestedEnvelope(value) {
    if (!isRecord(value)) return null;
    for (const key of ENVELOPE_KEYS) {
      try {
        const nested = value[key];
        if (isRecord(nested)) return nested;
      } catch (_) {
        // A broken bridge getter must not discard the outer response or stop
        // us from considering another, safe transport wrapper.
      }
    }
    return null;
  }

  function unwrap(value, maxDepth) {
    let payload = value;
    // Web, native bridges and reverse proxies do not consistently use the
    // same transport key.  Recognize only this small whitelist and stop as
    // soon as a real metadata projection is reached.  The bounded depth keeps
    // malformed/cyclic host objects from becoming an unbounded traversal.
    const depthLimit = Number.isFinite(maxDepth) ? Math.max(0, Math.min(4, Math.floor(maxDepth))) : 4;
    for (let depth = 0; depth < depthLimit; depth += 1) {
      // A host/proxy envelope can wrap a useful-looking stale payload even
      // after the request itself failed. Do not unwrap away an explicit
      // failure marker; clients need one stable boolean result contract.
      if (hasRejectedOk(payload)) return { ok: false };
      if (!isRecord(payload) || hasMetadataProjection(payload)) break;
      const nested = nestedEnvelope(payload);
      if (!nested) break;
      payload = nested;
    }
    return isRecord(payload) ? payload : {};
  }

  function unwrapTransport(value, maxDepth) {
    let payload = value;
    const depthLimit = Number.isFinite(maxDepth) ? Math.max(0, Math.min(4, Math.floor(maxDepth))) : 4;
    for (let depth = 0; depth < depthLimit; depth += 1) {
      if (!isRecord(payload)) break;
      const nested = nestedEnvelope(payload);
      if (!nested) break;
      payload = nested;
    }
    return isRecord(payload) ? payload : {};
  }

  function isRecoverableFilenameFallback(payload, candidate) {
    let status = "";
    let source = "";
    try {
      status = boundedLowerText(payload && typeof payload === "object" ? payload.status : "");
    } catch (_) {}
    try {
      source = boundedLowerText(candidate && typeof candidate === "object" ? candidate.source : "");
    } catch (_) {}
    return (status === "failed" || status === "no_match") && source === "filename";
  }

  function isTransientHttpStatus(status) {
    if (typeof status !== "number" || !Number.isFinite(status)) return false;
    return status === 408 || status === 425 || status === 429 || status >= 500;
  }

  global.fnAudioMetadataResponsePolicy = {
    unwrap, unwrapTransport, isRecoverableFilenameFallback, isTransientHttpStatus,
  };
})(typeof window !== "undefined" ? window : globalThis);
