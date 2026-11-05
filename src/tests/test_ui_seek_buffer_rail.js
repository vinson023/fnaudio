// R484: the rail carries two readings on one painted band — how far the track
// has played, and how far the element has buffered ahead of that.  The band is a
// third stop in the same gradient, so nothing new is stacked on the native range
// and the drag target is unchanged.
//
// Two things can silently rot here and both are covered below: the CSS stops
// (a reordered gradient paints the buffer over the played edge) and the mapping
// from the element's clock onto the rail's (a stream offset or a cue start that
// is applied to the position but not to the buffered edge puts the band in the
// wrong place).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const theme = fs.readFileSync("app/ui/fnos-theme.css", "utf8");

// The theme sheet is layered, so a selector can appear twice and only the last
// copy is the one that paints.  Every lookup below reads the last match.
function blocks(selector) {
  const pattern = new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*\\{([^}]*)\\}", "g");
  const matches = [...theme.matchAll(pattern)];
  assert.ok(matches.length, `${selector} must stay a rule in the theme sheet`);
  return matches.map(match => match[1]);
}
function block(selector) {
  const all = blocks(selector);
  return all[all.length - 1];
}
function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

// ---------------------------------------------------------------- the paint --
const track = block(".player .progress input::-webkit-slider-runnable-track");
assert.match(track, /height:\s*4px\s*!important/, "the band stays a 4px line");
assert.match(track, /var\(--ui-accent\)\s+0\s+var\(--seek-fill,\s*0%\)/,
  "the played edge has to be the first stop, or the buffer paints over it");
assert.match(track, /var\(--ui-selected\)\s+var\(--seek-fill,\s*0%\)\s+var\(--seek-buffer,\s*var\(--seek-fill,\s*0%\)\)/,
  "the buffered band runs from the played edge to the buffered edge and falls back to the played edge");
assert.match(track, /var\(--ui-line\)\s+var\(--seek-buffer,\s*var\(--seek-fill,\s*0%\)\)\s+100%/,
  "everything past the buffered edge is the empty track");
assert.doesNotMatch(track, /color-mix|rgba\(/, "the band must come from a theme token, not a literal or a color-mix");

const thumb = block(".player .progress input::-webkit-slider-thumb");
assert.match(thumb, /width:\s*10px\s*!important/, "the handle is 10px so it clears the 4px band on both sides");
assert.match(thumb, /height:\s*10px\s*!important/);
assert.match(thumb, /background:\s*var\(--ui-surface\)\s*!important/, "the core stays the surface colour");
assert.match(thumb, /box-shadow:\s*0 0 0 2px var\(--ui-accent\)\s*!important/, "the ring is what makes the core read as a handle");

// The rail is anchored, not laid out: R484 may change how it is drawn and not
// where it sits.  Both copies that are meant to paint keep the anchor, and the
// last one is the phone override.
const rails = blocks(".player .progress");
const anchored = rails.filter(css => /position:\s*fixed\s*!important/.test(css)
  && /left:\s*0\s*!important/.test(css)
  && /right:\s*0\s*!important/.test(css)
  && /bottom:\s*var\(--ui-player-height\)\s*!important/.test(css));
assert.ok(anchored.length >= 2, "the desktop and phone rails both stay pinned to the player's top edge");

// app.css pins the phone rail to overflow:hidden; a 10px handle in a 4px box
// would be clipped to a sliver there.
assert.match(rails[rails.length - 1], /overflow:\s*visible\s*!important/,
  "the phone rail has to let the handle overflow, or it is clipped to the band");

// ------------------------------------------------------------------ the map --
const nodes = { seek: { value: "0", style: new Map(), styleWrites: 0 } };
const stubs = {
  isIncomingRendererSession: () => false,
  isRemoteTarget: () => false,
  nativePlaybackAvailable: () => false,
  seekDuration: () => 240,
  localPlaybackSeconds: () => 84,
  audio: { currentTime: 84, buffered: { length: 1, start: () => 0, end: () => 151 } },
};
const context = {
  state: {},
  String, Number, Math,
  $: id => (id === "seek" ? nodes.seek : null),
  setStyleVarIfChanged: (node, name, value) => {
    if (!node || node.style.get(name) === value) return;
    node.style.set(name, value);
    node.styleWrites += 1;
  },
  ...stubs,
};
const sources = ["seekPercent", "playbackSeconds", "seekBufferedPercent", "updateSeekRail"]
  .map(functionSource).join("\n");
vm.runInNewContext(sources + "\nglobalThis.rail = { updateSeekRail, seekBufferedPercent };", context);
const railApi = context.rail;

const read = () => ({
  fill: nodes.seek.style.get("--seek-fill"),
  buffer: nodes.seek.style.get("--seek-buffer"),
});

// 84s played of 240s, 151s buffered.
railApi.updateSeekRail(35);
assert.deepEqual(read(), {fill: "35%", buffer: "62.9%"},
  "the band ends where the element stopped buffering, in rail percent");

// One decimal, not the twelve a raw division produces: the compare-first writer
// only earns its keep if the value is stable between ticks.
context.audio.buffered = { length: 1, start: () => 0, end: () => 151.02 };
assert.equal(railApi.seekBufferedPercent(), 62.9, "a sub-tick buffer change must not move the band");

// Seeking past the buffer leaves the ranges behind the playhead.  The band must
// not shrink behind the fill: that reads as the file being unloaded.
context.localPlaybackSeconds = () => 200;
context.audio.currentTime = 200;
context.audio.buffered = { length: 1, start: () => 0, end: () => 120 };
railApi.updateSeekRail(83);
assert.deepEqual(read(), {fill: "83%", buffer: "83%"},
  "the buffered band may never sit behind the played edge");

// No usable ranges (a fresh track, the host player) collapses the middle stop.
context.audio.buffered = { length: 0, start: () => 0, end: () => 0 };
assert.equal(railApi.seekBufferedPercent(), 0, "an empty TimeRanges list is not a reading");
railApi.updateSeekRail(40);
assert.deepEqual(read(), {fill: "40%", buffer: "40%"}, "no ranges means the rail looks exactly as it did before R484");

// A row that belongs to a caster, or to the host player, has no element ranges
// behind it; drawing a band there would be a guess.
context.audio.buffered = { length: 1, start: () => 0, end: () => 200 };
context.isIncomingRendererSession = () => true;
assert.equal(railApi.seekBufferedPercent(), 0, "a caster's rail carries no local buffer reading");
context.isIncomingRendererSession = () => false;
context.isRemoteTarget = () => true;
assert.equal(railApi.seekBufferedPercent(), 0, "a remote target has its own length; the local buffer says nothing about it");
context.isRemoteTarget = () => false;
context.nativePlaybackAvailable = () => true;
assert.equal(railApi.seekBufferedPercent(), 0, "the host player reports no element buffer");
context.nativePlaybackAvailable = () => false;

// A zero-length track must not divide by zero into Infinity%.
context.seekDuration = () => 0;
assert.equal(railApi.seekBufferedPercent(), 0, "no duration means no percentage");

// --------------------------------------------------------------- the wiring --
// Buffer growth is the one rail change that arrives without a position tick.
assert.match(app, /audio\.onprogress = \(\) => updateSeekRail\(\);/,
  "a paused element keeps buffering, so progress has to repaint the rail");
assert.match(app, /audio\.onemptied = \(\) => updateSeekRail\(\);/,
  "stopping drops the ranges; the band has to disappear with them");

// The band is written through the same compare-first helper as the fill.
assert.equal((app.match(/"--seek-buffer"/g) || []).length, 1,
  "exactly one place may name the buffer variable, and it is the guarded writer");

console.log("Seek buffer rail checks passed.");
