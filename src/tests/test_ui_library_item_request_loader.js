const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_item_request_loader.js", "utf8");
const context = { globalThis: {}, Promise, Number, Array, TypeError, Math, JSON };
vm.runInNewContext(source, context);
const loader = context.globalThis.fnAudioLibraryItemRequestLoader;

(async () => {
  const inflight = new Map();
  let calls = 0;
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const fetchJson = async batch => { calls += 1; assert.deepEqual(batch, ["a", "b"]); await pending; return batch; };
  const first = loader.loadBatch({ batch: ["a", "b"], inflight, limit: 4, fetchJson });
  const second = loader.loadBatch({ batch: ["a", "b"], inflight, limit: 4, fetchJson });
  assert.strictEqual(first, second, "identical item batches must share one request");
  assert.equal(calls, 0, "fetch should be deferred to a microtask");
  await Promise.resolve();
  assert.equal(calls, 1);
  release();
  assert.deepEqual(await first, ["a", "b"]);
  await Promise.resolve();
  assert.equal(inflight.size, 0);

  const collisionInflight = new Map();
  const collisionResults = [];
  const firstCollision = loader.loadBatch({
    batch: ["a\u0001b"],
    inflight: collisionInflight,
    limit: 4,
    fetchJson: async batch => { collisionResults.push(batch); return "first"; },
  });
  const secondCollision = loader.loadBatch({
    batch: ["a", "b"],
    inflight: collisionInflight,
    limit: 4,
    fetchJson: async batch => { collisionResults.push(batch); return "second"; },
  });
  assert.notStrictEqual(firstCollision, secondCollision, "opaque IDs must not collide in batch keys");
  assert.equal(await firstCollision, "first");
  assert.equal(await secondCollision, "second");
  assert.equal(collisionResults.length, 2);
  const saturated = new Map([["active", new Promise(() => {})]]);
  await assert.rejects(
    () => loader.loadBatch({ batch: ["c"], inflight: saturated, limit: 1, fetchJson }),
    /concurrency limit/,
  );
  assert.equal(calls, 1, "a saturated loader must not start an untracked request");
  const zeroLimit = loader.loadBatch({ batch: ["d"], inflight: new Map(), limit: 0, fetchJson: async batch => batch });
  assert.deepEqual(await zeroLimit, ["d"], "zero must normalize to one request slot");
  await assert.rejects(() => loader.loadBatch({ batch: [], inflight, fetchJson }), TypeError);
  console.log("Library item request loader regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
