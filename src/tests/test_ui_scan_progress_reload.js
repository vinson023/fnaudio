// R603: on a fresh install the list stayed empty for the whole first scan.
//
// The server used to publish nothing until the walk finished, and the page only
// reloaded once the status poll said the scan was over. Both halves are fixed;
// this file pins the page half. `scheduleScanProgressReload` must ask for the
// first page while the walk is still running, but only in the situation the
// owner reported -- nothing on screen yet -- so a visible list is never rebuilt
// under the user's hands.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the scan-progress regression`);
  return match[0];
}

// The scheduler reads this module constant, so it has to be injected with the
// function. Read it out of the source rather than restating the number: the test
// then also notices if the delay disappears from the file.
const delayMatch = app.match(/const SCAN_PROGRESS_RELOAD_DELAY_MS = (\d+);/);
assert.ok(delayMatch, "the scan progress reload delay must stay a named constant");

function buildScheduler(options = {}) {
  const timers = [];
  const calls = [];
  const state = {
    scanProgressReloadTimer: options.timer || 0,
    libraryLoading: options.loading === true,
    pageItems: options.items || [],
    view: options.view || "all",
    libraryStatus: options.status || { scanning: true },
  };
  const context = {
    state,
    SCAN_PROGRESS_RELOAD_DELAY_MS: Number(delayMatch[1]),
    setTimeout: (callback, delay) => {
      timers.push({ callback, delay });
      return timers.length;
    },
    clearTimeout: () => {},
    currentQueryText: () => options.query || "",
    clearLibraryResponseCaches: () => calls.push(["clear"]),
    requestLibraryLoad: (page, refresh) => calls.push(["load", page, refresh]),
  };
  vm.createContext(context);
  vm.runInContext(
    `${functionSource("scheduleScanProgressReload")}\nglobalThis.h = { schedule: scheduleScanProgressReload };`,
    context,
  );
  return { schedule: context.h.schedule, state, timers, calls };
}

// --- when it must ask ------------------------------------------------------

const emptyLibrary = buildScheduler();
assert.equal(emptyLibrary.schedule(), true, "an empty list during a scan must schedule a reload");
assert.equal(emptyLibrary.timers.length, 1, "exactly one timer is armed");
assert.ok(emptyLibrary.timers[0].delay > 0, "the reload is delayed, not immediate");

// Firing it is what actually asks for the page.
emptyLibrary.timers[0].callback();
assert.deepEqual(emptyLibrary.calls, [["clear"], ["load", 1, false]],
  "the reload clears the cached empty page and asks for page 1");
assert.equal(emptyLibrary.state.scanProgressReloadTimer, 0, "the timer slot is released before loading");

// --- when it must stay out of the way --------------------------------------

const alreadyShown = buildScheduler({ items: [{ id: "a" }] });
assert.equal(alreadyShown.schedule(), false, "a visible list must not be rebuilt under the user");
assert.equal(alreadyShown.timers.length, 0);

const pending = buildScheduler({ timer: 7 });
assert.equal(pending.schedule(), false, "a second poll must not arm a second timer");
assert.equal(pending.timers.length, 0);

const loading = buildScheduler({ loading: true });
assert.equal(loading.schedule(), false, "a load already in flight needs no second one");

const searching = buildScheduler({ query: "adele" });
assert.equal(searching.schedule(), false, "a search result page is not the empty-library case");

const folders = buildScheduler({ view: "folders" });
assert.equal(folders.schedule(), false, "the folder browser has its own loading path");

// --- the timer must re-check the world it was armed in ---------------------

const finishedEarly = buildScheduler();
finishedEarly.schedule();
finishedEarly.state.libraryStatus = { scanning: false };
finishedEarly.timers[0].callback();
assert.deepEqual(finishedEarly.calls, [],
  "the scan ended before the timer fired: the ordinary end-of-scan reload owns it now");

const filledMeanwhile = buildScheduler();
filledMeanwhile.schedule();
filledMeanwhile.state.pageItems = [{ id: "a" }];
filledMeanwhile.timers[0].callback();
assert.deepEqual(filledMeanwhile.calls, [],
  "rows arrived before the timer fired: do not reload over them");

// --- wiring ----------------------------------------------------------------

assert.match(app, /if \(data\.scanning === true\) scheduleScanProgressReload\(\);/,
  "the status poll must arm the reload while the scan runs");
assert.match(app, /const SCAN_PROGRESS_RELOAD_DELAY_MS = \d+;/,
  "the reload delay stays a named constant");

console.log("scan progress reload checks passed.");
