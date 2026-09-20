(function (root) {
  "use strict";
  function parse(text) {
    const rows = [];
    String(text || "").split(/\r?\n/).forEach(line => {
      const matches = [...line.matchAll(/\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]/g)];
      const content = line.replace(/\[[^\]]+\]/g, "").trim();
      if (!content) return;
      if (!matches.length) { rows.push({ time: -1, text: content }); return; }
      matches.forEach(match => {
        rows.push({ time: Number(match[1]) * 60 + Number(match[2]) + Number(`0.${match[3] || 0}`), text: content });
      });
    });
    return rows.sort((a, b) => a.time - b.time);
  }
  root.fnAudioLyricsParsePolicy = { parse };
})(globalThis);
