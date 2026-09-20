const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_page_cursor_policy.js", "utf8");
const context = { globalThis: {}, Map };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryPageCursorPolicy;

const store = new Map();
assert.equal(policy.remember(store, "query-a", 1, " first "), true);
assert.equal(policy.get(store, "query-a", 2), "first");
assert.equal(policy.remember(store, "query-a", 2, "second"), true);
assert.equal(policy.get(store, "query-a", 3), "second");
policy.remember(store, "query-a", 1, "reset");
assert.equal(policy.get(store, "query-a", 2), "reset");
assert.equal(policy.get(store, "query-a", 3), "");

for (let page = 1; page <= 80; page += 1) policy.remember(store, `query-${page}`, page, `token-${page}`);
assert.equal(store.size, policy.MAX_ENTRIES);
assert.equal(policy.get(store, "query-1", 2), "");
assert.equal(policy.get(store, "query-80", 81), "token-80");

assert.equal(policy.remember(store, "query-bad", "2", "token"), false);
assert.equal(policy.remember(store, "query-bad", 2, { trim() { throw new Error("must not coerce"); } }), true);
assert.equal(policy.get(store, "query-bad", 3), "");
assert.equal(policy.remember(store, "query-bad", 2, "x".repeat(769)), true);
assert.equal(policy.get(store, "query-bad", 3), "");
assert.doesNotThrow(() => policy.clearQuery(store, { toString() { throw new Error("must not coerce"); } }));
assert.match(source, /MAX_ENTRIES = 64/);
assert.match(source, /MAX_TOKEN_CHARS = 768/);
console.log("Library page cursor policy regression checks passed.");
