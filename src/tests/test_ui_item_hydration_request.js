const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/item_hydration_request.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const request = context.globalThis.fnAudioItemHydrationRequest;

const active = request.create("favorites", ["one", "two"]);
assert.equal(request.matches(active, "favorites", ["one", "two"]), true);
assert.equal(request.matches(active, "favorites", ["two", "one"]), false);
assert.equal(request.matches(active, "playlist:mix", ["one", "two"]), false);
assert.equal(request.matches(active, "favorites", ["one"]), false);
const many = Array.from({ length: 2048 }, (_, index) => `id-${index}`);
assert.equal(request.matches(request.create("favorites", many), "favorites", many.slice()), true);
console.log("Item hydration request identity regression checks passed.");
