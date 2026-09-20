(function (global) {
  "use strict";

  // Only committed metadata that changed the visible projection affects the
  // library page. Pending/terminal queue churn is deliberately excluded so a
  // background job for an off-page item cannot reload rows or restart cover
  // decoding after the first paint.
  function safeCount(value) {
    if (typeof value === "number") return Number.isFinite(value) ? Math.max(0, Math.min(1000000000, Math.floor(value))) : 0;
    if (typeof value !== "string" || value.length > 24 || !/^\d+$/.test(value.trim())) return 0;
    const parsed = Number(value.trim());
    return Number.isSafeInteger(parsed) ? Math.max(0, Math.min(1000000000, parsed)) : 0;
  }
  function safeText(value) {
    return typeof value === "string" ? value.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 180) : "";
  }
  function boundedMatchSignature(matches) {
    const keys = [];
    try {
      for (const key in matches) {
        let isOwn = false;
        try {
          isOwn = Object.prototype.hasOwnProperty.call(matches, key);
        } catch (_) {
          continue;
        }
        if (!isOwn) continue;

        let insertAt = keys.length;
        while (insertAt > 0 && keys[insertAt - 1] > key) insertAt -= 1;
        if (keys.length >= 64 && insertAt === keys.length) continue;
        keys.splice(insertAt, 0, key);
        if (keys.length > 64) keys.pop();
      }
    } catch (_) {
      // A hostile proxy can throw while enumerating; retain the safe prefix.
    }
    return keys.map(key => {
      let value;
      try {
        value = matches[key];
      } catch (_) {
        value = undefined;
      }
      return `${safeText(key)}:${safeCount(value)}`;
    }).join(",");
  }
  function signature(data) {
    const source = data && typeof data === "object" ? data : {};
    const jobs = source.jobs && typeof source.jobs === "object" ? source.jobs : {};
    const matches = source.track_matches && typeof source.track_matches === "object" ? source.track_matches : {};
    const terminalJobs = ["done", "failed", "no_match", "skipped"].reduce(
      (sum, key) => sum + safeCount(jobs[key]), 0,
    );
    const terminalMatches = boundedMatchSignature(matches);
    return [
      safeCount(source.lyrics),
      terminalJobs,
      terminalMatches,
      safeCount(source.tag_written),
      safeCount(source.metadata_projection_revision),
      safeText(source.last_error),
    ].join("|");
  }

  global.fnAudioMetadataProjectionPolicy = { signature };
})(typeof window !== "undefined" ? window : globalThis);
