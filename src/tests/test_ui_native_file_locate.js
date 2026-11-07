/* Locating a song inside fnOS's own file manager.
 *
 * 「打开包含的文件夹」 used to stop at the directory: the host bridge navigates and
 * nothing more, so the song still had to be found by hand among hundreds of rows.
 * R500 reads the file manager's own rows instead — the row carries the absolute
 * path, the table is virtualised (so later rows only exist after the list scrolls),
 * and a row is selected by pressing it.
 *
 * The lookups are pinned against a fake document and the three steps of
 * `findNativeFileRow` (already rendered / page the list / fall back to the search
 * box) are executed in a vm, because the failure mode of a wrong order is silent:
 * the folder opens and the file is simply not highlighted.
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app/ui/app.js"), "utf8");
const bridgeSource = fs.readFileSync(path.join(root, "app/ui/native_share_bridge.js"), "utf8");

function functionSource(source, name) {
  const match = source.match(new RegExp("^(?:async )?function " + name + "\\([^]*?^}", "m"));
  assert.ok(match, `no function ${name}`);
  return match[0];
}

// ---- the bridge, against a fake document -----------------------------------

function makeView() {
  class FakeEvent {
    constructor(type, init) { this.type = type; this.bubbles = Boolean(init && init.bubbles); }
  }
  class FakeMouseEvent extends FakeEvent {
    constructor(type, init) { super(type, init); Object.assign(this, init || {}); }
  }
  class FakeKeyboardEvent extends FakeMouseEvent {}
  class FakeInput {}
  Object.defineProperty(FakeInput.prototype, "value", { get() { return this._value; }, set(next) { this._value = next; } });
  return { Event: FakeEvent, MouseEvent: FakeMouseEvent, KeyboardEvent: FakeKeyboardEvent, HTMLInputElement: FakeInput };
}
const view = makeView();

function makeElement(options = {}) {
  const { text = "", width = 120, height = 24, dataPath = "", children = [] } = options;
  const events = [];
  const element = {
    textContent: text,
    className: options.className || "",
    dataset: dataPath ? { path: dataPath } : {},
    children,
    events,
    scrollTop: options.scrollTop || 0,
    scrollHeight: options.scrollHeight || 0,
    clientHeight: options.clientHeight || 0,
    getAttribute: () => null,
    getBoundingClientRect: () => {
      const top = options.y ?? 60;
      return { x: 40, y: top, left: 40, top, width, height, bottom: top + height, right: 40 + width };
    },
    dispatchEvent: event => { events.push(event); return true; },
    contains: other => children.includes(other),
    querySelectorAll: selector => (selector === ".trim-ui__table--td" ? children : []),
    ownerDocument: { defaultView: view },
  };
  return element;
}

function makeDocument(buckets) {
  return { querySelectorAll: selector => buckets[selector] || [] };
}

const sandbox = { console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(bridgeSource, sandbox);
const bridge = sandbox.fnAudioNativeShare;

// ---- relativePath / parentOf ------------------------------------------------

assert.equal(bridge.relativePath("/vol1/1000/music/a.mp3"), "vol1/1000/music/a.mp3");
assert.equal(bridge.relativePath("vol1/1000/music/a.mp3"), "vol1/1000/music/a.mp3");
assert.equal(bridge.relativePath("  //vol1//music/  "), "vol1/music/",
  "both spellings and doubled separators normalise to one path");
assert.equal(bridge.relativePath(""), "");
assert.equal(bridge.relativePath(null), "");
assert.equal(bridge.parentOf("/vol1/music/album/a.mp3"), "vol1/music/album");
assert.equal(bridge.parentOf("a.mp3"), "", "a bare name has no parent inside the shell");
assert.equal(bridge.parentOf("/vol1"), "");

// ---- findFileRow ------------------------------------------------------------

{
  const target = makeElement({ dataPath: "vol1/music/album/song.flac" });
  const sameName = makeElement({ dataPath: "vol1/music/other/song.flac" });
  const hidden = makeElement({ dataPath: "vol1/music/album/song.flac", width: 0 });
  const doc = makeDocument({ "tr[data-path]": [sameName, hidden] });
  assert.equal(bridge.findFileRow(doc, "/vol1/music/album/song.flac"), null,
    "an unrendered row is not a row we can point at");
  assert.equal(bridge.findFileRow(makeDocument({ "tr[data-path]": [sameName, target] }), "/vol1/music/album/song.flac"), target,
    "the path decides, not the file name");
  assert.equal(bridge.findFileRow(makeDocument({ "tr[data-path]": [sameName] }), "/vol1/music/album/song.flac"), null,
    "the same file name in another folder is another file");
  assert.equal(bridge.findFileRow(makeDocument({}), ""), null);
  assert.equal(bridge.findFileRow(null, "/vol1/a.mp3"), null);
}

// ---- isFolderListing --------------------------------------------------------

{
  const doc = makeDocument({ "tr[data-path]": [
    makeElement({ dataPath: "vol1/music/album/song.flac" }),
    makeElement({ dataPath: "vol1/music/album/disc/track.flac" }),
  ] });
  assert.equal(bridge.isFolderListing(doc, "/vol1/music/album"), true, "a file directly inside counts");
  assert.equal(bridge.isFolderListing(doc, "/vol1/music"), false,
    "a child folder's files do not make the parent the open folder");
  assert.equal(bridge.isFolderListing(makeDocument({}), "/vol1/music"), false);
  assert.equal(bridge.isFolderListing(doc, ""), false);
}

// ---- findListScroller / scrollListBy ---------------------------------------

{
  const flat = makeElement({ scrollHeight: 400, clientHeight: 400 });
  const tiny = makeElement({ scrollHeight: 900, clientHeight: 40 });
  const scroller = makeElement({ scrollHeight: 3774, clientHeight: 399 });
  const doc = makeDocument({ ".trim-ui__table--scrollbar": [flat, tiny, scroller] });
  assert.equal(bridge.findListScroller(doc), scroller, "only an element that can actually scroll counts");

  assert.equal(bridge.scrollListBy(scroller, 300), true);
  assert.equal(scroller.scrollTop, 300);
  assert.equal(scroller.events[0].type, "scroll", "the virtual list only re-renders if it hears the scroll");
  assert.equal(bridge.scrollListBy(scroller, 999999), true);
  assert.equal(scroller.scrollTop, 3774 - 399, "the scroll must stop at the last page");
  assert.equal(bridge.scrollListBy(scroller, 100), false, "a step that cannot move reports so");
  assert.equal(bridge.scrollListBy(null, 100), false);
}

// ---- revealRow --------------------------------------------------------------

{
  const row = makeElement({ y: 900, height: 37 });
  const box = makeElement({ y: 100, height: 399, scrollHeight: 3000, clientHeight: 399, scrollTop: 0 });
  assert.equal(bridge.revealRow(row, box), true);
  assert.equal(box.scrollTop, (900 - 100) - (399 - 37) / 2, "the row is centred in the list box");
  assert.equal(bridge.revealRow(makeElement({ width: 0 }), box), false);
}

// ---- nameCellOf / isRowSelected / selectRow --------------------------------

{
  const nameCell = makeElement({ text: "song.flac" });
  const hiddenCell = makeElement({ width: 0 });
  const row = makeElement({ dataPath: "vol1/a/song.flac", children: [hiddenCell, nameCell] });
  assert.equal(bridge.nameCellOf(row), nameCell, "the first rendered cell is the name column");
  assert.equal(bridge.nameCellOf(null), null);

  assert.equal(bridge.isRowSelected(makeElement({ className: "trim-ui__table--tr trim-ui__table--tr-selected" })), true);
  assert.equal(bridge.isRowSelected(makeElement({ className: "trim-ui__table--tr-selected-ish" })), false,
    "the class must be whole");
  assert.equal(bridge.isRowSelected(null), false);

  assert.equal(bridge.selectRow(row), true);
  assert.deepEqual(row.events.map(event => event.type), ["mouseover", "mousedown", "mouseup", "click"],
    "rows are list items, so the press sequence is replayed");
}

// ---- findNativeFileRow, executed -------------------------------------------

const findBody = functionSource(app, "findNativeFileRow");
const selectBody = functionSource(app, "selectNativeFileRow");
const locateBody = functionSource(app, "locateNativeFile");
const scanConstant = app.match(/^const NATIVE_FILE_SCAN_PAGES = \d+;/m);
assert.ok(scanConstant, "the paging budget must be a named constant");
assert.match(findBody, /for \(let page = 0; page < NATIVE_FILE_SCAN_PAGES; page \+= 1\)/,
  "paging must be bounded by that constant");

const folder = "/vol1/music/album";
const location = { path: `${folder}/song.flac`, folder };

function harness(bridgeOverrides = {}, options = {}) {
  const calls = [];
  const context = {
    console,
    NATIVE_FILE_SCAN_PAGES: 8,
    // One shot: the production code polls, the test only cares about what is read.
    waitForElement: async probe => probe() || null,
    globalThis: null,
  };
  context.globalThis = context;
  context.fnAudioNativeShare = Object.assign({
    hasTable: () => true,
    isFolderListing: (doc, value) => { calls.push(["isFolderListing", value]); return true; },
    findFileRow: () => null,
    findListScroller: () => null,
    scrollListBy: () => { calls.push(["scrollListBy"]); return true; },
    findSearchInput: () => null,
    typeInto: (input, value) => { calls.push(["typeInto", value]); return true; },
    searchTerm: name => name.replace(/\.[^.]+$/, ""),
    revealRow: () => { calls.push(["revealRow"]); return true; },
    selectRow: () => { calls.push(["selectRow"]); return true; },
    isRowSelected: row => Boolean(row && row.selected),
  }, bridgeOverrides);
  if (options.shell !== undefined) context.parentShellDocument = () => options.shell;
  vm.createContext(context);
  vm.runInContext([findBody, selectBody, locateBody].join("\n"), context);
  return { context, calls };
}

(async () => {
  // 1. Already rendered: read it and stop.
  {
    const row = { id: "row", selected: false };
    const { context, calls } = harness({ findFileRow: () => row, findListScroller: () => ({ clientHeight: 300 }) });
    assert.equal(await context.findNativeFileRow({}, location), row);
    assert.deepEqual(calls.filter(entry => entry[0] === "scrollListBy"), [], "a visible row must not page the list");
  }

  // 2. Rendered only after paging: step by 80% of the box, then read it.
  {
    const row = { id: "row", selected: false };
    let reads = 0;
    const scroller = { clientHeight: 300, scrollTop: 0 };
    const steps = [];
    const { context } = harness({
      findFileRow: () => (++reads > 2 ? row : null),
      findListScroller: () => scroller,
      scrollListBy: (node, delta) => { steps.push(delta); node.scrollTop += delta; return true; },
    });
    assert.equal(await context.findNativeFileRow({}, location), row);
    assert.deepEqual(steps, [240, 240], "each page is 80% of the visible box, so no row is skipped");
  }

  // 3. Paging runs out: the file manager's own search is the last resort, and it
  //    is typed with the file's stem rather than the whole name.
  {
    const row = { id: "row", selected: false };
    let typed = false;
    const { context, calls } = harness({
      findFileRow: () => (typed ? row : null),
      findListScroller: () => ({ clientHeight: 300 }),
      scrollListBy: () => false,
      findSearchInput: () => ({ id: "search" }),
      typeInto: (input, value) => { typed = true; calls.push(["typeInto", value]); return true; },
    });
    assert.equal(await context.findNativeFileRow({}, location), row);
    const typedCall = calls.find(entry => entry[0] === "typeInto");
    assert.ok(typedCall, "the search box must be used once paging stops moving");
    assert.equal(typedCall[1], "song", "the extension is not part of the query");
  }

  // 4. The window is showing another folder: nothing is read out of it.
  {
    const reads = [];
    const { context, calls } = harness({
      isFolderListing: (doc, value) => { calls.push(["isFolderListing", value]); return false; },
      findFileRow: path => { reads.push(path); return null; },
    });
    assert.equal(await context.findNativeFileRow({}, location), null);
    assert.deepEqual(reads, [], "a stale listing must not be paged around");
    assert.deepEqual(calls, [["isFolderListing", folder]]);
  }

  // 5. Missing inputs short-circuit instead of throwing.
  {
    const { context } = harness();
    assert.equal(await context.findNativeFileRow({}, { path: "", folder }), null);
    assert.equal(await context.findNativeFileRow({}, { path: `${folder}/song.flac`, folder: "" }), null);
    assert.equal(await context.findNativeFileRow(null, location), null);
  }

  // 6. Selecting: centre, press, then confirm the class actually landed.
  {
    const row = { id: "row", selected: false };
    const order = [];
    const { context } = harness({
      findFileRow: () => row,
      findListScroller: () => ({ clientHeight: 300 }),
      revealRow: () => { order.push("reveal"); return true; },
      selectRow: target => { order.push("select"); target.selected = true; return true; },
      isRowSelected: target => Boolean(target && target.selected),
    });
    assert.equal(await context.selectNativeFileRow({}, location), true);
    assert.deepEqual(order, ["reveal", "select"], "the row is brought into view before it is pressed");
  }
  {
    const { context } = harness({ findFileRow: () => null });
    assert.equal(await context.selectNativeFileRow({}, location), false, "a row that never appears is not a location");
  }
  {
    // The press landed but the shell re-rendered and lost the selection.
    const { context } = harness({
      findFileRow: () => ({ id: "row", selected: false }),
      selectRow: () => true,
      isRowSelected: () => false,
    });
    assert.equal(await context.selectNativeFileRow({}, location), false,
      "a selection that does not survive is reported as not located");
  }

  // 7. locateNativeFile is the only place that reaches for the desktop shell.
  {
    const shell = { id: "shell" };
    const { context } = harness({ findFileRow: () => ({ selected: true }), isRowSelected: row => row.selected }, { shell });
    assert.equal(await context.locateNativeFile(location), true);
  }
  {
    const { context } = harness({}, { shell: null });
    assert.equal(await context.locateNativeFile(location), false, "a plain tab has no shell to read");
  }

  console.log("native file locate: all assertions passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
