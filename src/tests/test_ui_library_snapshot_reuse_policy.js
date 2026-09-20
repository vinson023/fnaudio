const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_snapshot_reuse_policy.js", "utf8");
const context = { globalThis: {}, window: undefined };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibrarySnapshotReusePolicy;

assert.equal(policy.canReuseMarkup(["first", "second"], ["first", "second"]), true);
assert.equal(policy.canReuseMarkup(["first"], ["second"]), false);
assert.equal(policy.canReuseMarkup(["first"], ["first", "second"]), false);
assert.equal(policy.canReuseMarkup([], []), false);
assert.equal(policy.canReuseMarkup(["first"], [{ value: "first" }]), false);
assert.equal(policy.canReuseMarkup(Array.from({ length: policy.MAX_ROWS + 1 }, () => "row"), Array.from({ length: policy.MAX_ROWS + 1 }, () => "row")), false);
assert.equal(policy.canReuseMarkup(["x".repeat(policy.MAX_SIGNATURE_CHARS + 1)], ["x".repeat(policy.MAX_SIGNATURE_CHARS + 1)]), false);
console.log("Library snapshot reuse policy regression checks passed.");
