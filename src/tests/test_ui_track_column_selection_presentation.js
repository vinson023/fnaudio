const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// R170 reads two contiguous unread faces of src/app/ui/app.js in one sitting: the
// per-scope track-column preference family, and the list-selection plus navigation
// family.  Three defects came out of that read, and each is reproduced below
// against the code as it stands on disk before any repair:
//
// A. formatSize() only ever handled a number.  It is reached from the fallback
//    track-column renderer, which produces the size cell of every visible row, and
//    from the runtime-lyrics budget label.  A size that arrives as a string - which
//    is what a stored snapshot or a JSON edge can hand over - never enters the
//    division loop and then calls a number method on a string, so the render throws
//    instead of showing a size; a non-finite size paints "Infinity GB" and a
//    negative one paints "-5 B".
//
// B. persistTrackColumnPreferences() writes both column keys straight to
//    localStorage, while every sibling in the same family - the read side and the
//    legacy migration - already wraps the same call in try/catch.  One of its five
//    callers is on the read path: a scope that only has a legacy key migrates
//    itself and persists, so a full or blocked quota turns "open a list" into an
//    exception thrown out of the renderer.
//
// C. toggleTrackSelection() mutates state.selectedTrackRowKeys in place and then
//    hands that very collection to setTrackSelection(), whose memo compares the
//    request against the state that was just changed.  The comparison is therefore
//    always equal, the early return always wins, and no row class is ever applied:
//    a Ctrl+click moves the selection in state only, and the row the user clicked
//    keeps - or keeps losing - its highlight.  The declarative callers rely on that
//    same memo on purpose, which is why the repair belongs at the caller.

const app = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const policy = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "creator_view_policy.js"), "utf8");

// The library views that own a paged request, copied from the constant above so
// setView() keeps the branch it really takes on a playlist surface.
const PAGED_VIEWS = ["all", "dsd", "recent", "random100", "folders", "albums", "artists", "composers", "genres"];

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the column/selection regression`);
  return match[0];
}

function constSource(name) {
  const block = app.match(new RegExp("^const " + name + " = \\{[\\s\\S]*?^\\};", "m"));
  if (block) return block[0];
  const line = app.match(new RegExp("^const " + name + " = [^\\n]*", "m"));
  assert.ok(line, `const ${name} must stay extractable for the column/selection regression`);
  return line[0];
}

function literalOf(name) {
  const match = constSource(name).match(/"([^"]+)"/);
  assert.ok(match, `const ${name} must keep a string literal key`);
  return match[1];
}

// Values built inside the vm come from that realm, so compare them structurally.
function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

function classNode(kind, key, dataset = {}) {
  const node = { kind, key, selected: null, writes: [], dataset: { ...dataset } };
  if (kind === "track") node.dataset.trackRowKey = key;
  if (kind === "group") node.dataset.groupKey = key;
  if (kind === "nav") node.dataset.view = key;
  node.classList = {
    toggle(className, force) {
      node.writes.push(`${className}=${force === true}`);
      if (className === "is-selected") node.selected = force === true;
    },
  };
  return node;
}

function painted(rows) {
  return rows.filter(row => row.selected === true).map(row => row.key);
}

function writeCount(rows) {
  return rows.reduce((total, row) => total + row.writes.length, 0);
}

function makeStorage(options) {
  const store = new Map();
  for (const [key, value] of Object.entries(options.prefill || {})) store.set(key, value);
  const writes = [];
  return {
    store,
    writes,
    getItem(key) {
      writes.push(`get:${key}`);
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      writes.push(`set:${key}`);
      if (options.storageThrows) {
        const error = new Error("simulated quota failure");
        error.name = "QuotaExceededError";
        throw error;
      }
      store.set(key, value);
    },
  };
}
// The slice of app.js this regression needs, copied verbatim out of the file so a
// repair cannot quietly change the shape of a function and leave the test asserting
// a stale contract.  Everything is evaluated inside one vm context whose only globals
// are the fake DOM, the fake storage, and the fake collaborators listed below.
const SOURCE = [
  policy,
  constSource("MAX_UI_PREFERENCE_STORAGE_CHARS"),
  constSource("TRACK_COLUMNS_STORE_KEY"),
  constSource("TRACK_COLUMN_WIDTHS_STORE_KEY"),
  constSource("LEGACY_TRACK_COLUMNS_STORE_KEY"),
  constSource("OLDER_TRACK_COLUMNS_STORE_KEY"),
  constSource("TRACK_COLUMN_DEFINITIONS"),
  constSource("DEFAULT_TRACK_COLUMNS"),
  constSource("DEFAULT_LIBRARY_TRACK_COLUMNS"),
  constSource("DEFAULT_ALBUM_DETAIL_TRACK_COLUMNS"),
  constSource("PAGED_LIBRARY_VIEWS"),
  functionSource("parseStoredJson"),
  functionSource("escapeHtml"),
  functionSource("isCreatorView"),
  functionSource("currentCreatorName"),
  functionSource("setCurrentCreator"),
  functionSource("setCurrentCreatorAllTracks"),
  functionSource("resetCreatorState"),
  functionSource("isCreatorAllTracksView"),
  functionSource("isPlaylistView"),
  functionSource("isPagedLibraryView"),
  functionSource("normalizeTrackColumns"),
  functionSource("defaultTrackColumnsForScope"),
  functionSource("trackColumnsForScope"),
  functionSource("loadTrackColumnPreferences"),
  functionSource("normalizeTrackColumnWidths"),
  functionSource("loadTrackColumnWidthPreferences"),
  functionSource("trackColumnScopePart"),
  functionSource("buildTrackColumnScope"),
  functionSource("trackColumnScope"),
  functionSource("legacyTrackColumnScope"),
  functionSource("trackColumnScopeLabel"),
  functionSource("persistTrackColumnPreferences"),
  functionSource("currentTrackColumns"),
  functionSource("saveTrackColumns"),
  functionSource("currentTrackColumnWidths"),
  functionSource("saveTrackColumnWidth"),
  functionSource("trackColumnWidthLimits"),
  functionSource("clampTrackColumnWidth"),
  functionSource("formatSize"),
  functionSource("renderPlaylistNav"),
  functionSource("updateNavigationActiveState"),
  functionSource("setView"),
  functionSource("sameTrackSelection"),
  functionSource("setTrackSelection"),
  functionSource("toggleTrackSelection"),
  functionSource("selectedTrackIds"),
  functionSource("setGroupSelection"),
  functionSource("toggleGroupSelection"),
  functionSource("clearTransientListSelection"),
  functionSource("groupDescriptorFromRow"),
  functionSource("selectedGroupDescriptors"),
  functionSource("resetLibraryScrollPosition"),
  functionSource("openGroupRow"),
  "globalThis.h = { normalizeTrackColumns, defaultTrackColumnsForScope, trackColumnsForScope, loadTrackColumnPreferences, trackColumnScope, legacyTrackColumnScope, trackColumnScopeLabel, persistTrackColumnPreferences, currentTrackColumns, saveTrackColumns, currentTrackColumnWidths, saveTrackColumnWidth, clampTrackColumnWidth, formatSize, renderPlaylistNav, updateNavigationActiveState, setView, isPagedLibraryView, setTrackSelection, toggleTrackSelection, selectedTrackIds, setGroupSelection, toggleGroupSelection, clearTransientListSelection, selectedGroupDescriptors, groupDescriptorFromRow, resetLibraryScrollPosition, openGroupRow };",
].join("\n");

function setup(options = {}) {
  const calls = [];
  const trackKeys = options.trackKeys || ["k1", "k2", "k3"];
  const groupKeys = options.groupKeys || ["g1", "g2", "g3"];
  const trackRows = trackKeys.map(key => classNode("track", key, { trackId: `id-${key}` }));
  const groupRows = groupKeys.map((key, index) => classNode("group", key, (options.groupDatasets || {})[index] || {}));
  const navButtons = (options.playlists || []).map(list => classNode("nav", `playlist:${list.id}`));
  const nav = { writes: [], dataset: {} };
  let navHtml = "";
  Object.defineProperty(nav, "innerHTML", {
    get() { return navHtml; },
    set(next) { nav.writes.push(next); navHtml = next; },
  });
  nav.querySelectorAll = selector => {
    if (selector !== ".nav-item") throw new Error(`unexpected nav selector ${selector}`);
    return navButtons;
  };
  const viewport = { writes: [], top: 240 };
  const list = { writes: [], top: 120 };
  for (const node of [viewport, list]) {
    Object.defineProperty(node, "scrollTop", {
      get() { return node.top; },
      set(next) { node.writes.push(`scrollTop=${next}`); node.top = next; },
    });
  }
  const state = {
    view: options.view || "all",
    groupName: options.groupName || "",
    folderRoot: options.folderRoot || "",
    folderPath: options.folderPath || "",
    page: 3,
    playlists: options.playlists || [],
    trackColumnPreferences: options.trackColumnPreferences || {},
    trackColumnWidthPreferences: options.trackColumnWidthPreferences || {},
    autoTrackColumnWidths: options.autoTrackColumnWidths || {},
    selectedTrackRowKeys: new Set(options.selected || []),
    selectedGroupKeys: new Set(options.selectedGroups || []),
    renderedNavigationView: options.renderedNavigationView === undefined ? "" : options.renderedNavigationView,
    artistName: options.creatorName || "",
    artistAllTracks: options.creatorAllTracks === true,
    composerName: "",
    composerAllTracks: false,
  };
  const storage = makeStorage(options);
  const knownIds = options.knownIds || trackKeys.map(key => `id-${key}`);
  const document = {
    queries: [],
    getElementById(id) {
      calls.push(`getElementById:${id}`);
      return id === "playlistNav" ? nav : null;
    },
    querySelectorAll(selector) {
      document.queries.push(selector);
      if (selector === "[data-track-row-key]") return trackRows;
      if (selector === "[data-group-row]") return groupRows;
      if (selector === ".nav-item") return navButtons;
      throw new Error(`unexpected selector ${selector}`);
    },
  };
  const context = {
    state, calls, document, localStorage: storage,
    String, Number, Boolean, Math, Array, Object, JSON, Promise, Error, Set, RegExp, Map, Date,
    encodeURIComponent, decodeURIComponent, setTimeout, clearTimeout,
    $(id) {
      calls.push(`$:${id}`);
      if (id === "libraryScroll") return viewport;
      if (id === "trackList") return list;
      return document.getElementById(id);
    },
    scheduleUserStateSave: () => calls.push("scheduleUserStateSave"),
    itemById: id => (knownIds.map(String).includes(String(id)) ? { id: String(id) } : null),
    closeTrackContextMenu: () => calls.push("closeTrackContextMenu"),
    invalidateLibraryLoad: () => calls.push("invalidateLibraryLoad"),
    requestLibraryLoad: (page, refresh) => {
      calls.push(`requestLibraryLoad(${page},${refresh})`);
      return Promise.resolve();
    },
    requestAnimationFrame: callback => {
      calls.push("requestAnimationFrame");
      callback();
      return 1;
    },
    render: () => calls.push("render"),
    setMobileNavigation: value => calls.push(`setMobileNavigation:${value}`),
  };
  vm.createContext(context);
  vm.runInContext(SOURCE, context);
  return { ...context.h, state, calls, document, storage, knownIds, nav, navButtons, trackRows, groupRows, viewport, list };
}

function sizeOf(formatSize, value) {
  try {
    return formatSize(value);
  } catch (error) {
    return `threw:${error && error.name ? error.name : "unknown"}`;
  }
}

function activeIndexes(markup) {
  return markup.split("<button").slice(1)
    .map((chunk, index) => (/class="nav-item playlist-nav-item active"/.test(chunk) ? index : -1))
    .filter(index => index >= 0);
}
(async () => {
  // ---- A. formatSize keeps a size cell from breaking the render ---------------
  const sizes = setup();
  assert.equal(sizes.formatSize(1536), "1.5 KB", "a kilobyte-scale size keeps one decimal");
  assert.equal(sizes.formatSize(1024), "1.0 KB", "and the unit boundary is not off by one");
  assert.equal(sizes.formatSize(1073741824), "1.0 GB", "the top unit is reached, not overshot");
  assert.equal(sizes.formatSize(512), "512 B", "bytes stay integers, no fake decimal");
  assert.deepEqual([0, "", null, undefined, false].map(value => sizeOf(sizes.formatSize, value)),
    ["", "", "", "", ""],
    "a missing size renders as nothing, which the caller turns into the em dash");
  // Defect A: a string size never entered the division loop, so it reached a number
  // method on a string and threw; a non-finite size painted "Infinity GB" and a
  // negative one painted "-5 B".  All of them must degrade like a missing size.
  assert.deepEqual(["500", "12345", "abc", Infinity, -Infinity, NaN, -5].map(value => sizeOf(sizes.formatSize, value)),
    ["500 B", "12.1 KB", "", "", "", "", ""],
    "a size that arrives as a string, outside the unit range, or as a non-number must never throw out of the size cell");
  assert.match(functionSource("formatSize"), /Number\.isFinite\(/,
    "the guard has to be a finite-number test, not a truthiness test, or a string size walks past it again");

  // ---- B. a blocked storage quota may not escape the column family ------------
  const legacyScope = "albums:tracks:A B";
  const columnsKey = literalOf("TRACK_COLUMNS_STORE_KEY");
  const widthsKey = literalOf("TRACK_COLUMN_WIDTHS_STORE_KEY");
  const quota = setup({
    view: "albums",
    groupName: "A B",
    storageThrows: true,
    trackColumnPreferences: { [legacyScope]: ["title", "artist"] },
  });
  assert.equal(quota.legacyTrackColumnScope(), legacyScope, "sanity: the unencoded scope is the legacy key");
  assert.notEqual(quota.trackColumnScope(), legacyScope, "sanity: the encoded scope differs, so the read path really migrates");
  const escapes = [];
  const attempt = (label, run) => {
    try {
      run();
    } catch (error) {
      escapes.push(`${label}:${error && error.name ? error.name : "unknown"}`);
    }
  };
  // Defect B: the first attempt is reached from the renderer, so before the repair a
  // full quota threw out of "open a list" instead of degrading to memory.
  attempt("migration", () => quota.currentTrackColumns());
  attempt("columns", () => quota.saveTrackColumns(["title", "duration"]));
  attempt("width", () => quota.saveTrackColumnWidth("title", 500));
  assert.deepEqual(escapes, [],
    "no caller of the column family may let a storage failure escape: " + escapes.join(","));
  assert.deepEqual(plain(quota.currentTrackColumns()), ["title", "duration"], "the preference still lands in memory for this session");
  assert.equal(quota.currentTrackColumnWidths().title, 500, "so does a dragged width, inside its own band");
  assert.ok(quota.storage.writes.includes(`set:${columnsKey}`),
    "and the write is still attempted, so a healthy browser keeps the preference");

  const healthy = setup({ view: "albums", groupName: "A B", trackColumnPreferences: { [legacyScope]: ["title", "artist"] } });
  assert.deepEqual(plain(healthy.currentTrackColumns()), ["title", "artist"], "the same migration on healthy storage returns the legacy columns");
  assert.deepEqual(JSON.parse(healthy.storage.store.get(columnsKey))[healthy.trackColumnScope()], ["title", "artist"],
    "the migrated scope is persisted under the encoded key");
  healthy.saveTrackColumnWidth("title", 4000);
  assert.equal(JSON.parse(healthy.storage.store.get(widthsKey))[healthy.trackColumnScope()].title, 520,
    "the width write converges on the resize band instead of storing the phantom");

  // Every write in this family is guarded, which is what makes one choke point safe.
  const persisted = functionSource("persistTrackColumnPreferences");
  const persistWrites = persisted.split("\n").filter(line => line.includes("localStorage.setItem("));
  assert.equal(persistWrites.length, 2, "the choke point persists exactly the two column keys");
  for (const line of persistWrites) {
    assert.match(line, /^\s*try \{ localStorage\.setItem\(.*\} catch \(_\) \{\s*\}\s*$/,
      "each storage write is individually wrapped, like the migration beside it: " + line.trim());
  }

  // ---- C. Ctrl+click must move the highlight, not only the state --------------
  const rows = ["k1", "k2", "k3"];
  const sel = setup({ trackKeys: rows });
  // Defect C: before the repair the memo inside setTrackSelection() always matched the
  // collection toggleTrackSelection() had just edited in place, so not one row class
  // was ever written from this path and the click was invisible.
  sel.toggleTrackSelection("k2");
  assert.deepEqual(painted(sel.trackRows), ["k2"], "the clicked row is highlighted; a state-only selection is invisible to the user");
  sel.toggleTrackSelection("k3");
  assert.deepEqual(painted(sel.trackRows), ["k2", "k3"], "a second Ctrl+click adds to the set instead of replacing it");
  sel.toggleTrackSelection("k2");
  assert.deepEqual(painted(sel.trackRows), ["k3"], "and clicking the selected row again takes its highlight away");
  assert.deepEqual([...sel.state.selectedTrackRowKeys], ["k3"], "state and paint agree");

  const ghost = setup({ trackKeys: ["k1", "k2"], selected: ["gone"] });
  ghost.toggleTrackSelection("k1");
  assert.deepEqual([...ghost.state.selectedTrackRowKeys], ["k1"], "a key whose row left the page is pruned, not kept as a phantom selection");
  assert.deepEqual(painted(ghost.trackRows), ["k1"], "and only rows on the page are painted");

  // The memo itself is intentional: the declarative render path calls with force left
  // false so a playback repaint does not walk every row.
  const memo = setup({ trackKeys: rows, selected: ["k1"] });
  memo.setTrackSelection(["k1"], false);
  assert.equal(writeCount(memo.trackRows), 0, "an unchanged declarative request must not touch a single row class");
  assert.deepEqual(memo.document.queries, [], "it must not even query the rows");
  memo.setTrackSelection(["k1"], true);
  assert.equal(writeCount(memo.trackRows), rows.length, "a forced request republishes every visible row");
  assert.deepEqual(painted(memo.trackRows), ["k1"], "and the forced repaint agrees with state");
  assert.match(app, /if \(!force && sameTrackSelection\(state\.selectedTrackRowKeys, requested\)\) return;/,
    "the short-circuit stays in place; the repair belongs to the caller");
  assert.equal((app.match(/setTrackSelection\(\[\.\.\.state\.selectedTrackRowKeys\], true\);/g) || []).length, 1,
    "the imperative toggle is the one caller that has to force the repaint");
  assert.doesNotMatch(app, /setTrackSelection\(\[\.\.\.state\.selectedTrackRowKeys\]\);/,
    "no caller may hand setTrackSelection() the collection it just edited without forcing it");

  // Control: the group lane never had this bug, because its setter has no memo.  If
  // this ever goes red the two lanes diverged again and the pin above needs a re-read.
  const groups = setup({ groupKeys: ["g1", "g2", "g3"] });
  groups.toggleGroupSelection("g1");
  assert.deepEqual(painted(groups.groupRows), ["g1"], "group rows highlight on the first click");
  groups.toggleGroupSelection("g1");
  assert.deepEqual(painted(groups.groupRows), [], "and un-highlight on the second");
  assert.equal(writeCount(groups.groupRows), 2 * 3, "the group lane republishes all rows on every click, memo-free");

  // ---- D. Falsified: the two dead column scopes really are unreachable --------
  const matrix = setup({ view: "all" });
  const albumLabel = /^\s*if \(scope\.startsWith\("albums:tracks:"\)\) return "([^"]+)";$/m.exec(app)[1];
  const genreLabel = /^\s*if \(scope\.startsWith\("genres:tracks:"\)\) return "([^"]+)";$/m.exec(app)[1];
  const fallbackLabel = /\|\| "([^"]+)";\s*$/m.exec(functionSource("trackColumnScopeLabel"))[1];
  const views = [...PAGED_VIEWS, "favorites", "queue", "playlist:p1"];
  assert.equal(views.length, 12, "the matrix covers every view id the switch can hold");
  const seen = new Set();
  for (const view of views) {
    for (const groupName of ["", "A B"]) {
      for (const creatorName of ["", "Some Singer"]) {
        for (const creatorAllTracks of [false, true]) {
          Object.assign(matrix.state, { view, groupName, folderRoot: "root1", folderPath: "x/y" });
          matrix.state.artistName = view === "composers" ? "" : creatorName;
          matrix.state.artistAllTracks = view === "composers" ? false : creatorAllTracks;
          matrix.state.composerName = view === "composers" ? creatorName : "";
          matrix.state.composerAllTracks = view === "composers" ? creatorAllTracks : false;
          const scope = matrix.trackColumnScope();
          const legacy = matrix.legacyTrackColumnScope();
          seen.add(scope);
          assert.ok(!scope.startsWith("artists:tracks:"), `no reachable state may build ${scope}`);
          assert.ok(!scope.startsWith("genres:tracks:"), `no reachable state may build ${scope}`);
          assert.equal(scope, legacy.replace(/ /g, "%20").replace(/\//g, "%2F"),
            "the two scopes differ only by encoding, which is what the migration depends on: " + legacy);
        }
      }
    }
  }
  assert.ok(seen.has("albums:tracks:A%20B"), "sanity: the album-detail scope really is produced");
  assert.ok(seen.has("folders:root1:x%2Fy"), "sanity: the folder scope really is produced");
  assert.deepEqual(plain(matrix.defaultTrackColumnsForScope("artists:tracks:x")), plain(matrix.defaultTrackColumnsForScope("all")),
    "the unreachable default branch cannot be told apart from the library default, which is why it was never noticed");
  Object.assign(matrix.state, { view: "genres", groupName: "A B", artistName: "", composerName: "" });
  assert.equal(matrix.trackColumnScope(), "all", "a genre group falls back to the library scope");
  assert.equal(matrix.trackColumnScopeLabel(), "全部音乐", "so the genre-detail label is never shown");
  assert.notEqual(genreLabel, matrix.trackColumnScopeLabel(), "the genres:tracks: label is a dead string");
  Object.assign(matrix.state, { view: "albums", groupName: "A B" });
  assert.equal(matrix.trackColumnScopeLabel(), albumLabel, "the album-detail label is reached from state, not from an argument");
  Object.assign(matrix.state, { view: "favorites", groupName: "", artistName: "", composerName: "" });
  assert.equal(matrix.trackColumnScopeLabel(), "全部音乐", "a client-paged list shares the library scope");
  assert.notEqual(fallbackLabel, albumLabel, "sanity: the fallback label is distinguishable from the detail label");

  // ---- E. Falsified: the playlist nav active mark cannot go stale -------------
  const nav = setup({
    view: "playlist:p2",
    renderedNavigationView: "",
    playlists: [{ id: "p1", name: "One", trackIds: ["a"] }, { id: "p2", name: "Two", trackIds: ["b", "c"] }],
  });
  nav.renderPlaylistNav();
  assert.deepEqual(activeIndexes(nav.nav.writes[nav.nav.writes.length - 1]), [1],
    "the active mark is computed from state.view at template time, so a stale nav cache cannot leave it on the old list");
  const navWrites = nav.nav.writes.length;
  nav.renderPlaylistNav();
  assert.equal(nav.nav.writes.length, navWrites, "an identical markup is not rewritten");
  nav.state.view = "playlist:p1";
  nav.renderPlaylistNav();
  assert.deepEqual(activeIndexes(nav.nav.writes[nav.nav.writes.length - 1]), [0],
    "and after the view changes, exactly one mark moves with it");
  assert.ok(/<b>2<\/b>/.test(nav.nav.writes[nav.nav.writes.length - 1]), "the count comes from the same list object");
  nav.state.playlists = [{ id: "pX", name: "<i>&", trackIds: [] }];
  nav.state.view = "playlist:pX";
  nav.renderPlaylistNav();
  assert.ok(!nav.nav.writes[nav.nav.writes.length - 1].includes("<span><i>&<"),
    "a playlist name is escaped before it reaches innerHTML");
  const lastActive = button => button.writes.length > 0 && button.writes[button.writes.length - 1] === "active=true";
  nav.state.view = "playlist:p2";
  nav.state.renderedNavigationView = "";
  nav.updateNavigationActiveState();
  assert.deepEqual(nav.navButtons.map(lastActive).map((value, index) => (value ? index : -1)).filter(index => index >= 0), [1],
    "the imperative nav update marks exactly the current view");
  assert.equal(nav.state.renderedNavigationView, "playlist:p2", "and refreshes its own cache by comparison");
  const toggles = writeCount(nav.navButtons);
  nav.updateNavigationActiveState();
  assert.equal(writeCount(nav.navButtons), toggles, "a second call with the same view writes nothing");
  nav.navButtons[0].onclick();
  assert.equal(nav.state.view, "playlist:p1", "a nav click really switches the view");
  assert.ok(nav.calls.includes("invalidateLibraryLoad"), "a playlist is not a paged view, so the pending request is invalidated");
  assert.ok(nav.calls.includes("render"), "and the list is re-rendered in place");
  assert.ok(!nav.calls.some(entry => entry.startsWith("requestLibraryLoad")), "no page request is made for a client-paged view");
  assert.equal(nav.calls[nav.calls.length - 1], "setMobileNavigation:false", "the mobile drawer closes last");
  const paged = setup({ view: "playlist:p1" });
  paged.setView("albums");
  assert.ok(paged.calls.includes("requestLibraryLoad(1,false)"), "a paged view asks for page one instead");
  assert.ok(paged.calls.includes("invalidateLibraryLoad"), "and invalidates the outgoing paged request before switching categories");
  assert.ok(paged.calls.includes("requestLibraryLoad(1,false)"), "while keeping the incoming paged request path");
  assert.deepEqual([...paged.state.selectedTrackRowKeys], [], "switching views drops a stale row selection");

  // ---- F. Falsified: selectedTrackIds follows the live rows -------------------
  const ids = setup({ trackKeys: ["k1", "k2"], selected: ["k1", "gone"], knownIds: ["id-k1", "id-k2"] });
  assert.deepEqual(plain(ids.selectedTrackIds("id-k2")), ["id-k1"], "only a row on the page contributes its id");
  const fallback = setup({ trackKeys: ["k1"], selected: [], knownIds: ["id-k1"] });
  assert.deepEqual(plain(fallback.selectedTrackIds("id-k1")), ["id-k1"], "an unselected row can still act on itself");
  assert.deepEqual(plain(fallback.selectedTrackIds("nope")), [], "an id with no item is dropped");

  // ---- G. Falsified: the group lane clears state, not markup ------------------
  const opened = setup({ groupKeys: ["g1"], selectedGroups: ["g1"], playlists: [] });
  opened.groupRows[0].dataset.groupType = "group";
  opened.groupRows[0].dataset.groupView = "albums";
  opened.groupRows[0].dataset.groupName = "An%20Album";
  opened.state.view = "albums";
  opened.openGroupRow(opened.groupRows[0]);
  assert.deepEqual([...opened.state.selectedGroupKeys], [], "entering a group drops the multi-selection");
  assert.equal(writeCount(opened.groupRows), 0, "without touching a class - the incoming list is rebuilt from markup");
  assert.equal(opened.state.groupName, "An Album", "the descriptor name is decoded once");
  assert.deepEqual([opened.state.sortKey, opened.state.sortDir], ["track_no", "asc"], "an album detail sorts by track number");
  assert.ok(opened.calls.includes("requestLibraryLoad(1,false)"), "and the new page is loaded once");
  assert.deepEqual(opened.viewport.writes, ["scrollTop=0"], "its scroll position is reset");
  assert.deepEqual(opened.list.writes, ["scrollTop=0"], "in both scrollable containers");
  assert.equal((app.match(/class="[^"]*\$\{state\.selectedGroupKeys\.has\([^)]*\) \? " is-selected" : ""\}/g) || []).length, 3,
    "the three group templates are the only producers of a group highlight, so a cleared state cannot leave a stale mark");
  assert.match(app, /^  return Promise\.resolve\(\)\.then\(.*\)\.catch\(\(\) => \{\}\);$/m,
    "the loader a fire-and-forget caller chains from swallows its own rejection, so a finally there cannot surface as an unhandled one");

  console.log("Track column and selection presentation regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exit(1);
});
