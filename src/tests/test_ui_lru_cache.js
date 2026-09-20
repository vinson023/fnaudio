const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/lru_cache.js", "utf8");
const context = { globalThis: {}, Map };
vm.runInNewContext(source, context);
const cache = context.globalThis.fnAudioLruCache(2);
cache.set("a", 1).set("b", 2);
assert.equal(cache.get("a"), 1);
cache.set("c", 3);
assert.equal(cache.has("a"), true);
assert.equal(cache.has("b"), false);
assert.equal(cache.size, 2);
cache.clear();
assert.equal(cache.size, 0);
assert.equal(cache.weight, 0);

const weighted = context.globalThis.fnAudioLruCache(4, {
  maxWeight: 3,
  weightOf: value => value.weight
});
weighted.set("a", { weight: 1 }).set("b", { weight: 2 });
assert.equal(weighted.weight, 3);
weighted.set("c", { weight: 2 });
assert.equal(weighted.has("a"), false);
assert.equal(weighted.weight, 2);
weighted.set("huge", { weight: 4 });
assert.equal(weighted.has("huge"), false);
assert.equal(weighted.has("c"), true);
const bounded = context.globalThis.fnAudioLruCache(Infinity, { maxWeight: Infinity });
bounded.set("one", 1);
assert.equal(bounded.size, 1);
const hostile = { valueOf() { throw new Error("must not escape cache boundary"); } };
const hostileCache = context.globalThis.fnAudioLruCache(Symbol("limit"), { maxWeight: hostile });
hostileCache.set("safe", 1);
assert.equal(hostileCache.size, 1);
const fractional = context.globalThis.fnAudioLruCache(1.9);
fractional.set("a", 1).set("b", 2);
assert.equal(fractional.size, 1);
const booleanLimit = context.globalThis.fnAudioLruCache(true);
booleanLimit.set("a", 1).set("b", 2);
assert.equal(booleanLimit.size, 1);
const selective = context.globalThis.fnAudioLruCache(4);
selective.set("keep", { id: "keep" }).set("drop", { id: "drop" });
assert.equal(selective.deleteWhere(value => value.id === "drop"), 1);
assert.equal(selective.has("drop"), false);
assert.equal(selective.has("keep"), true);
assert.equal(selective.deleteWhere("bad"), 0);
assert.match(source, /MAX_ENTRIES = 50000/);
console.log("LRU cache regression checks passed.");
