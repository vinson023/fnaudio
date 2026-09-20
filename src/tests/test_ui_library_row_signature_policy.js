const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_row_signature_policy.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryRowSignaturePolicy;
assert.ok(policy && typeof policy.signature === "function");

const base = {
  index: 0,
  title: "Song",
  artist: "Artist",
  album: "Album",
  cover: "http://example.test/cover.jpg?size=160",
  columns: ["title", "duration", "format"],
  values: { duration: "3:00", format: "FLAC" },
  isDsd: false,
};
assert.equal(policy.signature(base), policy.signature({
  ...base,
  index: 0.9,
  values: { duration: "3:00", format: "FLAC" },
}), "stable rendered cells must ignore equivalent transport representations");
assert.notEqual(policy.signature(base), policy.signature({ ...base, cover: "http://example.test/new.jpg?size=160" }));
assert.notEqual(policy.signature(base), policy.signature({ ...base, values: { duration: "3:01", format: "FLAC" } }));
assert.equal(policy.signature({ columns: new Array(100).fill("artist"), values: { artist: "A" } }).length < 4096, true);
console.log("Library row signature policy regression checks passed.");
