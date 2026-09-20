const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_track_filter_policy.js", "utf8");
const context = { globalThis: {}, Array, Number, Boolean, String };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryTrackFilterPolicy;
const rows = [
  { id: "a", artist: "甲", is_dsd: true },
  { id: "b", artist: "乙", is_dsd: false },
  { id: "c", artist: "甲", is_dsd: true },
];
assert.deepEqual(policy.selectTracks({ pagedTrackListing: true, pageItems: rows.slice(0, 1), items: rows }), [rows[0]]);
assert.deepEqual(policy.selectTracks({ items: rows, view: "dsd", search: "甲", matches: item => item.artist === "甲", sort: list => list.reverse() }).map(item => item.id), ["c", "a"]);
assert.deepEqual(policy.selectTracks({ items: [...rows, { id: "bad", is_dsd: "true" }], view: "dsd" }).map(item => item.id), ["a", "c"]);
assert.deepEqual(policy.selectTracks({ items: rows, groupKey: "artist", groupName: "甲", matches: () => true }).map(item => item.id), ["a", "c"]);
assert.deepEqual(policy.selectTracks({ items: rows, view: "queue", queue: [rows[1]], matches: () => true }).map(item => item.id), ["b"]);
assert.deepEqual(policy.selectTracks({ items: rows, view: "playlist", playlist: [rows[2]], matches: () => true }).map(item => item.id), ["c"]);
assert.deepEqual(policy.selectTracks({ items: rows, search: "x", matches: () => { throw new Error("isolated"); } }), []);
assert.deepEqual(policy.selectTracks({ items: rows, sort: () => { throw new Error("isolated"); } }).map(item => item.id), ["a", "b", "c"]);
console.log("Library track filter policy regression checks passed.");
