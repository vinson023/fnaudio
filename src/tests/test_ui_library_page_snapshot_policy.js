const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_page_snapshot_policy.js", "utf8");
const context = { globalThis: {}, window: undefined, JSON, Number, Math, Array, Object, String };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryPageSnapshotPolicy;
const options = { key: "page-1", now: 1000, ttlMs: 500, maxBytes: 1000, boundItems: items => items.filter(item => item && item.id).slice(0, 2) };

assert.equal(policy.boundedPage(0), 1);
assert.equal(policy.boundedPage(3.8), 3);
assert.equal(policy.boundedTotal(NaN, 2), 2);
assert.equal(policy.boundedTotal(1e20, 2), policy.MAX_TOTAL);
const restored = policy.restore(JSON.stringify({ key: "page-1", savedAt: 800, total: "bad", items: [{ id: "a" }, { id: "b" }] }), options);
assert.equal(restored.status, "hit");
assert.equal(restored.savedAt, 800);
assert.equal(restored.total, 2);
assert.deepEqual(JSON.parse(JSON.stringify(restored.items)), [{ id: "a" }, { id: "b" }]);
assert.equal(policy.restore(JSON.stringify({ key: "page-1", savedAt: 400, items: [{ id: "a" }] }), options).status, "stale");
assert.equal(policy.restore("x".repeat(1001), options).status, "miss");
assert.equal(policy.restore("{", options).status, "miss");
assert.equal(policy.restore(JSON.stringify({ key: "page-1", savedAt: 900, items: [{ nope: true }] }), options).status, "miss");
const encoded = policy.encode({ key: "page-1", savedAt: 900, total: NaN, items: [{ id: "a" }], maxBytes: 1000 });
assert.ok(encoded);
assert.equal(JSON.parse(encoded).total, 1);
assert.equal(policy.encode({ key: "page-1", savedAt: 900, items: [{ id: "a", text: "x".repeat(2000) }], maxBytes: 100 }), "");
console.log("Library page snapshot policy regression checks passed.");
