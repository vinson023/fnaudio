// The local ALSA output has two names: the server's output registry key "mpd"
// and the published device id "mpd:<stable id>". A paused cast used to persist
// the bare key, the reload compared it against the published list, found nothing
// and posted the target back to "local" - which stopped the device the user had
// just paused. These checks pin the one rule both sides must agree on.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "playback_target_policy.js"), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioPlaybackTargetPolicy;
assert.equal(policy.normalize(""), "local");
assert.equal(policy.normalize("dac:usb"), "dac:usb");
assert.equal(policy.isRemote("mpd:nas"), true);
assert.equal(policy.isRemote("mpd"), true);
assert.equal(policy.isRemote("local"), false);
assert.equal(policy.isDac("dac:usb"), true);
assert.equal(policy.isMpd("mpd:nas"), true);
assert.equal(policy.isMpd("mpd"), true);
assert.equal(policy.isMpd("local"), false);
assert.equal(policy.isRemote({ toString() { throw new Error("must not coerce"); } }), false);

// One device, two spellings.
assert.equal(policy.sameDevice("mpd", "mpd:usb:0644:0bda:4c01:dev0"), true);
assert.equal(policy.sameDevice("mpd:usb:0644:a:dev0", "mpd:usb:0644:a:dev0"), true);
// Two published ids are two DACs, not one device.
assert.equal(policy.sameDevice("mpd:usb:0644:a:dev0", "mpd:usb:0644:b:dev1"), false);
assert.equal(policy.sameDevice("mpd", "local"), false);
assert.equal(policy.sameDevice("local", "local"), true);
assert.equal(policy.sameDevice("uuid:a", "uuid:b"), false);
assert.equal(policy.sameDevice("", "mpd"), false);
assert.equal(policy.sameDevice(null, "mpd"), false);

const dac = { id: "mpd:usb:0644:0bda:4c01:dev0", kind: "mpd", online: true, selected: true };
const otherDac = { id: "mpd:usb:0644:other:dev1", kind: "mpd", online: true, selected: false };
const devices = [{ id: "local", kind: "browser", online: true }, dac, otherDac];

// A bare registry key resolves to the DAC the server currently has selected.
assert.equal(policy.resolvePublished(devices, "mpd"), dac.id);
assert.equal(policy.resolvePublished(devices, dac.id), dac.id);
assert.equal(policy.resolvePublished(devices, "local"), "local");
// Only the mpd family is aliased: an unknown id must never land on another device.
assert.equal(policy.resolvePublished(devices, "uuid:gone"), "");
assert.equal(policy.resolvePublished(devices, ""), "");
assert.equal(policy.resolvePublished([], "mpd"), "");
assert.equal(policy.resolvePublished(null, "mpd"), "");
// Without a selected row the first online DAC wins instead of nothing.
assert.equal(
  policy.resolvePublished([{ id: "local" }, { id: "mpd:usb:x", online: false }, { id: "mpd:usb:y", online: true }], "mpd"),
  "mpd:usb:y",
);
assert.equal(
  policy.resolvePublished([{ id: "local" }, { id: "mpd:usb:x", online: false }], "mpd"),
  "mpd:usb:x",
);
console.log("Playback target policy regression checks passed.");
