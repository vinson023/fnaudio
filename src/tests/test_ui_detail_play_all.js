/* R501: the two things R499 left open in the UI.

1. `播放全部` existed only on a *category* header (artist / genre root).  Opening a
   single album or one genre replaced that header with a breadcrumb, so the only
   way to start the set was double-clicking one song.  Both pages now carry the
   button in their own breadcrumb.

2. Queue / playlist from a group row still resolved `ids -> selectedItems ->
   itemById`, so a set larger than the 12,000-entry item cache lost its tail while
   the action reported success.  `playlistTrackIds` is the new boundary: rows that
   a caller already resolved are authoritative, bare ids still have to exist.
*/
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "app/ui/app.js"), "utf8");

function functionSource(name, endMarker) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `no function ${name}`);
  const end = source.indexOf(endMarker, start);
  assert.ok(end > start, `no end marker for ${name}`);
  return source.slice(start, end);
}

// ---- 1. the button is rendered by both detail pages ---------------------------

const albumDetail = functionSource("renderAlbumDetail", "function trackRowSelectionKey");
const genreTracks = functionSource("renderGenreTracks", "function renderFolders");
assert.match(albumDetail, /data-play-all/, "the album detail page must offer 播放全部");
assert.match(genreTracks, /data-play-all/, "the genre detail page must offer 播放全部");
assert.match(albumDetail, /breadcrumb-play-all/, "the button belongs in the breadcrumb row the page already has");
assert.match(genreTracks, /breadcrumb-play-all/);

// The album page's own order is `track_no` (set when the row is opened), and
// `playAll` resolves the set through `currentQueryParams()`, so the button plays
// the same order the page lists.  If either half changes, the button and the list
// disagree about what "the album" is.
const openGroupRow = functionSource("openGroupRow", "async function resolveSelectedGroupTracks");
assert.match(openGroupRow, /state\.sortKey = "track_no"/, "opening an album must set the album's own order");
const playAll = functionSource("playAll", "function nextIndex");
assert.match(playAll, /fetchAllTracksForCurrentView\(extra\)/, "playAll must resolve through the page's query");
assert.doesNotMatch(playAll, /sort:\s*"track_no"/, "the page query already carries the order; overriding it here would drift");

// Both detail views reach the same branch of playAll.
assert.match(playAll, /groupViews\[state\.view\] && state\.groupName/,
  "album detail and genre detail both resolve as a group view");

// ---- 2. playlist rows survive an evicted item cache ---------------------------

const playlistTrackIds = functionSource("playlistTrackIds", "function openPlaylistDialogForTracks");
const context = {
  Array, String, Set, Boolean, Object, Number,
  // The cache knows "known" and nothing else: the tail of a large set is exactly
  // what it has already forgotten.
  itemById: id => (id === "known" ? { id } : null),
};
vm.createContext(context);
vm.runInContext(`${playlistTrackIds}; globalThis.idsFor = playlistTrackIds;`, context);

const rows = [{ id: "known" }, { id: "evicted-1" }, { id: "evicted-2" }, { id: "known" }];
assert.deepEqual(
  JSON.parse(JSON.stringify(context.idsFor(rows))),
  ["known", "evicted-1", "evicted-2"],
  "rows a caller already resolved must not be re-checked against the cache, and repeats must collapse",
);
assert.deepEqual(
  JSON.parse(JSON.stringify(context.idsFor(["known", "evicted-1", "known"]))),
  ["known"],
  "a bare id still has to exist — a stale menu must not write ghosts into a playlist",
);
assert.deepEqual(JSON.parse(JSON.stringify(context.idsFor([]))), []);
assert.deepEqual(JSON.parse(JSON.stringify(context.idsFor("known"))), ["known"], "a single value is a list of one");

// The dialog has to carry the rows to the moment it saves, not just to the moment
// it opens: the same re-filter ran a second time inside createPlaylist.
const openDialog = functionSource("openPlaylistDialogForTracks", "function renderPlaylistChoices");
assert.match(openDialog, /state\.pendingPlaylistTracks = list\.slice\(\)/,
  "the rows must be kept with the dialog so saving cannot re-filter them");
const saveDialog = functionSource("savePlaylistFromDialog", "function deletePlaylist");
assert.match(saveDialog, /state\.pendingPlaylistTracks/, "saving must prefer the rows it was given");
const createPlaylist = functionSource("createPlaylist", "function addTracksToPlaylist");
assert.match(createPlaylist, /playlistTrackIds\(values\)/, "createPlaylist must go through the new boundary");
const addTracks = functionSource("addTracksToPlaylist", "function closeTrackActionDialog");
assert.match(addTracks, /playlistTrackIds\(values\)/, "adding to an existing list must too");
assert.doesNotMatch(addTracks, /itemById\(/, "no second cache filter may survive in the add path");

console.log("detail play-all and playlist row checks passed.");
