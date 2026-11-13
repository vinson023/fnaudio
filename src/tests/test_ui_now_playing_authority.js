// The transport row must name the track the element is holding.
//
// Reported symptom: while a song was playing, the sound was right and the name
// became a *different* queue entry, most visibly right after 上一首 / 下一首.
// The position has two writers -- a track-changing command and every other
// reply that echoes the core's `current` -- and only the first one is a
// statement about this client. This pins that split, and pins the queue echo to
// the id the save asked for rather than to whatever the server had moved on to.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the now-playing regression`);
  return match[0];
}

const queue = () => [{ id: "a" }, { id: "b" }, { id: "c" }];

function setup(overrides) {
  const calls = [];
  const state = {
    index: 0,
    queue: queue(),
    repeat: "off",
    shuffle: false,
    mode: "local",
    ...overrides,
  };
  const context = {
    state,
    calls,
    isRemoteTarget: () => state.mode === "remote",
    updateRepeatShuffleButtons: () => calls.push("buttons"),
    updateFavoriteControls: () => calls.push("favorites"),
    resetPlaybackProgress: () => calls.push("resetProgress"),
    loadCurrent: () => calls.push("loadCurrent"),
    // Mirrors the real guard: the row is only repainted when the position actually moved.
    syncCurrentQueuePresentation: previous => {
      if (previous !== state.index) calls.push(`presentation:${previous}`);
    },
    String,
  };
  vm.createContext(context);
  vm.runInContext([
    functionSource("applyCoreSnapshot"),
    functionSource("applyConfirmedQueue"),
    "globalThis.g = { core: (...args) => applyCoreSnapshot(...args), confirmed: (...args) => applyConfirmedQueue(...args) };",
  ].join("\n"), context);
  return { ...context, state, calls };
}

// 1. The regression itself: a non-transport reply moved the position to another
//    queue entry, and the next repaint named that entry while the element kept
//    playing the previous one.
const playing = setup({ index: 0 });
playing.calls.length = 0;
playing.g.core({ current: "c" }, false);
assert.equal(playing.state.index, 0, "A play/pause/seek/repeat/shuffle reply must not move the position");
assert.deepEqual(playing.calls.filter(name => name === "loadCurrent"), [], "It must not load either");
assert.deepEqual(playing.calls.filter(name => name === "presentation:0"), [], "Nothing to repaint for the row");

// 2. The same reply still carries the mode flags, which is why it is read at all.
const flags = setup({ index: 0, repeat: "off", shuffle: false });
flags.g.core({ current: "c", repeat: "all", shuffle: true }, false);
assert.equal(flags.state.repeat, "all", "Repeat still comes from the reply");
assert.equal(flags.state.shuffle, true, "Shuffle still comes from the reply");
assert.equal(flags.state.index, 0, "The position still does not");

// 3. A track-changing command is the one reply that may move it, and it loads.
const stepped = setup({ index: 0 });
stepped.calls.length = 0;
stepped.g.core({ current: "b" }, true);
assert.equal(stepped.state.index, 1, "上一首/下一首 adopt the new track");
assert.deepEqual(stepped.calls, ["buttons", "resetProgress", "loadCurrent", "presentation:0", "favorites"],
  "The load path runs in the same order as before");

// 4. A remote target has no local element to describe, so its snapshot stays
//    authoritative -- otherwise the guard above would freeze the row.
const remote = setup({ index: 0, mode: "remote" });
remote.g.core({ current: "c" }, false);
assert.equal(remote.state.index, 2, "A device that plays on its own still moves the row");

// 5. An explicit opt-in exists for the one caller that means it (boot restore of
//    a remote session is covered by 4; this keeps the switch honest).
const opted = setup({ index: 0 });
opted.g.core({ current: "b" }, false, { adoptPosition: true });
assert.equal(opted.state.index, 1, "adoptPosition still adopts");

// 6. A reply without a usable current changes nothing.
for (const core of [null, {}, { current: "" }, { state: { current: "zz" } }]) {
  const probe = setup({ index: 1 });
  assert.equal(probe.g.core(core, true), false, `An unusable reply reports no change: ${JSON.stringify(core)}`);
  assert.equal(probe.state.index, 1, "And leaves the position alone");
}

// 7. The queue echo: the save asked for "c" while the server had already moved
//    to "a" (another command landed in flight). Trusting the echo rolled the
//    position back to the outgoing track.
const echo = setup({ index: 0 });
echo.g.confirmed(queue(), { current: "a", repeat: "off" }, "c");
assert.equal(echo.state.index, 2, "The requested id wins over the echo");

// 8. Without a requested id the echo is all there is.
const plainEcho = setup({ index: 0 });
plainEcho.g.confirmed(queue(), { current: "b" }, "");
assert.equal(plainEcho.state.index, 1, "The echo is used when the caller named no track");

// 9. A requested id that is no longer in the queue falls back to the echo, then
//    to the head -- a queue edit can legitimately remove the track mid-save.
const gone = setup({ index: 0 });
gone.g.confirmed(queue(), { current: "b" }, "zz");
assert.equal(gone.state.index, 1, "A vanished request falls back to the echo");
const empty = setup({ index: 0 });
empty.g.confirmed(queue(), { current: "zz" }, "zz");
assert.equal(empty.state.index, 0, "With neither, the queue head is the row");
const cleared = setup({ index: 2 });
cleared.g.confirmed([], { current: "" }, "");
assert.equal(cleared.state.index, -1, "A cleared queue has no position to report");

console.log("Now-playing authority regression checks passed.");
