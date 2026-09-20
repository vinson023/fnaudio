const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app/ui/device_target_presentation.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const api = context.globalThis.fnAudioDeviceTargetPresentation;
const targets = [
  { id: "dlna:b", kind: "dlna", name: "乙" },
  { id: "mpd:a", kind: "mpd", name: "DAC" },
  { id: "local", kind: "browser", name: "当前设备" },
  { id: "dlna:a", kind: "dlna", name: "甲" },
];
assert.deepEqual(Array.from(api.stableTargets(targets, String)).map(item => item.id), ["local", "mpd:a", "dlna:a", "dlna:b"]);
assert.equal(api.resolvedTarget(targets, "mpd:a"), "mpd:a");
assert.equal(api.resolvedTarget(targets, "missing"), "local");
assert.equal(api.resolvedTarget(targets, { toString() { throw new Error("must not stringify"); } }), "local");
assert.equal(api.stableTargets(Array.from({ length: 300 }, (_, index) => ({ id: `x-${index}`, kind: "dlna", name: String(index) }))).length, 256);
assert.doesNotThrow(() => api.stableTargets([{ id: "x", name: { toString() { throw new Error("must not stringify"); } } }]));
assert.doesNotThrow(() => api.stableTargets([{ id: "x", name: "x" }], () => { throw new Error("broken label"); }));
assert.equal(api.resolvedTarget([{ get id() { throw new Error("broken id"); } }], "x"), "local");
assert.doesNotThrow(() => api.resolvedTarget([{ id: { toString() { throw new Error("must not stringify"); } } }], "x"));
assert.deepEqual(JSON.parse(JSON.stringify(api.projectTarget({ id: "mpd:a", kind: "mpd", name: "DAC", online: false, message: "忙", selected: true }))), { id: "mpd:a", kind: "mpd", name: "DAC", online: false, selected: true, message: "忙", caps: null });
assert.equal(api.projectTarget({ id: "bad", kind: "mpd", name: "坏设备", online: "false" }).online, false);
assert.equal(api.projectTarget({ id: "legacy", kind: "mpd", name: "旧设备" }).online, true);
const broken = new Proxy({}, { get() { throw new Error("broken target"); } });
assert.doesNotThrow(() => api.projectTargets([broken, { id: "local", kind: "browser", name: "当前设备" }]));
assert.equal(api.projectTargets([broken, { id: "local", kind: "browser", name: "当前设备" }]).map(item => item.id).join(","), "local");
assert.equal(api.projectTargets("bad").length, 0);
assert.match(source, /MAX_TARGETS = 256/);
console.log("Device target presentation regression checks passed.");
