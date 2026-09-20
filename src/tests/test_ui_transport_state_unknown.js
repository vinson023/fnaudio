const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");
const html = fs.readFileSync("app/ui/index.html", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the staleness lamp regression`);
  return match[0];
}
function constSource(name) {
  const match = app.match(new RegExp("^const " + name + " = [^\\n]+", "m"));
  assert.ok(match, `const ${name} must stay extractable for the staleness lamp regression`);
  return match[0];
}

// ---------------------------------------------------------------------------
// 1. Where the lamp lives, and what it is allowed to touch (TODO.md:74).
// ---------------------------------------------------------------------------
// R99 measured that #elapsed and #duration are display:none at every width, so the row had
// no visible number to mark stale: the lamp has to be its own element, sitting right after
// #elapsed, which is where the user put it.
assert.match(html, /<span id="elapsed">0:00<\/span><span id="transportStateUnknown" role="status"[^>]*>状态未知<\/span>/,
  "the lamp must sit directly after #elapsed and announce itself politely");
// Its copy is static HTML: writing it from a poll would be exactly the unconditional
// textContent write R99 closed on :61.
assert.doesNotMatch(app, /\$\("transportStateUnknown"\)\.textContent\s*=/,
  "#transportStateUnknown must never be written as text");
assert.doesNotMatch(app, /setTextContentIfChanged\(\$\("transportStateUnknown"\)/,
  "the lamp must not be painted through the text writer either");
// Hidden by default, shown only by the attribute, and qualified by the ID because three
// !important rules hide every span in this row.
assert.match(css, /#transportStateUnknown\{display:none\}/,
  "the lamp has to start hidden without needing the row-wide rules to stay");
assert.match(css, /#transportStateUnknown\[data-state="unknown"\]\{[^}]*display:inline-flex!important/,
  "the shown state must out-rank the !important hides on .progress span, which needs an ID");
// A `hidden` attribute would be a trap: every hiding rule here is !important, so a
// !important display would win over it and the lamp could never be turned off again.
assert.doesNotMatch(html, /id="transportStateUnknown"[^>]*\shidden/,
  "the lamp must not be gated by the hidden attribute");

// ---------------------------------------------------------------------------
// 2. Wiring shape: who drives it, and in what order.
// ---------------------------------------------------------------------------
const remoteBody = functionSource("updateRemoteUi");
const lampCall = remoteBody.indexOf("updateTransportStateUnknown();");
const firstReturn = remoteBody.search(/^[ \t]*(?:if \([^\n]*\)[ \t]*)?return\b/m);
assert.ok(lampCall >= 0, "the outbound remote tick has to drive the lamp");
assert.ok(firstReturn >= 0, "updateRemoteUi is expected to keep its early returns");
assert.ok(lampCall < firstReturn,
  "the lamp must be written before the early returns: currentSeconds clamps at the limit, so a frozen memo would hide it");
assert.match(functionSource("syncPlayerProgress"), /^[ \t]*updateTransportStateUnknown\(\);[ \t]*$/m,
  "the shared transport paint has to keep the lamp in step with the numbers");
assert.match(functionSource("updateDeviceLabel"), /^[ \t]*updateTransportStateUnknown\(\);[ \t]*$/m,
  "a device switch repaints the row's owner but not the row, so it must clear the lamp too");
// The boundary must stay the single shared budget, not a second number invented here.
assert.match(functionSource("transportStateIsUnknown"), /TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS/,
  "the lamp and the freeze must share one budget");
assert.doesNotMatch(functionSource("transportStateIsUnknown").split("{")[1], /\d/,
  "the staleness predicate must not grow its own threshold");
assert.equal(Number(/=\s*([0-9.]+)/.exec(constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS"))[1]), 10,
  "the ruled budget is 10 seconds");

// ---------------------------------------------------------------------------
// 3. Behaviour: run the real painter against a fake node that counts attribute writes.
// ---------------------------------------------------------------------------
function lampNode(initial) {
  const store = { ...(initial || {}) };
  const counts = { dataset: 0, text: 0, html: 0, style: 0 };
  return {
    counts,
    dataset: {
      get state() { return store.state; },
      set state(value) { store.state = String(value); counts.dataset += 1; },
    },
    get textContent() { return store.textContent || ""; },
    set textContent(value) { store.textContent = String(value); counts.text += 1; },
    style: { getPropertyValue: () => "", setProperty: () => { counts.style += 1; } },
  };
}

const BASE = 1_700_000_000_000;
let now = BASE;

function runPainter(state) {
  const lamp = lampNode();
  const context = {
    state,
    Date: { now: () => now },
    String, Number, Math, Boolean,
    $: id => (id === "transportStateUnknown" ? lamp : undefined),
    isIncomingRendererSession: () => Boolean(state.rendererSession && state.rendererSession.uri),
    isRemoteTarget: () => state.mode === "remote",
  };
  vm.runInNewContext([
    constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS"),
    functionSource("transportExtrapolation"),
    functionSource("transportStateIsUnknown"),
    functionSource("setDatasetStateIfChanged"),
    functionSource("updateTransportStateUnknown"),
    "globalThis.paint = updateTransportStateUnknown;",
  ].join("\n"), context);
  // Hand the state object back too: the later cases age the snapshot in place.
  return { paint: context.paint, lamp, state };
}
const remote = (extra = {}) => ({ mode: "remote", remoteStatus: { transport: { state: "PLAYING" } }, remoteSnapshotAt: 0, ...extra });
const renderer = (extra = {}) => ({ mode: "local", rendererSession: { uri: "http://render/track.flac", transport: "PLAYING" }, rendererSnapshotAt: 0, ...extra });

// Nothing arrived for 9.9s: still inside the budget the numbers are evidence-backed.
now = BASE;
let subject = runPainter(remote({ remoteSnapshotAt: BASE - 9900 }));
subject.paint();
assert.equal(subject.lamp.counts.dataset, 0, "9.9s of silence must not touch the DOM");
assert.equal(subject.lamp.textContent, "", "the lamp must not be written as text");

// 10.1s: the clock has stopped, which is the moment the row starts lying.
subject = runPainter(remote({ remoteSnapshotAt: BASE - 10100 }));
subject.paint();
assert.equal(subject.lamp.dataset.state, "unknown", "past the budget the row must say the state is unknown");
assert.equal(subject.lamp.counts.dataset, 1, "lighting the lamp costs exactly one attribute write");
subject.paint();
subject.paint();
assert.equal(subject.lamp.counts.dataset, 1, "the 500ms poll must write zero times on an unchanged state");

// Exactly on the budget it already counts as unknown, and evidence ends the claim.
subject = runPainter(remote({ remoteSnapshotAt: BASE - 10000 }));
subject.paint();
assert.equal(subject.lamp.dataset.state, "unknown", "the boundary belongs to the stale side");
now = BASE + 5000;
subject.state.remoteSnapshotAt = now;
subject.paint();
assert.equal(subject.lamp.dataset.state, "", "a fresh snapshot clears the lamp");
assert.equal(subject.lamp.counts.dataset, 2, "clearing costs one write and no more");
subject.paint();
assert.equal(subject.lamp.counts.dataset, 2, "a steady fresh channel stays write-free");
// Put the clock back so every case below is measured against the same budget.
now = BASE;

// A paused or never-answered channel has no frozen motion to explain.
subject = runPainter(remote({ remoteSnapshotAt: BASE - 60000, remoteStatus: { transport: { state: "PAUSED_PLAYBACK" } } }));
subject.paint();
assert.equal(subject.lamp.counts.dataset, 0, "PAUSED must not light the lamp");
subject = runPainter(remote({ remoteSnapshotAt: 0 }));
subject.paint();
assert.equal(subject.lamp.counts.dataset, 0, "a channel that never answered has no extrapolation to flag");
subject = runPainter(remote({ remoteSnapshotAt: BASE - 60000, remoteStatus: null }));
subject.paint();
assert.equal(subject.lamp.counts.dataset, 0, "no transport state means no claim about playing");

// Local playback is not a status channel: a lamp left over from a cast has to go out.
subject = runPainter(remote({ remoteSnapshotAt: BASE - 60000 }));
subject.paint();
assert.equal(subject.lamp.dataset.state, "unknown", "a cast that went silent lights the lamp first");
Object.assign(subject.state, { mode: "local", rendererSession: null });
subject.paint();
assert.equal(subject.lamp.dataset.state, "", "plain local playback must clear the lamp");
assert.equal(subject.lamp.counts.dataset, 2, "and it costs exactly the one clearing write");
subject.paint();
assert.equal(subject.lamp.counts.dataset, 2, "a steady local row stays write-free");

// The render session owns the row even when this app is not the one casting.
subject = runPainter(renderer({ rendererSnapshotAt: BASE - 60000, mode: "remote", remoteStatus: { transport: { state: "PLAYING" } }, remoteSnapshotAt: BASE }));
subject.paint();
assert.equal(subject.lamp.dataset.state, "unknown", "an incoming session is asked about first");
subject = runPainter(renderer({ rendererSnapshotAt: BASE - 9900, remoteStatus: { transport: { state: "PLAYING" } }, remoteSnapshotAt: BASE - 60000 }));
subject.paint();
assert.equal(subject.lamp.counts.dataset, 0, "a fresh session keeps the lamp dark even behind a dead outbound channel");

// The painter must survive a page without the element (the vm contexts of the other suites).
const barrenContext = { state: {}, String, Number, Math, Boolean, isIncomingRendererSession: () => false, isRemoteTarget: () => false, $: () => undefined };
vm.runInNewContext([
  constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS"),
  functionSource("transportExtrapolation"),
  functionSource("transportStateIsUnknown"),
  functionSource("setDatasetStateIfChanged"),
  functionSource("updateTransportStateUnknown"),
  "globalThis.ok = (() => { try { updateTransportStateUnknown(); return true; } catch (error) { return String(error); } })();",
].join("\n"), barrenContext);
assert.equal(barrenContext.ok, true, "a missing lamp must be ignored, not thrown");

console.log("Transport state-unknown lamp regression checks passed.");
