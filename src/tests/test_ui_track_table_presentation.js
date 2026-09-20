const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/track_table_presentation.js", "utf8");
const context = {};
context.globalThis = context;
vm.runInNewContext(source, context);
const table = context.fnAudioTrackTablePresentation;
const definitions = { title: { label: "标题", width: 420, sort: "title" }, artist: { label: "歌手", width: 200, sort: "artist" } };

assert.equal(table.gridTemplate(["title", "artist"], { title: 300 }, definitions), "300px 200px minmax(0,1fr)");
assert.deepEqual([...table.widthLimits("title")], [260, 620]);
assert.deepEqual([...table.widthLimits("unknown")], [80, 260]);
assert.equal(table.safeWidth("title", Infinity, 120), 260);
assert.equal(table.safeWidth("artist", "bad", 120), 120);

const tracks = table.tableHeadPresentation({ columns: ["title", "artist"], widths: { title: 360 }, definitions, currentSort: "title", sortDir: "desc", sortableSortKeys: ["title"] });
assert.match(tracks.markup, /data-track-sort="title"/);
assert.doesNotMatch(tracks.markup, /data-track-sort="artist"/);
assert.match(tracks.markup, /&#9660;/);
assert.match(tracks.markup, /data-open-columns/);
assert.equal(tracks.template, "360px 200px minmax(0,1fr)");

const group = table.tableHeadPresentation({ mode: "group", groupSortKey: "artist", currentSort: "artist" });
assert.equal(group.template, "minmax(280px,1fr)");
assert.match(group.markup, /data-track-sort="artist"/);
assert.equal(table.gridTemplate(null, {}, {}), "minmax(0,1fr)");
assert.equal(table.gridTemplate([{ toString() { throw new Error("must not stringify"); } }], {}, {}), "minmax(0,1fr)");
assert.match(source, /MAX_COLUMNS = 32/);
console.log("Track table presentation regression checks passed.");
