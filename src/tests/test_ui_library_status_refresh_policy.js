const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/library_status_refresh_policy.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const { plan } = context.globalThis.fnAudioLibraryStatusRefreshPolicy;

function assertPlan(actual, reuse, queueRefresh) {
  assert.equal(actual.reuse, reuse);
  assert.equal(actual.queueRefresh, queueRefresh);
}
assertPlan(plan(false, false), false, false);
assertPlan(plan(false, true), false, false);
assertPlan(plan(true, false), true, false);
assertPlan(plan(true, true), true, true);

console.log("Library status refresh policy regression checks passed.");
