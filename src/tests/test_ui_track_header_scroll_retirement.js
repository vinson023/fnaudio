const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// R163 - the "group/album/creator/genre/folder renderers + pager + track-header
// geometry" face of app.js (source lines 3667-3793 at intake, 127 lines, 10
// named functions).
//
// Deep reading this face found a whole mechanism that cannot do anything:
// syncTrackHeaderScroll() and its binder.
//
//   syncTrackHeaderScroll() (app.js:3767-3783 at intake) has two branches and
//   both of them write exactly the same values:
//
//     * every row gets  row.style.width = "";      (:3772 mobile, :3780 desktop)
//     * the head gets   head.style.width = "";     (:3774-:3775, :3781-:3782)
//     * the head gets   head.style.transform = "";
//     * the viewport gets --fnaudio-library-content-width: "100%" (:3779)
//
//   Grepping the whole shipped UI shows those clears are the ONLY writers of
//   style.width / style.transform in app.js: the live column mechanism works
//   through the --fnaudio-track-columns custom property instead (app.js:2956,
//   :2978, :2984, :3078, :3104), and --fnaudio-library-content-width appears
//   exactly once in the JavaScript while app.css declares it to 100% already.
//
//   Worse, the values it clears cannot even be set: app.css:621-632 applies
//   `width: var(--fnaudio-library-content-width) !important` and
//   `min-width: ... !important` to .library-scroll .table-head / .track /
//   .group-row inside @media(min-width:761px), and an !important author
//   declaration beats every inline style, so on desktop a JS inline width is
//   both unreproducible and unnecessary. Below 761px the media query does not
//   apply, but the function only ever writes "" there too, which also cannot
//   change the layout.
//
//   So the mechanism is dead weight, and it is not free: bindTrackHeaderScroll()
//   runs from every render() (app.js:3864), registers a permanent window
//   "resize" listener (app.js:3788) plus a ResizeObserver on the viewport
//   (app.js:3790) that is never disconnected (app.js has zero .disconnect(
//   calls), and the render() animation frame (app.js:3873) walks every visible
//   row on every list change to write nothing. `git log -S syncTrackHeaderScroll`
//   returns exactly one commit - the v0.1.150 baseline - i.e. it was never
//   changed into something live.
//
//   Removing them deletes 39 lines, 2 render-path call sites, 1 listener and 1
//   never-disconnected observer, and cannot change any painted pixel. The
//   positive-control blocks below pin the CSS contract that licenses the
//   deletion: if that !important grid width ever disappears, JS geometry control
//   becomes necessary again and this suite must fail loudly instead of silently.
//
//   Deliberately NOT claimed: a listener leak. #libraryScroll is static markup
//   (index.html:59) that is never replaced, and the dataset guard makes the
//   registration one-shot, so the cost is dead work per frame, not unbounded
//   growth.

const uiDir = path.join(__dirname, "..", "app", "ui");
const appSource = fs.readFileSync(path.join(uiDir, "app.js"), "utf8");
const cssSource = fs.readFileSync(path.join(uiDir, "app.css"), "utf8");

function appLines() { return appSource.split("\n"); }

function optionalFunctionSource(name) {
  const match = appSource.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  return match ? match[0] : null;
}

// Slice of the render() tail that owns the geometry wiring: from the pager
// visibility hand-off through the interaction binder. This is the region that
// used to call into the header mechanism, and it is executed for real below.
function renderGeometryRegion() {
  const lines = appLines();
  const start = lines.findIndex(line => line === "  if (pagerChanged) updateMobilePagerVisibility();");
  assert.ok(start >= 0, "the render() geometry region must still start at the pager visibility hand-off");
  const binder = lines.findIndex((line, index) => index >= start && line === "  bindTrackListInteractions();");
  assert.ok(binder > start, "the render() geometry region must still contain the row interaction binder");
  // The region does not stop at the binder: the geometry animation-frame block
  // follows it, so the executed slice runs through that block closing brace.
  let end = -1;
  for (let index = binder; index < lines.length; index += 1) {
    if (lines[index] === "  }") { end = index; break; }
  }
  assert.ok(end > binder, "the render() geometry region must still end at the geometry animation-frame block");
  return { source: lines.slice(start, end + 1).join("\n"), start: start + 1, end: end + 1 };
}

// --- counting fake DOM -------------------------------------------------------
const counters = {
  scans: [],
  styleWrites: [],
  propertySets: [],
  datasetWrites: [],
  listeners: [],
  observers: [],
  observes: 0,
  disconnects: 0,
  calls: Object.create(null),
};

function reset() {
  counters.scans.length = 0;
  counters.styleWrites.length = 0;
  counters.propertySets.length = 0;
  counters.datasetWrites.length = 0;
  counters.listeners.length = 0;
  counters.observers.length = 0;
  counters.observes = 0;
  counters.disconnects = 0;
  counters.calls = Object.create(null);
  // Every node is reused across cases, so the dataset bookkeeping written by
  // one run must not make the next run take an early-return branch.
  datasetStores.forEach(store => Object.keys(store).forEach(key => { delete store[key]; }));
}

const datasetStores = [];

function fakeNode(label, children) {
  const store = Object.create(null);
  datasetStores.push(store);
  const node = {
    label,
    dataset: new Proxy(store, {
      set(target, key) {
        counters.datasetWrites.push(label + "." + String(key));
        target[key] = "1";
        return true;
      },
      get(target, key) { return target[key]; },
    }),
    style: {
      setProperty(name, value) { counters.propertySets.push(label + " " + name + "=" + value); },
    },
    querySelectorAll(selector) {
      counters.scans.push(label + " " + selector);
      return children || [];
    },
  };
  // Every inline geometry assignment the shipped code can reach is recorded, so
  // a mutant that reintroduces a clear - or reintroduces a real value - fails.
  ["width", "transform", "minWidth", "maxWidth", "left", "top"].forEach(prop => {
    Object.defineProperty(node.style, prop, {
      configurable: true,
      get() { return ""; },
      set(value) { counters.styleWrites.push(label + ".style." + prop + "=" + JSON.stringify(value)); },
    });
  });
  return node;
}

const rowNodes = [fakeNode("row-1"), fakeNode("row-2"), fakeNode("row-3")];
const viewportNode = fakeNode("viewport");
const listNode = fakeNode("list", rowNodes);
const headNode = fakeNode("head");
const pagerNode = fakeNode("pager");

const rafQueue = [];

const context = {
  state: { folderPage: 1, folderPageSize: 50, folderTotal: 0, page: 1 },
  pagerChanged: true,
  listChanged: true,
  tableHeadChanged: false,
  albumHeadChanged: false,
  albumDetail: false,
  $: id => ({ libraryScroll: viewportNode, trackList: listNode, tableHead: headNode, pager: pagerNode, empty: fakeNode("empty") })[id] || null,
  window: {
    matchMedia: () => ({ matches: false }),
    addEventListener: (type, handler, options) => { counters.listeners.push(type + ":" + (typeof handler)); },
  },
  ResizeObserver: function ResizeObserver(cb) {
    counters.observers.push("constructed");
    this.cb = cb;
    this.observe = () => { counters.observes += 1; };
    this.disconnect = () => { counters.disconnects += 1; };
  },
  requestAnimationFrame: cb => { rafQueue.push(cb); },
  // The survivors of this region: counted so an over-deletion mutant fails.
  measureAutoTrackColumnWidths: () => { counters.calls.measure = (counters.calls.measure || 0) + 1; },
  updateMobilePagerVisibility: () => { counters.calls.pagerVisibility = (counters.calls.pagerVisibility || 0) + 1; },
  bindTrackListInteractions: () => { counters.calls.bindInteractions = (counters.calls.bindInteractions || 0) + 1; },
  console,
};
if (typeof context.ResizeObserver === "function") context.ResizeObserver.prototype = {};
vm.createContext(context);

const headerSyncSource = optionalFunctionSource("syncTrackHeaderScroll");
const headerBindSource = optionalFunctionSource("bindTrackHeaderScroll");
if (headerSyncSource || headerBindSource) {
  vm.runInContext([headerSyncSource, headerBindSource].filter(Boolean).join("\n"), context);
}

function runRenderGeometryRegion() {
  reset();
  rafQueue.length = 0;
  const region = renderGeometryRegion();
  vm.runInContext(region.source, context);
  // Flush the animation frame exactly like the browser would after a commit.
  const queued = rafQueue.splice(0, rafQueue.length);
  queued.forEach(fn => fn());
  return { region, frames: queued.length };
}

const cases = [];
function test(name, body) { cases.push([name, body]); }

// 1. Behavioural: running the real render() geometry region must not touch a
//    single inline style, must not scan the row set, and must not leave a
//    listener or observer behind.
test("the render() geometry region performs no inline geometry writes", () => {
  const run = runRenderGeometryRegion();
  assert.deepEqual(counters.styleWrites, [], "the render() geometry region still writes inline styles: " + JSON.stringify(counters.styleWrites));
  assert.deepEqual(counters.propertySets, [], "the render() geometry region still sets --fnaudio-library-content-width from JavaScript: " + JSON.stringify(counters.propertySets));
  assert.equal(run.frames, 1, "the render() animation frame must still be scheduled once");
});

// 2. Behavioural: the region must still run the two survivors it owns, so the
//    removal cannot be paid for by deleting real work.
test("the render() animation frame still measures columns and pager visibility", () => {
  runRenderGeometryRegion();
  assert.equal(counters.calls.measure, 1, "measureAutoTrackColumnWidths() must still run once per committed geometry change");
  assert.ok((counters.calls.pagerVisibility || 0) >= 1, "updateMobilePagerVisibility() must still run");
  assert.equal(counters.calls.bindInteractions, 1, "bindTrackListInteractions() must still run");
});

// 3. Behavioural: no row walk is left in the render path.
test("the render() geometry region no longer walks the visible row set", () => {
  runRenderGeometryRegion();
  assert.deepEqual(counters.scans, [], "the render() geometry region still queries rows: " + JSON.stringify(counters.scans));
});

// 4. Behavioural: no permanent resize listener or observer is created per view.
test("the render path registers no resize listener and no ResizeObserver", () => {
  runRenderGeometryRegion();
  assert.deepEqual(counters.listeners, [], "the render path still registers window listeners: " + JSON.stringify(counters.listeners));
  assert.deepEqual(counters.observers, [], "the render path still constructs ResizeObservers: " + JSON.stringify(counters.observers));
  assert.equal(counters.datasetWrites.length, 0, "the render path still writes geometry bookkeeping into dataset: " + JSON.stringify(counters.datasetWrites));
});

// 5. Wiring: the mechanism must be gone from the whole shipped file, not just
//    from this region.
test("the retired header-geometry helpers are absent from app.js", () => {
  ["syncTrackHeaderScroll", "bindTrackHeaderScroll", "headerScrollBound", "_headerResizeObserver"].forEach(name => {
    assert.equal(appSource.includes(name), false, "app.js still mentions " + name);
  });
  assert.equal(/style\.width\s*=/.test(appSource), false, "app.js must not write element.style.width at all");
  assert.equal(/style\.transform\s*=/.test(appSource), false, "app.js must not write element.style.transform at all");
  assert.equal(appSource.includes("--fnaudio-library-content-width"), false, "the library content width is a CSS-only contract");
});

// 6. Positive control: the CSS !important grid width is what makes the removed
//    JS redundant; if it changes, this suite has to fail and be re-read.
test("app.css still owns the library grid width with !important", () => {
  // The rule is matched as a whole declaration block, and each declaration is
  // anchored to its own line: an unanchored /width:var\(\)/ would also be
  // satisfied by the min-width line below it, which let a mutant that dropped
  // !important from "width" alone survive the first draft of this suite.
  const ruleAt = cssSource.indexOf(".library-scroll .table-head,");
  assert.ok(ruleAt >= 0, "the desktop grid rule must still cover the table head");
  const rule = cssSource.slice(ruleAt, cssSource.indexOf("}", ruleAt) + 1);
  assert.ok(rule.includes(".library-scroll .track,") && rule.includes(".library-scroll .group-row{"), "the rule must still cover rows and group rows: " + rule);
  assert.match(rule, /^[ \t]*width:var\(--fnaudio-library-content-width\)!important;[ \t]*$/m, "the content width must still be an !important author declaration");
  assert.match(rule, /^[ \t]*min-width:var\(--fnaudio-library-content-width\)!important;[ \t]*$/m, "the min width must still be an !important author declaration");
  assert.match(cssSource, /^[ \t]*--fnaudio-library-content-width:100%;[ \t]*$/m, "the viewport must still default the content width to 100% in CSS");
});

// 7. Positive control: the live column mechanism is untouched.
test("the column widths still travel through the --fnaudio-track-columns property", () => {
  const sets = (appSource.match(/setProperty\("--fnaudio-track-columns"/g) || []).length;
  assert.ok(sets >= 5, "expected the surviving column mechanism to keep setting --fnaudio-track-columns, found " + sets);
  assert.match(cssSource, /\.table-head,\.track\{grid-template-columns:var\(--fnaudio-track-columns/, "the grid template must still read the column property");
});

// 8. Wiring: the animation frame keeps bounded layout work and refreshes the
//    album-detail head only when that view is active.
test("the render() animation frame body keeps only real layout work", () => {
  const lines = appLines();
  const region = renderGeometryRegion();
  const frame = lines.slice(region.start - 1, region.end + 12).join("\n");
  const body = frame.slice(frame.indexOf("requestAnimationFrame(() => {"));
  assert.ok(body.length > 0, "the animation frame must still exist");
  assert.match(body, /measureAutoTrackColumnWidths\(\);/, "column measurement must stay in the frame");
  assert.match(body, /updateMobilePagerVisibility\(\);/, "pager visibility must stay in the frame");
  const statements = body.slice(body.indexOf("{") + 1, body.indexOf("});")).split("\n").map(line => line.trim()).filter(Boolean);
  assert.deepEqual(statements, [
    "measureAutoTrackColumnWidths();",
    "if (albumDetail) {",
    'const albumHead = $("albumDetailTableHead");',
    "if (albumHead) {",
    'albumHead.dataset.fnaudioTableHeadSignature = "";',
    "renderTableHead(albumHead);",
    "}",
    "}",
    "updateMobilePagerVisibility();",
  ], "the frame must not carry retired geometry writes back in: " + JSON.stringify(statements));
});

// 9. Face-level regression: the folder pager still renders from the same math.
test("the folder pager still renders page and total from state", () => {
  const source = optionalFunctionSource("renderFolders");
  assert.ok(source, "renderFolders must stay in app.js");
  assert.match(source, /const folderPages = Math\.max\(1, Math\.ceil\(libraryCount\(state\.folderTotal\) \/ state\.folderPageSize\)\);/, "the folder page count must stay derived, not cached");
  assert.match(source, /文件夹 \$\{state\.folderPage\} \/ \$\{folderPages\}/, "the folder pager must still print the live page and page count");
});

// 10. Face-level regression: the mobile pager hand-off stays gated on a change.
test("mobile pager visibility is only recomputed when the pager markup changed", () => {
  const region = renderGeometryRegion();
  const head = appLines().slice(region.start - 6, region.start).join("\n");
  assert.match(head, /const pagerChanged = pager\.innerHTML !== pagerHtml;/, "the pager must still be compared before being rewritten");
  assert.match(head, /if \(pagerChanged\) updateMobilePagerVisibility\(\);/, "visibility refresh must stay gated on pagerChanged");
});

let failures = 0;
for (const [name, body] of cases) {
  try { body(); } catch (error) { failures += 1; console.error(`FAIL ${name}\n  ${error.message}`); continue; }
  console.log(`ok   ${name}`);
}
if (failures) { console.error(`${failures} of ${cases.length} track header geometry checks failed`); process.exit(1); }
console.log("track header geometry retirement regression checks passed.");
