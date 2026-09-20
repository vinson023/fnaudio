const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the remote-unit regression`);
  return match[0];
}
function constSource(name) {
  const match = app.match(new RegExp("^const " + name + " = [^\\n]+", "m"));
  assert.ok(match, `const ${name} must stay extractable for the remote-unit regression`);
  return match[0];
}

// Shape: the unit of the remote seconds is written in five places - two resets,
// the declared snapshot, its fallback, and the optimistic load projection.  Any
// additional writer would let a second copy disagree with the backend.
assert.equal((app.match(/state\.remoteCueSegment = /g) || []).length, 5, "The remote unit keeps exactly five writers");
// The declaration test must stay strict: a truthy string would silence the fallback.
assert.match(app, /const declaredCueSegment = data\.cue_segment === true \|\| data\.cue_segment === false;/, "A declared unit must be recognised by identity, not truthiness");
assert.match(app, /if \(declaredCueSegment\) state\.remoteCueSegment = data\.cue_segment === true;/, "A declared unit must be taken from the frame");
assert.match(app, /if \(!declaredCueSegment\) state\.remoteCueSegment = /, "Only an undeclared frame may fall back to local metadata");
// Every site that mixes a declaration with a derivation must refuse to let the
// derivation override a declared false, or the two routes disagree by arrival.
assert.equal((app.match(/data\.cue_segment === true/g) || []).length, 3, "Three reads of the declaration: gate, snapshot, load");
assert.equal((app.match(/data\.cue_segment !== false/g) || []).length, 1, "The load projection guards its fallback with the same rule");

const now = 1_700_000_000_000;
const state = {};
const calls = [];
const context = {
  state,
  Date: { now: () => now },
  isRemoteTarget: () => state.mode === "remote",
  isIncomingRendererSession: () => false,
  isDacTarget: () => state.dac === true,
  nativePlaybackAvailable: () => false,
  currentItem: () => state.queue[state.index],
  syncCurrentQueuePresentation: (previous) => calls.push(previous),
  maybeAdvanceRemoteQueue: () => calls.push("advance"),
  updateRemoteUi: () => calls.push("ui"),
  nativeRemoteUpdate: () => calls.push("native"),
  audio: { currentTime: 0, duration: NaN },
};
vm.createContext(context);
vm.runInContext([
  functionSource("playbackSeconds"),
  functionSource("remoteStateVersion"),
  constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS"),
  functionSource("transportExtrapolation"),
  functionSource("seekDuration"),
  functionSource("currentSeconds"),
  functionSource("applyRemotePlaybackSnapshot"),
  "globalThis.harness = { applyRemotePlaybackSnapshot, currentSeconds, seekDuration };",
].join("\n"), context);
const harness = context.harness;

// 100s into the source file, this segment is 30s long; the backend reports 42s
// of a 300s stream because it already folded the offset out.
const SEGMENT = { id: "cue-2", cue_track: true, cue_start: 100, duration: 0 };

function reset(index) {
  state.mode = "remote";
  state.dac = false;
  state.playTarget = "mpd:usb";
  state.queue = [SEGMENT];
  state.index = index;
  state.remoteStatus = null;
  state.remoteStateVersion = 0;
  state.remoteGeneration = 0;
  state.remoteEngineEpoch = 0;
  state.remoteSnapshotAt = 0;
  state.remoteBaseSeconds = 0;
  state.remoteCueSegment = false;
  calls.length = 0;
}
function observed() {
  return {
    cueSegment: state.remoteCueSegment,
    seconds: harness.currentSeconds(),
    duration: harness.seekDuration(),
    version: state.remoteStateVersion,
  };
}
function frame(overrides) {
  return {
    target_id: "mpd:usb",
    state_version: 5,
    cue_segment: true,
    position: { rel_seconds: 42, duration_seconds: 300 },
    core: { current: "cue-2" },
    ...overrides,
  };
}

// The server states the unit, so the bar shows the segment as the backend wrote
// it.  Under the old derivation the same frame left remoteCueSegment false and
// both getters subtracted cue_start a second time.
reset(0);
harness.applyRemotePlaybackSnapshot(frame());
assert.equal(state.remoteCueSegment, true, "A declared segment stays declared");
assert.equal(harness.currentSeconds(), 42, "The folded position must not lose cue_start again");
assert.equal(harness.seekDuration(), 300, "The folded duration is the segment length");
assert.equal(state.remoteBaseSeconds, 42);
assert.equal(state.remoteStateVersion, 5);
assert.deepEqual(observed(), { cueSegment: true, seconds: 42, duration: 300, version: 5 });

// Both consumers read the one flag: without the declaration the subtraction
// returns, which is what discriminates the two sides of the fix.
state.remoteCueSegment = false;
assert.equal(harness.seekDuration(), 200, "An undeclared remote duration still folds cue_start");
assert.equal(harness.currentSeconds(), 0, "currentSeconds and seekDuration share the flag");

// The frame must answer the same way whether or not the row was already indexed
// when it arrived: SSE and a poll are two routes for one logical snapshot.
reset(0);
harness.applyRemotePlaybackSnapshot(frame());
const indexedFirst = observed();
reset(-1);
harness.applyRemotePlaybackSnapshot(frame());
assert.deepEqual(observed(), indexedFirst, "Arrival order must not change the projected unit");
assert.deepEqual(calls, [-1, "advance", "ui", "native"], "The newly indexed row still syncs its presentation once");

// A declared false is authoritative even where local metadata says otherwise:
// this is the whole-file/segment pair that used to disagree between the routes.
reset(-1);
harness.applyRemotePlaybackSnapshot(frame({ cue_segment: false, state_version: 6 }));
assert.equal(state.remoteCueSegment, false, "The backend unit beats queue metadata");
assert.equal(harness.seekDuration(), 200, "A whole-file duration is still folded locally");

// An older server sends no declaration at all: the fallback keeps working, and it
// still refuses to fold for a DAC, which is seeked in whole-file seconds.
reset(-1);
harness.applyRemotePlaybackSnapshot({ target_id: "mpd:usb", state_version: 7, position: { rel_seconds: 42, duration_seconds: 300 }, core: { current: "cue-2" } });
assert.equal(state.remoteCueSegment, true, "Without a declaration a cue item is a segment");
assert.equal(harness.seekDuration(), 300, "The fallback keeps the pre-declaration arithmetic verbatim");
reset(-1);
state.dac = true;
harness.applyRemotePlaybackSnapshot({ target_id: "mpd:usb", state_version: 7, position: { rel_seconds: 42, duration_seconds: 300 }, core: { current: "cue-2" } });
assert.equal(state.remoteCueSegment, false, "A DAC target never folds a second time");

// Monotonic versioning: a newer poll is accepted, an older one is dropped.
reset(0);
harness.applyRemotePlaybackSnapshot(frame({ state_version: 11, position: { rel_seconds: 60, duration_seconds: 300 } }));
assert.equal(state.remoteStateVersion, 11);
assert.equal(harness.currentSeconds(), 60);
harness.applyRemotePlaybackSnapshot(frame({ state_version: 10, position: { rel_seconds: 99, duration_seconds: 300 } }));
assert.equal(state.remoteStateVersion, 11, "An older version must not rewind the bar");
assert.equal(harness.currentSeconds(), 60);
harness.applyRemotePlaybackSnapshot(frame({ state_version: "12", position: { rel_seconds: 70, duration_seconds: 300 } }));
assert.equal(state.remoteStateVersion, 12, "A poll frame carrying its version as text is still ordered");
assert.equal(harness.currentSeconds(), 70, "The text version must not cost the client its position");

console.log("remote cue unit checks passed");
