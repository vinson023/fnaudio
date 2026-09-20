(function (root) {
  "use strict";
  function targetText(target) { return typeof target === "string" ? target : ""; }
  function isRemote(target) { const value = targetText(target); return Boolean(value) && value !== "local"; }
  function isDac(target) { return targetText(target).startsWith("dac:"); }
  function isMpd(target) { return targetText(target).startsWith("mpd:"); }
  function normalize(target) { const value = targetText(target); return value || "local"; }
  root.fnAudioPlaybackTargetPolicy = { targetText, isRemote, isDac, isMpd, normalize };
})(globalThis);
