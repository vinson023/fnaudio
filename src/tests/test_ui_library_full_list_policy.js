const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "library_full_list_policy.js"), "utf8");
const context = { globalThis: {}, Number, Math };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryFullListPolicy;

assert.equal(policy.boundedCount("250"), 250);
assert.equal(policy.boundedCount("9".repeat(1000)), 0);
assert.equal(policy.boundedCount(Symbol("bad")), 0);
assert.equal(policy.boundedCount(999999, 500), 500);
assert.equal(policy.shouldStopMerge(120, 250, 100), false);
assert.equal(policy.shouldStopMerge(250, 250, 100), true);
assert.equal(policy.shouldStopMerge(120, 250, 0), true);
console.log("Library full-list policy regression checks passed.");
