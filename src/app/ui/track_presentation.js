(() => {
  function quality(item = {}) {
    const rate = Number(item.sample_rate || 0);
    const depth = Number(item.bit_depth || 0);
    const bitrate = Number(item.bitrate || 0);
    const pcm = rate ? `${Math.round(rate / 1000)}kHz${depth ? `/${depth}bit` : ""}` : "";
    return pcm || (bitrate ? `${Math.round(bitrate / 1000)}kbps` : "—");
  }

  function addedDate(item = {}, itemAddedTime) {
    const seconds = Number(itemAddedTime(item) || 0);
    if (!seconds) return "—";
    try {
      return new Date(seconds > 99999999999 ? seconds / 1000000000 : seconds * 1000).toLocaleDateString("zh-CN");
    } catch (error) {
      return "—";
    }
  }

  function columnValue(item = {}, key, helpers = {}) {
    const displayText = helpers.displayText || (value => String(value || ""));
    const clock = helpers.clock || (value => String(value || ""));
    const formatSize = helpers.formatSize || (value => String(value || ""));
    const escapeHtml = helpers.escapeHtml || (value => String(value || ""));
    const trackNo = Number(item.track_no || 0) > 0 ? String(Number(item.track_no)).padStart(2, "0") : "—";
    const values = {
      track_no: trackNo,
      artist: displayText(item.artist),
      album: displayText(item.album),
      format: item.format || "—",
      duration: Number(item.duration || 0) > 0 ? clock(item.duration) : "—",
      size: formatSize(item.size) || "—",
      quality: quality(item),
      added: addedDate(item, helpers.itemAddedTime || (() => 0)),
      composer: displayText(item.composer),
      genre: displayText(item.genre),
    };
    return escapeHtml(values[key] || "—");
  }

  function rowSelectionKey(item = {}, index = 0) {
    return `${String(item?.id || "")}::${Math.max(0, Number(index) || 0)}`;
  }

  window.fnAudioTrackPresentation = { quality, addedDate, columnValue, rowSelectionKey };
})();
