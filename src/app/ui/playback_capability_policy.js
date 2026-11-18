// R587: the only place the browser reads the server's playback capabilities.
//
// The queue cap belongs to the output target, so the server says what it is
// instead of the client hardcoding 500 (which is where the silent truncation
// came from: the Android remote snapshot dropped row 501 and said nothing).
//
// Defaults are deliberately "old behaviour": with no block, no client-side
// slice and no notice, exactly as before this change.
(() => {
  const FALLBACK = {
    queue: { max: 0, remote: 0, notice: false },
    position: { enabled: false, minIntervalMs: 30000 },
    shuffle: "random",
  };

  function text(value) {
    return typeof value === "string" ? value : "";
  }

  function positiveInt(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) return 0;
    return Math.min(Math.floor(number), 50000);
  }

  function read(source) {
    const data = source && typeof source === "object" ? source : null;
    if (!data) return { ...FALLBACK, queue: { ...FALLBACK.queue }, position: { ...FALLBACK.position } };
    const queue = data.queue && typeof data.queue === "object" ? data.queue : {};
    const position = data.position && typeof data.position === "object" ? data.position : {};
    const shuffle = data.shuffle && typeof data.shuffle === "object" ? data.shuffle : {};
    const minInterval = positiveInt(position.min_interval_ms);
    return {
      queue: {
        max: positiveInt(queue.max_items),
        remote: positiveInt(queue.remote_max_items),
        notice: queue.truncation_notice === true,
      },
      position: {
        enabled: position.report === true,
        // A server that reports an interval below the floor would turn the
        // report into a write per second, which is the Audio Station habit this
        // change exists to avoid.
        minIntervalMs: minInterval ? Math.max(5000, minInterval) : FALLBACK.position.minIntervalMs,
      },
      shuffle: text(shuffle.mode) || FALLBACK.shuffle,
    };
  }

  // Return the rows a target accepts plus how many had to be dropped.  A cap of
  // 0 means "no limit known", which keeps an older server working.
  function boundQueue(items, cap) {
    const list = Array.isArray(items) ? items : [];
    const limit = positiveInt(cap);
    if (!limit || list.length <= limit) return { items: list, dropped: 0, limit };
    return { items: list.slice(0, limit), dropped: list.length - limit, limit };
  }

  function truncationMessage(dropped, limit) {
    const missing = positiveInt(dropped);
    const cap = positiveInt(limit);
    if (!missing || !cap) return "";
    return `当前播放设备最多接收 ${cap} 首，已发送前 ${cap} 首，其余 ${missing} 首未发送。`;
  }

  window.fnAudioPlaybackCapabilityPolicy = { boundQueue, read, truncationMessage };
})();
