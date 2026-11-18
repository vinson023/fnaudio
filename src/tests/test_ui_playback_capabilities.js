// R587: the client half of the playback capability block.
//
// The Android remote snapshot has always cut the queue at 500 rows and said
// nothing about it. The cap itself is fine -- the silence was the bug -- so the
// server now publishes the number and the client says so once. Everything here
// degrades to the pre-R587 behaviour when the block is missing, which is what
// keeps an older server working with a newer page.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/playback_capability_policy.js", "utf8");
const context = vm.createContext({ window: {} });
vm.runInContext(source, context);
const policy = context.window.fnAudioPlaybackCapabilityPolicy;

assert.ok(policy, "playback_capability_policy.js must publish fnAudioPlaybackCapabilityPolicy");
for (const name of ["read", "boundQueue", "truncationMessage"]) {
  assert.equal(typeof policy[name], "function", name + " must be callable");
}

// The block the server actually serves (src/app/server/playback_capability_policy.py).
const served = {
  version: 1,
  queue: { max_items: 50000, remote_max_items: 500, truncation_notice: true },
  position: { report: true, min_interval_ms: 30000 },
  shuffle: { mode: "queue-order" },
};

// A missing or malformed block means "old behaviour": no cap, no notice, no
// resume interval change. Silently inventing a cap would drop rows on a server
// that never asked for one.
const old = policy.read(null);
assert.equal(old.queue.max, 0);
assert.equal(old.queue.remote, 0);
assert.equal(old.queue.notice, false);
assert.equal(old.position.enabled, false);
assert.equal(old.position.minIntervalMs, 30000);
assert.equal(old.shuffle, "random");
assert.deepEqual(policy.read(undefined), policy.read(null));
assert.deepEqual(policy.read({}), policy.read(null));
assert.deepEqual(policy.read({ queue: "no", position: 5, shuffle: [] }), policy.read(null));

// The served block, read as the page reads it.
const read = policy.read(served);
assert.equal(read.queue.max, 50000);
assert.equal(read.queue.remote, 500);
assert.equal(read.queue.notice, true);
assert.equal(read.position.enabled, true);
assert.equal(read.position.minIntervalMs, 30000);
assert.equal(read.shuffle, "queue-order");

// The report interval has a floor: a server that asks for a write per second is
// the Audio Station habit this change exists to avoid, and a client that obeyed
// it would hammer SQLite.
assert.equal(policy.read({ position: { report: true, min_interval_ms: 1000 } }).position.minIntervalMs, 5000);
assert.equal(policy.read({ position: { report: true, min_interval_ms: 0 } }).position.minIntervalMs, 30000);
assert.equal(policy.read({ position: { report: true, min_interval_ms: -1 } }).position.minIntervalMs, 30000);
assert.equal(policy.read({ position: { report: true, min_interval_ms: "soon" } }).position.minIntervalMs, 30000);

// Junk numbers must not become a cap of NaN, which would slice the queue to
// nothing (`list.slice(0, NaN)` is empty).
for (const junk of ["", "x", null, {}, [], Number.NaN, Number.POSITIVE_INFINITY, -3]) {
  const junked = policy.read({ queue: { max_items: junk, remote_max_items: junk } });
  assert.equal(junked.queue.max, 0, "max from " + String(junk));
  assert.equal(junked.queue.remote, 0, "remote from " + String(junk));
}
assert.equal(policy.read({ queue: { remote_max_items: 500.9 } }).queue.remote, 500, "a cap is a whole number of rows");
assert.equal(policy.read({ queue: { remote_max_items: 999999 } }).queue.remote, 50000, "a cap is bounded");

// boundQueue: cap 0 means "no limit known".
const rows = Array.from({ length: 600 }, (_, position) => ({ id: "t" + position }));
assert.equal(policy.boundQueue(rows, 0).items.length, 600);
assert.equal(policy.boundQueue(rows, 0).dropped, 0);
assert.equal(policy.boundQueue(rows, 0).limit, 0);

const capped = policy.boundQueue(rows, 500);
assert.equal(capped.items.length, 500);
assert.equal(capped.items[0].id, "t0", "the head of the queue is what a target gets");
assert.equal(capped.items[499].id, "t499");
assert.equal(capped.dropped, 100);
assert.equal(capped.limit, 500);

assert.equal(policy.boundQueue(rows, 5000).dropped, 0, "a cap above the queue drops nothing");
assert.equal(policy.boundQueue(rows, 5000).items.length, 600);
assert.equal(policy.boundQueue([], 500).dropped, 0);
assert.equal(policy.boundQueue(null, 500).items.length, 0);
assert.equal(policy.boundQueue(rows, "500").items.length, 500, "a numeric string is still a cap");

// truncationMessage: say it once, and say the numbers.
const message = policy.truncationMessage(100, 500);
assert.match(message, /500/, "the message names the cap");
assert.match(message, /100/, "the message names how many rows were left behind");
assert.equal(policy.truncationMessage(0, 500), "", "nothing dropped, nothing to say");
assert.equal(policy.truncationMessage(100, 0), "", "no cap known, no claim to make");
assert.equal(policy.truncationMessage(null, 500), "");
assert.equal(policy.truncationMessage("x", 500), "");

console.log("Playback capability checks passed (caps are stated, not guessed).");
