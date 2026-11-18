const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "lyrics_parse_policy.js"), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const parse = context.globalThis.fnAudioLyricsParsePolicy.parse;
assert.deepEqual(JSON.parse(JSON.stringify(parse("[00:02.50]later\nplain\n[00:01]early\n"))), [
  { time: -1, text: "plain" },
  { time: 1, text: "early" },
  { time: 2.5, text: "later" },
]);
assert.deepEqual(JSON.parse(JSON.stringify(parse("[00:01.1][00:03]same"))), [
  { time: 1.1, text: "same" },
  { time: 3, text: "same" },
]);
// R591: `[offset:N]` shifts every line that follows.  Borrowed from Audio
// Station's reader, which is the only player in this comparison that honours it.
// The sign is pinned here because it is the one thing implementations disagree
// about: `[offset:+500]` means "this line is 500 ms late", so the cue fires
// LATER.  Audio Station subtracts instead; this module follows the tag.
assert.deepEqual(JSON.parse(JSON.stringify(parse("[offset:500]\n[00:10]late\n"))), [
  { time: 10.5, text: "late" },
]);
assert.deepEqual(JSON.parse(JSON.stringify(parse("[offset:-250]\n[00:10]early\n"))), [
  { time: 9.75, text: "early" },
]);
// It applies from its own position onward, not to lines already read.
assert.deepEqual(JSON.parse(JSON.stringify(parse("[00:01]first\n[offset:1000]\n[00:02]second\n"))), [
  { time: 1, text: "first" },
  { time: 3, text: "second" },
]);
// The offset line itself must not become a lyric row, and a malformed value is
// ignored rather than read as zero.
assert.deepEqual(JSON.parse(JSON.stringify(parse("[offset:]\n[offset:abc]\n[00:02]only\n"))), [
  { time: 2, text: "only" },
]);
// A line carrying both a timestamp and the tag keeps its timestamp and does not
// also change the offset for later lines.
assert.deepEqual(JSON.parse(JSON.stringify(parse("[offset:500][00:05]mixed\n[00:06]after\n"))), [
  { time: 5, text: "mixed" },
  { time: 6, text: "after" },
]);
console.log("Lyrics parse policy regression checks passed.");
