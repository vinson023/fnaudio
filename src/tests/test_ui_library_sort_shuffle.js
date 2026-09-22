const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert").strict;

// R159 - the library view / playlist / column-picker / sort / transcode face of
// app.js (source lines 1568-1816 at intake, 44 named functions, 42 of them never
// named in any root document before this round).
//
// Deep reading this face turned up one real defect and one piece of dead code:
//
//   1. `ui/shuffle_policy.js` is declared in index.html, unit tested on its own,
//      and the TODO.md item 「核心边界拆分：随机队列 Fisher–Yates 策略抽至
//      `ui/shuffle_policy.js`」 is checked off as done, with CHANGELOG_AI.md and
//      PROJECT_CONTEXT.md both claiming app.js calls it "通过兼容入口".  On disk that
//      entry point, `shuffleItems()`, had zero call sites - and `git log -S` finds
//      it in the baseline import only, so within all recorded history no live path
//      ever used the module.  Meanwhile the two queue builders that actually run,
//      `playGroup()` and `playAll()`, shuffled with
//      `[...list].sort(() => Math.random() - 0.5)`.  A comparator-driven sort is
//      not a uniform shuffle, and it bypassed the module's 50,000-item budget and
//      its abnormal-RNG guards, so none of that hardening ever reached a listener.
//
//   2. `compareName()` was a zero-reference comparator that folded the current sort
//      direction into a locale collation - a second, direction-dependent definition
//      of a rule the live sort lane already owns.
//
// Each check below is a discriminator, not a preference: reverting either change,
// or re-introducing a comparator shuffle, or letting this face grow another
// zero-reference function, fails this file.

const uiDir = path.join(__dirname, "..", "app", "ui");
const source = fs.readFileSync(path.join(uiDir, "app.js"), "utf8");
const policySource = fs.readFileSync(path.join(uiDir, "shuffle_policy.js"), "utf8");
const indexSource = fs.readFileSync(path.join(uiDir, "index.html"), "utf8");

function countOf(haystack, needle) {
  return haystack.split(needle).length - 1;
}

// The wrapper under test runs in its own vm realm, so a literal it returns is not
// the host realm Array. Normalising through JSON keeps every comparison below
// realm-independent instead of quietly depending on which side allocated first.
function asArray(value) {
  return JSON.parse(JSON.stringify(value));
}

// --- 1. the face must still be anchored where this review read it -------------
const faceStart = source.indexOf("function isPlaylistView(");
const faceEnd = source.indexOf("function scanProgressText() {");
assert.ok(faceStart >= 0 && faceEnd > faceStart, "library face anchors moved; re-read the face before editing this test");
const face = source.slice(faceStart, faceEnd);
for (const anchor of ["function shuffleItems(list) {", "function playGroup", "function isPrivateHost(host) {",
  "function effectiveProfile() {", "function updateModeButton() {"]) {
  assert.ok(countOf(source, anchor) === 1, "expected exactly one " + anchor);
}

// --- 2. index.html must keep shipping the policy the UI now depends on --------
assert.ok(/<script[^>]*shuffle_policy\.js/.test(indexSource),
  "index.html must keep declaring shuffle_policy.js: app.js routes random playback through it");

// --- 3. load the real module, then the wrapper under test --------------------
function realPolicy() {
  const box = { window: {} };
  vm.runInNewContext(policySource, box);
  return box.window.fnAudioShufflePolicy;
}

function loadWrapper(policy) {
  const start = source.indexOf("function shuffleItems(list) {");
  const finish = source.indexOf("\n}\n", start);
  assert.ok(finish > start, "shuffleItems body is not terminated where this test expects");
  const box = { window: {} };
  if (policy !== null) box.window.fnAudioShufflePolicy = policy;
  vm.runInNewContext(source.slice(start, finish + 3), box);
  assert.equal(typeof box.shuffleItems, "function", "shuffleItems must stay a plain function declaration");
  return box.shuffleItems;
}

const policy = realPolicy();
assert.equal(policy.MAX_ITEMS, 50000, "the shipped policy budget is what the wrapper reasons about");
const shuffle = loadWrapper(policy);

// --- 4. integrity: same items, same length, caller array untouched -----------
const source60 = [];
for (let index = 0; index < 60; index += 1) source60.push(index);
const expected60 = source60.slice();
const shuffled60 = shuffle(source60);
assert.notEqual(shuffled60, source60, "a shuffle must not hand back the caller's own array");
assert.equal(shuffled60.length, 60, "a shuffle must not change the queue length");
assert.deepEqual(asArray(shuffled60.slice().sort((a, b) => a - b)), expected60, "a shuffle must not add or drop items");
assert.deepEqual(asArray(source60), expected60, "a shuffle must not mutate the caller's array");

// --- 5. wiring: prove app.js consults the module instead of shuffling itself --
const marker = { MAX_ITEMS: 50000, shuffle: list => list.slice().reverse() };
assert.deepEqual(asArray(loadWrapper(marker)([1, 2, 3])), [3, 2, 1],
  "app.js must route queue shuffles through fnAudioShufflePolicy rather than re-implementing one");

// --- 6. the budget reorders at most MAX_ITEMS and never truncates the queue ---
const capped = { MAX_ITEMS: 3, shuffle: list => list.slice().reverse() };
assert.deepEqual(asArray(loadWrapper(capped)([1, 2, 3, 4, 5])), [3, 2, 1, 4, 5],
  "beyond-budget items keep their original order at the tail instead of vanishing");
const oversized = [];
for (let index = 0; index < 50001; index += 1) oversized.push(index);
const shuffledBig = shuffle(oversized);
assert.equal(shuffledBig.length, 50001, "shuffling a library larger than the policy budget must not drop the last track");
assert.equal(shuffledBig[50000], 50000, "the tail beyond the budget must stay put");
const zeroBudget = { MAX_ITEMS: 0, shuffle: list => list.slice().reverse() };
assert.deepEqual(asArray(loadWrapper(zeroBudget)([1, 2])), [2, 1], "a non-positive budget must be read as the whole queue");

// --- 7. fail-safe: a missing or hostile policy must not empty the queue ------
const absent = loadWrapper(null);
const sourceAbs = [7, 8, 9];
const outAbs = absent(sourceAbs);
assert.deepEqual(asArray(outAbs), [7, 8, 9], "a missing policy module must degrade to ordered playback, not silence");
assert.notEqual(outAbs, sourceAbs, "even the fallback must not expose the caller's array");
assert.deepEqual(asArray(absent(undefined)), [], "a non-array argument must yield an empty queue");
assert.deepEqual(asArray(absent([])), [], "an empty queue must stay empty");
assert.deepEqual(asArray(loadWrapper({ MAX_ITEMS: 50000, shuffle: () => "nope" })([1, 2])), [1, 2],
  "a non-array policy result must fall back to the caller's order");
assert.deepEqual(asArray(loadWrapper({ MAX_ITEMS: 50000, shuffle: () => [1] })([1, 2, 3])), [1, 2, 3],
  "a short policy result must never truncate the queue");
assert.deepEqual(asArray(loadWrapper({ MAX_ITEMS: 50000, shuffle: () => { throw new Error("hostile rng"); } })([1, 2])), [1, 2],
  "a throwing policy must not abort playback");

// --- 8. source-level lane: both live builders use the entry, none sorts -------
assert.equal(countOf(source, "state.shuffle ? shuffleItems(group) : group;"), 1, "playGroup must shuffle through the policy entry");
assert.equal(countOf(source, "state.shuffle ? shuffleItems(tracks) : tracks;"), 1, "playAll must shuffle through the policy entry");
assert.equal(countOf(source, ".sort(() => Math.random()"), 0, "a comparator-driven shuffle must not return to app.js");
assert.ok(countOf(source, "shuffleItems(") >= 3, "the compatibility entry point must stay wired to real call sites");

// --- 9. the dead comparator must stay gone everywhere the UI can see it ------
for (const file of fs.readdirSync(uiDir)) {
  if (!file.endsWith(".js") && !file.endsWith(".html")) continue;
  assert.equal(countOf(fs.readFileSync(path.join(uiDir, file), "utf8"), "compareName"), 0,
    "the zero-reference compareName comparator must stay removed from " + file);
}

// --- 10. registered orphan: this face may not grow new zero-reference code ---
// `effectiveProfile()` is the only reader of `state.accessProfile` and the only
// caller of `isPrivateHost()`, which is the only consumer of
// `ui/host_privacy_policy.js`.  Deleting it would strand a module index.html still
// ships and the Android bundle still embeds, so that removal belongs to the
// bundled-UI round tracked in docs/REAL_DEVICE_GOALS.md rather than to an offline
// pass.  Empty this list when that decision lands; a second orphan fails here.
const pendingOrphans = ["effectiveProfile"];
const declared = [];
for (const line of face.split("\n")) {
  const match = /^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/.exec(line);
  if (match) declared.push(match[1]);
}
assert.ok(declared.length >= 40, "the reviewed face must keep its shape; found " + declared.length + " functions");
const orphans = declared.filter(name => countOf(source, name) === 1);
assert.deepEqual(orphans.slice().sort(), pendingOrphans.slice().sort(),
  "every zero-reference function in this face must be registered as a pending orphan");
assert.equal(source.split("\n").filter(line => /state\.accessProfile\b/.test(line) && !/state\.accessProfile\s*=/.test(line)).length, 1,
  "the access profile read side must stay confined to the registered orphan until the badge decision lands");

console.log("Library sort/shuffle policy regression checks passed.");
