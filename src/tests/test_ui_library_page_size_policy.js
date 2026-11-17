const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_page_size_policy.js", "utf8");
const sandbox = { globalThis: {}, window: null };
sandbox.window = sandbox;
vm.runInNewContext(source, sandbox);
const policy = sandbox.fnAudioLibraryPageSizePolicy;
const mobile = { matchMedia: query => ({ matches: query === "(max-width: 760px)" }) };
const desktop = { matchMedia: () => ({ matches: false }) };
// R569: both viewports default to 50, and the setting offers 50/100/150/200/500.
assert.equal(policy.defaultPageSize(mobile), 50);
assert.equal(policy.defaultPageSize(desktop), 50);
assert.equal(policy.PAGE_SIZE_OPTIONS.join(","), "50,100,150,200,500");
assert.equal(policy.resolvePageSize({ getItem: () => "" }, mobile), 50);
assert.equal(policy.resolvePageSize({ getItem: () => "" }, desktop), 50);
// Any 1..500 value is honoured, even one the select does not offer: the fixture
// and older stored defaults (96 desktop / 60 mobile) set exact numbers.
assert.equal(policy.resolvePageSize({ getItem: () => "96" }, desktop), 96);
assert.equal(policy.resolvePageSize({ getItem: () => "60" }, mobile), 60);
assert.equal(policy.resolvePageSize({ getItem: () => "2" }, desktop), 2);
assert.equal(policy.resolvePageSize({ getItem: () => "240" }, mobile), 240);
// Only the settings select snaps, so its chosen step is always visible.
assert.equal(policy.nearestOption(96), 100);
assert.equal(policy.nearestOption(240), 200);
assert.equal(policy.nearestOption(2), 50);
assert.equal(policy.resolvePageSize({ getItem: () => "999999" }, desktop), 500);
assert.equal(policy.resolvePageSize({ getItem: () => "invalid" }, mobile), 50);
assert.equal(policy.resolvePageSize({ getItem: () => { throw new Error("storage"); } }, desktop), 50);
console.log("Library page-size policy regression checks passed.");
