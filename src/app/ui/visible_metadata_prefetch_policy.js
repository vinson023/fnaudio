(function (global) {
  "use strict";
  const DEFAULT_LIMIT = 6;
  const MAX_LIMIT = 12;
  const DEFAULT_MAX_ATTEMPTS = 12;
  const DEFAULT_MAX_REARMS = 2;

  function boundedLimit(value, fallback, maximum) {
    if (typeof value === "boolean" || (typeof value !== "number" && typeof value !== "string")) return fallback;
    // A blank string is an unset value, not zero. Number("") and Number(" ")
    // both coerce to 0, which would silently switch a bounded lane off (or on)
    // because a bridge handed over an empty field instead of omitting it.
    if (typeof value === "string" && !value.trim()) return fallback;
    try {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return fallback;
      return Math.max(0, Math.min(maximum, Math.floor(numeric)));
    } catch (_) {
      return fallback;
    }
  }

  function hasText(item, key) {
    try {
      return typeof item?.[key] === "string" && item[key].trim().length > 0;
    } catch (_) {
      return false;
    }
  }

  function hasValidArtworkId(item) {
    try {
      const value = item?.metadata_artwork_id;
      return typeof value === "string" && /^[a-f0-9]{64}$/i.test(value.trim());
    } catch (_) {
      return false;
    }
  }

  // Scanner placeholders are presentation text, not authoritative metadata.
  // Treat them as missing so a row such as “未知专辑” can still enter the
  // bounded provider lane (especially when its artwork is already cached).
  const PLACEHOLDERS = new Set([
    "", "未分类", "未知歌曲", "未知专辑", "未知歌手", "未知艺术家", "未知作曲者",
    "unknown song", "unknown album", "unknown artist", "unknown composer",
  ]);
  function hasMeaningfulText(item, key) {
    if (!hasText(item, key)) return false;
    try { return !PLACEHOLDERS.has(item[key].trim().toLowerCase()); } catch (_) { return false; }
  }

  function needsMetadata(item) {
    if (!item || typeof item !== "object" || Array.isArray(item)) return false;
    try {
      const hasCover = hasText(item, "cover_url") || hasText(item, "cover_thumbnail_url") || hasValidArtworkId(item);
      return !hasMeaningfulText(item, "title") || !hasCover
        || !hasMeaningfulText(item, "album") || !hasMeaningfulText(item, "artist");
    } catch (_) {
      return true;
    }
  }

  function stableId(item) {
    try {
      const value = item?.id;
      if (typeof value !== "string" && typeof value !== "number") return "";
      const id = String(value).trim();
      return id.length <= 256 ? id : "";
    } catch (_) {
      return "";
    }
  }

  function selectCandidates(items, limit = DEFAULT_LIMIT, excludedId = "") {
    const rows = Array.isArray(items) ? items : [];
    const bounded = boundedLimit(limit, DEFAULT_LIMIT, MAX_LIMIT);
    const excluded = stableId({ id: excludedId });
    const seen = new Set();
    const result = [];
    for (const item of rows) {
      // The budget is spent before a row is taken, so a limit of zero selects
      // nothing instead of one: checking after the push handed back a candidate
      // even when the caller asked for none.
      if (result.length >= bounded) break;
      if (!item) continue;
      const id = stableId(item);
      if (!id) continue;
      if (excluded && id === excluded) continue;
      if (seen.has(id)) continue;
      seen.add(id);
      // A title-only or filename-derived row still needs provider lookup when
      // its canonical title is absent.  Previously rows with artist/album but
      // no title were skipped, making metadata appear unavailable even though
      // the priority lane could resolve them.
      if (needsMetadata(item)) result.push(item);
    }
    return result;
  }

  function shouldRetry(payload, attempt, maxAttempts = DEFAULT_MAX_ATTEMPTS) {
    const boundedAttempts = boundedLimit(maxAttempts, DEFAULT_MAX_ATTEMPTS, DEFAULT_MAX_ATTEMPTS);
    if (typeof attempt !== "number" || !Number.isFinite(attempt) || attempt >= boundedAttempts - 1) return false;
    // A transient HTTP failure, proxy disconnect, or malformed JSON is
    // represented by a null payload in the bounded visible-row lane. Treat
    // it as retryable instead of abandoning metadata after the first request;
    // the attempt cap and page AbortController still keep this finite.
    if (!payload) return true;
    let status = "";
    try { status = typeof payload.status === "string" ? payload.status.toLowerCase() : ""; } catch (_) {}
    // A few host bridges answer HTTP 200 with only a generic `{ok:true}`
    // envelope while the metadata lane is still warming or the payload was
    // stripped by a proxy.  It is not a successful empty match: keep the
    // bounded recovery window alive instead of permanently consuming the
    // page dedupe key.
    if (payload.ok !== false && !status && !payload.pending
      && !payload.retryable && !payload.best && !Array.isArray(payload.candidates)
      && !payload.image_url && !payload.lyrics) return true;
    return payload.pending === true || status === "pending" || payload.retryable === true;
  }

  // A terminal provider result is not proof that metadata is permanently
  // unavailable.  Release the page-level dedupe key so a later status change
  // (worker recovery, cooldown expiry, or a fresh library projection) can
  // give the row another bounded opportunity.  Pending work keeps its key so
  // the current poll window remains the only owner.
  function shouldReleaseKey(payload) {
    if (!payload || typeof payload !== "object") return true;
    let status = "";
    try { status = typeof payload.status === "string" ? payload.status.toLowerCase() : ""; } catch (_) {}
    if (status === "failed" || status === "no_match" || payload.retryable === true) return true;
    // Release malformed/generic success envelopes as well. They are not
    // authoritative negative matches and must be eligible on a later page or
    // worker recovery cycle.
    return payload.ok !== false && !status && !payload.pending
      && !payload.best && !Array.isArray(payload.candidates)
      && !payload.image_url && !payload.lyrics;
  }

  // A provider job may still be alive after the visible lane has spent its
  // bounded polling budget.  Keep the row deduplicated while it cools down,
  // then allow only a couple of quiet, page-owned re-arms.  Without this,
  // `pending` could retain the key forever when a worker recovered without a
  // visible metadata-projection revision.  This deliberately does *not*
  // re-arm failed/no_match responses: those use the regular terminal retry
  // path and must not turn a first-page hint into background crawling.
  function shouldRearmPending(payload, attempts, rearms, maxAttempts = DEFAULT_MAX_ATTEMPTS, maxRearms = DEFAULT_MAX_REARMS) {
    const boundedAttempts = boundedLimit(maxAttempts, DEFAULT_MAX_ATTEMPTS, DEFAULT_MAX_ATTEMPTS);
    const boundedRearms = boundedLimit(maxRearms, DEFAULT_MAX_REARMS, DEFAULT_MAX_REARMS);
    if (typeof attempts !== "number" || !Number.isFinite(attempts) || attempts < boundedAttempts) return false;
    if (typeof rearms !== "number" || !Number.isFinite(rearms) || rearms >= boundedRearms) return false;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return false;
    let status = "";
    try { status = typeof payload.status === "string" ? payload.status.toLowerCase() : ""; } catch (_) {}
    if (status === "failed" || status === "no_match") return false;
    // Preserve the generic host-envelope recovery behavior used by
    // shouldRetry(): a stripped but otherwise successful 200 response is
    // still an indeterminate pending result, not a confirmed empty match.
    const genericEnvelope = payload.ok !== false && !status && !payload.pending
      && !payload.retryable && !payload.best && !Array.isArray(payload.candidates)
      && !payload.image_url && !payload.lyrics;
    return payload.pending === true || status === "pending" || payload.retryable === true || genericEnvelope;
  }

  function pendingRearmDelayMs(rearms) {
    const count = boundedLimit(rearms, 1, DEFAULT_MAX_REARMS);
    // 3.5s then 7s: long enough to let the provider/worker progress, short
    // enough that an explicit visible row does not look permanently broken.
    return Math.min(7000, Math.max(3500, count * 3500));
  }

  // Status polling may publish a revision while this page's lane is still
  // queued or running. Reuse only that exact page/request lane.
  function shouldReuseActiveLane(requestSeq, activeRequestSeq, sameItems, hasPendingWork) {
    return hasPendingWork === true && sameItems === true
      && typeof requestSeq === "number" && Number.isFinite(requestSeq)
      && requestSeq === activeRequestSeq;
  }

  // The playback-owned lane only excludes the current row while it has an
  // actual request or bounded retry timer. Historical attempt counters are
  // diagnostic state, not ownership: treating them as active can strand a
  // settled but still-incomplete current row outside the visible recovery
  // lane for the rest of the page.
  function ownsCurrentTrackLane(trackId, activeTrackId, controller, timer) {
    return Boolean(trackId && trackId === activeTrackId && (controller || timer));
  }

  global.fnAudioVisibleMetadataPrefetchPolicy = {
    DEFAULT_MAX_ATTEMPTS, DEFAULT_MAX_REARMS, needsMetadata, selectCandidates, shouldRetry,
    shouldReleaseKey, shouldRearmPending, pendingRearmDelayMs, shouldReuseActiveLane, ownsCurrentTrackLane,
  };
})(typeof window !== "undefined" ? window : globalThis);
