const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the authority regression`);
  return match[0];
}
function constSource(name) {
  const match = app.match(new RegExp("^const " + name + " = [^\\n]+", "m"));
  assert.ok(match, `const ${name} must stay extractable for the authority regression`);
  return match[0];
}

const handler = app.match(/^audio\.ontimeupdate = \(\) => \{[\s\S]*?^\};/m);
assert.ok(handler, "audio.ontimeupdate must stay extractable for the authority regression");

const commitQueueSource = app.match(/^async function commitQueue\([\s\S]*?^\}/m);
assert.ok(commitQueueSource, "commitQueue must stay extractable for the host handoff regression");

// Shape: the cue-tail decision reads the local pair, the painting keeps reading
// the shared getters (a cast in progress has to be able to move the visible row).
assert.match(handler[0], /const localSeconds = localPlaybackSeconds\(\);[\s\S]*const localDuration = localPlaybackDuration\(\);/, "The cue check must take the local pair");
assert.match(handler[0], /localSeconds >= Math\.max\(0, localDuration - 0\.25\)/, "The cue check must compare local against local");
assert.doesNotMatch(handler[0], /currentSeconds\(\) >= Math\.max\(0, duration - 0\.25\)/, "A cast must not be able to advance the local queue");
assert.match(handler[0], /setTextContentIfChanged\(\$\("elapsed"\), clock\(currentSeconds\(\)\)\)/, "Painting stays on the shared getter");
assert.match(app, /function seekDuration\(\) \{\n  if \(isIncomingRendererSession\(\)\) return playbackSeconds\(state\.rendererSession\.duration\);/, "The renderer display path keeps the caster's length");
assert.equal((app.match(/function localPlaybackSeconds\(\) \{/g) || []).length, 1, "One local-seconds authority");
assert.equal((app.match(/function localPlaybackDuration\(\) \{/g) || []).length, 1, "One local-duration authority");
assert.equal((app.match(/function localIsPlayingNow\(\) \{/g) || []).length, 1, "One local-playing authority");
assert.equal((app.match(/audio\.src && !audio\.paused/g) || []).length, 1, "The local-playing tail exists exactly once");
assert.match(app, /function isPlayingNow\(\) \{[\s\S]*?\n  return localIsPlayingNow\(\);\n\}/, "isPlayingNow ends by delegating to the local oracle");
// The queue handoff to the Android host is a decision about the host player, not
// about whatever a caster is doing.
assert.match(app, /nativeLoadQueue\(localIsPlayingNow\(\), localPlaybackSeconds\(\), true\);/, "The host handoff reports the local player");
assert.doesNotMatch(app, /nativeLoadQueue\(isPlayingNow\(\), currentSeconds\(\)/, "The host handoff must not report the caster");
assert.equal((app.match(/return localPlaybackSeconds\(\);/g) || []).length, 1, "currentSeconds delegates once, it does not keep a second copy");
assert.match(app, /function currentSeconds\(\) \{[\s\S]*?\n  return localPlaybackSeconds\(\);\n\}/, "currentSeconds ends by delegating to the local authority");
assert.match(app, /function seekDuration\(\) \{[\s\S]*?remoteDuration > cueStart \? remoteDuration - cueStart : 0;[\s\S]*?\n\}/, "seekDuration keeps its own remote cue arithmetic");

function clock(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

function setup(overrides) {
  const calls = [];
  const nodes = {};
  const audio = {
    currentTime: 0,
    duration: NaN,
    paused: false,
    ended: false,
    src: "",
    ontimeupdate: null,
    pause() { calls.push("audio.pause"); audio.paused = true; },
  };
  const state = {
    index: 3,
    rendererSession: null,
    rendererSnapshotAt: 0,
    remoteStatus: null,
    remoteSnapshotAt: 0,
    remoteBaseSeconds: 0,
    remoteCueSegment: false,
    item: null,
    mode: "local",
    seeking: false,
    playSourceKind: "",
    streamOffset: 0,
    pendingSeekTime: 12,
    transcodeCacheReady: true,
    repeat: "none",
    shuffle: false,
    userStateRevision: 3,
    nativePlayback: { supported: false, active: false, playing: false, mediaId: "", position: 0, duration: 0 },
    next: 4,
    ...overrides,
  };
  const context = {
    state,
    audio,
    calls,
    nodes,
    Date: { now: () => 1_700_000_000_000 },
    $(id) { return nodes[id] || (nodes[id] = { textContent: "", value: "0" }); },
    currentItem: () => state.item,
    isRemoteTarget: () => state.mode === "remote",
    isIncomingRendererSession: () => Boolean(state.rendererSession && state.rendererSession.uri),
    nativePlaybackAvailable: () => Boolean(state.nativePlayback.supported && state.nativePlayback.active),
    nextIndex: () => state.next,
    loadCurrent: () => calls.push("loadCurrent"),
    syncCurrentQueuePresentation: previous => calls.push(`presentation:${previous}`),
    updateMediaSessionPlaybackState: () => calls.push("mediaPlayback"),
    updateMediaSessionPosition: () => calls.push("mediaPosition"),
    syncPlayerProgress: () => calls.push("playerProgress"),
    updateLyricHighlight: () => calls.push("lyrics"),
    setTextContentIfChanged: (node, value) => { if (node) node.textContent = value === null || value === undefined ? "" : String(value); },
    setStyleVarIfChanged: () => {},
    seekPercent: value => Number(value) || 0,
    transportExtrapolation: () => 0,
    apiFetch: async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ ok: true, core: { queue: ["a"] }, revision: 7 }),
    }),
    applyConfirmedQueue: () => calls.push("applyConfirmedQueue"),
    nativeLoadQueue: (autoPlay, startSeconds, force) => calls.push(`nativeLoadQueue:${autoPlay}:${startSeconds}:${force}`),
    userStateRevision: (value, fallback = 0) => (typeof value === "number" ? value : fallback),
    scheduleUserStateSave: () => calls.push("scheduleUserStateSave"),
    clock,
  };
  vm.createContext(context);
  vm.runInContext([
    functionSource("playbackSeconds"),
    constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS"),
    functionSource("localPlaybackSeconds"),
    functionSource("localPlaybackDuration"),
    functionSource("currentSeconds"),
    functionSource("seekDuration"),
    functionSource("isPlayingNow"),
    functionSource("localIsPlayingNow"),
    commitQueueSource,
    handler[0],
    "globalThis.g = { run: audio.ontimeupdate, commit: (...args) => commitQueue(...args), currentSeconds, seekDuration, localPlaybackSeconds, localPlaybackDuration, isPlayingNow, localIsPlayingNow };",
  ].join("\n"), context);
  return { ...context.g, state, audio, calls, nodes };
}

function castSession(overrides) {
  return { uri: "http://cast/track.flac", transport: "PLAYING", position: 99.9, duration: 100, ...overrides };
}
function cueItem() {
  return { id: "cue", cue_track: true, cue_start: 10, duration: 20 };
}

// 1. A caster reaching its end must not advance this browser's queue.  Before the
//    fix both getters answered 99.9/100 here, the cue tail matched, and the local
//    index walked on to the next track.
const cast = setup({ rendererSession: castSession(), rendererSnapshotAt: 1_700_000_000_000, item: cueItem() });
cast.audio.currentTime = 5;
cast.run();
assert.equal(cast.state.index, 3, "A finished cast must not advance the local queue");
assert.deepEqual(cast.calls.filter(name => name === "loadCurrent" || name === "audio.pause" || name === "mediaPlayback"), [], "No queue action at all");
assert.equal(cast.nodes.elapsed.textContent, "1:39", "The visible row still follows the caster");
assert.equal(cast.nodes.seek.value, 99.9, "The rail still follows the caster too");

// 2. Local cue playback still advances at its own tail.
const local = setup({ item: cueItem() });
local.audio.currentTime = 29.9;
local.run();
assert.equal(local.state.index, 4, "The local cue tail still advances the queue");
assert.deepEqual(local.calls, ["presentation:3", "loadCurrent"]);
assert.equal(local.state.playSourceKind, "", "The advance resets the source kind");
assert.equal(local.state.pendingSeekTime, null, "The advance clears a pending seek");
assert.equal(local.state.transcodeCacheReady, false, "The advance invalidates the transcode cache");

// 3. Both at once: cast on screen *and* the local element at its own tail.
const both = setup({ rendererSession: castSession({ position: 5, duration: 300 }), item: cueItem() });
both.audio.currentTime = 29.95;
both.run();
assert.equal(both.state.index, 4, "A local tail advances even while a cast is on screen");

// 4. Nothing to advance to: pause instead of walking off the end.
const last = setup({ next: -1, item: cueItem() });
last.audio.currentTime = 30;
last.run();
assert.equal(last.state.index, 3, "The index stays on the final track");
assert.deepEqual(last.calls, ["audio.pause", "mediaPlayback"]);

// 5. The Android host player is the other local authority.
const native = setup({
  nativePlayback: { supported: true, active: true, position: 19.95, duration: 20 },
  item: cueItem(),
});
assert.equal(native.localPlaybackSeconds(), 19.95, "Native position wins over the element clock");
assert.equal(native.localPlaybackDuration(), 20, "Native duration wins over the element clock");
native.run();
assert.equal(native.state.index, 4, "A native host tail advances the queue");

// 6. Stream sources keep their own arithmetic: offset in, cue start out.
const stream = setup({ playSourceKind: "stream", streamOffset: 15, item: cueItem() });
stream.audio.currentTime = 4.95;
assert.equal(stream.localPlaybackSeconds(), 19.95, "A stream position is offset plus element clock");
stream.run();
assert.equal(stream.state.index, 4, "A stream tail advances the queue");

// 6b. The cue tail is measured from the segment start, never from the file
//     position: 25 s into a file whose segment starts at 10 s is 15 s of a 20 s
//     segment, so nothing may advance yet.
const midCue = setup({ item: cueItem() });
midCue.audio.duration = 300;
midCue.audio.currentTime = 25;
assert.equal(midCue.localPlaybackSeconds(), 15, "The cue offset is subtracted from the element clock");
assert.equal(midCue.localPlaybackDuration(), 20, "The segment length wins over the whole-file duration");
midCue.run();
assert.equal(midCue.state.index, 3, "Mid-segment never advances");

// 7. A remote target is still excluded before anything is read.
const remote = setup({ mode: "remote", item: cueItem() });
remote.audio.currentTime = 30;
remote.run();
assert.deepEqual(remote.calls, [], "A remote target never reaches the local cue check");
assert.equal(remote.state.index, 3);
// 7b. The guard is the runtime half of the "caller has already excluded remote"
//     contract (TODO.md:49): a direct call under a remote target must fail
//     loudly instead of answering with the local item's length, and an
//     *incoming* render session must stay outside the guard -- scenarios 1/3/9
//     call through it on purpose while painting the caster's transport row.
assert.throws(() => remote.localPlaybackDuration(),
  /requires a caller that excluded remote playback/,
  "A direct call under a remote target must not answer with the local length");
assert.doesNotThrow(() => cast.localPlaybackDuration(),
  "An incoming render session is deliberately not a remote target here");
assert.equal(cast.localPlaybackDuration(), 20, "It still answers with the local track's own length");

// 8. The extraction must be behaviour-preserving for every non-cast state: the
//    local getters equal the shared ones whenever neither a render session nor a
//    remote target owns the answer.
for (const cue of [false, true]) {
  for (const kind of ["", "stream", "cue_segment"]) {
    for (const useNative of [false, true]) {
      for (const audioDuration of [NaN, 88]) {
        const shape = { cue, kind, useNative, audioDuration };
        const probe = setup({
          playSourceKind: kind,
          streamOffset: 7,
          nativePlayback: { supported: true, active: useNative, position: 11, duration: 44 },
          item: cue ? cueItem() : { id: "plain", duration: 20 },
        });
        probe.audio.currentTime = 6.5;
        probe.audio.duration = audioDuration;
        const label = JSON.stringify(shape);
        assert.equal(probe.localPlaybackSeconds(), probe.currentSeconds(), `seconds agree for ${label}`);
        assert.equal(probe.localPlaybackDuration(), probe.seekDuration(), `duration agrees for ${label}`);
      }
    }
  }
}

// 9. And they must disagree exactly when a render session owns the display, or
//    the guard above would be dead code.
const split = setup({ rendererSession: castSession({ position: 70, duration: 100 }), item: cueItem() });
split.audio.currentTime = 3;
assert.equal(split.currentSeconds(), 70, "The shared getter follows the caster");
assert.equal(split.localPlaybackSeconds(), 0, "The local getter follows the element, clamped at the cue start");
assert.equal(split.localPlaybackDuration(), 20);
assert.equal(split.seekDuration(), 100);
split.run();
assert.equal(split.state.index, 3, "The caster's mid-stream position never advances the queue");

// 10. The same split for the transport-state oracle used by the host handoff:
//     identical while nothing is being cast, and deliberately different when a
//     render session owns the audible output.
for (const useNative of [false, true]) {
  for (const hostPlaying of [false, true]) {
    for (const localState of [{ src: "", paused: true, ended: false }, { src: "http://x/s.flac", paused: false, ended: false }, { src: "http://x/s.flac", paused: true, ended: true }]) {
      const probe = setup({ nativePlayback: { supported: true, active: useNative, playing: hostPlaying, position: 4, duration: 40 } });
      Object.assign(probe.audio, localState);
      const label = `${useNative}/${hostPlaying}/${JSON.stringify(localState)}`;
      assert.equal(probe.localIsPlayingNow(), probe.isPlayingNow(), `playing state agrees with no cast for ${label}`);
      if (!useNative && !localState.paused && !localState.ended && localState.src) {
        assert.equal(probe.localIsPlayingNow(), true, `a running element reports playing for ${label}`);
      }
    }
  }
}
const castPlaying = setup({
  rendererSession: castSession({ transport: "PLAYING" }),
  nativePlayback: { supported: true, active: true, playing: false, position: 4, duration: 40 },
});
assert.equal(castPlaying.isPlayingNow(), true, "The shared oracle follows the caster");
assert.equal(castPlaying.localIsPlayingNow(), false, "The host oracle reports the host player");
const castPaused = setup({
  rendererSession: castSession({ transport: "PAUSED_PLAYING" }),
  nativePlayback: { supported: true, active: true, playing: true, position: 4, duration: 40 },
});
assert.equal(castPaused.isPlayingNow(), false, "A paused cast is not local playback");
assert.equal(castPaused.localIsPlayingNow(), true, "The host keeps its own running state");

// 11. The host handoff itself.  commitQueue reloads the Android host player when
//     the queue changed under the track it is playing; with a cast on screen it
//     used to be told the caster's transport state and position.
(async () => {
  const casting = setup({
    rendererSession: castSession({ transport: "PLAYING", position: 70, duration: 100 }),
    item: { id: "cue", cue_track: true, cue_start: 10, duration: 20 },
    nativePlayback: { supported: true, active: true, playing: false, mediaId: "cue", position: 12.5, duration: 20 },
  });
  assert.equal(casting.isPlayingNow(), true, "sanity: the shared oracle still follows the caster");
  await casting.commit([{ id: "cue" }], "cue", {});
  assert.deepEqual(casting.calls, ["applyConfirmedQueue", "nativeLoadQueue:false:12.5:true", "scheduleUserStateSave"],
    "The host is described by the host, not by the cast");
  assert.equal(casting.state.userStateRevision, 7, "The revision bookkeeping still runs");

  const plain = setup({
    item: { id: "cue", cue_track: true, cue_start: 10, duration: 20 },
    nativePlayback: { supported: true, active: true, playing: true, mediaId: "cue", position: 12.5, duration: 20 },
  });
  await plain.commit([{ id: "cue" }], "cue", {});
  assert.deepEqual(plain.calls, ["applyConfirmedQueue", "nativeLoadQueue:true:12.5:true", "scheduleUserStateSave"],
    "Without a cast the handoff is unchanged");

  const otherMedia = setup({
    item: { id: "cue", cue_track: true, cue_start: 10, duration: 20 },
    nativePlayback: { supported: true, active: true, playing: true, mediaId: "something-else", position: 12.5, duration: 20 },
  });
  await otherMedia.commit([{ id: "cue" }], "cue", {});
  assert.deepEqual(otherMedia.calls, ["applyConfirmedQueue", "scheduleUserStateSave"],
    "A host playing another track is not reloaded");
})().then(() => {
  console.log("Playback authority regression checks passed.");
}).catch(error => {
  console.error(error && error.message ? error.message : error);
  process.exitCode = 1;
});
