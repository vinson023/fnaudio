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

console.log("UI queue and album-column regression checks passed.");
