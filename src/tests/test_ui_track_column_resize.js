const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// R161 - the "table head / album detail / track row / metadata row patch" face of
// app.js (source lines 3019-3380 at intake, 12 named functions).
//
// Deep reading this face found a real defect family in the interactive column
// resize path inside renderTableHead():
//
//   (a) Two width regimes.  Every declarative path uses the *per-column* band: the
//       shared track-table presentation module limits each column on its own
//       (duration 72..96, track_no 64..84, title 260..620, ...), the committed grid
//       template goes through safeWidth(), and measureAutoTrackColumnWidths()
//       clamps measured widths with trackColumnWidthLimits().  The two *user* write
//       paths instead used a flat 64..900 band: saveTrackColumnWidth() persisted
//       that, and the in-drag handler applied that while rebuilding the grid
//       template by hand rather than reusing trackGridTemplate().  Dragging the
//       duration column ~40px past its 96px maximum therefore persisted 112px and
//       displayed 112px; the next header re-render recomputed 96px, so the column
//       snapped back by itself, and the following drag started from the phantom
//       112px - the first pointermove jumped the column before the pointer travelled
//       that far.  A stored width the renderer can never honour is the bug.
//   (b) One leaking drag listener.  The drag attached `pointermove` on window and
//       detached it only inside the `pointerup` handler.  A drag ended by
//       `pointercancel` (touch-gesture takeover, lost pointer capture) never
//       delivers pointerup, so the handler stayed attached.  `pointermove` also
//       fires while merely hovering the page, so every later mouse move rewrote
//       --fnaudio-track-columns from the stale startWidth/startX, and a second drag
//       left two handlers fighting over the same CSS variable.  The same file
//       already pairs the two endings for the long-press gesture
//       (list.addEventListener("pointercancel", finishTrackLongPress)), so this fix
//       reuses the writing pattern the file already owns.
//
// The fix routes every width through trackColumnWidthLimits() - the accessor that
// already prefers the shared table - converges legacy out-of-band preferences when
// they are read, reuses trackGridTemplate() for the in-drag template, and gives the
// drag one guarded teardown for both endings.
//
// Each numbered case below is a discriminator with a named mutation target; see the
// fnAudio-R161 review notes for the mutation matrix (V1..V8).

const uiDir = path.join(__dirname, "..", "app", "ui");
const appSource = fs.readFileSync(path.join(uiDir, "app.js"), "utf8");
const presentationSource = fs.readFileSync(path.join(uiDir, "track_table_presentation.js"), "utf8");

function sourceSlice(startMarker, endMarker) {
  const start = appSource.indexOf(startMarker);
  const end = appSource.indexOf(endMarker, start);
  assert.ok(start >= 0 && end > start, `app.js no longer contains ${startMarker} .. ${endMarker}`);
  return appSource.slice(start, end);
}

function functionSource(name) {
  const match = appSource.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the column resize regression`);
  return match[0];
}

// New in R161. Kept optional so this same file still runs - and fails
// behaviourally instead of erroring while building the harness - against the
// pre-fix source used for the red proof.
function optionalFunctionSource(name) {
  const match = appSource.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  return match ? match[0] : "";
}

const constBlock = sourceSlice("const TRACK_COLUMN_DEFINITIONS", "state.libraryStatus = null;");
const shipped = [
  "normalizeTrackColumnWidths",
  "currentTrackColumnWidths",
  "saveTrackColumnWidth",
  "trackColumnWidthLimits",
  "trackGridTemplate",
  "renderTableHead",
].map(functionSource).join("\n");
const clampSource = optionalFunctionSource("clampTrackColumnWidth");

const COLUMNS = ["title", "duration"];
const GRID_VAR = "--fnaudio-track-columns";

function styleSink() {
  return {
    vars: new Map(),
    writes: 0,
    getPropertyValue(name) {
      return this.vars.get(name) || "";
    },
    removeProperty(name) {
      const value = this.vars.get(name) || "";
      this.vars.delete(name);
      return value;
    },
    setProperty(name, value) {
      this.vars.set(name, value);
      this.writes += 1;
    },
  };
}

// The handles are read back out of the markup the shipped code actually committed,
// so a header that stopped emitting (or binding) resize handles fails here rather
// than silently testing nothing.
function createHead() {
  const handles = new Map();
  const head = {
    dataset: {},
    style: styleSink(),
    innerHTML: "",
    querySelectorAll(selector) {
      if (selector !== "[data-column-resize]") return [];
      return [...String(head.innerHTML).matchAll(/data-column-resize="([^"]+)"/g)].map(match => {
        const key = match[1];
        if (!handles.has(key)) {
          handles.set(key, {
            dataset: { columnResize: key },
            captures: 0,
            setPointerCapture() { this.captures += 1; },
          });
        }
        return handles.get(key);
      });
    },
  };
  return head;
}

function templateWidths(template) {
  return String(template).trim().split(/\s+/)
    .map(part => Number(part.replace("px", "")))
    .filter(value => Number.isFinite(value));
}

function harness(options = {}) {
  const scope = "songs";
  const state = {
    view: "all",
    sortKey: "title",
    sortDir: "asc",
    groupName: "",
    autoTrackColumnWidths: { songs: {} },
    trackColumnWidthPreferences: { songs: Object.assign({}, options.preferences) },
  };
  const head = createHead();
  const persist = { preferences: 0, userState: 0 };
  const registrations = new Map();
  const listener = {
    addEventListener(type, handler, config) {
      const list = registrations.get(type) || [];
      list.push({ handler, once: !!(config && config.once) });
      registrations.set(type, list);
    },
    removeEventListener(type, handler) {
      registrations.set(type, (registrations.get(type) || []).filter(entry => entry.handler !== handler));
    },
  };
  // Faithful enough for this path: an entry detached by an earlier handler in the
  // same dispatch must not run, and a `once` entry leaves after firing.
  function fire(type, event) {
    [...(registrations.get(type) || [])].forEach(entry => {
      if (!(registrations.get(type) || []).includes(entry)) return;
      entry.handler(event);
      if (entry.once) {
        registrations.set(type, (registrations.get(type) || []).filter(other => other !== entry));
      }
    });
    return (registrations.get(type) || []).length;
  }
  const context = {
    assert,
    state,
    head,
    persist,
    registrations,
    $: id => (id === "tableHead" ? head : null),
    document: { body: { style: styleSink() }, createElement: () => ({ innerHTML: "", content: {} }) },
    window: Object.assign({ matchMedia: () => ({ matches: false }) }, listener),
    trackColumnScope: () => scope,
    activeTrackColumns: () => (options.columns || COLUMNS).slice(),
    sortOptionsForView: () => [["title", "label"]],
    isCreatorView: () => false,
    currentCreatorName: () => "",
    isAlbumCollectionView: () => false,
    groupViews: {},
    applyTrackSort: () => { context.sortClicks += 1; },
    openColumnsDialog: () => { context.columnDialogOpens += 1; },
    persistTrackColumnPreferences: () => { persist.preferences += 1; },
    scheduleUserStateSave: () => { persist.userState += 1; },
    sortClicks: 0,
    columnDialogOpens: 0,
  };
  vm.runInNewContext([
    options.presentation === false ? "" : presentationSource,
    constBlock,
    shipped,
    clampSource,
    "this.api = {"
    + " renderTableHead: renderTableHead,"
    + " trackGridTemplate: trackGridTemplate,"
    + " currentTrackColumnWidths: currentTrackColumnWidths,"
    + " saveTrackColumnWidth: saveTrackColumnWidth,"
    + " clampTrackColumnWidth: typeof clampTrackColumnWidth === \"function\" ? clampTrackColumnWidth : null,"
    + " presentation: typeof fnAudioTrackTablePresentation === \"object\" ? fnAudioTrackTablePresentation : null,"
    + " definitions: TRACK_COLUMN_DEFINITIONS,"
    + "};",
  ].filter(Boolean).join("\n"), context);

  const api = context.api;
  const view = {
    context,
    api,
    state,
    head,
    persist,
    registrations,
    fire,
    render() {
      api.renderTableHead();
      return view.applied();
    },
    applied() {
      return head.style.vars.get(GRID_VAR) || context.document.body.style.vars.get(GRID_VAR) || "";
    },
    bodyApplied() {
      return context.document.body.style.vars.get(GRID_VAR) || "";
    },
    handle(key) {
      return head.querySelectorAll("[data-column-resize]").find(entry => entry.dataset.columnResize === key) || null;
    },
    widths() {
      return templateWidths(view.applied());
    },
    stored(key) {
      return state.trackColumnWidthPreferences.songs[key];
    },
    attached(type) {
      return (registrations.get(type) || []).length;
    },
    startDrag(key, clientX) {
      const handle = view.handle(key);
      assert.ok(handle, `renderTableHead() must bind a [data-column-resize="${key}"] handle`);
      let prevented = false;
      handle.onpointerdown({ clientX, pointerId: 7, preventDefault() { prevented = true; } });
      assert.equal(prevented, true, "a resize drag must prevent the default pointerdown");
      assert.equal(handle.captures, 1, "a resize drag must capture its pointer");
      return handle;
    },
  };
  return view;
}

// --- 1. the in-drag width must respect the column's own band, not a flat 900 ----
const first = harness();
first.render();
assert.deepEqual(first.widths(), [280, 72], "the committed template must start from the compact column definitions");
first.startDrag("duration", 500);
first.fire("pointermove", { clientX: 540 });
assert.deepEqual(first.widths(), [280, 96],
  "V1: dragging must clamp duration at its 96px maximum instead of the flat 900px band");
assert.equal(first.attached("pointermove"), 1, "an in-flight drag must listen for pointermove");

// --- 2. what a drag persists must be what the renderer shows (no snap-back) ----
first.fire("pointerup", { clientX: 540 });
assert.equal(first.stored("duration"), 96,
  "V2: a resize must persist exactly the width the grid is able to render");
assert.equal(first.persist.preferences, 1, "one completed drag must persist the preferences once");
assert.equal(first.persist.userState, 1, "one completed drag must schedule the user-state save once");
const dragTemplate = first.applied();
first.context.state.sortDir = "desc";
first.render();
assert.equal(first.applied(), dragTemplate,
  "V2: the next header render must not snap a persisted column back to another width");

// --- 3. a legacy out-of-band width must converge, and must not jump on grab ----
const legacy = harness({ preferences: { duration: 372 } });
const legacyCommitted = legacy.render();
assert.deepEqual(legacy.widths(), [280, 96], "V3: the committed template clamps a stored 372px duration");
assert.equal(legacy.api.currentTrackColumnWidths().duration, 96,
  "V3: reading stored widths must converge them to the shared per-column band");
legacy.startDrag("duration", 600);
legacy.fire("pointermove", { clientX: 600 });
assert.equal(legacy.applied(), legacyCommitted,
  "V4: grabbing a column must not jump it to a width the grid never displayed");
legacy.fire("pointermove", { clientX: 640 });
assert.deepEqual(legacy.widths(), [280, 96], "V4: a legacy width may not be dragged past its own maximum");
legacy.fire("pointerup", { clientX: 640 });
assert.equal(legacy.stored("duration"), 96, "V4: releasing a legacy-width drag must store the honoured width");

// --- 5. pointercancel must tear the drag down ---------------------------------
const cancelled = harness();
const preDragTemplate = cancelled.render();
cancelled.startDrag("duration", 500);
cancelled.fire("pointermove", { clientX: 540 });
assert.deepEqual(cancelled.widths(), [280, 96], "the drag itself must work before testing how it ends");
assert.equal(cancelled.attached("pointermove"), 1, "precondition: the drag registered pointermove");
cancelled.fire("pointercancel", {});
assert.equal(cancelled.attached("pointermove"), 0,
  "V5: a drag ended by pointercancel must detach its window pointermove handler");
assert.equal(cancelled.attached("pointerup"), 0, "V5: pointercancel must detach the pointerup handler");
const writesAfterCancel = cancelled.head.style.writes;
cancelled.fire("pointermove", { clientX: 4000 });
assert.equal(cancelled.head.style.writes, writesAfterCancel,
  "V5: a leaked resize handler must not rewrite the grid while the pointer merely hovers");
assert.equal(cancelled.applied(), preDragTemplate,
  "V6: a cancelled drag must leave the pre-drag template applied, not an unsaved width");
assert.equal(cancelled.persist.preferences, 0, "a cancelled drag must not persist a width");

// --- 7. the pointerup path stays single-shot even if both endings arrive -------
const doubled = harness();
doubled.render();
doubled.startDrag("duration", 500);
doubled.fire("pointermove", { clientX: 560 });
doubled.fire("pointerup", { clientX: 560 });
const settledTemplate = doubled.applied();
assert.equal(doubled.stored("duration"), 96, "V7 precondition: the completed drag stored the honoured width");
assert.equal(doubled.persist.preferences, 1, "V7 precondition: one save per drag");
doubled.fire("pointercancel", {});
doubled.fire("pointerup", { clientX: 100 });
assert.equal(doubled.persist.preferences, 1, "V7: a second end event must not save again");
assert.equal(doubled.applied(), settledTemplate,
  "V7: a second end event must not rewind or reapply a width after the drag settled");

// --- 8. persistence and the read path must agree with the shared module --------
const presentation = first.api.presentation;
assert.ok(presentation && typeof presentation.widthLimits === "function",
  "the shared track-table presentation module must stay the source of the width band");
["title", "duration", "track_no", "composer"].forEach(key => {
  const probe = harness();
  probe.api.saveTrackColumnWidth(key, 1000000);
  assert.equal(probe.stored(key), presentation.widthLimits(key)[1],
  `V8: saveTrackColumnWidth("${key}") must clamp to that column's own maximum`);
  probe.api.saveTrackColumnWidth(key, Number.NaN);
  assert.equal(probe.stored(key), presentation.widthLimits(key)[0] <= first.api.definitions[key].width
    ? first.api.definitions[key].width
    : presentation.widthLimits(key)[0],
  `an unusable width must fall back to the "${key}" column definition`);
});

// --- 9. the fallback (no shared module) must keep the same band ---------------
const fallback = harness({ presentation: false, preferences: { duration: 372 } });
fallback.render();
assert.equal(fallback.api.currentTrackColumnWidths().duration, 96,
  "V9: the in-file limits table must agree with the shared module when the module is absent");
fallback.startDrag("duration", 500);
fallback.fire("pointermove", { clientX: 560 });
assert.deepEqual(fallback.widths(), [280, 96], "V9: the fallback path must clamp the drag the same way");

// --- 10. source wiring: one regime, one teardown, no private band -------------
const dragBlock = sourceSlice(
  "head.querySelectorAll(\"[data-column-resize]\")",
  "\n  head.dataset.fnaudioTableHeadBound"
);
assert.ok(dragBlock.includes("\"pointercancel\""),
  "V10: the resize drag must end on pointercancel as well as pointerup");
assert.ok(dragBlock.includes("clampTrackColumnWidth("),
  "V10: the resize drag must reuse the shared per-column clamp");
assert.ok(dragBlock.includes("trackGridTemplate("),
  "V10: the resize drag must reuse the committed grid template instead of a second formula");
assert.ok(!/Math\.min\(900/.test(dragBlock), "V10: the resize drag must not keep a private width band");
assert.ok(functionSource("saveTrackColumnWidth").includes("clampTrackColumnWidth("),
  "V10: the persistence path must use the same clamp as the renderer");

console.log("track column resize regression checks passed.");
