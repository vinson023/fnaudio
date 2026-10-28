const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/track_table_presentation.js", "utf8");
const context = {};
context.globalThis = context;
vm.runInNewContext(source, context);
const table = context.fnAudioTrackTablePresentation;
const definitions = { title: { label: "标题", width: 280, sort: "title" }, artist: { label: "歌手", width: 140, sort: "artist" } };

assert.equal(table.gridTemplate(["title", "artist"], { title: 300 }, definitions), "300px 140px minmax(0,1fr)");
assert.deepEqual([...table.widthLimits("title")], [180, 520]);
assert.deepEqual([...table.widthLimits("artist")], [88, 220]);
assert.deepEqual([...table.widthLimits("album")], [110, 280]);
assert.deepEqual([...table.widthLimits("unknown")], [80, 260]);
assert.equal(table.safeWidth("title", Infinity, 120), 180);
assert.equal(table.safeWidth("artist", "bad", 120), 120);

const tracks = table.tableHeadPresentation({ columns: ["title", "artist"], widths: { title: 360 }, definitions, currentSort: "title", sortDir: "desc", sortableSortKeys: ["title"] });
assert.match(tracks.markup, /data-track-sort="title"/);
assert.doesNotMatch(tracks.markup, /data-track-sort="artist"/);
assert.match(tracks.markup, /class="track-sort-indicator" aria-hidden="true"><svg[^>]*aria-hidden="true"[^>]*><path d="m6 10 6 6 6-6"\/><\/svg><\/span>/);
assert.doesNotMatch(tracks.markup, /&#9650;|&#9660;/);
assert.match(tracks.markup, /data-open-columns/);
assert.equal(tracks.template, "360px 140px minmax(0,1fr)");

const group = table.tableHeadPresentation({ mode: "group", groupSortKey: "artist", currentSort: "artist" });
assert.equal(group.template, "minmax(280px,1fr)");
assert.match(group.markup, /data-track-sort="artist"/);
assert.equal(table.gridTemplate(null, {}, {}), "minmax(0,1fr)");
assert.equal(table.gridTemplate([{ toString() { throw new Error("must not stringify"); } }], {}, {}), "minmax(0,1fr)");
assert.match(source, /MAX_COLUMNS = 32/);
const css = fs.readFileSync("app/ui/app.css", "utf8");
assert.match(css, /\.table-head,\.track\{[^}]*gap:10px/,
  "track tables must use a compact content-fit gap");
assert.doesNotMatch(css, /grid-template-columns:var\(--fnaudio-track-columns,minmax\(280px,1\.35fr\)/,
  "the later table override must not restore the old wide fallback");
assert.match(css, /\.album-detail-table-head\{[^}]*gap:10px/,
  "album detail tables must use the same compact gap");
console.log("Track table presentation regression checks passed.");
