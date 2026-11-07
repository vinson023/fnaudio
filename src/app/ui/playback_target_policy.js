(function (root) {
  "use strict";
  function targetText(target) { return typeof target === "string" ? target : ""; }
  function isRemote(target) { const value = targetText(target); return Boolean(value) && value !== "local"; }
  function isDac(target) { return targetText(target).startsWith("dac:"); }
  // The server registers its local ALSA output under the bare key "mpd", while
  // `/api/playback/targets` publishes the very same DAC as "mpd:<stable id>".
  // A persisted session keeps whichever spelling the last writer used, so both
  // name one device: treating the bare key as "not mpd" made a paused USB DAC
  // look like a switched-off target after a reload.
  function isMpd(target) { const value = targetText(target); return value === "mpd" || value.startsWith("mpd:"); }
  function normalize(target) { const value = targetText(target); return value || "local"; }
  // Same audible output, possibly written two ways. Only the bare registry key
  // aliases a published DAC id; two different stable ids are two outputs, so an
  // unknown id never collapses onto a different device.
  function sameDevice(left, right) {
    const a = targetText(left);
    const b = targetText(right);
    if (!a || !b) return false;
    if (a === b) return true;
    return (a === "mpd" && b.startsWith("mpd:")) || (b === "mpd" && a.startsWith("mpd:"));
  }
  // Resolve a reported target id against the published device list. Returns the
  // published id when the device is present, "" when it is genuinely missing, so
  // callers can tell "this is local" apart from "this is not in the list".
  function resolvePublished(targets, reported) {
    const wanted = targetText(reported);
    if (!wanted) return "";
    const rows = Array.isArray(targets) ? targets : [];
    const idOf = row => (row && typeof row === "object" ? targetText(row.id) : "");
    const exact = rows.find(row => idOf(row) === wanted);
    if (exact) return idOf(exact);
    if (wanted === "mpd") {
      const family = rows.filter(row => isMpd(idOf(row)));
      if (family.length) {
        const online = family.filter(row => row && row.online !== false);
        const pick = online.find(row => row && row.selected === true) || online[0] || family[0];
        return idOf(pick);
      }
    }
    return "";
  }
  root.fnAudioPlaybackTargetPolicy = { targetText, isRemote, isDac, isMpd, normalize, sameDevice, resolvePublished };
})(globalThis);
