const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/ui_metrics_policy.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioUiMetricsPolicy;
assert.equal(typeof policy.snapshot, "function");
const snapshot = policy.snapshot({ renders: 4.9, listCommits: 1e30, firstListCommitMs: 12.8, metadataPrefetchFailures: "bad", metadataPrefetchNoMatches: 7.9, metadataPrefetchFirstMs: 18.8, metadataPrefetchLastMs: 21.8, metadataPrefetchMaxMs: 1e30, metadataPrefetchTotalMs: 42.9 });
assert.deepEqual(JSON.parse(JSON.stringify(snapshot)), {
  renders: 4, listCommits: 1000000, coverHydrations: 0, coverRequests: 0, coverLoads: 0, coverFailures: 0, coverRetries: 0, snapshotMarkupReuses: 0, listMarkupNoops: 0,
  metadataPrefetchRequests: 0, metadataPrefetchSuccesses: 0, metadataPrefetchFailures: 0, metadataPrefetchNoMatches: 7,
  firstListCommitMs: 12, firstCoverHydrationMs: 0, metadataPrefetchFirstMs: 18,
  metadataPrefetchLastMs: 21, metadataPrefetchMaxMs: 3600000, metadataPrefetchTotalMs: 42,
});
assert.equal(Object.prototype.hasOwnProperty.call(snapshot, "sessionStartedAt"), false);
const hostile = { valueOf() { throw new Error("must not coerce"); }, toString() { throw new Error("must not stringify"); } };
assert.deepEqual(policy.snapshot({ renders: hostile, listCommits: true, coverHydrations: Symbol("x") }).renders, 0);
assert.deepEqual(policy.snapshot({ renders: "9" }).renders, 9);
console.log("UI metrics policy regression checks passed.");
