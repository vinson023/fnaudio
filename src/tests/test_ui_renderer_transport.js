const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the transport regression`);
  return match[0];
}
function constSource(name) {
  const match = app.match(new RegExp("^const " + name + " = [^\\n]+", "m"));
  assert.ok(match, `const ${name} must stay extractable for the transport regression`);
  return match[0];
}
const stalenessLampNames = [
  "updateTransportStateUnknown",
  "transportStateIsUnknown",
  "transportExtrapolation",
  "setDatasetStateIfChanged",
];
const limitConst = constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS");

// Shape invariants.  Every write below is reachable from a timer, so each one has
// to go through a compare-first helper instead of assigning unconditionally.
["nowTitle", "nowArtist", "elapsed", "duration"].forEach(id => {
  assert.doesNotMatch(app, new RegExp('\\$\\("' + id + '"\\)\\.textContent\\s*='), `#${id} must only be written through setTextContentIfChanged`);
});
assert.equal((app.match(/button\.innerHTML = `<span class="transport-icon/g) || []).length, 1, "Only setPlayButton may write the transport icon");
assert.equal((app.match(/transport-icon \$\{/g) || []).length, 1, "The transport icon class must be produced in exactly one place");
assert.equal((app.match(/setTextContentIfChanged\(\$\("nowTime"\)/g) || []).length, 1, "The compact clock needs one shared write point");
assert.match(app, /setStyleVarIfChanged\(\$\("seek"\), "--seek-fill"/, "The seek rail must skip identical fill values");
assert.match(app, /const next = playing === true \? "playing" : "paused";\s*if \(!button \|\| button\.dataset\.playing === next\) return;/, "An unchanged transport state must not rebuild the play icon");
assert.match(app, /setNowPlayingCover\(art\);\s*\n[\s\S]*?updateIncomingRendererUi\(\);\s*\n\s*updateNowMarquee\(\);/, "The renderer status poll must paint the transport row as well");

function createNode(initial) {
  let text = initial === undefined ? "" : String(initial);
  let html = "";
  const vars = new Map();
  const counts = { text: 0, html: 0, style: 0 };
  return {
    counts,
    dataset: {},
    value: "0",
    get textContent() { return text; },
    set textContent(value) { text = String(value); counts.text += 1; },
    get innerHTML() { return html; },
    set innerHTML(value) { html = String(value); counts.html += 1; },
    style: {
      getPropertyValue: name => (vars.has(name) ? vars.get(name) : ""),
      setProperty: (name, value) => { vars.set(name, value); counts.style += 1; },
    },
  };
}

const nodes = {};
["nowTitle", "nowArtist", "nowTime", "elapsed", "duration", "seek", "playBtn"].forEach(id => { nodes[id] = createNode(); });
const counters = { cover: 0, marquee: 0, lyricHighlight: 0, mediaPosition: 0 };
const session = { uri: "http://render/track.flac", transport: "PLAYING", position: 12, duration: 100 };
// A DLNA control point streaming in is not an outbound play target: isRemoteTarget
// stays false on this path, which is exactly the combination that used to freeze.
const transportState = { rendererSession: session, seeking: false, playTargetName: "USB DAC" };
const context = {
  state: transportState,
  String, Number, Math, Boolean, Map,
  nodes,
  counters,
  isIncomingRendererSession: () => Boolean(transportState.rendererSession && transportState.rendererSession.uri),
  isRemoteTarget: () => false,
  seekDuration: () => Number(transportState.rendererSession.duration || 0),
  currentSeconds: () => Number(transportState.rendererSession.position || 0),
  currentItem: () => null,
  displayText: value => String(value === undefined || value === null ? "" : value),
  externalArtworkUrl: value => String(value || ""),
  setNowPlayingCover: () => { counters.cover += 1; },
  updateNowMarquee: () => { counters.marquee += 1; },
  updateLyricHighlight: () => { counters.lyricHighlight += 1; },
  updateMediaSessionPosition: () => { counters.mediaPosition += 1; },
  $: id => nodes[id],
};
const sources = [
  "clock",
  "seekPercent",
  "setTextContentIfChanged",
  "setStyleVarIfChanged",
  "syncNowPlayingTime",
  "syncPlayerProgress",
  "updateSeekRail",
  "setPlayButton",
  "renderIncomingRendererSession",
  "updateRemoteUi",
  "updateIncomingRendererUi",
].concat(stalenessLampNames).map(functionSource).join("\n");
vm.runInNewContext(`${limitConst}
${sources}
globalThis.harness = { renderIncomingRendererSession, updateRemoteUi, setPlayButton, setTextContentIfChanged, setStyleVarIfChanged };`, context);
const harness = context.harness;
const paintSnapshot = () => Object.keys(nodes).reduce((sum, id) => sum + nodes[id].counts.text + nodes[id].counts.html + nodes[id].counts.style, 0);
const snapshot = paintSnapshot();

harness.renderIncomingRendererSession({ title: "Track One", artist: "Singer One", art_url: "api/cover/a.jpg" });
assert.ok(counters.cover >= 1, "The incoming session must still paint its artwork");
assert.equal(nodes.nowTitle.textContent, "Track One");
assert.match(nodes.nowArtist.textContent, /DLNA/, "The incoming session line must name the control point");
assert.equal(nodes.duration.textContent, "1:40", "The transport row must learn the render duration");
assert.equal(nodes.elapsed.textContent, "0:12", "The transport row must learn the render position");
assert.equal(nodes.seek.value, 12, "The slider must follow an incoming render position");
assert.equal(nodes.seek.style.getPropertyValue("--seek-fill"), "12%", "The rail fill must follow the slider");
assert.equal(nodes.nowTime.textContent, "0:12 / 1:40", "The compact clock must advance with the transport row");
assert.match(nodes.playBtn.innerHTML, /pause-icon/, "A playing render session shows the pause icon");
assert.ok(counters.mediaPosition >= 1, "The media session position must advance for an incoming session");
assert.ok(paintSnapshot() > snapshot, "The first poll after a status change has to paint");

// A poll that returns the same snapshot must be free, which is what keeps the
// 500ms/1.5s ticks from reading as flicker.
const steady = paintSnapshot();
harness.renderIncomingRendererSession({ title: "Track One", artist: "Singer One", art_url: "api/cover/a.jpg" });
assert.equal(paintSnapshot(), steady, "An identical transport snapshot must not touch the DOM");
assert.equal(nodes.playBtn.counts.html, 1, "A repeated transport state must not rebuild the icon");

session.position = 40;
harness.renderIncomingRendererSession({ title: "Track One", artist: "Singer One", art_url: "api/cover/a.jpg" });
assert.equal(nodes.elapsed.textContent, "0:40");
assert.equal(nodes.elapsed.counts.text, 2, "The clock is rewritten once per real change");
assert.equal(nodes.nowTitle.counts.text, 1, "An unchanged title must not be rewritten by the poll");
assert.equal(nodes.nowArtist.counts.text, 1, "An unchanged artist line must not be rewritten by the poll");
assert.equal(nodes.seek.counts.style, 2, "The rail is rewritten once per real change");

const afterPosition = paintSnapshot();
session.transport = "PAUSED_PLAYBACK";
harness.updateRemoteUi();
assert.equal(nodes.playBtn.counts.html, 2, "A transport change repaints the icon once");
assert.match(nodes.playBtn.innerHTML, /play-icon/, "A paused render session shows the play icon");
assert.equal(nodes.elapsed.counts.text, 2, "Pausing must not move the clock");
assert.equal(paintSnapshot(), afterPosition + 1, "Only the icon may change when nothing else moved");
harness.updateRemoteUi();
assert.equal(paintSnapshot(), afterPosition + 1, "A repeated transport state must not touch the DOM at all");

// The two compare-first helpers own the whole claim, checked directly.
const textNode = createNode("same");
harness.setTextContentIfChanged(textNode, "same");
assert.equal(textNode.counts.text, 0, "Identical text must not reach the DOM");
harness.setTextContentIfChanged(textNode, "other");
assert.equal(textNode.counts.text, 1);
harness.setTextContentIfChanged(textNode, null);
assert.equal(textNode.textContent, "", "A missing value must clear rather than print null");
harness.setTextContentIfChanged(undefined, "ignored");
const styled = createNode();
harness.setStyleVarIfChanged(styled, "--x", "5%");
harness.setStyleVarIfChanged(styled, "--x", "5%");
assert.equal(styled.counts.style, 1, "An identical style variable must not be written twice");
harness.setStyleVarIfChanged({}, "--x", "5%");
harness.setStyleVarIfChanged(undefined, "--x", "5%");

// updateRemoteUi must keep its own snapshot gate for the outbound remote path.
assert.match(app, /const previous = state\.remoteUiLast \|\| \{\};/, "The remote transport tick keeps its change gate");

// R101: the 1.5s render poll used to paint the transport row twice per tick, because
// updateNowMarquee() ended in a syncPlayerProgress() of its own.  This second context
// runs the real marquee next to the real paint path, so the paint count is the claim:
// updateSeekRail is the single observable reached exactly once per syncPlayerProgress().
const railNodes = {};
["nowTitle", "nowArtist", "nowTime", "elapsed", "duration", "seek", "playBtn"].forEach(id => { railNodes[id] = createNode(); });
const railCounters = { sync: 0, cover: 0, mediaPosition: 0 };
const railSession = { uri: "http://render/second.flac", title: "Second", artist: "Singer Two", art_url: "api/cover/b.jpg", transport: "PLAYING", position: 20, duration: 200 };
const railState = { rendererSession: railSession, seeking: false, playTargetName: "USB DAC" };
const railContext = {
  state: railState,
  String, Number, Math, Boolean,
  document: { body: { classList: { contains: () => false } } },
  requestAnimationFrame: () => 0,
  isIncomingRendererSession: () => Boolean(railState.rendererSession && railState.rendererSession.uri),
  isRemoteTarget: () => false,
  seekDuration: () => Number(railState.rendererSession.duration || 0),
  currentSeconds: () => Number(railState.rendererSession.position || 0),
  currentItem: () => null,
  displayText: value => String(value === undefined || value === null ? "" : value),
  externalArtworkUrl: value => String(value || ""),
  setNowPlayingCover: () => { railCounters.cover += 1; },
  updateMediaSessionPosition: () => { railCounters.mediaPosition += 1; },
  updateSeekRail: () => { railCounters.sync += 1; },
  $: id => railNodes[id],
};
const railSources = [
  "clock",
  "setTextContentIfChanged",
  "setStyleVarIfChanged",
  "syncNowPlayingTime",
  "syncPlayerProgress",
  "setPlayButton",
  "updateNowMarquee",
  "updateIncomingRendererUi",
  "renderIncomingRendererSession",
].concat(stalenessLampNames).map(functionSource).join("\n");
vm.runInNewContext(limitConst + "\n" + railSources + "\nglobalThis.rail = { renderIncomingRendererSession, updateIncomingRendererUi, updateNowMarquee };", railContext);
const rail = railContext.rail;

// One poll is one transport paint, and the marquee contributes none of its own.
rail.renderIncomingRendererSession(railSession);
assert.equal(railCounters.sync, 1, "A render poll must paint the transport row exactly once");
assert.equal(railNodes.nowTime.textContent, "0:20 / 3:20", "The single paint still has to be a real one");
rail.updateNowMarquee();
assert.equal(railCounters.sync, 1, "The marquee owns geometry and must never repaint progress");
rail.updateIncomingRendererUi();
assert.equal(railCounters.sync, 2, "The renderer paint path keeps its own single sync");

// Every owner that used to inherit the marquee sync now states it explicitly, and no
// other shape (a resize wrapper, a moved sync) is allowed to grow back into it.
assert.equal((app.match(/syncPlayerProgress\(\);\n[ \t]*updateNowMarquee\(\);/g) || []).length, 6, "restore/load/DAC/boot each pair their sync with their own marquee repaint");
assert.doesNotMatch(functionSource("updateNowMarquee"), /^[ \t]*syncPlayerProgress\(\);[ \t]*$/m, "The marquee body must not call syncPlayerProgress at all");
assert.match(functionSource("updateIncomingRendererUi"), /^[ \t]*syncPlayerProgress\(\);[ \t]*$/m, "The render poll paints the transport row itself");
assert.match(functionSource("restoreLibraryNowPlaying"), /syncPlayerProgress\(\);\n[ \t]*updateNowMarquee\(\);/, "The restore path repaints progress before geometry");
assert.match(functionSource("updateRemoteUi"), /^[ \t]*syncPlayerProgress\(\);[ \t]*$/m, "The outbound remote tick keeps its own transport paint");
// The timer/event owners that must keep painting on their own.  Each block is extracted
// with a column-zero terminator so an assertion cannot reach past the end of its handler
// and be satisfied by a sync belonging to a different one.
const paintBlocks = [
  ["audio.ontimeupdate", /^audio\.ontimeupdate = \(\) => \{[\s\S]*?^\};/m, "Local playback is ticked by the audio element, not by the marquee"],
  ["audio.onloadedmetadata", /^audio\.onloadedmetadata = \(\) => \{[\s\S]*?^\};/m, "A freshly loaded track paints its own progress"],
  ["window.fnAudioNativeOnState", /^window\.fnAudioNativeOnState = payload => \{[\s\S]*?^\};/m, "The native state pump paints the transport row itself"],
];
paintBlocks.forEach(entry => {
  const block = app.match(entry[1]);
  assert.ok(block, entry[0] + " must stay extractable for the transport regression");
  assert.match(block[0], /^[ \t]*syncPlayerProgress\(\);[ \t]*$/m, entry[2]);
});
assert.match(app, /updateModeButton\(\);\nsyncPlayerProgress\(\);\nupdateNowMarquee\(\);/, "Boot paints the row then the marquee");
assert.match(app, /nativeRemoteEnter\(true\);\n[ \t]*syncPlayerProgress\(\);\n[ \t]*updateNowMarquee\(\);/, "The cast-enter branch paints the row it just wrote");
assert.match(app, /window\.addEventListener\("resize", updateNowMarquee\);/, "Resize stays a geometry-only listener");
assert.doesNotMatch(app, /addEventListener\("resize",\s*\(\)\s*=>\s*\{[\s\S]{0,200}syncPlayerProgress/, "A window resize must not gain a wrapper that repaints progress");

console.log("Incoming render transport regression checks passed.");