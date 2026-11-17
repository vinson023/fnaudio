// R571: the queue grows by pages, the way Audio Station's does.
//
// A 50k-song library used to make one tap fire ~1000 requests (one page at a
// time, whole view) before the queue was coherent. This pins the new contract:
// one tap = one commit, and every later page is fetched only when playback
// actually approaches the end of what is queued.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");

function extracted(pattern, label) {
  const match = source.match(pattern);
  assert.ok(match, `${label} must stay extractable`);
  return match[0];
}

const beginSource = extracted(/^function beginQueueStream\([\s\S]*?^\}/m, "beginQueueStream");
const appendSource = extracted(/^async function appendNextQueuePage\([\s\S]*?^\}/m, "appendNextQueuePage");
const maybeSource = extracted(/^function maybeExtendQueue\([\s\S]*?^\}/m, "maybeExtendQueue");
const lookahead = Number((source.match(/const QUEUE_LOOKAHEAD = (\d+);/) || [])[1]);
assert.ok(Number.isFinite(lookahead) && lookahead > 0, "QUEUE_LOOKAHEAD must stay a real number");

const PAGE = 50;
const TOTAL = 50000;

function makeQueue(count, from = 0) {
  return Array.from({ length: count }, (_, index) => ({ id: `s${from + index}` }));
}

function build(overrides = {}) {
  const state = Object.assign({
    view: "all",
    page: 1,
    pageSize: PAGE,
    pageTotal: TOTAL,
    libraryTotal: TOTAL,
    index: 0,
    queue: makeQueue(PAGE),
    index_placeholder: undefined,
  }, overrides);
  const trace = { fetches: 0, commits: [] };
  let served = 0;
  const context = {
    state,
    queueStream: null,
    currentQueryText: () => "",
    isPagedTrackListing: () => true,
    libraryCount: value => Number(value) || 0,
    currentQueryParams: () => new URLSearchParams("view=all"),
    render: () => {},
    async fetchLibraryResponse() {
      trace.fetches += 1;
      const start = PAGE * (1 + served);
      served += 1;
      return { items: makeQueue(PAGE, start) };
    },
    async commitQueue(queue, currentId) {
      state.queue = queue;
      trace.commits.push({ ids: queue.map(item => String(item.id)), currentId });
      return {};
    },
  };
  vm.createContext(context);
  vm.runInContext(
    [`const QUEUE_LOOKAHEAD = ${lookahead};`, beginSource, appendSource, maybeSource,
      "globalThis.h = { begin: n => beginQueueStream(n), append: () => appendNextQueuePage(), maybe: () => maybeExtendQueue(), stream: () => queueStream };"].join("\n\n"),
    context,
  );
  return { context, state, trace, h: context.h };
}

(async () => {
  // One tap, 50k library: no page crawling at all.
  {
    const q = build();
    q.h.begin(PAGE);
    assert.equal(q.trace.fetches, 0, "opening a queue must not fetch anything");
    assert.equal(q.trace.commits.length, 0, "opening a queue must not commit anything");
    assert.equal(q.h.stream().nextOffset, PAGE, "the cursor starts after the page on screen");
    assert.equal(q.h.stream().total, TOTAL, "the cursor knows how much is left");
  }

  // Sitting near the start: nothing to top up.
  {
    const q = build();
    q.h.begin(PAGE);
    q.state.index = 3;
    q.h.maybe();
    assert.equal(q.trace.fetches, 0, "far from the end, playback must not fetch");
  }

  // Approaching the end of what is queued: exactly one page is fetched.
  {
    const q = build();
    q.h.begin(PAGE);
    q.state.index = PAGE - 1;
    q.h.maybe();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(q.trace.fetches, 1, "one page, not the whole view");
    assert.equal(q.state.queue.length, PAGE * 2, "the queue grows by one page");
    assert.equal(q.trace.commits.length, 1, "the growth is one commit");
    assert.equal(q.trace.commits[0].currentId, "s49", "playback stays on the same track");
  }

  // Playing through: request count tracks pages actually played, not library size.
  {
    const q = build();
    q.h.begin(PAGE);
    for (let page = 1; page <= 3; page += 1) {
      q.state.index = q.state.queue.length - 1;
      q.h.maybe();
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    assert.equal(q.trace.fetches, 3, "three pages played, three pages fetched");
    assert.equal(q.state.queue.length, PAGE * 4);
    const requestsForWholeLibrary = Math.ceil((TOTAL - PAGE) / PAGE);
    assert.ok(q.trace.fetches < requestsForWholeLibrary,
      "a tap must not cost what a full enumeration costs (" + requestsForWholeLibrary + ")");
  }

  // The end of the library closes the stream instead of polling forever.
  {
    const q = build({ pageTotal: PAGE, libraryTotal: PAGE });
    q.h.begin(PAGE);
    q.state.index = PAGE - 1;
    q.h.maybe();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(q.trace.fetches, 0, "a single-page library has nothing to append");
    assert.equal(q.h.stream(), null, "the stream closes once the total is reached");
  }

  // A view change ends it: appending would splice another list into the queue.
  {
    const q = build();
    q.h.begin(PAGE);
    q.state.view = "favorites";
    q.state.index = PAGE - 1;
    q.h.maybe();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(q.trace.fetches, 0, "a different view must not be appended");
    assert.equal(q.h.stream(), null, "the stream is dropped");
  }

  console.log("Queue stream regression checks passed (pages, not 50k rows).");
})().catch(error => { console.error(error); process.exit(1); });
