// R572: client navigation must agree with the server's `next_track()`.
//
// The reported bug ("the last track repeats for ever, and next replays it") came
// from two places that did not agree: the client treated repeat "one" as "no
// next", and the native bridge navigated without looking at the queue at all.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");

function extracted(pattern, label) {
  const match = source.match(pattern);
  assert.ok(match, `${label} must stay extractable`);
  return match[0];
}

const nextSource = extracted(/^function nextIndex\([\s\S]*?^\}/m, "nextIndex");
const previousSource = extracted(/^function previousIndex\([\s\S]*?^\}/m, "previousIndex");

function build(state) {
  // The vm must see the *merged* object, otherwise mutating the returned state
  // afterwards would leave the sandbox reading its own copy.
  const merged = Object.assign({ queue: [], index: -1, repeat: "off", shuffle: false }, state);
  const context = { state: merged };
  vm.createContext(context);
  vm.runInContext([nextSource, previousSource,
    "globalThis.h = { next: () => nextIndex(), previous: () => previousIndex() };"].join("\n\n"), context);
  return { state: merged, h: context.h };
}

const three = [{ id: "a" }, { id: "b" }, { id: "c" }];

// Same table as tests/test_playback_core_state.py::test_next_track_respects_off_all_and_one_repeat_modes
{
  const q = build({ queue: three, index: 2, repeat: "off" });
  assert.equal(q.h.next(), -1, "off: the queue ends, it does not wrap");
  assert.equal(q.h.previous(), 1);

  q.state.repeat = "all";
  assert.equal(q.h.next(), 0, "all: wrap to the first row");
  q.state.index = 0;
  assert.equal(q.h.previous(), 2, "all: wrap backwards to the last row");

  q.state.repeat = "one";
  q.state.index = 2;
  assert.equal(q.h.next(), 2, "one: next restarts the current row, as the server does");
  assert.equal(q.h.previous(), 2, "one: previous restarts it too");
}

// The end of the queue, straight: nothing to move to.
for (const index of [0, 1, 2]) {
  const q = build({ queue: three, index, repeat: "off" });
  if (index < 2) assert.equal(q.h.next(), index + 1);
  else assert.equal(q.h.next(), -1);
}

{
  const empty = build({ queue: [], index: -1, repeat: "all" });
  assert.equal(empty.h.next(), -1, "an empty queue has nowhere to go");
  assert.equal(empty.h.previous(), -1);
}

{
  const single = build({ queue: [{ id: "only" }], index: 0, repeat: "off" });
  assert.equal(single.h.next(), -1, "a single row ends rather than replays");
  const singleAll = build({ queue: [{ id: "only" }], index: 0, repeat: "all" });
  assert.equal(singleAll.h.next(), 0, "all keeps a one-row queue alive");
}

{
  // Shuffle never returns the row it is on when there is a choice.
  const q = build({ queue: three, index: 1, repeat: "off", shuffle: true });
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const next = q.h.next();
    assert.ok(next >= 0 && next < 3 && next !== 1, "shuffle must pick a different row: " + next);
  }
}

console.log("Queue navigation regression checks passed (client == server).");
