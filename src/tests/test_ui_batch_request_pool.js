const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app/ui/batch_request_pool.js", "utf8");
const context = { globalThis: {}, Map, Promise, setTimeout };
vm.runInNewContext(source, context);
(async () => {
  const started = [];
  let active = 0;
  let maxActive = 0;
  const pool = context.globalThis.fnAudioBatchRequestPool([1, 2, 3], 2, async value => {
    started.push(value);
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise(resolve => setTimeout(resolve, 2));
    active -= 1;
    return value * 10;
  });
  assert.deepEqual([await pool.get(0), await pool.get(1), await pool.get(2)], [10, 20, 30]);
  assert.deepEqual(started.slice(0, 2), [1, 2]);
  assert.equal(maxActive, 2);
  const allPool = context.globalThis.fnAudioBatchRequestPool([1, 2, 3], 1, async value => value * 2);
  assert.deepEqual(await allPool.all(), [2, 4, 6]);
  let cancelStarted = 0;
  const cancelPool = context.globalThis.fnAudioBatchRequestPool([1, 2, 3], 1, async value => {
    cancelStarted += 1;
    await new Promise(resolve => setTimeout(resolve, 5));
    return value;
  });
  cancelPool.cancel("stale page");
  await assert.rejects(cancelPool.get(0), /stale page/);
  await assert.rejects(cancelPool.get(1), /stale page/);
  assert.equal(cancelStarted, 0, "cancellation before a reserved microtask runs must not start stale I/O");
  const boundedPool = context.globalThis.fnAudioBatchRequestPool([1, 2, 3], Infinity, async value => value);
  assert.deepEqual(await boundedPool.all(), [1, 2, 3]);
  const symbolPool = context.globalThis.fnAudioBatchRequestPool([1], Symbol("bad"), async value => value);
  assert.deepEqual(await symbolPool.all(), [1]);
  const cappedInput = context.globalThis.fnAudioBatchRequestPool((function* () {
    for (let index = 0; index < 5000; index += 1) yield index;
  })(), 1, async value => value);
  assert.equal(cappedInput.length, 4096);
  assert.equal((await cappedInput.get(4095)), 4095);
  assert.equal(await cappedInput.get(4096), undefined);
  const safeCancel = context.globalThis.fnAudioBatchRequestPool([1, 2], 1, async value => value);
  safeCancel.cancel({ toString() { throw new Error("must not stringify"); } });
  await assert.rejects(safeCancel.get(1), /Batch request cancelled/);
  const mutableBatch = ["first", "second", "third"];
  const snapshotPool = context.globalThis.fnAudioBatchRequestPool([mutableBatch], 1, async value => value.join(","));
  mutableBatch[0] = "changed";
  mutableBatch.push("late");
  assert.equal(await snapshotPool.get(0), "first,second,third");
  const oversizedBatch = Array.from({ length: 300 }, (_, index) => index);
  const boundedBatchPool = context.globalThis.fnAudioBatchRequestPool([oversizedBatch], 1, async value => value.length);
  assert.equal(await boundedBatchPool.get(0), 256);
  assert.equal(context.globalThis.fnAudioBatchRequestPoolLimits.MAX_BATCH_ITEMS, 256);
  assert.equal(context.globalThis.fnAudioBatchRequestPool.DEFAULT_CONCURRENCY, 4);
  assert.equal(context.globalThis.fnAudioBatchRequestPoolLimits.DEFAULT_CONCURRENCY, 4);
  console.log("Batch request pool regression checks passed.");
})().catch(error => { console.error(error); process.exit(1); });

const app = fs.readFileSync("app/ui/app.js", "utf8");
function functionSource(name) {
  const found = app.match(new RegExp(`^(?:async )?function ${name}\\([^]*?^}`, "m"));
  assert.ok(found, `${name} must remain executable in the batch cleanup regression`);
  return found[0];
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
function flushMicrotasks() {
  return new Promise(resolve => setImmediate(resolve));
}
function setup(kind, request) {
  const cache = new Map();
  cache.trim = () => {};
  const context = {
    URLSearchParams,
    state: { page: 2, pageSize: 1, queue: [], itemCache: cache },
    currentQueryParams: () => new URLSearchParams("view=all"),
    isPagedTrackListing: () => true,
    fetchLibraryResponse: url => {
      const offset = Number(new URLSearchParams(url.split("?")[1]).get("offset"));
      if (offset === 0) return Promise.resolve({ items: [{ id: "first" }], count: 12 });
      return request(offset).then(items => ({ items, count: 12 }));
    },
    fetchLibraryItemsByIds: ids => request(Number(ids[0].slice(1)) / 100 + 1),
    itemById: id => cache.get(id),
    cacheLibraryItems: items => items.forEach(item => cache.set(item.id, item)),
  };
  vm.createContext(context);
  for (const name of ["batch_request_pool", "library_page_plan", "library_page_merge",
    "library_full_list_policy", "item_hydration_policy"]) {
    vm.runInContext(fs.readFileSync(`app/ui/${name}.js`, "utf8"), context);
  }
  const name = kind === "pages" ? "fetchAllTracksForCurrentView" : "resolveTracksByIds";
  vm.runInContext(`${functionSource(name)}; globalThis.run = ${name};`, context);
  return () => kind === "pages" ? context.run()
    : context.run(Array.from({ length: 1200 }, (_, i) => `t${i}`));
}

(async () => {
  const failures = [];
  for (const kind of ["pages", "ids"]) {
    const started = [];
    const waiting = new Map();
    const run = setup(kind, index => {
      started.push(index);
      const pending = deferred();
      waiting.set(index, pending);
      return pending.promise;
    });
    const result = run();
    const sentinel = new Error(`${kind} transport failed`);
    const rejected = assert.rejects(result, error => error === sentinel,
      "cleanup must preserve the original request error");
    await flushMicrotasks();
    assert.deepEqual(started, [1, 2, 3, 4], "the real pool must start only its four active slots");
    waiting.get(1).reject(sentinel);
    await rejected;
    await flushMicrotasks();
    const terminalCount = started.length;
    for (const pending of waiting.values()) pending.resolve([{ id: "settled" }]);
    await flushMicrotasks();
    // Resolve any incorrectly launched work so this discriminator never leaves
    // dangling rejections or waits when run against the unfixed implementation.
    for (const pending of waiting.values()) pending.resolve([]);
    await flushMicrotasks();
    if (started.length !== terminalCount) failures.push(`${kind}: ${terminalCount} -> ${started.length}`);
  }
  assert.deepEqual(failures, [], "failed full-list consumers must not keep launching queued requests");

  {
    const started = [];
    const waiting = [];
    const run = setup("pages", index => {
      started.push(index);
      if (index === 1) return Promise.resolve([]);
      const pending = deferred();
      waiting.push(pending);
      return pending.promise;
    });
    const items = await run();
    assert.deepEqual(Array.from(items, item => item.id), ["first"],
      "an empty continuation page must retain the already collected items");
    await flushMicrotasks();
    const terminalCount = started.length;
    for (const pending of waiting) pending.resolve([]);
    await flushMicrotasks();
    assert.equal(started.length, terminalCount,
      "early completion must cancel the queued tail just as failure does");
  }

  for (const kind of ["pages", "ids"]) {
    const started = [];
    const run = setup(kind, index => {
      started.push(index);
      const count = kind === "pages" ? 1 : 100;
      return Promise.resolve(Array.from({ length: count }, (_, i) => ({
        id: kind === "pages" ? `page${index}` : `t${(index - 1) * 100 + i}`,
      })));
    });
    const items = await run();
    assert.equal(items.length, kind === "pages" ? 12 : 1200,
      "successful batches must keep every item");
    assert.equal(items[0].id, kind === "pages" ? "first" : "t0");
    assert.equal(items[items.length - 1].id, kind === "pages" ? "page11" : "t1199");
    assert.equal(started.length, kind === "pages" ? 11 : 12);
  }
  console.log("Library batch failure cleanup regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });

function setupGroups(request, groups = null) {
  const context = {
    URLSearchParams,
    currentQueryParams: () => new URLSearchParams("view=artists"),
    state: { view: "artists" },
    selectedGroupDescriptors: () => groups || Array.from({ length: 12 }, (_, i) => ({ view: "albums", name: `album${i}` })),
    isCreatorView: () => context.state.view === "artists",
    currentCreatorName: () => context.state.view === "artists" ? "original artist" : "",
    fetchAllTracksForCurrentView: request,
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  vm.runInContext(`${functionSource("resolveSelectedGroupTracks")}; globalThis.run = resolveSelectedGroupTracks;`, context);
  return context;
}
(async () => {
  const started = [];
  const waiting = [];
  const ctx = setupGroups(query => {
    started.push(query);
    const pending = deferred();
    waiting.push(pending);
    return pending.promise;
  });
  const error = new Error("group lookup failed");
  const rejected = assert.rejects(ctx.run(), caught => caught === error);
  await flushMicrotasks();
  assert.equal(started.length, 4);
  waiting[0].reject(error);
  await rejected;
  await flushMicrotasks();
  const terminal = started.length;
  for (const pending of waiting) pending.resolve([]);
  await flushMicrotasks();
  for (const pending of waiting) pending.resolve([]);
  await flushMicrotasks();
  assert.equal(started.length, terminal, "failed group consumer must cancel queued group requests");

  const queries = [];
  const pending = [];
  const success = setupGroups(query => {
    queries.push(query);
    const task = deferred();
    pending.push(task);
    return task.promise;
  });
  const result = success.run();
  await flushMicrotasks();
  success.state.view = "all";
  for (let batch = 0; batch < 3; batch += 1) {
    for (const task of pending) task.resolve([{ id: "shared" }, { id: `unique${pending.indexOf(task)}` }, { id: "" }]);
    await flushMicrotasks();
  }
  const items = await result;
  assert.equal(queries.length, 12);
  assert.ok(queries.every(query => query.view === "artists" && query.group === "original artist"),
    "queued groups must preserve the creator selection made when the operation started");
  assert.deepEqual(Array.from(items, item => item.id), ["shared", ...Array.from({ length: 12 }, (_, i) => `unique${i}`)],
    "group results must preserve selection order, remove duplicates and skip empty IDs");
  const ordinaryQueries = [];
  const ordinary = setupGroups(async query => {
    ordinaryQueries.push(query);
    return [{ id: query.folder || query.group }];
  }, [{ type: "folder", root: "/music", path: "disc" }, { view: "albums", name: "release" }]);
  ordinary.state.view = "all";
  assert.deepEqual(Array.from(await ordinary.run(), item => item.id), ["disc", "release"]);
  assert.deepEqual(JSON.parse(JSON.stringify(ordinaryQueries)), [
    { view: "folders", root: "/music", folder: "disc" },
    { view: "albums", group: "release" },
  ], "folder and ordinary album requests must keep their existing query contracts");
  const empty = setupGroups(() => { throw new Error("empty selection must not fetch"); }, []);
  assert.equal((await empty.run()).length, 0);
  console.log("Selected group batch cleanup and context regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });

function setupDeletion(request, ids = Array.from({ length: 12 }, (_, i) => `t${i}`)) {
  const status = { textContent: "" };
  const events = [], warnings = [], busy = [], queries = [];
  const context = {
    state: { pendingDeleteTrackIds: ids, queue: [{ id: "keep" }, { id: "t0" }], index: 1,
      pageTotal: 20, libraryStatus: { count: 20 } },
    $: () => status,
    setDeleteTrackBusy: value => busy.push(value),
    resolveTrackLocation: request,
    console: { warn: (...args) => warnings.push(args) },
    getTrimSdk: async () => { events.push("sdk"); return {
      ready: async () => events.push("ready"),
      query: async (query, options) => { events.push("delete"); queries.push({ query, options }); return { result: "succ" }; },
    }; },
    currentItem: () => ({ id: "t0" }),
    stopPlayback: async () => events.push("stop"),
    commitQueue: async (queue, current) => { events.push("queue"); context.committed = { queue, current }; },
    removeDeletedTracksFromClientState: ids => { events.push("remove"); context.removed = ids; },
    closeDeleteTrackDialog: () => events.push("close"),
    clearLibraryResponseCaches: () => events.push("clear"),
    render: () => events.push("render"),
    refreshLibraryStatus: () => events.push("refresh"),
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  vm.runInContext(`${functionSource("deleteTrackFiles")}; globalThis.run = deleteTrackFiles;`, context);
  return { context, status, events, warnings, busy, queries };
}
(async () => {
  const started = [], waiting = [];
  const failure = setupDeletion(id => {
    started.push(id);
    const task = deferred(); waiting.push(task); return task.promise;
  });
  const pending = failure.context.run();
  await flushMicrotasks();
  assert.equal(started.length, 4);
  const error = new Error("location unavailable");
  waiting[0].reject(error);
  await pending;
  await flushMicrotasks();
  const terminal = started.length;
  for (const task of waiting) task.resolve({ path: "/music/settled.flac" });
  await flushMicrotasks();
  for (const task of waiting) task.resolve({ path: "/music/settled.flac" });
  await flushMicrotasks();
  assert.equal(started.length, terminal, "failed deletion location lookup must stop launching queued requests");
  assert.equal(failure.status.textContent, error.message);
  assert.equal(failure.warnings[0][1], error, "location failure must preserve the original error for diagnostics");
  assert.deepEqual(failure.busy, [true, false]);
  assert.deepEqual(failure.events, [], "a failed lookup must not request host deletion or mutate playback/library state");
  assert.equal(failure.context.state.pageTotal, 20);

  for (const trash of [true, false]) {
    const lookups = [];
    const success = setupDeletion(async id => {
      lookups.push(id);
      return { path: `/music/song${Math.floor(Number(id.slice(1)) / 2)}.flac` };
    });
    await success.context.run(trash);
    assert.equal(lookups.length, 12);
    assert.equal(success.queries.length, 1);
    const { query, options } = success.queries[0];
    assert.equal(query.req, "file.rm");
    assert.equal(query.moveToTrashbin, trash);
    assert.deepEqual(Array.from(query.files), Array.from({ length: 6 }, (_, i) => `/music/song${i}.flac`));
    assert.equal(options.timeout, -1);
    assert.ok(success.events.indexOf("stop") < success.events.indexOf("delete"));
    assert.deepEqual(Array.from(success.context.committed.queue, item => item.id), ["keep"]);
    assert.equal(success.context.committed.current, "keep");
    assert.equal(success.context.removed.length, 12);
    assert.equal(success.context.state.pageTotal, 8);
    assert.equal(success.context.state.libraryStatus.count, 8);
    assert.equal(success.context.state.libraryStatus.scanning, true);
    assert.equal(success.warnings.length, 0);
    assert.ok(success.events.includes("refresh"));
  }
  const empty = setupDeletion(() => { throw new Error("must not resolve empty selection"); }, []);
  await empty.context.run();
  assert.deepEqual(empty.busy, []);
  assert.deepEqual(empty.events, []);
  console.log("Deletion location batch cleanup regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });

function setupGroupQuerySnapshot(search, kind = "artists") {
  const input = { value: search };
  const cache = new Map(); cache.trim = () => {};
  const queries = [], waiting = [];
  const context = {
    URLSearchParams,
    state: { view: "artists", artistName: "original artist", groupName: "", page: 2, pageSize: 1,
      sortKey: "track_no", sortDir: "asc", folderRoot: "", folderPath: "", queue: [], itemCache: cache },
    groupViews: { albums: "album", artists: "artist", composers: "composer", genres: "genre" },
    $: () => input,
    selectedGroupDescriptors: () => Array.from({ length: 12 }, (_, i) => ({ view: "albums", name: `album${i}` })),
    isPagedTrackListing: () => true,
    cacheLibraryItems: items => items.forEach(item => cache.set(item.id, item)),
    fetchLibraryResponse: url => {
      const params = new URLSearchParams(url.split("?")[1]);
      queries.push(params);
      const offset = Number(params.get("offset")), limit = Number(params.get("limit"));
      const task = deferred();
      waiting.push(() => task.resolve({ count: 2, items: Array.from({ length: Math.min(limit, 2 - offset) },
        (_, i) => ({ id: `${params.get("album") || params.get("folder") || params.get("group")}#${offset + i}` })) }));
      return task.promise;
    },
  };
  context.state.view = kind;
  if (kind === "folders") context.state.folderRoot = "/music";
  context.selectedGroupDescriptors = () => Array.from({ length: 12 }, (_, i) => kind === "folders"
    ? { type: "folder", root: "/music", path: `album${i}` }
    : { view: "albums", name: `album${i}` });
  vm.createContext(context);
  for (const name of ["batch_request_pool", "library_page_plan", "library_page_merge",
    "library_full_list_policy", "creator_view_policy", "library_query_params"]) {
    vm.runInContext(fs.readFileSync(`app/ui/${name}.js`, "utf8"), context);
  }
  vm.runInContext(["isCreatorView", "currentCreatorName", "isPlaylistView", "currentQueryText",
    "libraryQueryParamsFor", "currentQueryParams", "fetchAllTracksForCurrentView",
    "resolveSelectedGroupTracks"].map(functionSource).join("\n"), context);
  return { context, input, queries, waiting };
}
const snapshotWatchdog = setTimeout(() => {
  console.error("Selected group query snapshot checks did not finish.");
  process.exitCode = 1;
}, 5000);
(async () => {
  for (const kind of ["artists", "albums", "folders"]) {
    for (const initialSearch of ["", "original filter"]) {
      const h = setupGroupQuerySnapshot(initialSearch, kind);
      let done = false, result;
      const running = h.context.resolveSelectedGroupTracks().then(value => { done = true; result = value; });
      await flushMicrotasks();
      assert.equal(h.queries.length, 4);
      Object.assign(h.context.state, { view: "folders", pageSize: 2, sortKey: "title", sortDir: "desc",
        folderRoot: "/other-library", folderPath: "unrelated" });
      h.input.value = initialSearch ? "" : "unrelated filter";
      for (let tick = 0; tick < 40 && !done; tick += 1) {
        for (const release of h.waiting.splice(0)) release();
        await flushMicrotasks();
      }
      assert.equal(done, true, "all queued groups must settle without abandoning the original operation");
      await running;
      assert.ok(h.queries.every(query => (query.get("search") || "") === initialSearch),
        "every queued group must keep the original search, including an absent search filter");
      assert.ok(h.queries.every(query => query.get("sort") === "track_no" && query.get("dir") === "asc"),
        "every queued group must keep the original sort");
      assert.ok(h.queries.every(query => query.get("limit") === "1"),
        "queued groups and their continuation pages must retain the original page size");
      if (kind === "folders") {
        assert.ok(h.queries.every(query => query.get("root") === "/music" && /^album\d+$/.test(query.get("folder"))));
      } else {
        assert.ok(h.queries.every(query => !query.has("root") && !query.has("folder")),
          "navigating to another directory must not leak directory filters into earlier group requests");
      }
      assert.ok(h.queries.every(query => query.get("view") === kind));
      assert.ok(h.queries.every(query => kind === "artists"
        ? query.get("group") === "original artist" && /^album\d+$/.test(query.get("album"))
        : kind === "albums" ? /^album\d+$/.test(query.get("group")) : !query.has("group")));
      assert.equal(h.queries.length, 24);
      assert.deepEqual(Array.from(result, item => item.id),
        Array.from({ length: 12 }, (_, i) => [`album${i}#0`, `album${i}#1`]).flat());
    }
  }
  const direct = setupGroupQuerySnapshot("", "all");
  Object.assign(direct.context.state, { page: 1, libraryPageKey: "page-key", pageItems: [{ id: "cached" }], pageTotal: 1 });
  direct.context.libraryLoadRequestKey = () => "page-key";
  const cachedRequest = direct.context.fetchAllTracksForCurrentView();
  assert.equal(direct.queries.length, 0, "direct play-all must retain exact current-page reuse");
  const cached = await cachedRequest;
  assert.deepEqual(Array.from(cached, item => item.id), ["cached"]);

  const snapshot = { params: direct.context.currentQueryParams().toString(), pageSize: 1 };
  const explicit = direct.context.fetchAllTracksForCurrentView({}, snapshot);
  assert.equal(direct.queries.length, 1, "an explicit snapshot must never reuse an unrelated live page");
  direct.waiting.shift()();
  await flushMicrotasks();
  direct.waiting.shift()();
  const fetched = await explicit;
  assert.equal(fetched.length, 2);
  assert.ok(fetched.every(item => item.id !== "cached"));
  console.log("Selected group complete query snapshot regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; })
  .finally(() => clearTimeout(snapshotWatchdog));
