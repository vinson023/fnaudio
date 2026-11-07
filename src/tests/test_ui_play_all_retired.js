/* R511: 「播放全部」从界面上彻底消失（R501 加过，R508 撤了列表里的，R511 撤了剩下三处）。

1. R501 给专辑详情与类型详情加了面包屑按钮，R508 按「列表里面的」划界留下这三处
   （专辑详情、类型详情、分类详情头）。负责人看到之后说「还是有些地方有」，所以
   R511 把三处渲染、共用绑定、`playAll()` 实现与专用样式一起删掉。这条守卫现在
   钉的是**不存在**：源码里不许再出现按钮标记，详情页与分类头也不许把它拼回来。

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
const css = fs.readFileSync(path.join(root, "app/ui/app.css"), "utf8");
const page = fs.readFileSync(path.join(root, "app/ui/index.html"), "utf8");

function functionSource(name, endMarker) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `no function ${name}`);
  const end = source.indexOf(endMarker, start);
  assert.ok(end > start, `no end marker for ${name}`);
  return source.slice(start, end);
}

// ---- 1. no 播放全部 button is rendered anywhere -------------------------------

const albumDetail = functionSource("renderAlbumDetail", "function trackRowSelectionKey");
const genreTracks = functionSource("renderGenreTracks", "function renderFolders");
for (const [name, body] of [["album detail", albumDetail], ["genre detail", genreTracks]]) {
  assert.equal(/data-play-all|breadcrumb-play-all|播放全部/.test(body), false,
    `the ${name} page must not carry a 播放全部 button (R511)`);
}

// The category detail header (artist / genre drill-down) is the third site.
const toolbarChain = source.slice(source.indexOf("const countBar ="), source.indexOf("const listHtml ="));
assert.equal(/data-play-all|播放全部/.test(toolbarChain), false, "the category detail header must not carry one either");
assert.match(toolbarChain, /data-group-back/, "the header keeps its way back to the category");

// One binding used to serve every one of them; the buttons and the handler are
// both gone, so the selector, the attribute and the function must all be absent.
assert.equal(source.includes("data-play-all"), false, "no markup may reintroduce data-play-all");
assert.equal(source.includes("playAll"), false, "the handler went with the last button");
assert.equal(source.includes("breadcrumb-play-all"), false, "nor its dedicated class");
assert.equal(css.includes("breadcrumb-play-all"), false, "the stylesheet must not keep dead rules for it");
assert.equal(page.includes("data-play-all"), false, "nor may the shell markup carry one");
assert.equal(source.includes("data-play-artist-album"), false, "the stale artist-album selector was only another name for the same handler");

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

console.log("play-all retirement and playlist row checks passed.");
