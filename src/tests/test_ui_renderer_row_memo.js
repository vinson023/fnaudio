const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the render-row memo regression`);
  return match[0];
}
function constSource(name) {
  const match = app.match(new RegExp("^const " + name + " = [^\\n]+", "m"));
  assert.ok(match, `const ${name} must stay extractable for the render-row memo regression`);
  return match[0];
}

const limitConst = constSource("TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS");
const paintNames = [
  "clock", "playbackSeconds", "seekPercent",
  "setTextContentIfChanged", "setStyleVarIfChanged", "setDatasetStateIfChanged",
  "syncNowPlayingTime", "syncPlayerProgress", "updateSeekRail", "setPlayButton",
  "isIncomingRendererSession", "updateTransportStateUnknown",
  "transportStateIsUnknown", "transportExtrapolation",
  "updateMediaSessionPosition", "updateIncomingRendererUi", "resetTransportRow",
];

function createNode(initial) {
  let text = initial === undefined ? "" : String(initial);
  let html = "";
  let value = "0";
  const vars = new Map();
  const counts = { text: 0, html: 0, style: 0, value: 0 };
  return {
    counts,
    dataset: {},
    get value() { return value; },
    set value(next) { value = next; counts.value += 1; },
    get textContent() { return text; },
    set textContent(next) { text = String(next); counts.text += 1; },
    get innerHTML() { return html; },
    set innerHTML(next) { html = String(next); counts.html += 1; },
    style: {
      getPropertyValue: name => (vars.has(name) ? vars.get(name) : ""),
      setProperty: (name, next) => { vars.set(name, next); counts.style += 1; },
    },
  };
}

const NODE_IDS = ["nowTitle", "nowArtist", "nowTime", "elapsed", "duration", "seek", "playBtn", "transportStateUnknown"];

function harness(seed) {
  const nodes = {};
  NODE_IDS.forEach(id => { nodes[id] = createNode(); });
  const session = { ...seed };
  const state = { rendererSession: session, rendererSnapshotAt: Date.now(), seeking: false, remoteUiLast: null, rendererUiLast: null };
  // Models what `currentSeconds` does on this channel: a *paused* caster yields
  // `transportExtrapolation(..., false) === 0`, so an unchanged `position` really does
  // produce an identical reading on every tick. A playing one advances between polls.
  const model = { ticks: 0 };
  const context = {
    state, nodes, session, model, assert,
    String, Number, Math, Boolean, Map, Set, JSON, Object, Array,
    navigator: { mediaSession: { setPositionState: () => { context.hostCalls += 1; } } },
    hostCalls: 0,
    isRemoteTarget: () => false,
    isDacTarget: () => false,
    nativePlaybackAvailable: () => false,
    currentItem: () => null,
    audio: { duration: NaN },
    seekDuration: () => Number(state.rendererSession && state.rendererSession.duration) || 0,
    currentSeconds: () => {
      const s = state.rendererSession;
      if (!s) return 0;
      const transport = String(s.transport || "").toUpperCase();
      return transport === "PLAYING" ? Number(s.position) + model.ticks : Number(s.position);
    },
    $: id => nodes[id],
  };
  context.globalThis = context;
  vm.runInNewContext(
    limitConst + "\n" + paintNames.map(functionSource).join("\n") +
    "\nglobalThis.run = { updateIncomingRendererUi, resetTransportRow };",
    context
  );
  return context;
}

const total = c => NODE_IDS.reduce((sum, id) => sum + c.nodes[id].counts.text + c.nodes[id].counts.html + c.nodes[id].counts.style + c.nodes[id].counts.value, 0);

// ---- 1. The defect: a frozen incoming cast must stop being rewritten. ----
{
  const c = harness({ uri: "http://render/frozen.flac", transport: "PAUSED_PLAYBACK", position: 100, duration: 200 });
  c.run.updateIncomingRendererUi();
  const painted = { writes: total(c), host: c.hostCalls, rail: c.nodes.seek.counts.value };
  assert.ok(painted.rail === 1 && painted.host === 1, "the first paint of a cast must move the rail and tell the host");
  for (let i = 0; i < 6; i += 1) c.run.updateIncomingRendererUi();
  assert.equal(total(c), painted.writes, "six identical status polls must not touch the transport row at all");
  assert.equal(c.nodes.seek.counts.value, painted.rail, "an unchanged render position must not rewrite #seek.value");
  assert.equal(c.hostCalls, painted.host, "an unchanged render position must not call navigator.mediaSession.setPositionState again");
}

// ---- 2. Control: evidence that advances must still paint every tick. ----
{
  const c = harness({ uri: "http://render/live.flac", transport: "PLAYING", position: 10, duration: 300 });
  for (let i = 0; i < 3; i += 1) { c.model.ticks += 1; c.run.updateIncomingRendererUi(); }
  assert.equal(c.nodes.seek.counts.value, 3, "an advancing cast must repaint the rail on every poll");
  assert.equal(c.hostCalls, 3, "an advancing cast must report its position to the host on every poll");
  assert.equal(c.nodes.elapsed.textContent, "0:13", "the clock must follow the advancing position");
}

// ---- 3. A transport change with an unchanged position must repaint. ----
{
  const c = harness({ uri: "http://render/edge.flac", transport: "PLAYING", position: 42, duration: 100 });
  c.run.updateIncomingRendererUi();
  c.run.updateIncomingRendererUi();
  const before = total(c);
  c.session.transport = "PAUSED_PLAYBACK";
  c.run.updateIncomingRendererUi();
  assert.ok(total(c) > before, "a transport change is new evidence and has to repaint");
  assert.equal(c.nodes.playBtn.counts.html, 2, "the icon follows the transport change once");
  const repainted = total(c);
  c.run.updateIncomingRendererUi();
  assert.equal(total(c), repainted, "the memo is re-armed behind the transport change, so the next identical poll is suppressed again");
}

// ---- 4. Self-healing: the memo must not survive the cast it described. ----
{
  const c = harness({ uri: "http://render/again.flac", transport: "PAUSED_PLAYBACK", position: 60, duration: 240 });
  c.run.updateIncomingRendererUi();
  assert.equal(c.run.updateIncomingRendererUi(), true, "an active cast owns the row");
  assert.equal(c.nodes.seek.counts.value, 1, "the second identical poll is suppressed");
  c.state.rendererSession = null;
  assert.equal(c.run.updateIncomingRendererUi(), false, "no session, no claim on the row");
  assert.equal(c.state.rendererUiLast, null, "the memo is cleared when the cast ends");
  c.state.rendererSession = { uri: "http://render/again.flac", transport: "PAUSED_PLAYBACK", position: 60, duration: 240 };
  c.run.updateIncomingRendererUi();
  assert.equal(c.nodes.seek.counts.value, 2, "a later cast with byte-identical evidence still paints");
  assert.equal(c.hostCalls, 2, "and still tells the host about it");
}

// ---- 5. A user drag must not be stamped on, and must resume afterwards. ----
{
  const c = harness({ uri: "http://render/drag.flac", transport: "PLAYING", position: 5, duration: 120 });
  c.run.updateIncomingRendererUi();
  c.state.seeking = true;
  const during = total(c);
  c.run.updateIncomingRendererUi();
  assert.equal(total(c), during, "while the user drags, the poll must not move the rail");
  c.state.seeking = false;
  c.model.ticks += 1;
  c.run.updateIncomingRendererUi();
  assert.equal(c.nodes.seek.counts.value, 2, "the rail resumes once the drag ends and evidence moves");
}

// ---- 6. No staleness-lamp regression on a suppressed tick. ----
{
  const c = harness({ uri: "http://render/lamp.flac", transport: "PLAYING", position: 8, duration: 60 });
  c.run.updateIncomingRendererUi();
  // The compare-first writer leaves an untouched node with no attribute at all, so the
  // readable value is the normalised one, not a literal empty string.
  assert.equal(c.nodes.transportStateUnknown.dataset.state || "", "", "a fresh snapshot is not flagged");
  // Freeze the evidence and let the snapshot go stale: the memo now suppresses the
  // slider and the host call, but the lamp depends on the wall clock rather than on
  // these values, so it must still light. Gating it would be the regression.
  const frozen = total(c);
  c.state.rendererSnapshotAt = 1;
  c.run.updateIncomingRendererUi();
  assert.equal(total(c), frozen, "this really is a memo-hit tick: the row is untouched");
  assert.equal(c.hostCalls, 1, "and a memo-hit tick for the host call as well");
  assert.equal(c.nodes.transportStateUnknown.dataset.state, "unknown", "the lamp still lights when the channel runs out of evidence");
}

// ---- 7. resetTransportRow drops both memos with the row it resets. ----
{
  const c = harness({ uri: "http://render/stop.flac", transport: "PLAYING", position: 30, duration: 90 });
  c.run.updateIncomingRendererUi();
  c.state.remoteUiLast = { transport: "PLAYING", duration: 90, seconds: 30, current: "x" };
  c.run.resetTransportRow();
  assert.equal(c.state.rendererUiLast, null, "the render memo goes with the row it was guarding");
  assert.equal(c.state.remoteUiLast, null, "the remote memo goes with the row it was guarding");
  assert.equal(c.nodes.seek.value, 0, "the rail is parked");
}

// ---- 8. Source-level wiring, so the behaviour above cannot be relocated away. ----
{
  const fn = functionSource("updateIncomingRendererUi");
  assert.match(app, /^state\.rendererUiLast = null;$/m, "the render memo is declared beside the render state");
  assert.match(fn, /if \(!isIncomingRendererSession\(\)\) \{\s*(?:\/\/[^\n]*\n\s*)*state\.rendererUiLast = null;\s*\n\s*return false;/,
    "the memo is cleared on the early exit that ends the cast");
  assert.match(fn, /const previous = state\.rendererUiLast \|\| \{\};/, "the inbound channel keeps its own change gate");
  assert.match(app, /const previous = state\.remoteUiLast \|\| \{\};/, "the outbound channel keeps its change gate");
  assert.match(fn, /previous\.uri === session\.uri && previous\.transport === transport[\s\S]*previous\.duration === duration && previous\.seconds === seconds/,
    "the gate compares the session, transport state, duration and position");
  assert.match(fn, /if \(!unchanged\) \{\s*\n\s*\$\("seek"\)\.value = Math\.max\(0, Math\.min\(100, seconds \/ duration \* 100\)\);/,
    "the slider is written only on new evidence");
  assert.match(fn, /if \(!unchanged\) updateMediaSessionPosition\(\);/, "the host media session is called only on new evidence");
  assert.match(fn, /^[ \t]*syncPlayerProgress\(\);[ \t]*$/m, "the staleness lamp must stay ungated");
  assert.doesNotMatch(fn, /if \(!unchanged\)\s*\n\s*syncPlayerProgress\(\);/, "the transport paint must not be gated away");
  assert.match(functionSource("resetTransportRow"), /state\.remoteUiLast = null;\s*\n\s*state\.rendererUiLast = null;/,
    "resetTransportRow clears both memos");
}

console.log("Incoming render transport-row memo checks passed.");
