const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_page_merge.js", "utf8");
const context = { globalThis: {}, window: undefined };
vm.runInNewContext(source, context);
const merge = context.globalThis.fnAudioLibraryPageMerge.mergePagedItems;
const append = context.globalThis.fnAudioLibraryPageMerge.appendPageItems;

const ids = value => Array.from(value || [], item => Number(item.id));
assert.deepEqual(ids(merge([{ id: 1 }], [[{ id: 2 }], [{ id: 3 }]], 3)), [1, 2, 3]);
assert.deepEqual(ids(merge([{ id: 1 }], [[{ id: 2 }], [], [{ id: 3 }]], 10)), [1, 2]);
assert.deepEqual(ids(merge(null, [[{ id: 1 }]], 1)), [1]);
assert.deepEqual(ids(merge([{ id: 1 }], [[{ id: 2 }, { id: 3 }]], 2)), [1, 2]);
const incremental = [{ id: 1 }];
append(incremental, [{ id: 2 }, { id: 3 }], 3);
assert.deepEqual(ids(incremental), [1, 2, 3]);
append(incremental, [{ id: 4 }], 3);
assert.deepEqual(ids(incremental), [1, 2, 3]);
const largePage = Array.from({ length: 250000 }, (_, id) => ({ id }));
assert.equal(merge([], [largePage], Infinity).length, 200000);
assert.doesNotThrow(() => merge([], [[{ id: 1 }]], { valueOf() { throw new Error("must not coerce"); } }));
assert.doesNotThrow(() => merge([], [[{ id: 1 }]], Symbol("bad-total")));
assert.doesNotThrow(() => merge([], [[{ id: 1 }]], "9".repeat(1000)));
assert.match(source, /MAX_MERGED_ITEMS = 200000/);
assert.match(source, /MAX_NUMERIC_TEXT = 64/);
console.log("Library page merge regression checks passed.");
