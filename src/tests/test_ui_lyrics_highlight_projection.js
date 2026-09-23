const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// R166 lyric face: TODO.md:58/:61 was the transport row; the lyric panel is the next
// open instance of the same shape - a projection repainted from polling surfaces that
// keeps no memory of what it already painted.  Three defects, all disk-evidenced:
//
// A. updateLyricHighlight() is reached from window.fnAudioNativeOnState (app.js:923),
//    updateRemoteUi (app.js:2243) and the audio timeupdate handler (app.js:8455, about
//    four times a second), plus renderLyrics.  With no memory field the whole
//    [data-lyric] set is re-toggled every tick and lyricBox.scrollTo({behavior:
//    "smooth"}) is re-issued every tick, so the smooth animation restarts before it can
//    settle and the panel keeps dragging the reader back to the current line.
//
// B. The scan only ever raises the index, so `let active = 0` asserts "line 1 is being
//    sung" - through an LRC intro (first cue commonly 10-20 s in) and for any plain-text
//    lyric, which lyrics_parse_policy.js gives time: -1 and sorts to the front.  "No cue
//    is due yet" is a real state and must paint nothing.
//
// C. The priority-lyrics prefetch lane wrote a status word nothing else in src/app/ui or
//    src/tests uses - state.lyricsStatus = "ready" - while the reuse gate in
//    loadLyricsForCurrentTrack() only honours ["loading", "loaded", "pending"].  That
//    silently opted the track out of the contract CHANGELOG_AI records as "客户端
//    loadLyricsForCurrentTrack() 在 state.lyricsStatus === \"loaded\" 后对该曲不再重取":
//    every reopen re-announced "正在匹配歌词...", blanked a panel that already held the
//    lyric, and re-requested the provider behind a 10 s timeout.  The same lane also
//    skipped renderLyrics() whenever the panel was hidden, so state.lyrics and the panel
//    DOM diverged there - which is exactly why "loaded" cannot be adopted without also
//    adopting the render (see the pairing assertion at the end).

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the lyric projection regression`);
  return match[0];
}

function tracked(initial) {
  const node = { writes: [] };
  for (const key of Object.keys(initial)) {
    let value = initial[key];
    Object.defineProperty(node, key, {
      enumerable: true,
      get() { return value; },
      set(next) { node.writes.push(key + "=" + next); value = next; },
    });
  }
  return node;
}

const DEFAULT_LINES = [
  { time: 12, text: "first" },
  { time: 20, text: "second" },
  { time: 30, text: "third" },
];

function lyricNode(index) {
  const node = { index, writes: [], dataset: { lyric: String(index) }, offsetTop: 120 * index, clientHeight: 40 };
  node.classList = {
    toggle(className, force) {
      node.writes.push(`toggle(${className},${force === true})`);
    },
  };
  return node;
}

function setup(options = {}) {
  const lines = (options.lines || DEFAULT_LINES).map(line => ({ ...line }));
  const nodes = lines.map((_, index) => lyricNode(index));
  const box = {
    writes: [],
    scrollTop: 0,
    clientHeight: 300,
    innerHTML: "",
    scrollTo(position) { box.writes.push(`scrollTo(${Math.round(position.top)},${position.behavior})`); },
  };
  const view = tracked({ hidden: options.hidden === true });
  const calls = [];
  const state = {
    lyrics: lines,
    lyricsTrackId: "t1",
    lyricsStatus: "loaded",
    lyricsRequestToken: 3,
    lyricsPollTimer: 0,
    lyricsPollAttempts: 0,
    queue: [{ id: "t1", title: "Song", artist: "Singer" }],
    index: 0,
  };
  const clock = { now: options.now === undefined ? 25 : options.now };
  const context = {
    state, calls, nodes, box, view, clock,
    String, Number, Boolean, Math, Array, Object, JSON, Promise, Error, Set, RegExp, setTimeout, clearTimeout,
    $(id) {
      if (id === "lyricsLines") return box;
      if (id === "lyricsView") return view;
      return null;
    },
    document: {
      querySelectorAll(selector) {
        assert.equal(selector, "[data-lyric]", "the highlight pass must stay scoped to the lyric line nodes");
        calls.push("querySelectorAll");
        return nodes;
      },
      querySelector(selector) {
        calls.push(`querySelector:${selector}`);
        const match = /^\[data-lyric="(-?\d+)"\]$/.exec(selector);
        assert.ok(match, `unexpected lyric selector ${selector}`);
        return nodes[Number(match[1])] || null;
      },
    },
    currentSeconds: () => clock.now,
    escapeHtml: value => String(value).replace(/&/g, "&amp;"),
    currentItem: () => state.queue[state.index],
    updateLyricsMeta: item => calls.push(`updateLyricsMeta:${item ? item.id : "null"}`),
    cancelLyricsPoll: () => calls.push("cancelLyricsPoll"),
    cancelLyricsRequest: () => calls.push("cancelLyricsRequest"),
    scheduleLyricsPoll: trackId => calls.push(`scheduleLyricsPoll:${trackId}`),
    unwrapMetadataResponsePayload: value => value,
    usableCoverSource: value => value || "",
    invalidateTrackRowsMarkup: () => calls.push("invalidateTrackRowsMarkup"),
    restoreLibraryNowPlaying: () => calls.push("restoreLibraryNowPlaying"),
    render: () => calls.push("render"),
    parseLyrics: text => [{ time: 0, text }],
    fetchMetadataRequest: async url => {
      calls.push(`fetchMetadataRequest:${url}`);
      return { response: { ok: true, status: 200 }, data: { lyrics: "fetched", status: "ok" } };
    },
  };
  vm.createContext(context);
  vm.runInContext([
    functionSource("showLyricsMessage"),
    functionSource("renderLyrics"),
    functionSource("updateLyricHighlight"),
    functionSource("cancelLyricsPoll"),
    functionSource("scheduleLyricsPoll"),
    functionSource("cancelLyricsRequest"),
    functionSource("loadLyricsForCurrentTrack"),
    functionSource("openLyrics"),
    "globalThis.h = { showLyricsMessage, renderLyrics, updateLyricHighlight, loadLyricsForCurrentTrack, openLyrics };",
  ].join("\n"), context);
  return { ...context.h, state, calls, nodes, box, view, clock };
}

function allWrites(env) {
  return [...env.box.writes, ...env.view.writes, ...env.nodes.flatMap(node => node.writes)];
}

function scrollWrites(env) {
  return env.box.writes.filter(entry => entry.startsWith("scrollTo"));
}

function activeToggles(env) {
  return env.nodes.flatMap(node => node.writes
    .filter(entry => entry === "toggle(active,true)")
    .map(entry => `${node.index}:${entry}`));
}

function selectorQueries(env) {
  return env.calls.filter(entry => entry.startsWith("querySelector:"));
}

function scans(env) {
  return env.calls.filter(entry => entry === "querySelectorAll").length;
}

async function settle() {
  for (let index = 0; index < 12; index += 1) await Promise.resolve();
}

(async () => {
  // 1. Defect B: an intro longer than the first cue must not announce line 1.
  const intro = setup({ now: 5 });
  intro.updateLyricHighlight();
  assert.deepEqual(activeToggles(intro), [],
    "no cue is due at 5 s of a lyric whose first cue is at 12 s, so nothing may be marked active");
  assert.deepEqual(scrollWrites(intro), [],
    "and the panel must not centre a line that is not being sung");
  assert.deepEqual(selectorQueries(intro), [],
    "it must not even ask the document for a line node that cannot exist");

  // 2. Defect B: a lyric without timestamps has no current line at any time.
  const plain = setup({ lines: [{ time: -1, text: "a" }, { time: -1, text: "b" }], now: 60 });
  plain.updateLyricHighlight();
  assert.deepEqual(activeToggles(plain), [], "a lyric without timestamps has no current line");
  assert.deepEqual(scrollWrites(plain), [], "and therefore nothing to centre on");
  assert.deepEqual(selectorQueries(plain), [], "and no dangling node query for a timestamp-less lyric");

  // 3. A cue that is due still projects, exactly once.
  const due = setup({ now: 25 });
  due.updateLyricHighlight();
  assert.deepEqual(activeToggles(due), ["1:toggle(active,true)"], "the second line is the one due at 25 s");
  assert.equal(scrollWrites(due).length, 1, "and it is scrolled into view once");
  assert.equal(scans(due), 1, "one projection is one scan of the line nodes");

  // 4. Defect A: the three polling surfaces funnel here while the active line changes
  //    every few seconds, so a repeated projection of the same line must be free.
  const memo = due.nodes.map(node => node.writes.length);
  const scrolls = scrollWrites(due).length;
  due.updateLyricHighlight();
  due.updateLyricHighlight();
  assert.equal(scans(due), 1, "a tick that changed nothing may not re-scan the line nodes");
  assert.deepEqual(due.nodes.map(node => node.writes.length), memo,
    "no line node may be toggled while the active line is unchanged");
  assert.equal(scrollWrites(due).length, scrolls,
    "the smooth scroll must not be restarted by a tick that changed nothing");

  // 5. A real advance still projects, and un-marks the line that stopped being current.
  due.clock.now = 35;
  due.calls.length = 0;
  due.nodes.forEach(node => { node.writes.length = 0; });
  due.box.writes.length = 0;
  due.updateLyricHighlight();
  assert.deepEqual(activeToggles(due), ["2:toggle(active,true)"], "line 3 is due at 35 s");
  assert.ok(due.nodes[1].writes.includes("toggle(active,false)"),
    "the line that stopped being current must be un-marked");

  // 6. The invariant that makes the memory field safe: rebuilding the nodes drops what the
  //    projection remembers, so the fresh pass repaints nodes that never saw a class.  The
  //    memory is null only for the instant of the rebuild - renderLyrics() ends with its own
  //    projection - so what proves the invalidation is the write, not the field value.
  due.calls.length = 0;
  due.nodes.forEach(node => { node.writes.length = 0; });
  due.renderLyrics(DEFAULT_LINES);
  assert.equal(scans(due), 1,
    "renderLyrics() replaces every [data-lyric] node, so it must invalidate the memory and re-project");
  assert.ok(due.nodes[2].writes.includes("toggle(active,true)"),
    "the rebuilt node of the line that is due must be marked again even though the index did not move");
  assert.equal(due.state.lyricsActiveLine, 2,
    "and the memory settles on the line this projection just painted");
  assert.ok(due.box.innerHTML.includes("data-lyric="), "sanity: renderLyrics rewrote the line container");
  const rebuilt = setup({ now: 25 });
  rebuilt.renderLyrics(DEFAULT_LINES);
  const firstScans = scans(rebuilt);
  rebuilt.renderLyrics(DEFAULT_LINES);
  assert.equal(scans(rebuilt), firstScans + 1,
    "the first projection after a rebuild must write again even when the line number repeats");

  // 7. showLyricsMessage() replaces the lines with a message node, so it drops the memory too.
  const message = setup({ now: 25 });
  message.updateLyricHighlight();
  message.showLyricsMessage("正在匹配歌词...");
  assert.equal(message.state.lyricsActiveLine, null, "a message panel has no active line to remember");
  // Array.isArray reaches across the vm realm, deep equality against a host [] would not: the empty
  // array below was built by the code under test, inside its own context.
  assert.ok(Array.isArray(message.state.lyrics) && message.state.lyrics.length === 0,
    "and it holds no lyric body either");

  // 8. A closed panel is never projected: the memory field must not become a reason to
  //    move this work in front of the visibility gate.
  const hidden = setup({ now: 25, hidden: true });
  hidden.updateLyricHighlight();
  assert.deepEqual(allWrites(hidden), [], "a hidden lyrics panel may not be toggled or scrolled");

  // 9. Defect C: reopening a panel that already holds this track's lyric must reuse it.
  const reopened = setup({ now: 5, hidden: true });
  reopened.updateLyricHighlight();
  assert.deepEqual(allWrites(reopened), [], "sanity: nothing is projected while the panel is closed");
  reopened.calls.length = 0;
  await reopened.openLyrics();
  await settle();
  assert.equal(reopened.calls.filter(entry => entry.startsWith("fetchMetadataRequest")).length, 0,
    "a lyric this browser already holds must not be re-requested when the page reopens");
  assert.ok(reopened.view.writes.includes("hidden=false"), "the reopen must unhide the panel");
  assert.deepEqual(activeToggles(reopened), [], "still no cue due at 5 s, so still no active line");
  assert.deepEqual(selectorQueries(reopened), [], "and the reopen may not query for a line that has not started");

  // 10. Unhiding is the one transition the memory cannot see: the DOM kept its old class
  //     while the clock moved on behind a closed panel, and a paused or seeked session
  //     emits no timeupdate to correct it.  openLyrics() owns that first projection.
  const stale = setup({ now: 15 });
  stale.updateLyricHighlight();
  assert.deepEqual(activeToggles(stale), ["0:toggle(active,true)"], "sanity: line 1 is current at 15 s");
  stale.view.hidden = true;
  stale.clock.now = 35;
  stale.calls.length = 0;
  stale.nodes.forEach(node => { node.writes.length = 0; });
  stale.box.writes.length = 0;
  await stale.openLyrics();
  await settle();
  assert.deepEqual(activeToggles(stale), ["2:toggle(active,true)"],
    "the reopened panel must show the line the clock is on, not the one it was closed on");
  assert.equal(scrollWrites(stale).length, 1, "and centre it exactly once");

  // 11. Control for the contract: the reuse gate is vocabulary-driven, which is what made
  //     a sixth status word fatal.  An unknown word falls through to a fresh request.
  const unknown = setup({ now: 25 });
  unknown.state.lyricsStatus = "ready";
  unknown.calls.length = 0;
  await unknown.loadLyricsForCurrentTrack(unknown.state.queue[0]);
  await settle();
  assert.ok(unknown.calls.some(entry => entry.startsWith("fetchMetadataRequest")),
    "sanity: a status outside loading/loaded/pending re-requests the lyric");

  // 12. Source wiring: the vocabulary stays closed, every "loaded" claim is paired with
  //     the render that proves it, and no projection entry point is dropped by accident.
  const statusWords = [...new Set((app.match(/state\.lyricsStatus\s*=\s*"([a-z]+)"/g) || [])
    .map(entry => /"([a-z]+)"/.exec(entry)[1]))].sort();
  assert.deepEqual(statusWords, ["error", "idle", "loaded", "loading", "pending"],
    "state.lyricsStatus must keep exactly the five words the gates and the labels know: " + statusWords.join("/"));
  const loadedSites = [...app.matchAll(/state\.lyricsStatus = "loaded";/g)];
  assert.equal(loadedSites.length, 2, "the visible loader and the prefetch lane are the two producers of a loaded lyric");
  for (const site of loadedSites) {
    const block = app.slice(site.index, site.index + 240).split("\n").slice(0, 4).join("\n");
    const renderLines = block.split("\n").filter(line => line.includes("renderLyrics("));
    assert.equal(renderLines.length, 1, 'every "loaded" must be followed by its render: ' + block);
    assert.ok(!renderLines[0].includes("hidden"),
      "the panel may not be allowed to hold a lyric body its DOM never received: " + renderLines[0]);
  }
  assert.equal((app.match(/^\s+updateLyricHighlight\(\);$/gm) || []).length, 5,
    "native status, cast UI, timeupdate, renderLyrics and openLyrics are the five projection entry points");
  assert.match(app, /if \(!force && state\.lyricsTrackId === trackId && \["loading", "loaded", "pending"\]\.includes\(state\.lyricsStatus\)\) return;/,
    "the reuse gate must keep honouring a loaded lyric");

  console.log("Lyric highlight projection regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exit(1);
});
