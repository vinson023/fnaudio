// R594: the album wall.
//
// Rows are good at carrying metadata (artist, release date, track count); a grid of
// covers is what you actually want when you are hunting an album by its sleeve.
// Audio Station offers both from one list -- `FileSongListAdapter` picks one of two
// view types per row -- and the choice is a density preference, not library state,
// so it is remembered per device.
//
// The tile is deliberately NOT a second selection model: it carries the same
// `data-group-*` contract as the row it replaces, so click, long-press, the group
// menu and the selection set all keep working through the existing handlers.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the album layout regression`);
  return match[0];
}

const GROUPS = [
  { name: "Alpha", artist: "A Band", cover_track_id: "t1", track_count: 12 },
  { name: "Beta", artist: "B Band", cover_track_id: "t2", track_count: 7 },
];

function build(options = {}) {
  const writes = [];
  const renders = [];
  const scroll = { scrollTop: options.scrollTop || 240 };
  const state = {
    albumLayout: options.layout || "list",
    albumMetadata: new Map(),
    itemCache: new Map(),
    selectedGroupKeys: new Set(options.selected || []),
  };
  const context = {
    state, writes, renders, scroll,
    escapeHtml: value => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"),
    displayText: value => (typeof value === "string" ? value.trim() : ""),
    libraryCount: value => `${Number(value) || 0}`,
    encodeURIComponent,
    groupIcon: () => '<div class="group-icon"></div>',
    groupFallbackIcon: () => "",
    writeStoredPreference: (key, value) => writes.push(`${key}=${value}`),
    render: () => renders.push("render"),
    requestAnimationFrame: handler => handler(),
    $: id => (id === "libraryScroll" ? scroll : null),
  };
  vm.createContext(context);
  // The storage key is a module const beside the functions that use it.
  const keyConst = app.match(/^const ALBUM_LAYOUT_KEY = "[^"]+";/m);
  assert.ok(keyConst, "ALBUM_LAYOUT_KEY must stay extractable for the album layout regression");
  vm.runInContext([
    keyConst[0],
    functionSource("albumLayoutBar"),
    functionSource("renderAlbumTiles"),
    functionSource("setAlbumLayout"),
    "globalThis.h = { albumLayoutBar, renderAlbumTiles, setAlbumLayout };",
  ].join("\n"), context);
  return { ...context.h, state, writes, renders, scroll };
}

// --- the tile keeps the row contract ---------------------------------------

{
  const env = build();
  const html = env.renderAlbumTiles(GROUPS);
  assert.match(html, /class="album-grid"/, "the tiles are wrapped in the grid container");
  assert.equal((html.match(/class="album-tile(?=[" ])/g) || []).length, 2, "one tile per group");
  for (const attribute of ["data-group-row", "data-group-key", "data-group-type=\"group\"", "data-group-view=\"albums\"", "data-group-name=", "data-group-track-count=", "data-album-metadata-name="]) {
    assert.ok(html.includes(attribute), `a tile must carry ${attribute} so the existing handlers keep working`);
  }
  assert.match(html, /role="button" tabindex="0"/, "a tile is reachable by keyboard like a folder row");
  assert.match(html, /<strong class="album-tile-name">Alpha<\/strong>/, "the album name is on the tile");
  assert.match(html, /<span class="album-tile-artist">A Band<\/span>/, "and the artist line");
}

{
  // The highlight is the same set the rows use; a tile cannot invent its own.
  const env = build({ selected: ["group:albums:Beta"] });
  const html = env.renderAlbumTiles(GROUPS);
  assert.match(html, /class="album-tile is-selected"[^>]*data-group-name="Beta"/, "a selected group is marked on its tile");
  assert.equal((html.match(/is-selected/g) || []).length, 1, "and only on the selected one");
}

// --- the toggle ------------------------------------------------------------

{
  const env = build({ layout: "list" });
  env.setAlbumLayout("grid");
  assert.equal(env.state.albumLayout, "grid", "the toggle switches the layout");
  assert.deepEqual(env.writes, ["fnaudio.albumLayout.v1=grid"], "and remembers it on this device");
  assert.equal(env.renders.length, 1, "and repaints the list");
  assert.equal(env.scroll.scrollTop, 240, "without throwing the reader back to the top");
}

{
  const env = build({ layout: "grid" });
  env.setAlbumLayout("grid");
  assert.equal(env.renders.length, 0, "choosing the layout that is already active must not repaint");
  assert.deepEqual(env.writes, [], "nor write a preference for a no-op");
}

{
  // Anything the storage layer hands back other than "grid" is the list: a hand
  // edited or truncated value must not leave the library in a state with no rows.
  const env = build({ layout: "list" });
  env.setAlbumLayout("nonsense");
  assert.equal(env.state.albumLayout, "list", "an unknown mode falls back to the list");
  // Boot already normalized the stored value, so asking for the list is a no-op
  // rather than a redundant write.
  assert.deepEqual(env.writes, [], "and asking for the layout already in force writes nothing");
  const fromGrid = build({ layout: "grid" });
  fromGrid.setAlbumLayout("nonsense");
  assert.equal(fromGrid.state.albumLayout, "list", "the same value also switches away from the grid");
  assert.deepEqual(fromGrid.writes, ["fnaudio.albumLayout.v1=list"]);
}

// --- the bar ---------------------------------------------------------------

{
  const env = build({ layout: "grid" });
  const html = env.albumLayoutBar(2);
  assert.match(html, /2 张专辑/, "the bar states how many albums are on screen");
  assert.match(html, /data-album-layout="list"/, "and offers both layouts");
  assert.match(html, /data-album-layout="grid"/);
  assert.match(html, /data-album-layout="grid"[^>]*aria-pressed="true"/, "the active one is announced as pressed");
  assert.match(html, /data-album-layout="list"[^>]*aria-pressed="false"/);
}

// --- boot ------------------------------------------------------------------

{
  assert.match(app, /state\.albumLayout = localStorage\.getItem\("fnaudio\.albumLayout\.v1"\) === "grid" \? "grid" : "list";/,
    "the layout is read once at boot, and only the exact value 'grid' means grid");
}

// --- the stylesheet --------------------------------------------------------

{
  assert.match(css, /\.album-grid\{display:grid;grid-template-columns:repeat\(auto-fill,minmax\(\d+px,1fr\)\)/, "the wall is an auto-filling grid");
  assert.match(css, /\.album-tile \.group-icon\{width:100%;height:auto;aspect-ratio:1/, "a tile's cover is square and fills the tile");
  assert.match(css, /@media\(max-width:760px\)\{\.album-grid\{grid-template-columns:repeat\(auto-fill,minmax\(\d+px,1fr\)\)/, "phones get narrower tiles");
}

console.log("Album layout regression checks passed.");
