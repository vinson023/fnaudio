const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_empty_response_policy.js", "utf8");
const context = { globalThis: {}, console };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryEmptyResponsePolicy;

assert.equal(policy.shouldRetainSnapshot({ items: [], count: 0 }, [{ id: "1" }], { snapshotHit: true }), true);
assert.equal(policy.shouldRetainSnapshot({ items: [], count: 0 }, [{ id: "1" }], { snapshotHit: true, guardUsed: true }), false);
assert.equal(policy.shouldRetainSnapshot({ items: [], count: 0 }, [{ id: "1" }], { snapshotHit: true, refresh: true }), false);
assert.equal(policy.shouldRetainSnapshot({ items: [], count: 2 }, [{ id: "1" }], { snapshotHit: true }), false);
assert.equal(policy.shouldRetryAfterRetention({ items: [], count: "0" }), true);
assert.equal(policy.shouldRetryAfterRetention({ items: [{ id: "1" }], count: 1 }), false);
console.log("Library empty-response policy regression checks passed.");
