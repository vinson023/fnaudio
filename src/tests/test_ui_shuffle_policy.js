const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/shuffle_policy.js", "utf8");
const context = vm.createContext({ window: {} });
vm.runInContext(source, context);
const policy = context.window.fnAudioShufflePolicy;

assert.equal(policy.MAX_ITEMS, 50000);
const asArray = value => JSON.parse(JSON.stringify(value));
assert.deepEqual(asArray(policy.shuffle([1, 2, 3], () => 0)), [2, 3, 1]);
assert.deepEqual(asArray(policy.shuffle([1, 2, 3], () => 0.999999999)), [1, 2, 3]);
assert.deepEqual(asArray(policy.shuffle(null)), []);
assert.deepEqual(asArray(policy.shuffle([1, 2], () => { throw new Error("bad rng"); })), [2, 1]);
assert.deepEqual(asArray(policy.shuffle([1, 2], () => Number.NaN)), [2, 1]);

console.log("Shuffle policy regression checks passed.");
