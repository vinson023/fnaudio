const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/metadata_projection_policy.js", "utf8");
const context = { globalThis: {}, window: undefined };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioMetadataProjectionPolicy;
assert.equal(typeof policy.signature, "function");

const base = { lyrics: 1, tag_written: 2, jobs: { pending: 5, done: 3 }, track_matches: { auto: 2 } };
assert.equal(policy.signature({ ...base, jobs: { pending: 6, done: 3 } }), policy.signature(base), "pending churn must not invalidate projection");
assert.notEqual(policy.signature({ ...base, lyrics: 2 }), policy.signature(base));
assert.notEqual(policy.signature({ ...base, track_matches: { auto: 3 } }), policy.signature(base));
assert.notEqual(policy.signature({ ...base, tag_written: 3 }), policy.signature(base));
assert.equal(policy.signature(null), "0|0||0|0|");
assert.equal(policy.signature({ lyrics: {}, jobs: { done: Symbol("bad") }, track_matches: { x: {} }, tag_written: "bad", last_error: {} }), "0|0|x:0|0|0|");
assert.equal(policy.signature({ lyrics: "999999999999999999999999", jobs: { done: "2" } }), "0|2||0|0|");
assert.notEqual(policy.signature({ ...base, metadata_projection_revision: 1 }), policy.signature({ ...base, metadata_projection_revision: 2 }));
assert.equal(policy.signature({ ...base, metadata_updated_at: 10 }), policy.signature(base), "A terminal-job timestamp without a projection revision must not reload the list");
const oversizedMatches = {};
for (let index = 199; index >= 0; index -= 1) oversizedMatches[`track-${String(index).padStart(3, "0")}`] = index;
const oversizedSignature = policy.signature({ track_matches: oversizedMatches });
assert.equal(oversizedSignature.split("|")[2].split(",").length, 64, "track match projection must remain bounded");
assert.equal(oversizedSignature.split("|")[2].split(",")[0], "track-000:0", "bounded projection must preserve sorted prefix");
const throwingMatches = new Proxy({ good: 1 }, {
  ownKeys() { throw new Error("enumeration failed"); },
});
assert.equal(policy.signature({ track_matches: throwingMatches }), "0|0||0|0|", "enumeration failures must not break projection");
const throwingValue = {};
Object.defineProperty(throwingValue, "bad", { enumerable: true, get() { throw new Error("read failed"); } });
assert.equal(policy.signature({ track_matches: throwingValue }), "0|0|bad:0|0|0|", "value getter failures must be bounded and deterministic");
console.log("Metadata projection policy regression checks passed.");
