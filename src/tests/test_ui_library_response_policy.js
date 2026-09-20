const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_response_policy.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryResponsePolicy;
assert.equal(policy.responseWeight(null), 1);
assert.equal(policy.responseWeight({}), 1);
assert.equal(policy.responseWeight({ items: [1, 2], groups: [3] }), 2);
assert.equal(policy.responseWeight({ folders: new Array(5) }), 5);
assert.equal(policy.responseWeight({ items: { length: 999999 } }), 1);
assert.equal(policy.responseWeight({ items: Array.from({ length: 7001 }, () => 1) }), 6000);
assert.equal(policy.MAX_RESPONSE_WEIGHT, 6000);
assert.match(source, /function responseWeight\(data\)/);
console.log("Library response policy regression checks passed.");
