const assert = require("assert");
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "../app/ui/library_query_params.js"), "utf8");
const context = { globalThis: {}, URLSearchParams };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryQueryParams;
const params = policy.buildLibraryQueryParams({
  page: 3, pageSize: 50, view: "albums", sortKey: "album", sortDir: "desc",
  search: "  周杰伦  ", creatorView: true, creatorName: "歌手", groupName: "专辑",
});
assert.strictEqual(params.get("offset"), "100");
assert.strictEqual(params.get("group"), "歌手");
assert.strictEqual(params.get("album"), "专辑");
assert.strictEqual(params.get("search"), "周杰伦");
assert.strictEqual(policy.buildLibraryQueryParams({ search: "x".repeat(5000) }).get("search").length, policy.MAX_SEARCH_CHARS);
assert.strictEqual(policy.buildLibraryQueryParams({ view: "folders", folderRoot: "/music", folderPath: "disc/1" }).get("folder"), "disc/1");
assert.strictEqual(policy.buildLibraryQueryParams({ page: 2.5, pageSize: 50 }).get("offset"), "0");
assert.strictEqual(policy.buildLibraryQueryParams({ page: "3.0", pageSize: 50 }).get("offset"), "100");
assert.doesNotThrow(() => policy.buildLibraryQueryParams({ page: Symbol("bad"), pageSize: { valueOf() { throw new Error("bad"); } } }));
console.log("Library query params regression checks passed.");
