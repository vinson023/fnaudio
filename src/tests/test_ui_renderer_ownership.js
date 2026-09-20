const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// TODO.md:72 (ruling D): one output owner at a time.  A cast stops local playback,
// a local play intent takes the output back, and an ended cast never resumes it.
// Every case below drives the real functions out of app.js; the recorders only stand
// in for effects that belong to another entry (painting, the server queue).

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the renderer-ownership regression`);
  return match[0];
}
function blockSource(pattern, label) {
  const match = app.match(pattern);
  assert.ok(match, `${label} must stay extractable for the renderer-ownership regression`);
  return match[0];
}

const castUri = "http://cast/track.flac";
function castSession(overrides) {
  return { uri: castUri, transport: "PLAYING", position: 40, duration: 100, ...overrides };
}

function setup(overrides) {
  const calls = [];
  const nodes = { playBtn: { dataset: {}, innerHTML: "" } };
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
    rendererSession: null,
    rendererSnapshotAt: 0,
    rendererPreemptedUri: "",
    rendererRequestInFlight: false,
    rendererRequestToken: 0,
    rendererRequestController: null,
    playbackLoadToken: 0,
    streamOffset: 5,
    pendingSeekTime: 7,
    transcodeCacheReady: true,
    playSourceKind: "cache",
    nativePlayback: { supported: false, active: false, playing: false, position: 0, duration: 0 },
    payload: { available: true, state: castSession() },
    ...overrides,
  };
  const context = {
    state,
    audio,
    calls,
    nodes,
    fetch: () => Promise.resolve({ ok: true }),
    alert: message => calls.push(`alert:${message}`),
    setTimeout: callback => calls.push("renderer-refresh-scheduled"),
    apiFetch: async (url, options) => {
      calls.push(`apiFetch:${url}:${options.method}:${options.body}`);
      return { ok: true, status: 200 };
    },
    readResponseJsonBounded: async () => ({ ok: true }),
    // refreshRendererSession reads the bridge through this loader; without it the
    // await throws inside the function's own empty catch and every case below would
    // silently assert against a poll that never ran.
    fnAudioResponseJsonLoader: {
      read: async () => ({ response: { ok: true }, status: 200, data: state.payload }),
    },
    updateRemoteUi: () => calls.push("updateRemoteUi"),
    nativePlaybackCall: action => calls.push(`native:${action}`),
    nativePlaybackAvailable: () => Boolean(state.nativePlayback.supported && state.nativePlayback.active),
    renderIncomingRendererSession: session => calls.push(`paint-cast:${session.uri}`),
    restoreLibraryNowPlaying: () => calls.push("restore-library-row"),
    updateMediaSessionPlaybackState: () => calls.push("mediaPlayback"),
    loadCurrent: () => calls.push("loadCurrent"),
    playbackSeconds: value => (Number.isFinite(Number(value)) ? Number(value) : 0),
    Date: { now: () => 1700000000000 },
    $(id) { return nodes[id] || (nodes[id] = { textContent: "", value: "0", dataset: {}, style: {} }); },
    String, Math, Number, Boolean, JSON, Promise, Object, Array, TypeError,
  };
  vm.createContext(context);
  vm.runInContext([
    functionSource("isIncomingRendererSession"),
    functionSource("localIsPlayingNow"),
    functionSource("setPlayButton"),
    functionSource("stopLocalAudio"),
    functionSource("controlIncomingRenderer"),
    functionSource("preemptIncomingRendererForLocalPlayback"),
    functionSource("refreshRendererSession"),
    "globalThis.h = { isIncomingRendererSession, localIsPlayingNow, stopLocalAudio, controlIncomingRenderer,"
    + " preempt: () => preemptIncomingRendererForLocalPlayback(), refresh: () => refreshRendererSession() };",
  ].join("\n"), context);
  return { ...context.h, state, audio, calls, nodes };
}

async function flush() {
  for (let index = 0; index < 20; index += 1) await Promise.resolve();
}

(async () => {
  // 1. Ruling D-1: the poll that first sees a cast stops whatever this browser was
  //    playing, on the element and on the host player alike, exactly once.
  const taken = setup();
  assert.equal(taken.localIsPlayingNow(), true, "sanity: the element is running before the cast");
  // Guards the stub above: the snapshot timestamp is only written after the loader
  // resolves, so this fails loudly if the poll ever becomes a silent no-op again.
  const staleSnapshot = taken.state.rendererSnapshotAt;
  await taken.refresh();
  assert.notEqual(taken.state.rendererSnapshotAt, staleSnapshot, "the poll really reached its write point");
  assert.ok(taken.calls.includes("audio.pause"), "The cast stops the local element");
  assert.ok(taken.calls.includes("audio.removeAttribute:src"), "and drops its source, not just its clock");
  assert.equal(taken.state.playSourceKind, "", "the local source kind goes with it");
  assert.equal(taken.nodes.playBtn.dataset.playing, "paused", "the icon follows the owner that just lost");
  assert.equal(taken.calls.filter(name => name === "audio.load").length, 1, "one teardown per takeover");
  assert.ok(taken.calls.includes(`paint-cast:${castUri}`), "the row is handed to the caster");
  assert.equal(taken.isIncomingRendererSession(), true, "the session is now the visible owner");

  // 1b. The same poll runs every 1.5s, and only the transition may stop anything -
  //     otherwise a stream that is already silent is torn down and reloaded once per
  //     tick.  The element is left *running* here on purpose: a host player reports its
  //     position one state callback behind the stop ruling D-1 issued, so "local
  //     playback still looks live under the same cast" is the ordinary second tick
  //     rather than a defect, and it must not buy another teardown.
  const polled = setup({ rendererSession: castSession(), rendererSnapshotAt: 1700000000000 });
  assert.equal(polled.localIsPlayingNow(), true,
    "sanity: the next tick can still see local playback running");
  await polled.refresh();
  assert.deepEqual(polled.calls.filter(name => name.startsWith("audio.")), [],
    "a repeated poll of the same cast must not touch the element again");
  assert.ok(polled.calls.includes(`paint-cast:${castUri}`), "while the row keeps following the cast");

  // 1c. The host player is covered by the same takeover.
  const host = setup({ nativePlayback: { supported: true, active: true, playing: true, position: 9, duration: 200 } });
  host.audio.paused = true;
  host.audio.src = "";
  await host.refresh();
  assert.ok(host.calls.includes("native:stop"), "the Android host decoder stops with the element");
  assert.equal(host.calls.filter(name => name === "native:stop").length, 1,
    "one host stop per takeover");
  // A takeover is not a preemption: only the local play intent (D-2) may leave a
  // claim behind, or the caster that just took the row would be ignored next poll.
  assert.equal(host.state.rendererPreemptedUri, "", "the takeover claims nothing for local playback");

  // 2. Ruling D-3: when the cast ends, the library row comes back and the transport
  //    icon is reset, but nothing resumes local playback - no load, no play.
  const ended = setup({
    rendererSession: castSession(),
    rendererSnapshotAt: 1700000000000,
    payload: { available: true, state: { uri: castUri, transport: "STOPPED", position: 100, duration: 100 } },
  });
  ended.nodes.playBtn.dataset.playing = "playing";
  await ended.refresh();
  assert.ok(ended.calls.includes("restore-library-row"), "the library row is restored");
  assert.equal(ended.nodes.playBtn.dataset.playing, "paused", "the icon does not keep the caster's state");
  assert.ok(ended.calls.includes("mediaPlayback"), "and neither does the host transport state");
  assert.deepEqual(ended.calls.filter(name => name === "loadCurrent" || name === "audio.play" || name === "native:play"), [],
    "an ended cast never restarts local playback by itself");
  assert.equal(ended.isIncomingRendererSession(), false, "the caster no longer owns the row");

  // 3. Ruling D-2: a local play intent drops the cast's claim synchronously and asks
  //    the bridge to stop exactly once. With no cast there is nothing to preempt and
  //    no request may leave the browser.
  const idle = setup();
  assert.equal(idle.preempt(), false, "no session, no preemption");
  assert.deepEqual(idle.calls.filter(name => name.startsWith("apiFetch")), [], "and no command sent either");
  assert.equal(idle.state.rendererPreemptedUri, "", "the claim stays empty");

  const casted = setup({ rendererSession: castSession(), rendererSnapshotAt: 1700000000000 });
  assert.equal(casted.preempt(), true, "a running cast is preempted by the local intent");
  assert.equal(casted.isIncomingRendererSession(), false, "the row is released before the caller continues");
  assert.equal(casted.state.rendererSnapshotAt, 0, "with the snapshot that described it");
  assert.equal(casted.state.rendererPreemptedUri, castUri, "and the uri remembered as preempted");
  await flush();
  assert.deepEqual(casted.calls.filter(name => name.startsWith("apiFetch")),
    [`apiFetch:api/playback/control:POST:{"target_id":"mpd","action":"stop","position":null}`],
    "exactly one best-effort stop for the preempted renderer");

  // 3b. The stop can lose the race - it was already on the wire, or the bridge refused
  //     it. The next poll must then treat that session as no session at all, or the
  //     caster would take the row back and silence the track this browser just loaded.
  const raced = setup({
    rendererPreemptedUri: castUri,
    payload: { available: true, state: castSession() },
  });
  assert.equal(raced.localIsPlayingNow(), true, "sanity: local playback is still running");
  await raced.refresh();
  assert.equal(raced.isIncomingRendererSession(), false, "the preempted cast does not come back");
  assert.deepEqual(raced.calls.filter(name => name.startsWith("paint-cast")), [], "and never repaints the row");
  assert.equal(raced.state.rendererPreemptedUri, castUri, "the claim holds while local playback runs");

  // 3c. The claim is deliberately narrow: a different uri is a new cast, local
  //     silence ends the user's claim, and either one restores normal takeover.
  const recast = setup({ rendererPreemptedUri: castUri, payload: { available: true, state: castSession({ uri: "http://cast/other.flac" }) } });
  await recast.refresh();
  assert.ok(recast.calls.includes("paint-cast:http://cast/other.flac"), "a new cast is adopted");
  assert.equal(recast.state.rendererPreemptedUri, "", "and the stale claim is dropped");

  const stopped = setup({ rendererPreemptedUri: castUri, payload: { available: true, state: castSession() } });
  stopped.audio.paused = true;
  await stopped.refresh();
  assert.ok(stopped.calls.includes(`paint-cast:${castUri}`), "with nothing playing locally the caster owns the row again");
  assert.equal(stopped.state.rendererPreemptedUri, "", "the claim lapsed instead of muting forever");

  // 4. Source wiring: the preemption sits inside the local branch of the load path,
  //    after the deliberate push-to-device return and before this browser touches its
  //    own element; the host keys route through the caster while it owns the row.
  const loadBody = blockSource(/^async function loadCurrent\(\) \{[\s\S]*?^\}/m, "loadCurrent");
  const remoteReturn = loadBody.indexOf("nativeRemoteEnter(true);");
  const preemptCall = loadBody.indexOf("preemptIncomingRendererForLocalPlayback();");
  const elementWrite = loadBody.indexOf("audio.src =");
  assert.ok(remoteReturn >= 0 && preemptCall > remoteReturn,
    "the push-to-device branch must return before anything preempts a cast");
  assert.ok(elementWrite > preemptCall, "the local element must not be started before the cast was released");
  const playHandler = blockSource(/setHandler\("play", \(\) => \{[\s\S]*?\n  \}\);/, "the MediaSession play handler");
  const pauseHandler = blockSource(/setHandler\("pause", \(\) => \{[\s\S]*?\n  \}\);/, "the MediaSession pause handler");
  for (const [handler, action] of [[playHandler, "play"], [pauseHandler, "pause"]]) {
    const routed = handler.indexOf(`controlIncomingRenderer("${action}")`);
    const local = handler.indexOf(action === "play" ? "audio" : "audio.pause()");
    assert.ok(routed >= 0 && (local < 0 || routed < local),
      `the host ${action} key must reach the caster before any local element call`);
  }
  const timeupdate = blockSource(/^audio\.ontimeupdate = \(\) => \{\n([\s\S]*?)^\};/m, "audio.ontimeupdate");
  assert.match(timeupdate, /item\?\.cue_track === true && !isIncomingRendererSession\(\)/,
    "a queued auto-advance is not a local play intent and must not preempt a cast");
  // The field is declared once, and exactly one statement in the file can ever put a
  // uri into it, so there is a single owner of the preemption claim.
  assert.equal((app.match(/^state\.rendererPreemptedUri = "";$/gm) || []).length, 1,
    "one declaration of the preempted claim");
  assert.equal((app.match(/state\.rendererPreemptedUri = (?!"";)\w+;/g) || []).length, 1,
    "one statement can claim a uri as preempted");
})().then(() => {
  console.log("Renderer ownership regression checks passed.");
}).catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
