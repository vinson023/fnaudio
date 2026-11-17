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

  global.fnAudioMediaErrorPolicy = { MAX_CONSECUTIVE, classify, decide };
})(typeof window !== "undefined" ? window : globalThis);
