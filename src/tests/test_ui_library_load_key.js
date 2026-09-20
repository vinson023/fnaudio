const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "library_load_key.js"), "utf8");
const context = { globalThis: {}, Number, JSON };
vm.runInNewContext(source, context);
const build = context.globalThis.fnAudioLibraryLoadKey.buildLibraryLoadKey;

const key = JSON.parse(build(
  { view: "all", pageSize: "120", sortKey: "title", sortDir: "asc" },
  "0", () => "歌手", () => true, () => "live",
));
assert.equal(key.page, 1);
assert.equal(key.pageSize, 120);
assert.equal(key.creator, "歌手");
assert.equal(key.creatorAllTracks, true);
assert.equal(key.search, "live");
assert.equal(JSON.parse(build({ view: "all" }, 2.5, null, null, null)).page, 1);
assert.equal(build(null, "bad", null, null, null), JSON.stringify({
  view: "all", page: 1, pageSize: 0, folderRoot: "", folderPath: "", folderPage: 0,
  folderPageSize: 0, groupName: "", creator: "", creatorAllTracks: false,
  sortKey: "title", sortDir: "asc", search: "",
}));
console.log("Library load key regression checks passed.");
