const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const source = fs.readFileSync(require.resolve("../app/ui/library_reference_items.js"), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const api = context.globalThis.fnAudioLibraryReferenceItems;

const json = value => JSON.stringify(value);
assert.strictEqual(json(api.projectReferencedItems(["a", "b"], id => ({ id }))), json([{ id: "a" }, { id: "b" }]));
assert.strictEqual(json(api.projectReferencedItems(["a", "missing", "b"], id => id === "missing" ? null : { id })), json([{ id: "a" }, { id: "b" }]));
assert.strictEqual(json(api.projectReferencedItems(["a", "b", "c"], id => ({ id }), 2)), json([{ id: "a" }, { id: "b" }]));
assert.strictEqual(json(api.projectReferencedItems(["a"], () => { throw new Error("bad cache"); })), json([]));
assert.strictEqual(json(api.projectReferencedItems("bad", () => ({ id: "a" }))), json([]));
const hostileIds = new Proxy(["a"], { get(target, key) { if (key === "length") throw new Error("bad length"); return target[key]; } });
assert.strictEqual(json(api.projectReferencedItems(hostileIds, id => ({ id }))), json([]));
console.log("ui library reference item tests passed");
