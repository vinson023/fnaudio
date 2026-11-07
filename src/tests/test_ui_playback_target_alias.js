// A reload must not mistake the active USB DAC for a vanished device.
//
// Reproduction on the test NAS: cast from machine 1 to machine 2, press pause on
// machine 2, then reload the page. The saved session carried `target_id: "mpd"`
// (the server's output registry key) while `/api/playback/targets` publishes the
// same DAC as `mpd:usb:0644:...:dev0`. `validateRestoredPlaybackTarget` compared
// the two literally, concluded the target was gone, POSTed `target_id: "local"`
// and stopped the output the user had just paused. The device dialog hit the same
// comparison and re-scheduled its own refresh forever.
//
// This test runs the real functions against a stub device list and asserts:
//   - one device spelled two ways is not "unavailable" and triggers no recovery,
//   - the session keeps the spelling it already used (no core target flip-flop),
//   - a device that is really gone still recovers to `local`.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const UI = path.join(__dirname, "..", "app", "ui");
const policySource = fs.readFileSync(path.join(UI, "playback_target_policy.js"), "utf8");
const app = fs.readFileSync(path.join(UI, "app.js"), "utf8");

function plainFunctionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the target-alias regression`);
  return match[0];
}
function asyncFunctionSource(name) {
  const match = app.match(new RegExp("^async function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `async function ${name} must stay extractable for the target-alias regression`);
  return match[0];
}

const DAC = "mpd:usb:0644:0bda:4c01:dev0";
const OTHER_DAC = "mpd:usb:0644:0bda:4c01:dev1";
const LOCAL = { id: "local", name: "当前设备", kind: "browser", online: true, selected: false };
const dacRow = (id = DAC, extra = {}) => ({ id, name: "NAS - USB Audio", kind: "mpd", online: true, selected: false, ...extra });

function harness() {
  const calls = { recover: [], rendered: [], teardown: 0, subscribed: 0, refreshes: 0, saved: 0 };
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) {
      elements.set(id, {
        id,
        open: false,
        innerHTML: "",
        textContent: "",
        disabled: false,
        childElementCount: 0,
        classList: { toggle() {}, contains() { return false; } },
      });
    }
    return elements.get(id);
  };
  const sandbox = {
    console,
    JSON,
    Math,
    Number,
    String,
    Object,
    Promise,
    Boolean,
    Array,
    Date,
    setTimeout: () => { calls.refreshes += 1; return 0; },
    clearTimeout: () => {},
    AbortController: class { abort() {} },
    fetch: async () => ({ ok: true, status: 200 }),
    $: element,
    displayText: value => String(value == null ? "" : value),
    updateDeviceLabel: () => {},
    scheduleUserStateSave: () => { calls.saved += 1; },
    recoverUnavailablePlaybackTarget: async (notify, expectedTarget) => {
      calls.recover.push({ notify, expectedTarget });
      return false;
    },
    scheduleDeviceRefresh: () => {},
    cancelDeviceLoad: () => {},
    stableDeviceTargets: targets => targets,
    renderDeviceTargets: (targets, currentTarget) => { calls.rendered.push({ targets, currentTarget }); },
    stopRemoteEventStream: () => { calls.teardown += 1; },
    startRemoteEventStream: () => { calls.subscribed += 1; },
    localIsPlayingNow: () => false,
    stopLocalAudio: () => { calls.teardown += 1; },
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(policySource, sandbox);
  sandbox.isRemoteTarget = () => sandbox.fnAudioPlaybackTargetPolicy.isRemote(sandbox.state.playTarget);
  const bundle = [
    plainFunctionSource("resolvedDeviceTarget"),
    plainFunctionSource("sameDeviceTarget"),
    asyncFunctionSource("validateRestoredPlaybackTarget"),
    asyncFunctionSource("loadDevices"),
  ].join("\n");
  vm.runInContext(bundle, sandbox);
  return { sandbox, calls, element };
}

function deviceListLoader(data) {
  return {
    read: async () => ({ response: { ok: true, status: 200 }, data, bodyStatus: "parsed" }),
    parsedBody: () => true,
  };
}

function freshState(playTarget) {
  return {
    playTarget,
    playTargetName: "已恢复播放设备",
    deviceLoadInFlight: false,
    deviceLoadController: null,
    deviceLoadRequestToken: 0,
    deviceTargetRevision: 0,
    deviceSwitchInFlight: false,
    deviceTargetsSignature: "",
    deviceTargetsRendered: [],
    devices: [],
    remoteStatus: null,
    remoteStateVersion: 0,
    remoteCueSegment: false,
  };
}

async function restoredSession() {
  // The saved session says "mpd"; the server publishes the DAC under its stable id.
  const { sandbox, calls } = harness();
  sandbox.state = freshState("mpd");
  sandbox.globalThis.fnAudioResponseJsonLoader = deviceListLoader({
    targets: [LOCAL, dacRow(DAC, { selected: true })],
    current_target: DAC,
    refreshing: false,
  });
  const kept = await sandbox.validateRestoredPlaybackTarget();
  assert.equal(kept, true, "an active DAC written as 'mpd' must count as available");
  assert.deepEqual(calls.recover, [], "recovery must not post the target back to local");
  assert.equal(sandbox.state.playTarget, "mpd", "the session keeps the spelling it was saved with");
  assert.equal(sandbox.state.playTargetName, "NAS - USB Audio");

  // Same answer through the device dialog: no recovery, no teardown, no resubscribe.
  const dialog = harness();
  dialog.sandbox.state = freshState("mpd");
  dialog.sandbox.globalThis.fnAudioResponseJsonLoader = deviceListLoader({
    targets: [LOCAL, dacRow(DAC, { selected: true }), dacRow(OTHER_DAC)],
    current_target: DAC,
    refreshing: false,
  });
  await dialog.sandbox.loadDevices();
  assert.deepEqual(dialog.calls.recover, [], "the device dialog must not recover a live DAC");
  assert.equal(dialog.calls.teardown, 0, "a spelling-only difference is not a device switch");
  assert.equal(dialog.sandbox.state.playTarget, "mpd");
  assert.equal(dialog.calls.rendered.length, 1);
  assert.equal(dialog.calls.rendered[0].currentTarget, DAC, "the row is painted as current under its published id");
  assert.deepEqual(
    dialog.sandbox.state.devices.map(target => target.id),
    [DAC, OTHER_DAC],
    "both DACs stay listed",
  );
}

async function vanishedDevice() {
  const { sandbox, calls } = harness();
  sandbox.state = freshState("mpd");
  sandbox.globalThis.fnAudioResponseJsonLoader = deviceListLoader({
    targets: [LOCAL],
    current_target: "mpd",
    refreshing: false,
  });
  const kept = await sandbox.validateRestoredPlaybackTarget();
  assert.equal(kept, false, "a genuinely absent DAC still recovers");
  assert.equal(calls.recover.length, 1);
  assert.equal(calls.recover[0].expectedTarget, "mpd");
}

async function realSwitch() {
  const { sandbox, calls } = harness();
  sandbox.state = freshState(OTHER_DAC);
  sandbox.globalThis.fnAudioResponseJsonLoader = deviceListLoader({
    targets: [LOCAL, dacRow(DAC, { selected: true }), dacRow(OTHER_DAC)],
    current_target: DAC,
    refreshing: false,
  });
  await sandbox.loadDevices();
  assert.equal(sandbox.state.playTarget, DAC, "another controller's real switch is adopted");
  assert.equal(calls.teardown, 1, "a real switch still tears the previous output down");
  assert.equal(calls.recover.length, 0);
}

(async () => {
  await restoredSession();
  await vanishedDevice();
  await realSwitch();
  console.log("Playback target alias regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
