const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the staleness regression`);
  return match[0];
}
function constSource(name) {
  const match = app.match(new RegExp("^const " + name + " = [^\\n]+", "m"));
  assert.ok(match, `const ${name} must stay extractable for the staleness regression`);
  return match[0];
}

// Shape invariants: the wall-clock delta must exist in exactly one place, and
// neither transport branch may recompute it by hand again.
assert.doesNotMatch(app, /Date\.now\(\) - state\.rendererSnapshotAt/, "The render session must not extrapolate inline");
assert.doesNotMatch(app, /Date\.now\(\) - state\.remoteSnapshotAt/, "The remote target must not extrapolate inline");
assert.equal((app.match(/transportExtrapolation\(state\./g) || []).length, 2, "Both transport branches go through the one gate");
assert.equal((app.match(/Math\.min\(elapsed, TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS\)/g) || []).length, 1, "There is exactly one clamp");

let now = 1_700_000_000_000;
const state = {
  rendererSession: null,
  rendererSnapshotAt: 0,
  remoteStatus: null,
  remoteSnapshotAt: 0,
  remoteBaseSeconds: 0,
  remoteCueSegment: false,
  item: null,
  mode: "",
};
const context = {
  state,
  Date: { now: () => now },
  isIncomingRendererSession: () => Boolean(state.rendererSession && state.rendererSession.uri),
  isRemoteTarget: () => state.mode === "remote",
  nativePlaybackAvailable: () => false,
  currentItem: () => state.item,
  audio: { currentTime: 0, duration: NaN },
};
vm.createContext(context);
vm.runInContext([
  functionSource("playbackSeconds"),
  constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS"),
  functionSource("transportExtrapolation"),
  functionSource("seekDuration"),
  functionSource("currentSeconds"),
  "globalThis.harness = { currentSeconds, seekDuration, transportExtrapolation, limit: TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS };",
].join("\n"), context);
const harness = context.harness;

// The limit has to sit between "one slow poll" and "an obviously dead session":
// freezing earlier would stutter the bar on normal latency, later would let the
// display keep inventing minutes.
assert.ok(harness.limit >= 2, "the clamp must survive at least one slow poll round");
assert.ok(harness.limit <= 30, "the clamp must stay inside one maximum job budget");

const direct = harness.transportExtrapolation;
assert.equal(direct(0, true), 0, "A session without an accepted snapshot must not extrapolate");
assert.equal(direct(now - 1000, false), 0, "PAUSED never extrapolates");
assert.equal(direct(now - 1000, true), 1, "A fresh snapshot extrapolates by its real age");
assert.equal(direct(now - 9 * 1000, true), 9, "Anything inside the window is trusted");
assert.equal(direct(now - 60000, true), harness.limit, "Beyond the window the guess stops growing");
assert.equal(direct(now + 60000, true), 0, "A backward clock step must not subtract");
assert.equal(direct("recent", true), 0, "A non-numeric stamp is not a snapshot");
assert.equal(direct(NaN, true), 0, "NaN is not a snapshot");

function rendererSession(overrides) {
  state.item = null;
  state.mode = "renderer";
  state.rendererSession = { uri: "http://render/track.flac", transport: "PLAYING", position: 12, duration: 100, ...overrides };
  state.remoteStatus = null;
}

rendererSession({});
state.rendererSnapshotAt = now - 2000;
assert.equal(harness.currentSeconds(), 14, "A two second old snapshot still tracks the device");
state.rendererSnapshotAt = now - 30000;
assert.equal(harness.currentSeconds(), 12 + harness.limit, "A dead session freezes at the window edge");
assert.ok(harness.currentSeconds() < harness.seekDuration(), "A stale render session must not stick the rail at full");
state.rendererSession.transport = "PAUSED_PLAYBACK";
assert.equal(harness.currentSeconds(), 12, "Pausing holds the last reported position");
state.rendererSession.transport = "PLAYING";
state.rendererSnapshotAt = now + 240000;
assert.equal(harness.currentSeconds(), 12, "Clock skew must not pull the position backwards");
state.rendererSnapshotAt = 0;
assert.equal(harness.currentSeconds(), 12, "No snapshot means no guess");

// The shape that made this a defect rather than a cosmetic question: with no
// reported duration there is nothing to clamp against, so an unreachable
// renderer counted upwards forever (a "4:37" label on a track the UI never
// learned the length of).
state.rendererSnapshotAt = now - 20 * 60 * 1000;
rendererSession({ duration: 0 });
state.rendererSnapshotAt = now - 20 * 60 * 1000;
assert.equal(harness.currentSeconds(), 12 + harness.limit, "An unknown duration stays bounded");
const unknownAgain = harness.currentSeconds();
now += 10 * 60 * 1000;
assert.equal(harness.currentSeconds(), unknownAgain, "Time passing on a dead session must not move the bar");
assert.ok(unknownAgain < 60, "The unbounded creep must be impossible");

function remoteTarget(overrides) {
  state.rendererSession = null;
  state.mode = "remote";
  state.remoteStatus = { transport: { state: "PLAYING" }, position: { rel_seconds: 30, duration_seconds: 100 }, ...overrides };
  state.remoteBaseSeconds = 30;
  state.remoteSnapshotAt = now - 1000;
}

remoteTarget({});
assert.equal(harness.currentSeconds(), 31, "The remote branch tracks a fresh snapshot the same way");
state.remoteSnapshotAt = now - 300000;
assert.equal(harness.currentSeconds(), 30 + harness.limit, "The remote branch freezes at the same window");
remoteTarget({ position: { rel_seconds: 30, duration_seconds: 0 } });
state.remoteSnapshotAt = now - 300000;
assert.equal(harness.currentSeconds(), 30 + harness.limit, "An outbound session with no duration is bounded too");
state.item = { cue_track: true, cue_start: 10, duration: 100 };
state.remoteCueSegment = true;
remoteTarget({});
state.remoteSnapshotAt = now - 300000;
assert.equal(harness.currentSeconds(), 30 + harness.limit, "A cue segment keeps the same bound");
state.item = { cue_track: true, cue_start: 10, duration: 100 };
state.remoteCueSegment = false;
state.remoteSnapshotAt = now - 1000;
assert.equal(harness.currentSeconds(), 31 - 10, "A cue track still subtracts its segment start");

// The negative-position shape: a backward clock on a non-cue remote track used
// to return the raw signed sum.
state.item = null;
remoteTarget({});
state.remoteBaseSeconds = 5;
state.remoteSnapshotAt = now + 60000;
assert.equal(harness.currentSeconds(), 5, "A backward clock step cannot report a negative position");
assert.ok(harness.currentSeconds() >= 0);

console.log("Transport snapshot staleness regression checks passed.");
