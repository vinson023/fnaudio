const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/item_negative_cache.js", "utf8");
const context = { globalThis: {}, Map, Number, Date };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioItemNegativeCache;

let current = 10_000;
const cache = policy.create(2, 1_000, () => current);
assert.equal(cache.remember("missing-a"), true);
assert.equal(cache.has("missing-a"), true);
assert.equal(cache.remember("missing-b"), true);
assert.equal(cache.remember("missing-c"), true);
assert.equal(cache.size, 2, "negative cache must evict its oldest entry at capacity");
assert.equal(cache.has("missing-a"), false);
assert.equal(cache.has("missing-c"), true);
current += 1_000;
assert.equal(cache.has("missing-c"), false, "negative entries must expire so later library updates can recover");
assert.equal(cache.remember("resolved"), true);
assert.equal(cache.delete("resolved"), true, "authoritative item data must clear the negative entry");
assert.equal(cache.has("resolved"), false);
assert.equal(cache.remember("x".repeat(513)), false);
assert.match(source, /MAX_ENTRIES = 2048/);
assert.match(source, /MAX_AGE_MS = 5 \* 60 \* 1000/);
console.log("Item negative cache regression checks passed.");
