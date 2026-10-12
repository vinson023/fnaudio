const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/metadata_request_loader.js", "utf8");
const context = { Map, Promise, Number, Math, Date, Error, TypeError, String, Object };
vm.runInNewContext(source, context);
const factory = context.fnAudioMetadataRequestLoader;
assert.ok(factory, "metadata request loader must expose a factory");

(async () => {
  let now = 1000;
  const loader = factory.create({ now: () => now, ttlMs: 750, maxEntries: 2 });
  let calls = 0;
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const first = loader.load("api/metadata/track?track_id=a", () => { calls += 1; return pending; });
  const second = loader.load("api/metadata/track?track_id=a", () => { calls += 1; return pending; });
  assert.equal(calls, 0, "requests start on the microtask boundary");
  release({ ok: true });
  assert.deepEqual(await Promise.all([first, second]), [{ ok: true }, { ok: true }]);
  assert.equal(calls, 1, "same URL callers must share one underlying request");

  assert.deepEqual(await loader.load("api/metadata/track?track_id=a", () => { calls += 1; }), { ok: true });
  assert.equal(calls, 1, "a settled result must be reused inside the short TTL");
  now += 751;
  await loader.load("api/metadata/track?track_id=a", () => { calls += 1; return { ok: false }; });
  assert.equal(calls, 2, "expired entries must issue a fresh request");

  const controller = new AbortController();
  let resolveShared;
  const shared = loader.load("api/metadata/track?track_id=b", () => new Promise(resolve => { resolveShared = resolve; }), controller.signal);
  const survivor = loader.load("api/metadata/track?track_id=b", () => { calls += 1; });
  await Promise.resolve();
  await Promise.resolve();
  controller.abort();
  await assert.rejects(shared, error => error?.name === "AbortError");
  resolveShared({ ok: "survived" });
  assert.deepEqual(await survivor, { ok: "survived" }, "one caller abort must not cancel other callers");
  assert.equal(loader.snapshot().inflight, 0, "settled requests must leave the in-flight map");

  let releaseClear;
  const stale = loader.load("api/metadata/track?track_id=stale", () => new Promise(resolve => { releaseClear = resolve; }));
  await Promise.resolve();
  loader.clear();
  releaseClear({ stale: true });
  await stale;
  assert.equal(loader.snapshot().cache, 0, "clearing the loader must prevent a late response from repopulating its cache");

  let independentCalls = 0;
  const independent = await Promise.all([
    loader.load("api/metadata/track?track_id=x", () => { independentCalls += 1; return { id: "x" }; }),
    loader.load("api/metadata/track?track_id=y", () => { independentCalls += 1; return { id: "y" }; }),
  ]);
  assert.deepEqual(independent.map(value => value.id), ["x", "y"], "different URLs must never be coalesced");
  assert.equal(independentCalls, 2);

  await loader.load("api/metadata/track?track_id=c", () => ({ id: "c" }));
  await loader.load("api/metadata/track?track_id=d", () => ({ id: "d" }));
  await loader.load("api/metadata/track?track_id=e", () => ({ id: "e" }));
  assert.equal(loader.snapshot().cache, 2, "the settled cache must stay bounded");
  console.log("Metadata request single-flight regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
