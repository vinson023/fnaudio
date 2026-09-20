const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(require("node:path").join(__dirname, "..", "app", "ui", "access_profile_loader.js"), "utf8");
const context = { globalThis: {}, Promise, Number };
vm.runInNewContext(source, context);
const create = context.globalThis.fnAudioAccessProfileLoader.create;

(async () => {
  let now = 1000;
  let calls = 0;
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const loader = create({ now: () => now, fetchProfile: async () => { calls += 1; await gate; return { profile: "cgi" }; } });
  const first = loader.load();
  const second = loader.load();
  assert.strictEqual(first, second);
  assert.equal(calls, 0);
  release();
  assert.equal((await first).profile, "cgi");
  assert.equal(calls, 1);
  assert.equal((await loader.load()).profile, "cgi");
  assert.equal(calls, 1);
  now += 10001;
  assert.equal((await loader.load()).profile, "cgi");
  assert.equal(calls, 2);
  loader.clear();
  assert.equal((await loader.load(true)).profile, "cgi");
  assert.equal(calls, 3);
  assert.doesNotThrow(() => create({ ttlMs: { valueOf() { throw new Error("ttl"); } }, fetchProfile: () => Promise.resolve({ profile: "lan" }) }));
  console.log("Access profile loader regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
