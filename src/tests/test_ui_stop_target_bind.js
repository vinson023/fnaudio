const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// TODO.md L69/L70 ruling surface, R165: pressing *stop* on a cast awaits a control
// request and then writes playback state.  Every other entry in that face re-binds the
// target after the await - `remoteControl` returns early on `targetId !== remoteDeviceId()`
// and says so in its comment ("a late response from the old renderer must never be
// projected onto the newly selected renderer"), `refreshRemoteStatus` gates on the same
// pair plus a request token.  `stopPlayback` did neither, so a device switch that lands
// while the stop POST is in flight has its *authoritative* snapshot overwritten by a
// snapshot this browser invented for the device the user just left, and the transport
// icon is flipped to "paused" on a speaker that is playing.
//
// The second defect on the same face: that invented snapshot carries rel_seconds: 0,
// but `currentSeconds` reads `state.remoteBaseSeconds` first, so a pressed stop flipped
// the icon to paused while the rail stayed frozen at the old position (TODO.md:58 class,
// residual cast numbers).  The load path pairs the snapshot with `remoteBaseSeconds = 0`
// for exactly that reason; stop now does the same, and the order is pinned below - the
// zeroing must sit *after* the target guard, or an abandoned stop would destroy the
// position the newly selected device has already declared.
//
// This suite runs the real `stopPlayback`, `updateRemoteUi`, `setPlayButton`,
// `seekDuration`, `currentSeconds`, `localPlaybackSeconds`, `remoteDeviceId`,
// `playbackSeconds`, `transportExtrapolation`, `clock` and `setTextContentIfChanged`
// against tracked fake nodes that count every write, so the assertion is about the row
// the user sees, not about a call log.

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the stale-stop-projection regression`);
  return match[0];
}

function tracked(initial) {
  const node = { writes: [] };
  for (const key of Object.keys(initial)) {
    let value = initial[key];
    Object.defineProperty(node, key, {
      enumerable: true,
      get() { return value; },
      set(next) { node.writes.push(key + "=" + next); value = next; },
    });
  }
  return node;
}

function setup() {
  const calls = [];
  const nodes = {
    elapsed: tracked({ textContent: "2:00" }),
    duration: tracked({ textContent: "3:20" }),
    seek: tracked({ value: "60" }),
    playBtn: tracked({ innerHTML: "" }),
    nowTitle: tracked({ textContent: "Old" }),
    nowArtist: tracked({ textContent: "Old" }),
  };
  nodes.playBtn.dataset = tracked({ playing: "playing" });
  const audio = {
    src: "", currentTime: 0, duration: 0, paused: true, ended: false,
    pause() { calls.push("audio.pause"); }, load() { calls.push("audio.load"); },
    removeAttribute() { calls.push("audio.removeAttribute"); },
  };
  const state = {
    playTarget: "salon",
    playTargetName: "Salon",
    deviceSwitchInFlight: false,
    seeking: false,
    queue: [{ id: "t1", duration: 200, artist: "a" }],
    index: 0,
    remoteStatus: {
      target_id: "salon",
      transport: { state: "PLAYING" },
      position: { rel_seconds: 120, duration_seconds: 200 },
    },
    remoteBaseSeconds: 120,
    remoteSnapshotAt: Date.now() - 1000,
    remoteStateVersion: 7,
    remoteCueSegment: false,
    remoteUiLast: null,
    nativePlayback: { supported: false, active: false, playing: false, position: 0, duration: 0 },
    streamOffset: 0, pendingSeekTime: null, transcodeCacheReady: false, playSourceKind: "",
  };
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const context = {
    state, audio, nodes, calls,
    TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS: 12,
    String, Math, Number, Boolean, JSON, Promise, Object, Array, Error, Set, Date, isNaN,
    $(id) { return nodes[id] || null; },
    isRemoteTarget: () => {
      const value = String(state.playTarget || "");
      return Boolean(value) && value !== "local";
    },
    isIncomingRendererSession: () => false,
    nativePlaybackAvailable: () => false,
    currentItem: () => state.queue[state.index],
    updateTransportStateUnknown: () => calls.push("updateTransportStateUnknown"),
    updateIncomingRendererUi: () => false,
    syncPlayerProgress: () => calls.push("syncPlayerProgress"),
    updateLyricHighlight: () => calls.push("updateLyricHighlight"),
    updateMediaSessionPosition: () => calls.push("updateMediaSessionPosition"),
    controlIncomingRenderer: async () => calls.push("controlIncomingRenderer"),
    restoreLibraryNowPlaying: () => calls.push("restoreLibraryNowPlaying"),
    stopLocalAudio: () => calls.push("stopLocalAudio"),
    updateMediaSessionPlaybackState: () => calls.push("updateMediaSessionPlaybackState"),
    syncState: () => calls.push("syncState"),
    coreControl: async action => { calls.push(`coreControl:${action}`); return {}; },
    // The stop request itself: it is in flight until the test releases it.
    remoteControl: async action => { calls.push(`remoteControl:${action}`); await gate; return true; },
  };
  vm.createContext(context);
  vm.runInContext([
    functionSource("playbackSeconds"),
    functionSource("transportExtrapolation"),
    functionSource("remoteDeviceId"),
    functionSource("localPlaybackSeconds"),
    functionSource("seekDuration"),
    functionSource("currentSeconds"),
    functionSource("clock"),
    functionSource("setTextContentIfChanged"),
    functionSource("setPlayButton"),
    functionSource("updateRemoteUi"),
    functionSource("stopPlayback"),
    "globalThis.h = { stopPlayback, updateRemoteUi, remoteDeviceId };",
  ].join("\n"), context);
  return { ...context.h, state, calls, nodes, release };
}

function rowWrites(env) {
  const n = env.nodes;
  return [
    ...n.elapsed.writes, ...n.duration.writes, ...n.seek.writes,
    ...n.playBtn.writes, ...n.playBtn.dataset.writes,
    ...n.nowTitle.writes, ...n.nowArtist.writes,
  ];
}

async function settle() {
  for (let index = 0; index < 12; index += 1) await Promise.resolve();
}

(async () => {
  // 1. The regression: the user presses stop on the Salon speaker, then moves the output
  //    to the Study speaker before that POST lands.  The Study speaker reports its own
  //    state first, so by the time the old stop reply arrives there is a real snapshot to
  //    destroy.  Nothing may touch the row, and neither of the two numbers the stop would
  //    have written may move.
  const moved = setup();
  const running = moved.stopPlayback();
  await settle();
  assert.ok(moved.calls.includes("remoteControl:stop"), "sanity: the stop request is in flight");
  moved.state.playTarget = "study";
  moved.state.playTargetName = "Study";
  moved.state.remoteStatus = null;
  moved.state.remoteBaseSeconds = 40;
  moved.state.remoteSnapshotAt = Date.now();
  const studySnapshot = {
    target_id: "study",
    transport: { state: "PLAYING" },
    position: { rel_seconds: 40, duration_seconds: 240 },
  };
  moved.state.remoteStatus = studySnapshot;
  moved.state.remoteUiLast = null;
  moved.nodes.elapsed.writes.length = 0;
  moved.nodes.duration.writes.length = 0;
  moved.nodes.seek.writes.length = 0;
  moved.nodes.playBtn.writes.length = 0;
  moved.nodes.playBtn.dataset.writes.length = 0;
  moved.release();
  await running;
  assert.equal(moved.state.remoteStatus, studySnapshot,
    "a stop reply for the renderer the user left must not overwrite the snapshot the new device declared");
  assert.equal(moved.state.remoteBaseSeconds, 40,
    "and it must not zero the position the new device is playing from, which is what the rail reads");
  assert.deepEqual(rowWrites(moved), [],
    "the transport row must not be repainted from a command addressed to another target");

  // 2. Control: the same stop with no switch in between must still take effect, or the
  //    guard would simply be "never apply the optimistic stop".
  const stayed = setup();
  const stayedRun = stayed.stopPlayback();
  await settle();
  stayed.release();
  await stayedRun;
  assert.equal(stayed.state.remoteStatus.transport.state, "STOPPED",
    "the optimistic stopped snapshot is still applied when the target did not move");
  assert.equal(stayed.state.remoteStatus.position.duration_seconds, 200,
    "and it keeps the duration the device reported instead of inventing zero");
  assert.equal(stayed.state.remoteBaseSeconds, 0,
    "the base the row reads is reset with it, so the stop is not a paused-looking freeze");
  assert.ok(stayed.nodes.playBtn.dataset.writes.includes("playing=paused"),
    "the icon still flips to paused for the target the user actually stopped");
  assert.deepEqual(stayed.nodes.elapsed.writes, ["textContent=0:00"],
    "the elapsed label is repainted to the stopped position");
  assert.deepEqual(stayed.nodes.seek.writes, ["value=0"],
    "and the rail is repainted with it instead of staying at the cast position");

  // 3. Switching back to this browser while the stop is in flight must not resurrect a
  //    fabricated remote snapshot either: local playback owns the row now.
  const back = setup();
  const backRun = back.stopPlayback();
  await settle();
  back.state.playTarget = "local";
  back.state.remoteStatus = null;
  back.nodes.elapsed.writes.length = 0;
  back.nodes.duration.writes.length = 0;
  back.nodes.seek.writes.length = 0;
  back.nodes.playBtn.writes.length = 0;
  back.nodes.playBtn.dataset.writes.length = 0;
  back.release();
  await backRun;
  assert.equal(back.state.remoteStatus, null,
    "no remote snapshot may exist for a target that is no longer remote");
  assert.equal(back.state.remoteBaseSeconds, 120,
    "an abandoned stop leaves the previous device numbers alone for the teardown path to settle");
  assert.deepEqual(rowWrites(back), [],
    "and the local row must not be repainted by the abandoned remote stop");

  // 4. Wiring: the guard has to sit between the await and the projection, the position
  //    reset has to sit after the guard, and the two neighbours that already enforce the
  //    rule must keep doing so - the three are one rule.
  const stopBody = functionSource("stopPlayback");
  const requestAt = stopBody.indexOf('await remoteControl("stop")');
  const bindAt = stopBody.indexOf("remoteDeviceId()", 0);
  const projectionAt = stopBody.indexOf("state.remoteStatus = {");
  const resetAt = stopBody.indexOf("state.remoteBaseSeconds = 0;");
  assert.ok(requestAt >= 0, "stopPlayback must keep issuing the remote stop through remoteControl");
  assert.ok(bindAt >= 0 && bindAt < requestAt,
    "the target has to be bound before the request is sent, not read afterwards");
  assert.ok(projectionAt >= 0, "sanity: the optimistic snapshot is still in stopPlayback");
  const bailAt = stopBody.indexOf("remoteDeviceId()", requestAt);
  assert.ok(bailAt >= 0 && bailAt < projectionAt,
    "the target must be re-checked after the await and before the projection");
  assert.ok(resetAt >= 0, "sanity: the position reset is still in stopPlayback");
  assert.ok(resetAt > bailAt && resetAt < projectionAt,
    "the position reset must sit behind the target guard, never in front of it");
  for (const name of ["remoteControl", "refreshRemoteStatus"]) {
    const body = functionSource(name);
    assert.ok(body.includes("targetId !== remoteDeviceId()"),
      name + " keeps the same post-await guard; this suite pins all three together");
  }

  console.log("Stop command target binding regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
