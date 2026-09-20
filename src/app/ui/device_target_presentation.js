(function (global) {
  "use strict";
  const MAX_TARGETS = 256;
  const MAX_TEXT = 256;
  function safeText(value) {
    return typeof value === "string" && value.length <= MAX_TEXT ? value : "";
  }
  function targetId(target) {
    try { return safeText(target?.id); } catch (_) { return ""; }
  }
  function targetKind(target) {
    try { return safeText(target?.kind); } catch (_) { return ""; }
  }
  function targetName(target) {
    try { return safeText(target?.name); } catch (_) { return ""; }
  }
  function projectTarget(target) {
    const id = targetId(target);
    const kind = targetKind(target);
    const name = targetName(target);
    let online = true;
    let selected = false;
    let message = "";
    let caps = null;
    try {
      const value = target?.online;
      online = value === undefined ? true : value === true;
    } catch (_) { online = true; }
    try { selected = target?.selected === true; } catch (_) { selected = false; }
    try { message = safeText(target?.message); } catch (_) { message = ""; }
    try { caps = target?.caps && typeof target.caps === "object" ? target.caps : null; } catch (_) { caps = null; }
    return { id, kind, name, online, selected, message, caps };
  }
  function targetRank(target) {
    if (targetId(target) === "local") return 0;
    if (targetKind(target) === "mpd") return 1;
    return 2;
  }
  function stableTargets(targets, displayText) {
    const text = typeof displayText === "function"
      ? displayText
      : value => typeof value === "string" ? value : "";
    const list = Array.isArray(targets) ? targets.slice(0, MAX_TARGETS) : [];
    return list.sort((left, right) => {
      let rank = 0;
      try { rank = targetRank(left) - targetRank(right); } catch (_) { rank = 0; }
      if (rank) return rank;
      let leftName = targetName(left);
      let rightName = targetName(right);
      try { leftName = safeText(text(leftName)); } catch (_) { leftName = ""; }
      try { rightName = safeText(text(rightName)); } catch (_) { rightName = ""; }
      return leftName.localeCompare(rightName, "zh-Hans-CN");
    });
  }
  function projectTargets(targets) {
    if (!Array.isArray(targets)) return [];
    return targets.slice(0, MAX_TARGETS).map(projectTarget).filter(target => target.id || target.name || target.kind);
  }
  function resolvedTarget(targets, reportedTarget) {
    const requestedId = safeText(reportedTarget) || "local";
    try {
      return (Array.isArray(targets) ? targets : []).some(target => targetId(target) === requestedId)
        ? requestedId
        : "local";
    } catch (_) {
      return "local";
    }
  }
  global.fnAudioDeviceTargetPresentation = { resolvedTarget, stableTargets, targetRank, projectTarget, projectTargets };
})(typeof window !== "undefined" ? window : globalThis);
