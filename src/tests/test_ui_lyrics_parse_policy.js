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
console.log("Lyrics parse policy regression checks passed.");
