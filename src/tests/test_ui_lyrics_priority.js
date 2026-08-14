const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(
  path.join(__dirname, "..", "app", "ui", "app.js"),
  "utf8"
);
const start = source.indexOf("function syncLyricsForCurrentTrack");
const end = source.indexOf("async function openLyrics", start);
assert.ok(start >= 0 && end > start, "Unable to locate lyric synchronization code");
const sync = source.slice(start, end);

assert.match(sync, /loadLyricsForCurrentTrack\(item\)/, "Track changes must preload lyrics");
assert.doesNotMatch(sync, /lyricsView"\)\.hidden\) return/, "Closed lyrics view must not disable lyric preload");
assert.match(source, /function scheduleLyricsPoll\(trackId\)/, "Pending lyrics must be refreshed automatically");
assert.match(source, /state\.lyricsPollAttempts >= 15/, "Automatic lyric polling needs a bounded retry limit");
assert.match(source, /showLyricsMessage\("正在获取歌词\.\.\."\)/, "Pending lyrics should show an active retrieval state");

console.log("Lyrics priority UI regression checks passed.");
