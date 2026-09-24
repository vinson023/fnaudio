const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// R172: a refused preference write may cost the persisted intent only. The
// in-memory state it mirrors is already updated, and the authoritative step
// that follows the write (a list re-render, a header repaint, a reload of the
// transcoding flag) must survive the refusal. A bare write in front of those
// steps turns a full local disk into "the header click did nothing".

const app = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");

function topLevelFunction(name, after) {
  const start = app.indexOf("function " + name + "(");
  assert.ok(start >= 0, "missing host function: " + name);
  const end = app.indexOf("\n" + after, start);
  assert.ok(end > start, "missing end marker for host function: " + name);
  return app.slice(start, end);
}

function guardSource() {
  const start = app.indexOf("function writeStoredPreference(");
  assert.ok(start >= 0, "a guarded preference writer must exist");
  const end = app.indexOf("\n}", start) + 2;
  return app.slice(start, end);
}

function writerSource() {
  const start = app.indexOf("function writeStoredUserMedia(");
  assert.ok(start >= 0, "the guarded user-media writer must stay");
  const end = app.indexOf("\n}", start) + 2;
  return app.slice(start, end);
}

const SORT_KEY = "fnaudio.sortKey.v1";
const SORT_DIR = "fnaudio.sortDir.v2";
const TRANSCODE = "fnaudio.mp3Transcode";

function harness(options) {
  const writes = [];
  const calls = [];
  const failing = options.failing === true;
  const context = vm.createContext({
    assert,
    localStorage: {
      setItem(key, value) {
        writes.push([key, value]);
        if (failing) throw new Error("exceeded the local storage quota");
      },
      getItem() { return null; },
    },
    globalThis: {},
    state: options.state,
    sortOptionsForView: () => options.sortOptions || [["title", "标题"], ["artist", "歌手"]],
    isAlbumDetailView: () => false,
    refreshSortedView: () => calls.push("refreshSortedView"),
    updateModeButton: () => calls.push("updateModeButton"),
    currentItem: () => ({ id: "one" }),
    isRemoteTarget: () => options.remote === true,
    loadCurrent: () => calls.push("loadCurrent"),
  });
  context.globalThis = context;
  context.globalThis.fnAudioLibrarySortOptionsPolicy = {
    defaultKey: () => options.defaultKey || "title",
  };
  vm.runInContext(guardSource() + "\n" + writerSource() + "\n" + options.host, context);
  return { context, writes, calls };
}

// ---- A. applyTrackSort: the two preference writes sit before the re-render ----
const sortHost = topLevelFunction("applyTrackSort", "function columnDragIcon");

{
  const state = { sortKey: "title", sortDir: "asc" };
  const ok = harness({ host: sortHost, state });
  vm.runInContext("applyTrackSort('artist')", ok.context);
  assert.deepEqual(ok.writes, [[SORT_KEY, "artist"], [SORT_DIR, "asc"]],
    "an accepted sort still persists both keys verbatim");
  assert.equal(state.sortKey, "artist");
  assert.deepEqual(ok.calls, ["refreshSortedView"], "the healthy path re-renders once");
}

{
  const state = { sortKey: "title", sortDir: "asc" };
  const broken = harness({ host: sortHost, state, failing: true });
  assert.doesNotThrow(() => vm.runInContext("applyTrackSort('artist')", broken.context),
    "a quota failure must not escape the header click");
  assert.equal(broken.writes.length, 2, "both writes are still attempted");
  assert.equal(state.sortKey, "artist", "the accepted sort is kept in memory");
  assert.deepEqual(broken.calls, ["refreshSortedView"],
    "the re-render survives the refused preference write: that is the whole point");
}

{
  const state = { sortKey: "title", sortDir: "asc" };
  const flip = harness({ host: sortHost, state, failing: true });
  assert.doesNotThrow(() => vm.runInContext("applyTrackSort('title')", flip.context),
    "the direction-flip branch is guarded as well");
  assert.equal(state.sortDir, "desc");
  assert.deepEqual(flip.writes, [[SORT_KEY, "title"], [SORT_DIR, "desc"]]);
  assert.deepEqual(flip.calls, ["refreshSortedView"]);
}

// ---- B. updateSortOptions: it runs inside render(), so a throw poisons painting ----
const optionsHost = topLevelFunction("updateSortOptions", "function compareTrackValue");

{
  const state = { sortKey: "unknown", view: "all" };
  const ok = harness({ host: optionsHost, state });
  assert.doesNotThrow(() => vm.runInContext("updateSortOptions()", ok.context));
  assert.equal(state.sortKey, "title", "a sort key the view cannot honour is corrected");
  assert.deepEqual(ok.writes, [[SORT_KEY, "title"]], "a corrected key is persisted verbatim");
}

{
  const state = { sortKey: "unknown", view: "all" };
  const broken = harness({ host: optionsHost, state, failing: true });
  assert.doesNotThrow(() => vm.runInContext("updateSortOptions()", broken.context),
    "the corrected key must not throw out of the render path");
  assert.equal(state.sortKey, "title");
  assert.equal(broken.writes.length, 1, "the write is still attempted");
}

{
  const state = { sortKey: "artist", view: "all" };
  const unchanged = harness({ host: optionsHost, state, failing: true });
  assert.doesNotThrow(() => vm.runInContext("updateSortOptions()", unchanged.context));
  assert.deepEqual(unchanged.writes, [],
    "an unchanged key still costs no storage write, so render() stays cheap");
}

// ---- C. toggleMp3Transcode: the flag flip must survive into the repaint ----
const transcodeHost = topLevelFunction("toggleMp3Transcode", '$("modeBtn")');

{
  const state = { mp3Transcode: false };
  const ok = harness({ host: transcodeHost, state });
  vm.runInContext("toggleMp3Transcode()", ok.context);
  assert.equal(state.mp3Transcode, true);
  assert.deepEqual(ok.writes, [[TRANSCODE, "1"]], "the persisted token is unchanged");
  assert.deepEqual(ok.calls, ["updateModeButton", "loadCurrent"],
    "the healthy path repaints the button and reloads the track");
}

{
  const state = { mp3Transcode: false };
  const broken = harness({ host: transcodeHost, state, failing: true });
  assert.doesNotThrow(() => vm.runInContext("toggleMp3Transcode()", broken.context));
  assert.equal(state.mp3Transcode, true, "the toggle is kept");
  assert.deepEqual(broken.calls, ["updateModeButton", "loadCurrent"],
    "the button cannot end up showing the opposite of the flag it just flipped");
}

{
  const state = { mp3Transcode: true };
  const remote = harness({ host: transcodeHost, state, failing: true, remote: true });
  assert.doesNotThrow(() => vm.runInContext("toggleMp3Transcode()", remote.context));
  assert.equal(state.mp3Transcode, false);
  assert.deepEqual(remote.writes, [[TRANSCODE, "0"]]);
  assert.deepEqual(remote.calls, ["updateModeButton"],
    "a remote target still repaints and still skips the local reload");
}

// ---- D2. The guard must not over-wrap: a real failure downstream still surfaces.
{
  const state = { sortKey: "title", sortDir: "asc" };
  const over = harness({ host: sortHost, state });
  over.context.refreshSortedView = () => { throw new Error("the table is broken"); };
  assert.throws(() => vm.runInContext("applyTrackSort('artist')", over.context), /the table is broken/,
    "only the storage call is swallowed; a failing re-render must stay visible");
}

{
  const state = { mp3Transcode: false };
  const over = harness({ host: transcodeHost, state });
  over.context.updateModeButton = () => { throw new Error("the button is broken"); };
  assert.throws(() => vm.runInContext("toggleMp3Transcode()", over.context), /the button is broken/,
    "only the storage call is swallowed; a failing repaint must stay visible");
}

// ---- D. Source-level sentinels: none of the three hosts may regress to bare writes ----
for (const [name, after, host] of [
  ["applyTrackSort", "function columnDragIcon", sortHost],
  ["updateSortOptions", "function compareTrackValue", optionsHost],
  ["toggleMp3Transcode", '$("modeBtn")', transcodeHost],
]) {
  assert.doesNotMatch(host, /localStorage\s*\./,
    name + " must persist through the guarded writer instead of touching storage directly");
  assert.match(host, /writeStoredPreference\(/, name + " must still persist its preference");
}
assert.match(guardSource(),
  /function writeStoredPreference\(key, value\) \{[\s\S]{0,600}?try \{[\s\S]{0,80}?localStorage\.setItem\(key, value\);[\s\S]{0,40}?\} catch \(_\) \{/,
  "the guarded writer must wrap exactly the storage call, and only that call");
assert.equal(writesOf(app, "writeStoredPreference("), 5,
  "the writer plus exactly the four preference call sites this round converted, no more");
assert.match(app, /function writeStoredUserMedia\(key, value\) \{/,
  "the user-media writer stays separate: its payload is JSON, the preference payload is not");

function writesOf(source, needle) {
  let count = 0;
  let index = source.indexOf(needle);
  while (index >= 0) {
    count += 1;
    index = source.indexOf(needle, index + needle.length);
  }
  return count;
}

console.log("Guarded preference-write regression checks passed.");
