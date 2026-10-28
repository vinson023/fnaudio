const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");
const recordPlaceholderSource = source.match(/function recordPlaceholderMarkup\(\) \{[\s\S]*?\n\}/)?.[0];
assert.ok(recordPlaceholderSource, "Cover placeholders must have one shared SVG renderer");

function sourceBetween(startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start);
  assert.ok(start >= 0 && end > start, `Unable to extract ${startMarker}`);
  return source.slice(start, end);
}

const columnsContext = {
  state: {},
  isPlaylistLibraryView: () => false,
  isCreatorAllTracksView: () => false,
  isCreatorView: () => false,
  currentCreatorName: () => "",
};
const columnDefinitions = sourceBetween("const TRACK_COLUMN_DEFINITIONS", "state.libraryStatus = null;");
const columnFunctions = sourceBetween("function normalizeTrackColumns", "function loadTrackColumnPreferences");
vm.runInNewContext(`${columnDefinitions}${columnFunctions}; this.columns = { defaultTrackColumnsForScope, trackColumnsForScope };`, columnsContext);

assert.deepEqual(
  [...columnsContext.columns.defaultTrackColumnsForScope("albums:tracks:Example")],
  ["track_no", "title", "artist", "album", "size", "format"],
);
assert.deepEqual(
  [...columnsContext.columns.trackColumnsForScope("albums:tracks:Example", ["title", "artist", "album", "size", "format"])],
  ["track_no", "title", "artist", "album", "size", "format"],
);

const queueContext = {
  state: {
    pageSize: 2,
    index: 0,
    queue: [
      { id: "duplicate", title: "Delta" },
      { id: "two", title: "Bravo" },
      { id: "duplicate", title: "Alpha" },
      { id: "four", title: "Charlie" },
    ],
    sortKey: "title",
    sortDir: "asc",
  },
  currentQueryText: () => "",
  sortDirectionFactor: () => 1,
  compareTrackValue: (left, right, key) => String(left[key] || "").localeCompare(String(right[key] || ""), "zh-CN", { numeric: true }),
};
vm.runInNewContext(`${sourceBetween("function queueDisplayEntries", "function groupFallbackIcon")}; this.queue = { queueDisplayEntries, currentQueuePage };`, queueContext);

assert.equal(queueContext.queue.currentQueuePage(), 2);
assert.deepEqual(
  queueContext.queue.queueDisplayEntries().map(entry => entry.queueIndex),
  [2, 1, 3, 0],
);

const queueRefreshContext = {
  state: { view: "queue", index: 3, page: 1 },
  currentQueuePage: () => 2,
  renderCount: 0,
  scrollCount: 0,
  render: () => { queueRefreshContext.renderCount += 1; },
  requestAnimationFrame: callback => callback(),
  scrollCurrentQueueTrackIntoView: () => { queueRefreshContext.scrollCount += 1; },
};
vm.runInNewContext(`${sourceBetween("function syncCurrentQueuePresentation", "function openCurrentQueue")}; this.queue = { syncCurrentQueuePresentation };`, queueRefreshContext);
queueRefreshContext.queue.syncCurrentQueuePresentation(2);
assert.equal(queueRefreshContext.state.page, 2);
assert.equal(queueRefreshContext.renderCount, 1);
assert.equal(queueRefreshContext.scrollCount, 1);

const trackRenderContext = {
  state: { view: "all", index: 1, selectedTrackRowKeys: new Set() },
  coverUrl: () => "",
  activeTrackColumns: () => ["title"],
  // renderTrack now batches non-title column formatting through this helper.
  // This isolated fixture renders only the title column, but it still needs
  // the dependency so the extracted function remains executable.
  trackColumnValues: () => ({}),
  displayText: value => String(value || ""),
  displayTrackTitle: item => String(item.title || ""),
  escapeHtml: value => String(value || ""),
};
vm.runInNewContext(`${recordPlaceholderSource}; ${sourceBetween("function trackRowSelectionKey", "function renderGroups")}; this.track = { renderTrack };`, trackRenderContext);
assert.match(trackRenderContext.track.renderTrack({ id: "two", title: "Two" }), /track-cover-fallback[^>]*><svg class="record-placeholder"[^>]*aria-hidden="true"/);
assert.doesNotMatch(
  trackRenderContext.track.renderTrack({ id: "two", title: "Two" }),
  /<img\b/,
  "Rows without a cover must render only the fallback glyph, never an image element",
);
trackRenderContext.coverUrl = () => "";
assert.doesNotMatch(
  trackRenderContext.track.renderTrack({ id: "two", title: "Two", cover_url: "" }),
  /<img\b/,
  "An explicitly empty cover URL must not become a broken image element",
);
assert.doesNotMatch(trackRenderContext.track.renderTrack({ id: "two", title: "Two", is_dsd: true }), /◈/);
assert.doesNotMatch(trackRenderContext.track.renderTrack({ id: "two", title: "Two", is_dsd: "true" }), /class="[^"]*dsd/);
trackRenderContext.coverUrl = () => "https://example.test/cover.jpg";
assert.match(trackRenderContext.track.renderTrack({ id: "two", title: "Two" }), /track-cover-fallback[^>]*><svg class="record-placeholder"[^>]*aria-hidden="true"/);
assert.match(trackRenderContext.track.renderTrack({ id: "two", title: "Two" }), /<img[^>]*style="visibility:hidden"/, "Artwork images must stay hidden until decoding succeeds");
assert.doesNotMatch(trackRenderContext.track.renderTrack({ id: "two", title: "Two" }), /<img[^>]*\ssrc="/, "Artwork requests must be started by the shared scheduler, not by inline markup");
assert.doesNotMatch(trackRenderContext.track.renderTrack({ id: "two", title: "Two" }), /track-cover-fallback[^>]*hidden[^>]*>\s*<svg/, "The fallback icon must remain visible until image decode succeeds");
assert.match(source, /onload="this\.hidden=false;this\.style\.visibility='visible';[^"]*const fallback=this\.parentElement\?\.querySelector\('\.track-cover-fallback'\);if\(fallback\)fallback\.hidden=true"/, "Loaded covers must restore the image and hide the fallback");
assert.match(source, /onerror="this\.hidden=true;this\.style\.visibility='hidden';const fallback=this\.parentElement\?\.querySelector\('\.track-cover-fallback'\);if\(fallback\)fallback\.hidden=false;const retry=Number\(this\.dataset\.coverRetryCount\|\|0\);/, "Failed covers must retain the fallback and use a bounded eager retry");
assert.doesNotMatch(source, /this\.src='';this\.src=source/, "Eager cover retry must not create an intermediate empty src");
assert.match(source, /function coverUrl\(item, size = 160\)/, "Track covers must default to list thumbnails");
assert.match(source, /artwork: coverUrl\(item, 512\)/, "Android media artwork must keep the larger cover size");
assert.doesNotMatch(trackRenderContext.track.renderTrack({ id: "two", title: "Two" }), /正在播放|is-current/);
trackRenderContext.state.view = "queue";
assert.match(trackRenderContext.track.renderTrack({ id: "two", title: "Two", __queueIndex: 1 }), /正在播放|is-current/);

const coreSnapshotContext = {
  state: { queue: [{ id: "one" }, { id: "two" }], index: 0, repeat: "off", shuffle: false },
  updateRepeatShuffleButtons: () => {},
  favoriteRefreshes: 0,
  updateFavoriteControls: () => { coreSnapshotContext.favoriteRefreshes += 1; },
  resetPlaybackProgress: () => {},
  loadCurrent: () => {},
  previousQueueIndex: null,
  syncCurrentQueuePresentation: previousIndex => { coreSnapshotContext.previousQueueIndex = previousIndex; },
};
vm.runInNewContext(`${sourceBetween("function applyCoreSnapshot", "async function coreControl")}; this.core = { applyCoreSnapshot };`, coreSnapshotContext);
assert.equal(coreSnapshotContext.core.applyCoreSnapshot({ current: "two" }, false), true);
assert.equal(coreSnapshotContext.state.index, 1);
assert.equal(coreSnapshotContext.previousQueueIndex, 0);
assert.equal(coreSnapshotContext.favoriteRefreshes, 1);

const favoriteContext = {
  state: { queue: [{ id: 42 }], index: 0, favorites: ["42"] },
  lyricsFavoriteLabel: { textContent: "" },
  nodes: {
    favoriteCurrentBtn: { dataset: {}, classList: { toggle: (_name, value) => { favoriteContext.currentActive = value; } }, setAttribute: (name, value) => { favoriteContext.currentAttributes[name] = value; } },
    lyricsFavoriteBtn: { dataset: {}, classList: { toggle: (_name, value) => { favoriteContext.lyricsActive = value; } }, setAttribute: (name, value) => { favoriteContext.lyricsAttributes[name] = value; }, querySelector: () => favoriteContext.lyricsFavoriteLabel },
  },
  currentAttributes: {},
  lyricsAttributes: {},
  $: id => favoriteContext.nodes[id],
};
vm.runInNewContext(`${sourceBetween("function currentItem", "function isPrivateHost")}${sourceBetween("function updateFavoriteControls", "function updateNowMarquee")}; this.favorites = { isFavorite, updateFavoriteControls };`, favoriteContext);
favoriteContext.favorites.updateFavoriteControls();
assert.equal(favoriteContext.currentActive, true, "Favorite IDs must match across numeric and string transport forms");
assert.equal(favoriteContext.currentAttributes["aria-pressed"], "true", "Favorite state must be exposed independently from hover styling");
assert.equal(favoriteContext.currentAttributes["aria-label"], "取消收藏当前歌曲", "The player favorite action must describe its active-state action");
assert.equal(favoriteContext.nodes.lyricsFavoriteBtn.dataset.favoriteLabel, "已收藏");
assert.equal(favoriteContext.lyricsAttributes["aria-label"], "取消收藏当前歌曲", "The lyrics favorite action must describe its active-state action");
assert.equal(favoriteContext.lyricsFavoriteLabel.textContent, "已收藏", "The visible lyrics action label must follow favorite state");
favoriteContext.state.favorites = [];
favoriteContext.favorites.updateFavoriteControls();
assert.equal(favoriteContext.currentActive, false, "Favorite control must clear when server state removes the current track");
assert.equal(favoriteContext.currentAttributes["aria-pressed"], "false");
assert.equal(favoriteContext.currentAttributes["aria-label"], "收藏当前歌曲");
assert.equal(favoriteContext.nodes.lyricsFavoriteBtn.dataset.favoriteLabel, "收藏");
assert.equal(favoriteContext.lyricsAttributes["aria-label"], "收藏当前歌曲");
assert.equal(favoriteContext.lyricsFavoriteLabel.textContent, "收藏");
assert.match(source, /const active = state\.shuffle === true;[\s\S]*?const pressed = String\(active\);[\s\S]*?setAttribute\("aria-pressed", pressed\)/, "Shuffle must render only an explicit boolean true as active");

assert.match(source, /openTrackContextMenu\(trackId, x, y, mobile = false\)/);
assert.match(source, /function desktopTrackContextActionButtons\(trackId\)/);
assert.match(source, /function mobileTrackContextActionButtons\(trackId\)/);
assert.match(source, /const actions = mobile\s*\? mobileTrackContextActionButtons\(trackId\)\s*:\s*desktopTrackContextActionButtons\(trackId\)/);
const desktopMenuFunctions = sourceBetween("function desktopTrackContextActionButtons", "function bindTrackActionButtons");
assert.doesNotMatch(desktopMenuFunctions, /data-track-action="(?:play|insert)"/);
assert.match(desktopMenuFunctions, /data-track-action="\(\?:open-folder\|share\|delete-file\)"/, "Mobile menu must filter file-manager-only actions separately");
assert.match(source, /actionButton\(multiple \? `删除所选 \$\{selected\.length\} 首歌曲` : "删除歌曲", "delete-file", true\)/);
assert.match(source, /req: "file\.rm"/);
assert.match(source, /moveToTrashbin: Boolean\(moveToTrashbin\)/);
const groupMenuFunctions = sourceBetween("function groupActionButtons", "function bindGroupActionButtons");
assert.doesNotMatch(groupMenuFunctions, /groupActionButton\("播放"|groupActionButton\("插播所选项目"/);
assert.match(source, /openTrackActionDialog\(trackId\)[\s\S]*?trackActionButtons\(trackId\)/);
assert.match(source, /openTrackContextMenu\(id, x, y, mobile\)/);
assert.match(source, /function bindTrackListInteractions\(\)/);
assert.match(source, /list\.dataset\.trackInteractionsBound === "1"/);
assert.match(source, /list\.addEventListener\("pointerdown", event => \{[\s\S]*?startTrackLongPress\(row, event\)/);
assert.match(source, /list\.addEventListener\("contextmenu", event => \{[\s\S]*?openTrackMenuForRow\(row, event\.clientX, event\.clientY, mobile\)/);
assert.match(source, /TRACK_LONG_PRESS_DURATION_MS = 550/);
assert.match(source, /if \(moved > TRACK_LONG_PRESS_MOVE_THRESHOLD_PX\) cancelTrackLongPress\(\)/);
assert.match(source, /\$\("trackList"\)\.addEventListener\("scroll", \(\) => \{\s*cancelTrackLongPress\(\);\s*closeTrackContextMenu\(\);/);
assert.match(source, /else if \(action === "play-from-current"\) playFromCurrentTrack\(trackId\)/);
assert.match(source, /tracks = await allTracksForCurrentContext\(\)/);

// Large persisted queues must be restored in bounded CGI requests and keep
// cached rows when a transient batch fails.
assert.match(source, /const batches = \[\];[\s\S]*?offset \+= 100/);
assert.match(source, /fnAudioBatchRequestPool\(batches, fnAudioBatchRequestPool\.DEFAULT_CONCURRENCY/);
assert.match(source, /api\/library\/items\?ids=\$\{encodeURIComponent\(batch\.join\(\",\"\)\)\}/);
assert.match(source, /const hydrated = queueIds\.map\(id => byId\.get\(id\) \|\| previousById\.get\(id\)\)\.filter\(Boolean\)/);

console.log("UI queue and album-column regression checks passed.");

(async () => {
  const helper = source.match(/^async function runTrimHostAction\([^]*?^}/m)?.[0];
  const openFolder = source.match(/^async function openContainingFolder\([^]*?^}/m)?.[0];
  assert.ok(helper, "file manager behavior must execute the real host helper");
  assert.ok(openFolder, "file manager behavior must execute the real folder action");
  let ready = false, locationCalls = 0;
  const opened = [], alerts = [];
  const location = {path: "/vol1/music/album/song.flac", folder: "/vol1/music/album"};
  const sdk = {isStandaloneWeb: false,
    async ready() { ready = true; },
    async openFileManager(folder) {
      assert.equal(ready, true, "SDK must be ready before invoking file manager");
      assert.equal(folder, location.folder, "host must receive the containing directory");
      assert.notEqual(folder, location.path, "full song path must not be opened as a file");
      opened.push(folder);
    },
  };
  const context = {getTrimSdk: async () => sdk, setTimeout, clearTimeout,
    resolveTrackLocation: async id => {
      assert.equal(id, "selected-track"); locationCalls++; return location;
    }, alert: message => alerts.push(message), console: {warn() {}},
  };
  vm.createContext(context);
  vm.runInContext(`${helper}\n${openFolder}`, context);
  assert.equal(await context.openContainingFolder("selected-track"), true);
  assert.equal(locationCalls, 1);
  assert.deepEqual(opened, [location.folder]);
  assert.equal(alerts.length, 0);
  sdk.isStandaloneWeb = true;
  assert.equal(await context.openContainingFolder("selected-track"), false);
  assert.equal(opened.length, 1, "standalone pages must not call the host file manager");
  assert.match(alerts.pop(), /飞牛桌面或飞牛 App/);
  sdk.isStandaloneWeb = false;
  sdk.openFileManager = async () => { throw new Error("宿主拒绝打开"); };
  assert.equal(await context.openContainingFolder("selected-track"), false);
  assert.equal(alerts.pop(), "宿主拒绝打开", "host handoff failure must be reported");
  console.log("Containing-folder path, host readiness, standalone and rejection behavior passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
