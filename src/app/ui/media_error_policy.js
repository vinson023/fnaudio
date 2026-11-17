(function (global) {
  "use strict";

  // Audio Station 的错误处理是"格式错就提示、其它自动下一首"。我们原来只处理 DSD，
  // 其它错误（转码进程失败、404、连接中断）什么都不做——元素停住、进度条不动，
  // 用户看到的就是"卡了"。
  //
  // 但无脑自动下一首也危险：一首坏文件会把整库刷一遍。所以设上限。
  const MAX_CONSECUTIVE = 3;

  // MediaError.code 的语义
  const CODES = { 1: "aborted", 2: "network", 3: "decode", 4: "src-not-supported" };

  function classify(code) {
    return CODES[Number(code)] || "unknown";
  }

  // 返回 "dsd-unsupported" | "stop" | "next"
  //   streak 是**本次失败之前**已经连续失败的次数。
  function decide(input) {
    const state = input || {};
    if (state.isDsd === true) return "dsd-unsupported";
    if (state.hasNext !== true) return "stop";
    const streak = Math.max(0, Number(state.streak) || 0);
    if (streak + 1 > MAX_CONSECUTIVE) return "stop";
    return "next";
  }

  // 「这首放不了」的名单：服务端能分辨 503（并发满了，可重试）与 502（起不来），
  // 但"文件本身解不开"目前只表现为 200 + 空响应，客户端看到的只是元素报错。
  // 与其每次重试三遍再跳过，不如记住它：下次点它直接跳下一首，成功播放则除名
  // （文件被替换后能自愈）。
  const MAX_UNPLAYABLE = 200;

  function isUnplayable(list, id) {
    const key = String(id || "");
    if (!key || !Array.isArray(list)) return false;
    return list.some(entry => String(entry) === key);
  }

  function markUnplayable(list, id) {
    const key = String(id || "");
    const next = Array.isArray(list) ? list.map(String).filter(entry => entry && entry !== key) : [];
    if (!key) return next;
    next.unshift(key);
    return next.slice(0, MAX_UNPLAYABLE);
  }

  function forgetUnplayable(list, id) {
    const key = String(id || "");
    if (!Array.isArray(list)) return [];
    return list.map(String).filter(entry => entry !== key);
  }

  // 自动续播时绕过"放不了"的那些：从 start 开始找第一首没被标记的。
  // wrap 对应循环=全部；找不到返回 -1，调用方据此停下。
  function nextPlayableIndex(ids, bad, start, wrap) {
    const list = Array.isArray(ids) ? ids : [];
    if (!list.length) return -1;
    const from = Math.max(0, Math.min(Number(start) || 0, list.length - 1));
    for (let step = 0; step < list.length; step += 1) {
      const index = wrap ? (from + step) % list.length : from + step;
      if (index >= list.length) break;
      if (!isUnplayable(bad, list[index])) return index;
    }
    return -1;
  }

  global.fnAudioMediaErrorPolicy = {
    MAX_CONSECUTIVE, MAX_UNPLAYABLE, classify, decide, forgetUnplayable, isUnplayable,
    markUnplayable, nextPlayableIndex,
  };
})(typeof window !== "undefined" ? window : globalThis);
