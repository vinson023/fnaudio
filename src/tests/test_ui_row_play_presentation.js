const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");

function extracted(pattern, label) {
  const match = source.match(pattern);
  assert.ok(match, `${label} must stay extractable for the row-play presentation regression`);
  return match[0];
}

const commitQueueSource = extracted(/^async function commitQueue\([\s\S]*?^\}/m, "commitQueue");
const applyConfirmedSource = extracted(/^function applyConfirmedQueue\([\s\S]*?^\}/m, "applyConfirmedQueue");
const playByIdSource = extracted(/^async function playById\([\s\S]*?^\}/m, "playById");
const presentationSource = extracted(/^function syncCurrentQueuePresentation\([\s\S]*?^\}/m, "syncCurrentQueuePresentation");

function build(overrides) {
  const state = {
    view: "queue",
    index: 0,
    page: 1,
    pageSize: 50,
    queue: [{ id: "a" }, { id: "b" }, { id: "c" }],
    repeat: "off",
    shuffle: false,
    streamOffset: 0,
    pendingSeekTime: 0,
    transcodeCacheReady: false,
    playSourceKind: "",
    userStateRevision: 0,
    nativePlayback: { supported: false, active: false, mediaId: "" },
  };
  Object.assign(state, overrides || {});
  const trace = { calls: [], rows: [], renderCount: 0, sent: null, scrollCount: 0 };
  const context = {
    state,
    trace,
    itemById: id => state.queue.find(item => String(item.id) === String(id)) || null,
    currentItem: () => state.queue[state.index] || null,
    loadCurrent: () => trace.calls.push("loadCurrent"),
    render: () => { trace.renderCount += 1; trace.calls.push("render"); },
    currentQueuePage: () => state.page,
    scrollCurrentQueueTrackIntoView: () => { trace.scrollCount += 1; },
    requestAnimationFrame: callback => callback(),
    updateCurrentQueueTrackRow: (queueIndex, current) => {
      trace.rows.push(`${queueIndex}:${current ? "on" : "off"}`);
      return true;
    },
    updateRepeatShuffleButtons: () => trace.calls.push("repeatShuffle"),
    updateFavoriteControls: () => trace.calls.push("favorites"),
    nativePlaybackAvailable: () => false,
    localIsPlayingNow: () => false,
    localPlaybackSeconds: () => 0,
    nativeLoadQueue: () => trace.calls.push("nativeLoadQueue"),
    userStateRevision: (value, fallback = 0) => (typeof value === "number" ? value : fallback),
    scheduleUserStateSave: () => trace.calls.push("scheduleUserStateSave"),
    apiFetch: async (_path, options) => {
      const sent = JSON.parse(options.body);
      trace.sent = sent;
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ ok: true, core: { current: sent.current_id, repeat: "all", shuffle: true }, revision: 11 }),
      };
    },
    alert: message => { throw new Error(message); },
  };
  vm.createContext(context);
  vm.runInContext(
    [presentationSource, applyConfirmedSource, commitQueueSource, playByIdSource,
      "globalThis.h = { playById: id => playById(id) };"].join("\n\n"),
    context,
  );
  return context;
}

(async () => {
  // The row that starts playing while the queue view is open has to move the
  // current-row marker with it. playById was the only queue writer that skipped
  // every presentation sync, so this is the observable symptom.
  {
    const q = build();
    await q.h.playById("b");
    assert.equal(q.trace.sent.current_id, "b", "playById must confirm the requested track with the core");
    assert.equal(q.state.index, 1, "the core answer must be mapped back onto the queue position");
    assert.deepEqual(q.trace.rows, ["0:off", "1:on"], "the current-row marker must move from the old row to the new one");
    assert.equal(q.trace.renderCount, 0, "a same-page row move must not rebuild the whole list");
    assert.equal(q.trace.calls.filter(name => name === "loadCurrent").length, 1, "the new row must still be loaded exactly once");
  }

  // Replaying the row that is already current is a no-op for the presentation.
  {
    const q = build();
    await q.h.playById("a");
    assert.equal(q.state.index, 0, "replaying the current row keeps its position");
    assert.deepEqual(q.trace.rows, [], "replaying the current row must not touch any row marker");
  }

  // Outside the queue view there are no queue rows on screen to restyle.
  {
    const q = build({ view: "all" });
    await q.h.playById("b");
    assert.equal(q.state.index, 1, "the queue position is tracked even while another view is showing");
    assert.deepEqual(q.trace.rows, [], "no queue row may be restyled while another view is active");
    assert.equal(q.trace.renderCount, 0, "the queue presentation sync must stay behind the view guard");
  }

  // Placement is part of the contract. playById has to capture the index it is
  // replacing before the writer rewrites it, and the shared writer must stay
  // clean: the other queue writers render right afterwards, so syncing there as
  // well would rebuild a cross-page jump twice.
  {
    const capture = playByIdSource.indexOf("const previousIndex = state.index;");
    const commit = playByIdSource.indexOf("await commitQueue(");
    assert.ok(capture >= 0, "playById must remember the queue row it is leaving");
    assert.ok(commit >= 0, "playById must keep committing through the shared queue writer");
    assert.ok(capture < commit, "the previous index must be captured before the writer rewrites state.index");
    assert.ok(
      /loadCurrent\(\);\s*\r?\n(?:[^\n]*\r?\n){0,6}?[^\n]*\r?\n?\s*syncCurrentQueuePresentation\(previousIndex\);/.test(playByIdSource),
      "playById must re-sync the row presentation after loading the new track",
    );
    assert.ok(
      !/syncCurrentQueuePresentation\(/.test(applyConfirmedSource),
      "applyConfirmedQueue must not sync: its rendering callers would then render twice",
    );
  }

  console.log("Row play presentation regression checks passed.");
})().catch(error => { console.error(error); process.exit(1); });
