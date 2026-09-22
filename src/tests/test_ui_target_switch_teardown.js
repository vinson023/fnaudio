const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// TODO.md L69 ruling D-1 has two doors.  A cast arriving *here* stops local playback,
// which test_ui_renderer_ownership.js already pins.  The other door is moving our own
// output *away*: the moment the audible output is a device, $("playBtn"), $("stopBtn")
// and the media session all route to that device, so the local element is left
// decoding behind a row nobody can control any more.  Both doors must tear the element
// down exactly once.  Neither may issue a follow-up api/playback/control request -
// that is what would race the target the server just accepted.

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the target-switch teardown regression`);
  return match[0];
}

function setup(overrides, contextOverrides) {
  const calls = [];
  const nodes = {
    playBtn: { dataset: {}, innerHTML: "" },
    deviceDialog: { open: false },
    deviceList: { childElementCount: 1, innerHTML: "" },
    scanDevices: {},
    deviceRefreshStatus: {},
  };
  const audio = {
    src: "http://local/track.flac",
    currentTime: 12,
    duration: 200,
    paused: false,
    ended: false,
    pause() { calls.push("audio.pause"); audio.paused = true; },
    removeAttribute(name) { calls.push(`audio.removeAttribute:${name}`); if (name === "src") audio.src = ""; },
    load() { calls.push("audio.load"); },
    play() { calls.push("audio.play"); audio.paused = false; return Promise.resolve(); },
  };
  const state = {
    playTarget: "local",
    playTargetName: "",
    deviceSwitchInFlight: false,
    deviceTargetRevision: 0,
    deviceLoadRequestToken: 0,
    deviceLoadController: null,
    deviceLoadInFlight: false,
    deviceTargetsSignature: "",
    userStateRevision: 0,
    remoteStatus: { transport: { state: "PLAYING" } },
    remoteStateVersion: 4,
    remoteCueSegment: true,
    remoteEventStreamOpen: false,
    playbackLoadToken: 0,
    streamOffset: 5,
    pendingSeekTime: 7,
    transcodeCacheReady: true,
    playSourceKind: "cache",
    nativePlayback: { supported: false, active: false, playing: false, position: 0, duration: 0 },
    queue: [{ id: "t1" }],
    index: 0,
    devices: [],
    ...overrides,
  };
  const context = {
    state,
    audio,
    calls,
    nodes,
    fetch: url => { calls.push(`fetch:${url}`); return Promise.resolve({ ok: true }); },
    AbortController: class { constructor() { this.signal = {}; } abort() { calls.push("abort"); } },
    alert: message => calls.push(`alert:${message}`),
    apiFetch: async (url, options) => {
      calls.push(`apiFetch:${url}:${options.method}`);
      return { ok: true, status: 200 };
    },
    readResponseJsonBounded: async () => ({ ok: true, revision: 3 }),
    fnAudioResponseJsonLoader: {
      read: async ({ request }) => ({ response: { ok: true }, status: 200, bodyStatus: "json",
        data: { ok: true, targets: context.targets, current_target: context.reportedTarget,
          current_target_name: "Salon", refreshing: false }, request }),
      parsedBody: status => status === "json",
    },
    targets: [{ id: "local", name: "local" }, { id: "salon", name: "Salon" }],
    reportedTarget: "salon",
    userStateRevision: (value, fallback = 0) => (Number.isFinite(value) ? value : fallback),
    isRemoteTarget: () => {
      const value = String(state.playTarget || "");
      return Boolean(value) && value !== "local";
    },
    nativePlaybackAvailable: () => Boolean(state.nativePlayback.supported && state.nativePlayback.active),
    nativePlaybackCall: action => calls.push(`native:${action}`),
    cancelDeviceLoad: () => calls.push("cancelDeviceLoad"),
    cancelRemoteLoad: () => calls.push("cancelRemoteLoad"),
    cancelRemoteStatusRequest: () => calls.push("cancelRemoteStatusRequest"),
    markCurrentDeviceTarget: (id, switching) => calls.push(`markCurrentDeviceTarget:${id}:${Boolean(switching)}`),
    updateDeviceLabel: () => calls.push("updateDeviceLabel"),
    render: () => calls.push("render"),
    renderDeviceTargets: () => calls.push("renderDeviceTargets"),
    scheduleUserStateSave: () => calls.push("scheduleUserStateSave"),
    scheduleDeviceRefresh: () => calls.push("scheduleDeviceRefresh"),
    stableDeviceTargets: value => value,
    resolvedDeviceTarget: (targets, reported) => {
      const id = String(reported || "local");
      return targets.some(target => String(target.id || "") === id) ? id : "local";
    },
    recoverUnavailablePlaybackTarget: async () => calls.push("recoverUnavailablePlaybackTarget"),
    stopRemoteEventStream: () => { state.remoteEventStreamOpen = false; calls.push("stopRemoteEventStream"); },
    startRemoteEventStream: () => { state.remoteEventStreamOpen = true; calls.push("startRemoteEventStream"); },
    nativeRemoteEnter: force => calls.push(`nativeRemoteEnter:${Boolean(force)}`),
    nativeRemoteExit: () => calls.push("nativeRemoteExit"),
    loadDevices: async () => calls.push("loadDevices"),
    displayText: value => String(value ?? ""),
    String, Math, Number, Boolean, JSON, Promise, Object, Array, TypeError, Error, Set, Map, Date,
    $(id) { return nodes[id] || (nodes[id] = { textContent: "", value: "0", dataset: {}, style: {} }); },
  };
  Object.assign(context, contextOverrides || {});
  vm.createContext(context);
  vm.runInContext([
    functionSource("setPlayButton"),
    functionSource("stopLocalAudio"),
    functionSource("localIsPlayingNow"),
    functionSource("selectPlaybackTarget"),
    functionSource("loadDevices"),
    "globalThis.h = { selectPlaybackTarget, loadDevices, localIsPlayingNow, stopLocalAudio };",
  ].join("\n"), context);
  return { ...context.h, state, audio, calls, nodes };
}

function teardownCalls(calls) {
  return calls.filter(name => name === "audio.pause" || name === "audio.removeAttribute:src" || name === "audio.load");
}

async function flush() {
  for (let index = 0; index < 30; index += 1) await Promise.resolve();
}

(async () => {
  // 1. A user moves the output to a device while this browser is playing.  The local
  //    element must be torn down once - and nothing may be sent to api/playback/control
  //    on the way, because the target transaction already owns the transition.
  const moved = setup();
  assert.equal(moved.localIsPlayingNow(), true, "sanity: the element is running before the switch");
  await moved.selectPlaybackTarget("salon", "Salon");
  await flush();
  assert.ok(moved.calls.includes("apiFetch:api/playback/target:POST"),
    "the switch must really reach the accepted-target transaction");
  assert.equal(moved.state.playTarget, "salon", "sanity: the new target is a device");
  assert.ok(moved.calls.includes("startRemoteEventStream"), "the device stream is opened");
  assert.ok(moved.calls.includes("nativeRemoteEnter:true"), "the host enters remote mode");
  assert.deepEqual(teardownCalls(moved.calls), ["audio.pause", "audio.removeAttribute:src", "audio.load"],
    "moving the output away must tear the local element down exactly once");
  assert.equal(moved.state.playSourceKind, "", "the local source kind goes with the element");
  assert.equal(moved.nodes.playBtn.dataset.playing, "paused", "the transport icon stops claiming to play");
  assert.equal(moved.calls.filter(name => name.startsWith("apiFetch:api/playback/control")).length, 0,
    "the switch must not issue a follow-up playback control request");

  // 1b. Under the host player the same teardown has to reach the native sink too.
  const hosted = setup({ nativePlayback: { supported: true, active: true, playing: true, position: 3, duration: 9 } });
  await hosted.selectPlaybackTarget("salon", "Salon");
  await flush();
  assert.equal(hosted.calls.filter(name => name === "native:stop").length, 1,
    "the host player must be stopped once when its output moves away");

  // 2. Silence must not buy a teardown: on an idle browser the switch writes nothing.
  const idle = setup();
  idle.audio.pause();
  idle.audio.src = "";
  idle.calls.length = 0;
  await idle.selectPlaybackTarget("salon", "Salon");
  await flush();
  assert.deepEqual(idle.calls.filter(name => name.startsWith("audio.")), [],
    "an idle local element must be left alone by a target switch");

  // 3. Moving back to this machine must not tear anything down either - the local
  //    branch has no deaf-element problem, and a stray stop would kill a resume.
  const back = setup({ playTarget: "salon" });
  await back.selectPlaybackTarget("local", "Current device");
  await flush();
  assert.ok(back.calls.includes("nativeRemoteExit"), "sanity: the local branch ran to its end");
  assert.deepEqual(teardownCalls(back.calls), [],
    "switching back to local must not touch the local element");

  // 4. The server or another controller can move the output without any click here;
  //    loadDevices() reconciles the target and owes the same teardown.
  const reconciled = setup();
  await reconciled.loadDevices();
  await flush();
  assert.deepEqual(teardownCalls(reconciled.calls), ["audio.pause", "audio.removeAttribute:src", "audio.load"],
    "a reconciled move to a device must tear the local element down exactly once");
  assert.equal(reconciled.state.playSourceKind, "", "and clear the local source kind with it");

  const alreadyRemote = setup({ playTarget: "salon" });
  await alreadyRemote.loadDevices();
  await flush();
  assert.deepEqual(teardownCalls(alreadyRemote.calls), [],
    "an unchanged device target must not tear anything down a second time");

  const toLocal = setup({ playTarget: "salon" }, { reportedTarget: "local" });
  await toLocal.loadDevices();
  await flush();
  assert.deepEqual(teardownCalls(toLocal.calls), [],
    "a reconciled move back to local must not touch the local element");
  assert.ok(toLocal.calls.includes("stopRemoteEventStream"), "sanity: the reconcile branch ran");

  // 5. Wiring: the teardown has to sit after the new target is accepted and before the
  //    host switches mode, inside the device branch only.  Otherwise a rejected switch
  //    would stop audio that is still the active output.
  const switchBody = functionSource("selectPlaybackTarget");
  const acceptedAt = switchBody.indexOf("state.playTarget = nextTarget;");
  const deviceBranchAt = switchBody.indexOf("} else {", acceptedAt);
  const localBranchAt = switchBody.indexOf('if (nextTarget === "local") {', acceptedAt);
  const teardownAt = switchBody.indexOf("if (localIsPlayingNow()) stopLocalAudio();", deviceBranchAt);
  const enterAt = switchBody.indexOf("nativeRemoteEnter(true);", deviceBranchAt);
  assert.ok(acceptedAt >= 0 && localBranchAt > acceptedAt && deviceBranchAt > localBranchAt && enterAt > deviceBranchAt,
    "the accepted-target block, the local branch and the device branch must stay in order");
  assert.ok(teardownAt > deviceBranchAt && teardownAt < enterAt,
    "the local teardown must live in the device branch, after the target is accepted and before the host enters remote mode");
  assert.ok(!switchBody.slice(localBranchAt, deviceBranchAt).includes("stopLocalAudio();"),
    "the local branch must not tear the element down");
  assert.equal(switchBody.split("stopLocalAudio();").length - 1, 1, "exactly one teardown on the switch path");
  assert.ok(!switchBody.includes('remoteControl("stop"'),
    "the switch must never send a stop control request");

  const devicesBody = functionSource("loadDevices");
  const reconcileAt = devicesBody.indexOf("if (previousTarget !== currentTarget) {");
  const remoteGateAt = devicesBody.indexOf("if (isRemoteTarget())", reconcileAt);
  const reconcileTeardownAt = devicesBody.indexOf("if (localIsPlayingNow()) stopLocalAudio();", reconcileAt);
  assert.ok(reconcileAt >= 0 && remoteGateAt > reconcileAt && reconcileTeardownAt > remoteGateAt,
    "the reconcile teardown must stay inside the changed-target block and behind the device gate");
  assert.equal(devicesBody.split("stopLocalAudio();").length - 1, 1, "exactly one teardown per reconcile path");
})().then(() => {
  console.log("Target switch local teardown checks passed.");
}).catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
