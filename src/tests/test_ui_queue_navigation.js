// R572: client navigation must agree with the server's `next_track()`.
//
// The reported bug ("the last track repeats for ever, and next replays it") came
// from two places that did not agree: the client treated repeat "one" as "no
// next", and the native bridge navigated without looking at the queue at all.
//
// R587 moved the arithmetic into app/ui/queue_order_policy.js so the server and
// the page run one table.  The extracted functions now resolve that table first
// and only fall back to inline arithmetic if the script failed to load, so the
// sandbox has to carry the policy -- and this file checks both paths, because a
// broken fallback would leave a page that cannot navigate at all.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");
const policySource = fs.readFileSync("app/ui/queue_order_policy.js", "utf8");

function extracted(pattern, label) {
  const match = source.match(pattern);
  assert.ok(match, `${label} must stay extractable`);
  return match[0];
}

const maxItemsSource = extracted(/^const QUEUE_ORDER_MAX_ITEMS = \d+;/m, "QUEUE_ORDER_MAX_ITEMS");
const resolverSource = extracted(/^function queueOrderPolicy\([\s\S]*?^\}/m, "queueOrderPolicy");
const cursorSource = extracted(/^function queueOrderCursor\([\s\S]*?^\}/m, "queueOrderCursor");
const nextSource = extracted(/^function nextIndex\([\s\S]*?^\}/m, "nextIndex");
const previousSource = extracted(/^function previousIndex\([\s\S]*?^\}/m, "previousIndex");

function build(state, options) {
  const settings = Object.assign({ policy: true }, options);
  // The vm must see the *merged* object, otherwise mutating the returned state
  // afterwards would leave the sandbox reading its own copy.
  const merged = Object.assign({ queue: [], index: -1, repeat: "off", shuffle: false }, state);
  const context = { state: merged, window: {} };
  vm.createContext(context);
  const parts = [];
  if (settings.policy) {
    parts.push(policySource, "globalThis.fnAudioQueueOrderPolicy = window.fnAudioQueueOrderPolicy;");
  }
  parts.push(maxItemsSource, resolverSource, cursorSource, nextSource, previousSource,
    "globalThis.h = { next: () => nextIndex(), previous: () => previousIndex() };");
  vm.runInContext(parts.join("\n\n"), context);
  return { state: merged, h: context.h, policy: context.window.fnAudioQueueOrderPolicy };
}

// Arrays built inside the vm carry that realm's Array.prototype, and strict
// deepEqual compares prototypes, so copy them out before comparing.
const plain = value => JSON.parse(JSON.stringify(value));

function seeded(seed) {
  let value = seed;
  return () => {
    value = (value * 1103515245 + 12345) % 2147483648;
    return value / 2147483648;
  };
}

const three = [{ id: "a" }, { id: "b" }, { id: "c" }];

// One table, both languages: tests/test_queue_order_policy.py reads the same
// file, so a rule changed on one side fails on the other.
const table = require("./queue_order_table.json");
const rows = length => Array.from({ length: Math.max(0, length) }, (_, position) => ({ id: "r" + position }));

for (const label of ["policy", "fallback"]) {
  for (const row of table.cases) {
    const q = build({ queue: rows(row.length), index: row.index, repeat: row.repeat }, { policy: label === "policy" });
    assert.equal(q.h.next(), row.next, `${label} next: ${row.why}`);
    assert.equal(q.h.previous(), row.previous, `${label} previous: ${row.why}`);
  }
}

// R587: shuffle is no longer a coin flip per press.  The queue itself is the
// play order, so `next` stays plain arithmetic even with shuffle on -- the old
// assertion here ("shuffle must pick a different row") described the behaviour
// that was removed, because it could not promise a full pass without repeats.
{
  const q = build({ queue: three, index: 1, repeat: "off", shuffle: true });
  assert.equal(q.h.next(), 2, "shuffle on: next is still the following row");
  assert.equal(q.h.previous(), 0, "shuffle on: previous is still the row before");

  q.state.repeat = "all";
  q.state.index = 2;
  assert.equal(q.h.next(), 0, "shuffle on: the end wraps exactly like repeat all");

  q.state.repeat = "off";
  assert.equal(q.h.next(), -1, "shuffle on: repeat off still ends");
}

// Turning shuffle on is a permutation of the queue: the playing row keeps its
// slot, one pass covers every row exactly once, and turning it back off returns
// the remembered order with the same song still playing.
{
  const items = Array.from({ length: 8 }, (_, position) => ({ id: "t" + position }));
  const policy = build({ queue: items, index: 3, repeat: "off" }).policy;
  assert.ok(policy, "queue_order_policy.js must expose fnAudioQueueOrderPolicy");
  assert.equal(policy.MAX_ITEMS, 50000);

  const original = plain(policy.orderIds(items));
  assert.deepEqual(original, ["t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7"]);

  const mixed = policy.shuffleQueue(items, 3, seeded(7));
  assert.equal(mixed.items.length, 8, "shuffle never loses a row");
  assert.equal(mixed.index, 3, "shuffle keeps the playing row in its slot");
  assert.equal(mixed.items[3].id, "t3", "the row in that slot is still the playing row");
  assert.deepEqual(
    plain(policy.orderIds(mixed.items)).slice().sort(),
    original.slice().sort(),
    "shuffle is a permutation, not a sample",
  );

  // Walk the shuffled queue the way the player does, with repeat all so a pass
  // that starts mid-list still comes round to the rows behind it.
  const visited = [];
  let cursor = mixed.index;
  for (let step = 0; step < 8; step += 1) {
    visited.push(mixed.items[cursor].id);
    const next = policy.nextIndex(cursor, mixed.items.length, "all");
    assert.ok(next >= 0, "repeat all never dead-ends");
    cursor = next;
  }
  assert.equal(visited.length, 8, "one pass visits every row");
  assert.equal(new Set(visited).size, 8, "no row repeats inside a pass");

  // Stop somewhere in the middle, then switch shuffle off.
  cursor = 5;
  const playing = mixed.items[cursor].id;
  const restored = policy.restoreQueue(mixed.items, cursor, original);
  assert.deepEqual(plain(policy.orderIds(restored.items)), original, "shuffle off restores the remembered order");
  assert.equal(restored.items[restored.index].id, playing, "shuffle off must not change the song");

  // Rows added while shuffled were never in the remembered order: they stay at
  // the end instead of jumping to the front.
  const added = mixed.items.concat([{ id: "late" }]);
  const withLate = policy.restoreQueue(added, cursor, original);
  assert.equal(withLate.items[withLate.items.length - 1].id, "late", "late arrivals keep to the end");
  assert.equal(withLate.items[withLate.index].id, playing);
}

// A hostile random source must reorder nothing rather than corrupt the queue.
{
  const items = [{ id: "a" }, { id: "b" }, { id: "c" }];
  const policy = build({ queue: items, index: 0 }).policy;
  const throwing = policy.shuffleQueue(items, 0, () => { throw new Error("bad rng"); });
  assert.equal(throwing.items.length, 3);
  assert.equal(throwing.items[0].id, "a");
  const nan = policy.shuffleQueue(items, 1, () => Number.NaN);
  assert.equal(nan.items.length, 3);
  assert.equal(nan.items[1].id, "b");
  const short = policy.shuffleQueue([{ id: "only" }], 0, seeded(1));
  assert.deepEqual(plain(policy.orderIds(short.items)), ["only"]);
  assert.deepEqual(plain(policy.orderIds(policy.shuffleQueue([], -1, seeded(1)).items)), []);
}

console.log("Queue navigation regression checks passed (client == server).");
