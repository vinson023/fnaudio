const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_root_label_policy.js", "utf8");
const context = { globalThis: {}, Array, Object, String };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibraryRootLabelPolicy;
const labels = value => JSON.stringify(policy.rootLabels(value));
assert.equal(labels(["/vol1/music", "/vol2/music"]), JSON.stringify(["vol1/music", "vol2/music"]));
assert.equal(labels(["/vol1/a", "/vol1/b"]), JSON.stringify(["a", "b"]));
assert.equal(labels(["/vol1/music/", "music", ""]), JSON.stringify(["vol1/music", "music", "音乐目录"]));
assert.equal(labels(null), "[]");
assert.equal(labels(["/vol1/music", { toString() { throw new Error("must not coerce"); } }]), JSON.stringify(["music", "音乐目录"]));
console.log("Library root label policy regression checks passed.");
