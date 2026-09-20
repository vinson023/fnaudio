(function (root) {
  "use strict";

  function safeText(value, displayText) {
    try { return displayText(value == null ? "" : value); } catch (_) { return ""; }
  }

  function compare(left, right, key, options = {}) {
    const text = typeof options.displayText === "function" ? options.displayText : value => String(value || "");
    const added = typeof options.itemAddedTime === "function" ? options.itemAddedTime : () => 0;
    if (key === "added") return (Number(added(left)) || 0) - (Number(added(right)) || 0);
    if (key === "track_no") {
      const leftNo = Number(left && left.track_no || 0) || 2147483647;
      const rightNo = Number(right && right.track_no || 0) || 2147483647;
      return leftNo - rightNo || safeText(left && left.title, text).localeCompare(safeText(right && right.title, text), "zh-CN", { numeric: true, sensitivity: "base" });
    }
    return safeText(left && left[key], text).localeCompare(safeText(right && right[key], text), "zh-CN", { numeric: true, sensitivity: "base" });
  }

  function sort(items, key, direction = 1, options = {}) {
    const list = Array.isArray(items) ? items.slice() : [];
    const factor = Number(direction) < 0 ? -1 : 1;
    return list.sort((a, b) => compare(a, b, key, options) * factor);
  }

  root.fnAudioTrackSortPolicy = Object.freeze({ compare, sort });
})(globalThis);
