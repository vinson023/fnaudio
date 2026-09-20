(function (root) {
  "use strict";

  const MODES = Object.freeze(["off", "all", "one"]);
  const LABELS = Object.freeze({ off: "循环关闭", all: "列表循环", one: "单曲循环" });
  const ACTIONS = Object.freeze({ off: "开启列表循环", all: "切换为单曲循环", one: "关闭循环播放" });

  function normalize(value) {
    return MODES.includes(value) ? value : "off";
  }

  function next(value) {
    return { off: "all", all: "one", one: "off" }[normalize(value)];
  }

  function label(value) { return LABELS[normalize(value)]; }
  function action(value) { return ACTIONS[normalize(value)]; }

  function iconMarkup(value) {
    const mode = normalize(value);
    const loop = '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>';
    if (mode === "one") return loop + '<path d="M11 8h2v8h-2v-5l-1.5 1.1-1.2-1.6L11 8Z" fill="currentColor" stroke="none"/>';
    return loop;
  }

  root.fnAudioRepeatModePolicy = Object.freeze({ normalize, next, label, action, iconMarkup });
})(globalThis);
