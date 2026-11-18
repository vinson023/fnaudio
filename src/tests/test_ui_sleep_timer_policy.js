// R588: the sleep timer's arithmetic, tested where it can actually be run.
//
// The feature exists because a phone on the nightstand keeps playing after the
// listener falls asleep. The two ways it can fail silently are (a) the deadline
// is recomputed from a countdown, so a suspended WebView drifts, and (b) an
// expired deadline from yesterday pauses the music somebody just started. Both
// are properties of these functions, not of the UI.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/sleep_timer_policy.js", "utf8");
const context = vm.createContext({ window: {} });
vm.runInContext(source, context);
const policy = context.window.fnAudioSleepTimerPolicy;

assert.ok(policy, "sleep_timer_policy.js must publish fnAudioSleepTimerPolicy");
for (const name of ["deadlineFrom", "describe", "formatRemaining", "isActive", "isExpired",
  "isFreshExpiry", "minutes", "readStored", "remainingMs", "writeStored"]) {
  assert.equal(typeof policy[name], "function", name + " must be callable");
}

const MINUTE = 60000;
const NOW = 1_700_000_000_000;

// A deadline is absolute: the same number survives a reload, a suspended page,
// and a service restart, which a countdown cannot.
assert.equal(policy.deadlineFrom(30, NOW), NOW + 30 * MINUTE);
assert.equal(policy.deadlineFrom(1, NOW), NOW + MINUTE);
assert.equal(policy.remainingMs(NOW + 30 * MINUTE, NOW), 30 * MINUTE);
assert.equal(policy.remainingMs(NOW + 30 * MINUTE, NOW + 29 * MINUTE), MINUTE);

// Nothing configured is not "expired": an empty timer must never pause anything.
assert.equal(policy.deadlineFrom(0, NOW), 0);
assert.equal(policy.deadlineFrom("", NOW), 0);
assert.equal(policy.deadlineFrom("soon", NOW), 0);
assert.equal(policy.deadlineFrom(-5, NOW), 0);
assert.equal(policy.deadlineFrom(null, NOW), 0);
assert.equal(policy.isActive(0, NOW), false);
assert.equal(policy.isExpired(0, NOW), false);
assert.equal(policy.isFreshExpiry(0, NOW), false);
assert.equal(policy.remainingMs(0, NOW), 0);
assert.equal(policy.describe(0, NOW).text, "");

// Bounds: one minute is the floor, a day is the ceiling. A mis-typed 100000
// must not become a week-long timer nobody can find again.
assert.equal(policy.minutes(0.9), 0);
assert.equal(policy.minutes(1), 1);
assert.equal(policy.minutes(30.9), 30);
assert.equal(policy.minutes(100000), policy.MAX_MINUTES);
assert.equal(policy.deadlineFrom(100000, NOW), NOW + policy.MAX_MINUTES * MINUTE);
assert.equal(policy.minutes(Number.NaN), 0);
assert.equal(policy.minutes(Number.POSITIVE_INFINITY), 0);

// Expiry has to distinguish "just fired" from "left over from yesterday".
assert.equal(policy.isExpired(NOW - 1, NOW), true);
assert.equal(policy.isActive(NOW - 1, NOW), false);
assert.equal(policy.isFreshExpiry(NOW - 1, NOW), true, "a deadline one second ago is this session's");
assert.equal(policy.isFreshExpiry(NOW - policy.GRACE_MS, NOW), true, "the grace window is inclusive");
assert.equal(policy.isFreshExpiry(NOW - policy.GRACE_MS - 1, NOW), false, "older than the window is stale");
assert.equal(policy.isFreshExpiry(NOW + MINUTE, NOW), false, "a future deadline has not fired yet");

// The label is what the user reads, so it must never say "还剩 0 分 00 秒".
assert.equal(policy.formatRemaining(0), "0 秒");
assert.equal(policy.formatRemaining(-5000), "0 秒");
assert.equal(policy.formatRemaining(1), "1 秒");
assert.equal(policy.formatRemaining(45_000), "45 秒");
assert.equal(policy.formatRemaining(MINUTE), "1 分 00 秒");
assert.equal(policy.formatRemaining(29 * MINUTE + 30_000), "29 分 30 秒");
assert.equal(policy.formatRemaining(60 * MINUTE), "1 小时");
assert.equal(policy.formatRemaining(90 * MINUTE), "1 小时 30 分");
assert.equal(policy.formatRemaining(Number.NaN), "0 秒");

assert.equal(policy.describe(NOW + 90_000, NOW).text, "睡眠定时：还剩 1 分 30 秒");
assert.equal(policy.describe(NOW + 90_000, NOW).active, true);
assert.equal(policy.describe(NOW - 1000, NOW).active, false);

// Storage: absent, full, or holding junk must all mean "no timer", never a throw.
function fakeStorage(initial) {
  const map = new Map(initial ? [[policy.STORAGE_KEY, String(initial)]] : []);
  return {
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => { map.set(key, String(value)); },
    removeItem: key => { map.delete(key); },
    has: () => map.size > 0,
    raw: () => map.get(policy.STORAGE_KEY),
  };
}

{
  const storage = fakeStorage();
  assert.equal(policy.readStored(storage), 0);
  assert.equal(policy.writeStored(storage, NOW + 5 * MINUTE), true);
  assert.equal(storage.raw(), String(NOW + 5 * MINUTE));
  assert.equal(policy.readStored(storage), NOW + 5 * MINUTE);
  assert.equal(policy.writeStored(storage, 0), true);
  assert.equal(storage.has(), false, "cancelling must remove the key, not store a zero");
  assert.equal(policy.readStored(storage), 0);
}

assert.equal(policy.readStored(fakeStorage("not-a-number")), 0);
assert.equal(policy.readStored(fakeStorage("-1")), 0);
assert.equal(policy.readStored(null), 0);
assert.equal(policy.readStored(undefined), 0);
assert.equal(policy.writeStored(null, NOW), false);
assert.equal(policy.writeStored({ setItem: () => { throw new Error("quota"); } }, NOW), false);

console.log("Sleep timer policy checks passed (absolute deadline, not a countdown).");
