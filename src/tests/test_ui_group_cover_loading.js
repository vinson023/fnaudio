const assert = require("node:assert/strict");
const fs = require("node:fs");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const scheduler = fs.readFileSync("app/ui/cover_load_scheduler.js", "utf8");

const groupIcon = app.slice(app.indexOf("function groupIcon("), app.indexOf("function applyGroupArtwork("));
const albumDetail = app.slice(app.indexOf("function renderAlbumDetail("), app.indexOf("function trackRowSelectionKey("));
const render = app.slice(app.indexOf("function render()"), app.indexOf("function renderPlaylistNav("));

assert.match(groupIcon, /<img data-cover-src="\$\{escapeHtml\(image\)\}" alt="">/);
assert.doesNotMatch(groupIcon, /loading="lazy"/);
assert.match(albumDetail, /<img data-cover-src="\$\{escapeHtml\(cover\)\}" alt="">/);
assert.match(render, /loadGroupArtwork\(\);\s*hydrateVisibleTrackCovers\(\);/, "Group fallback listeners must bind before shared source scheduling");
assert.match(app.slice(app.indexOf("function loadGroupArtwork("), app.indexOf("function activeTrackColumns(")), /const root = \$\("trackList"\) \|\| document;/, "Group artwork lookup should stay scoped to the rendered track list");
assert.match(app.slice(app.indexOf("function loadGroupArtwork("), app.indexOf("function activeTrackColumns(")), /new Set\(\[/, "Group artwork nodes should be de-duplicated before binding listeners");
assert.match(scheduler, /querySelectorAll\("img\[data-cover-src\]"\)/, "The shared scheduler must cover tracks and group artwork");
console.log("Group cover scheduling regression checks passed.");
