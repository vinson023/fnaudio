// R587: the page's copy of the queue navigation table.
//
// app/ui/queue_order_policy.js is the module; this file checks its contract and
// runs the same tests/queue_order_table.json the Python suite runs.  A rule
// changed on one side therefore fails on the other instead of shipping two
// behaviours behind one button.
//
// tests/test_ui_queue_navigation.js covers the other half: that app.js really
// delegates to this module (and keeps a working inline copy for a cached page).

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/queue_order_policy.js", "utf8");
const context = vm.createContext({ window: {} });
vm.runInContext(source, context);
const policy = context.window.fnAudioQueueOrderPolicy;

// Arrays built inside the vm carry that realm's Array.prototype, and strict
// deepEqual compares prototypes, so copy them out before comparing.
const plain = value => JSON.parse(JSON.stringify(value));

const table = require("./queue_order_table.json");

assert.ok(policy, "queue_order_policy.js must publish fnAudioQueueOrderPolicy");
assert.equal(policy.MAX_ITEMS, table.max_items);
assert.deepEqual(plain(policy.REPEAT_MODES), table.repeat_modes);
for (const name of ["nextIndex", "previousIndex", "orderIds", "shuffleQueue", "restoreQueue"]) {
  assert.equal(typeof policy[name], "function", name + " must be callable");
}

// One table, both languages.
for (const row of table.cases) {
  assert.equal(policy.nextIndex(row.index, row.length, row.repeat), row.next, "next: " + row.why);
  assert.equal(policy.previousIndex(row.index, row.length, row.repeat), row.previous, "previous: " + row.why);
}

// A client that sends no repeat mode gets "off", like the server default.
assert.equal(policy.nextIndex(0, 3), 1);
assert.equal(policy.previousIndex(0, 3), -1);

// orderIds drops rows it cannot identify rather than inventing an empty id.
assert.deepEqual(plain(policy.orderIds([{ id: "a" }, { id: "" }, {}, null, { id: 7 }])), ["a", "7"]);
assert.deepEqual(plain(policy.orderIds(null)), []);

function seeded(seed) {
  let value = seed;
  return () => {
    value = (value * 1103515245 + 12345) % 2147483648;
    return value / 2147483648;
  };
}

const items = count => Array.from({ length: count }, (_, position) => ({ id: "t" + position }));

// shuffleQueue: a permutation that leaves the playing row in its slot.
{
  const eight = items(8);
  const mixed = policy.shuffleQueue(eight, 3, seeded(11));
  assert.equal(mixed.index, 3, "the playing row keeps its slot");
  assert.equal(mixed.items[3].id, "t3");
  assert.deepEqual(plain(policy.orderIds(mixed.items)).slice().sort(), plain(policy.orderIds(eight)).sort());
  assert.notDeepEqual(plain(policy.orderIds(mixed.items)), plain(policy.orderIds(eight)), "a fixed rng must not be a no-op");
  assert.deepEqual(plain(policy.orderIds(eight)), ["t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7"], "the input is not mutated");

  // No current row: the whole queue is mixed, and the cursor stays "nothing".
  const noCursor = policy.shuffleQueue(eight, -1, seeded(3));
  assert.equal(noCursor.index, -1);
  assert.equal(noCursor.items.length, 8);

  // A cursor past the end is not a current row either.
  assert.equal(policy.shuffleQueue(eight, 99, seeded(3)).index, -1);
}

// restoreQueue: the remembered order comes back and the song does not change.
{
  const eight = items(8);
  const original = plain(policy.orderIds(eight));
  const mixed = policy.shuffleQueue(eight, 0, seeded(5));
  const playing = mixed.items[6].id;
  const restored = policy.restoreQueue(mixed.items, 6, original);
  assert.deepEqual(plain(policy.orderIds(restored.items)), original);
  assert.equal(restored.items[restored.index].id, playing, "shuffle off must not switch songs");

  // Rows added while shuffled were never in the remembered order: they stay at
  // the end, in the order they were added.
  const withLate = policy.restoreQueue(mixed.items.concat([{ id: "x" }, { id: "y" }]), 6, original);
  assert.deepEqual(plain(policy.orderIds(withLate.items)).slice(-2), ["x", "y"]);
  assert.equal(withLate.items[withLate.index].id, playing);

  // Rows removed while shuffled simply do not come back.
  const removedId = mixed.items.find(item => item.id !== playing).id;
  const kept = mixed.items.filter(item => item.id !== removedId);
  const keptCursor = kept.findIndex(item => item.id === playing);
  const missing = policy.restoreQueue(kept, keptCursor, original);
  assert.ok(!plain(policy.orderIds(missing.items)).includes(removedId), "a deleted row must not be resurrected");
  assert.equal(missing.items[missing.index].id, playing);

  // A remembered order that names rows the queue no longer has is harmless, and
  // an empty memory still keeps the playing row playing instead of jumping to
  // the top of the list.
  assert.equal(policy.restoreQueue(items(3), 1, ["ghost"]).items.length, 3);
  assert.equal(policy.restoreQueue(items(3), 1, []).index, 1);
  assert.equal(policy.restoreQueue([], -1, original).index, -1);

  // Duplicate ids in the memory must not duplicate rows.
  const duped = policy.restoreQueue(items(3), 0, ["t1", "t1", "t0", "t2"]);
  assert.deepEqual(plain(policy.orderIds(duped.items)), ["t1", "t0", "t2"]);
}

// Degenerate sizes and a hostile random source must not corrupt the queue.
{
  assert.deepEqual(plain(policy.orderIds(policy.shuffleQueue([], -1, seeded(1)).items)), []);
  const single = policy.shuffleQueue(items(1), 0, seeded(1));
  assert.deepEqual(plain(policy.orderIds(single.items)), ["t0"]);
  assert.equal(single.index, 0, "a one-row queue still has a playing row");

  const throwing = policy.shuffleQueue(items(4), 1, () => { throw new Error("bad rng"); });
  assert.equal(throwing.items.length, 4);
  assert.equal(throwing.items[1].id, "t1");

  const nan = policy.shuffleQueue(items(4), 2, () => Number.NaN);
  assert.equal(nan.items.length, 4);
  assert.equal(nan.items[2].id, "t2");

  const outOfRange = policy.shuffleQueue(items(4), 0, () => 5);
  assert.equal(outOfRange.items.length, 4);
  assert.equal(outOfRange.items[0].id, "t0");

  assert.deepEqual(plain(policy.orderIds(policy.shuffleQueue(null, 0, seeded(1)).items)), []);
}

console.log("Queue order policy checks passed (JS copy matches the shared table).");
