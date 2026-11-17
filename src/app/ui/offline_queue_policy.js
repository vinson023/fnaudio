(function (global) {
  "use strict";

  // 离线启动的队列快照。
  //
  // 服务端状态取不到时（断网、服务重启），界面本身是内置的，但队列只在服务端——
  // 没有它播放器就是空的。这个模块负责把队列连同**最小元数据**存下来再读回来：
  // 只有 id 渲染不了任何东西，标题/歌手/URL 也得一起存。
  const VERSION = 2;
  const MAX_ITEMS = 200;

  function pickItem(item) {
    if (!item || typeof item !== "object") return null;
    const id = String(item.id || "");
    if (!id) return null;
    return {
      id,
      title: String(item.title || ""),
      artist: String(item.artist || ""),
      album: String(item.album || ""),
      url: String(item.url || ""),
      duration: Number(item.duration) || 0,
      format: String(item.format || ""),
      cue_track: item.cue_track === true,
      cue_start: Number(item.cue_start) || 0,
    };
  }

  function encode(input) {
    const state = input || {};
    const items = (Array.isArray(state.queue) ? state.queue : [])
      .map(pickItem)
      .filter(Boolean)
      .slice(0, MAX_ITEMS);
    return JSON.stringify({
      v: VERSION,
      savedAt: Date.now(),
      items,
      current: String(state.current || ""),
      repeat: ["off", "all", "one"].includes(state.repeat) ? state.repeat : "off",
      shuffle: state.shuffle === true,
    });
  }

  function decode(raw) {
    if (typeof raw !== "string" || !raw.trim()) return null;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_) {
      return null;
    }
    if (!parsed || parsed.v !== VERSION) return null;
    const items = (Array.isArray(parsed.items) ? parsed.items : [])
      .map(pickItem)
      .filter(Boolean)
      .slice(0, MAX_ITEMS);
    if (!items.length) return null;
    return {
      items,
      current: String(parsed.current || ""),
      repeat: ["off", "all", "one"].includes(parsed.repeat) ? parsed.repeat : "off",
      shuffle: parsed.shuffle === true,
      savedAt: Number(parsed.savedAt) || 0,
    };
  }

  // 只有当快照里还找得到"当前曲"时才算可用；否则恢复出来是一排点了会静默失败的
  // 行，比空队列更难解释。
  function indexOfCurrent(snapshot) {
    if (!snapshot || !Array.isArray(snapshot.items)) return -1;
    const wanted = String(snapshot.current || "");
    if (!wanted) return snapshot.items.length ? 0 : -1;
    return snapshot.items.findIndex(item => String(item.id) === wanted);
  }

  function isUsable(snapshot) {
    return Boolean(snapshot && Array.isArray(snapshot.items) && snapshot.items.length
      && indexOfCurrent(snapshot) >= 0);
  }

  global.fnAudioOfflineQueue = { VERSION, MAX_ITEMS, decode, encode, indexOfCurrent, isUsable };
})(typeof window !== "undefined" ? window : globalThis);
