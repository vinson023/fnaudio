const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");

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
  displayText: value => String(value || ""),
  displayTrackTitle: item => String(item.title || ""),
  escapeHtml: value => String(value || ""),
};
vm.runInNewContext(`${sourceBetween("function trackRowSelectionKey", "function renderGroups")}; this.track = { renderTrack };`, trackRenderContext);
assert.doesNotMatch(trackRenderContext.track.renderTrack({ id: "two", title: "Two" }), /正在播放|is-current/);
trackRenderContext.state.view = "queue";
assert.match(trackRenderContext.track.renderTrack({ id: "two", title: "Two", __queueIndex: 1 }), /正在播放|is-current/);

const coreSnapshotContext = {
  state: { queue: [{ id: "one" }, { id: "two" }], index: 0, repeat: "off", shuffle: false },
  updateRepeatShuffleButtons: () => {},
  resetPlaybackProgress: () => {},
  loadCurrent: () => {},
  previousQueueIndex: null,
  syncCurrentQueuePresentation: previousIndex => { coreSnapshotContext.previousQueueIndex = previousIndex; },
};
vm.runInNewContext(`${sourceBetween("function applyCoreSnapshot", "async function coreControl")}; this.core = { applyCoreSnapshot };`, coreSnapshotContext);
assert.equal(coreSnapshotContext.core.applyCoreSnapshot({ current: "two" }, false), true);
assert.equal(coreSnapshotContext.state.index, 1);
assert.equal(coreSnapshotContext.previousQueueIndex, 0);

console.log("UI queue and album-column regression checks passed.");
