(() => {
  function read(item, key, fallback = "") {
    try {
      return item && typeof item === "object" ? item[key] : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function finiteNumber(value) {
    if (typeof value === "boolean" || (typeof value !== "number" && typeof value !== "string")) return 0;
    try {
      const number = Number(value);
      return Number.isFinite(number) ? number : 0;
    } catch (_) {
      return 0;
    }
  }

  function text(value, fallback = "") {
    if (typeof value !== "string" && typeof value !== "number") return fallback;
    try { return String(value); } catch (_) { return fallback; }
  }

  function quality(item = {}) {
    const rate = finiteNumber(read(item, "sample_rate"));
    const depth = finiteNumber(read(item, "bit_depth"));
    const bitrate = finiteNumber(read(item, "bitrate"));
    if (read(item, "is_dsd") === true) {
      const dsdRates = [2822400, 5644800, 11289600, 22579200];
      // Legacy ffprobe rows describe eight DSD bits per transport sample.
      // Native container rows already contain the one-bit sampling rate.
      const nativeRate = depth === 8 ? rate * 8 : rate;
      return dsdRates.includes(nativeRate) ? `${(nativeRate / 1000000).toFixed(1)}MHz` : "—";
    }
    const pcm = rate ? `${Math.round(rate / 1000)}kHz${depth ? `/${depth}bit` : ""}` : "";
    return pcm || (bitrate ? `${Math.round(bitrate / 1000)}kbps` : "—");
  }

  function addedDate(item = {}, itemAddedTime) {
    let value = 0;
    try { value = typeof itemAddedTime === "function" ? itemAddedTime(item) : 0; } catch (_) {}
    const seconds = finiteNumber(value);
    if (!seconds) return "—";
    try {
      return new Date(seconds > 99999999999 ? seconds / 1000000000 : seconds * 1000).toLocaleDateString("zh-CN");
    } catch (error) {
      return "—";
    }
  }

  function columnValues(item = {}, keys = [], helpers = {}) {
    const displayText = typeof helpers.displayText === "function" ? helpers.displayText : value => text(value);
    const clock = typeof helpers.clock === "function" ? helpers.clock : value => text(value);
    const formatSize = typeof helpers.formatSize === "function" ? helpers.formatSize : value => text(value);
    const escapeHtml = typeof helpers.escapeHtml === "function" ? helpers.escapeHtml : value => text(value);
    const trackNumber = finiteNumber(read(item, "track_no"));
    const trackNo = trackNumber > 0 ? String(Math.floor(trackNumber)).padStart(2, "0") : "—";
    const duration = finiteNumber(read(item, "duration"));
    const values = {
      track_no: trackNo,
      artist: displayText(read(item, "artist")),
      album: displayText(read(item, "album")),
      format: text(read(item, "format")) || "—",
      duration: duration > 0 ? clock(duration) : "—",
      size: formatSize(read(item, "size")) || "—",
      quality: quality(item),
      added: addedDate(item, helpers.itemAddedTime || (() => 0)),
      composer: displayText(read(item, "composer")),
      genre: displayText(read(item, "genre")),
    };
    const requested = Array.isArray(keys) ? keys : [keys];
    const result = {};
    requested.forEach(key => {
      if (typeof key === "string") result[key] = escapeHtml(values[key] || "—");
    });
    return result;
  }

  function columnValue(item = {}, key, helpers = {}) {
    return columnValues(item, [key], helpers)[key] || "—";
  }

  function rowSelectionKey(item = {}, index = 0) {
    return `${text(read(item, "id"))}::${Math.max(0, finiteNumber(index) || 0)}`;
  }

  window.fnAudioTrackPresentation = { quality, addedDate, columnValues, columnValue, rowSelectionKey };
})();
