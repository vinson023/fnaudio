(function (root) {
  "use strict";
  // R591: `[offset:N]` support, borrowed from Audio Station's LRC reader.
  //
  // Karaoke sheets carry `[offset:+500]` / `[offset:-300]` to shift every line
  // that follows.  Without it the whole lyric drifts by a constant the author
  // already measured, and the only fix a listener has is to re-time the file.
  //
  // Sign convention: `time = time + offset`, i.e. a positive offset makes the
  // line appear LATER.  That is what the LRC tag means ("+ shifts time up") and
  // what the desktop players that honour it do.  Audio Station subtracts
  // instead, so the same file reads 2*offset apart between the two; this module
  // follows the tag, and the test pins the sign so a later change is deliberate.
  function parseOffset(line) {
    const match = String(line || "").match(/\[offset:\s*([+-]?\d+)\s*\]/i);
    if (!match) return null;
    const value = Number(match[1]);
    return Number.isFinite(value) ? value / 1000 : null;
  }
  function parse(text) {
    const rows = [];
    // Milliseconds in the sheet, seconds here: the caller compares against the
    // player clock, which is seconds.
    let offset = 0;
    String(text || "").split(/\r?\n/).forEach(line => {
      const matches = [...line.matchAll(/\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]/g)];
      const content = line.replace(/\[[^\]]+\]/g, "").trim();
      if (!content) {
        // A metadata-only line.  `[offset:]` is the only one that changes how
        // the lines after it are read, and it must not become a lyric row.
        const declared = parseOffset(line);
        if (declared !== null) offset = declared;
        return;
      }
      if (!matches.length) { rows.push({ time: -1, text: content }); return; }
      matches.forEach(match => {
        rows.push({
          time: Number(match[1]) * 60 + Number(match[2]) + Number(`0.${match[3] || 0}`) + offset,
          text: content,
        });
      });
    });
    return rows.sort((a, b) => a.time - b.time);
  }
  root.fnAudioLyricsParsePolicy = { parse };
})(globalThis);
