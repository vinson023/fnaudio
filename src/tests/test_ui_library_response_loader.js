const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const source = fs.readFileSync(require("path").join(__dirname, "..", "app", "ui", "library_response_loader.js"), "utf8");
const context = { globalThis: {}, Promise, Number, TypeError, AbortController };
vm.runInNewContext(source, context);
const load = context.globalThis.fnAudioLibraryResponseLoader.loadLibraryResponse;

(async () => {
  const cache = new Map();
  const inflight = new Map();
  let calls = 0;
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const fetchJson = async () => { calls += 1; await gate; return { items: [calls] }; };
  const first = load({ url: "/api/library", cache, inflight, fetchJson, epoch: 1 });
  const second = load({ url: "/api/library", cache, inflight, fetchJson, epoch: 1 });
  assert.strictEqual(first, second);
  assert.strictEqual(calls, 0);
  release();
  assert.deepStrictEqual(await first, { items: [1] });
  assert.deepStrictEqual(await load({ url: "/api/library", cache, inflight, fetchJson, epoch: 1 }), { items: [1] });
  assert.strictEqual(calls, 1);

  const preAbortedCache = new Map();
  const preAbortedInflight = new Map();
  const preAbortedActive = { value: 0 };
  const preAbortedController = new AbortController();
  let preAbortedCalls = 0;
  preAbortedController.abort();
  await assert.rejects(
    load({
      url: "/pre-aborted",
      cache: preAbortedCache,
      inflight: preAbortedInflight,
      active: preAbortedActive,
      fetchJson: async () => { preAbortedCalls += 1; return {}; },
      signal: preAbortedController.signal,
      epoch: 1,
    }),
    error => error?.name === "AbortError",
  );
  assert.strictEqual(preAbortedCalls, 0, "A pre-aborted owner must not dispatch fetchJson");
  assert.strictEqual(preAbortedActive.value, 0);
  assert.strictEqual(preAbortedInflight.size, 0);

  const abortedCache = new Map();
  const abortedInflight = new Map();
  const abortedActive = { value: 0 };
  const oldController = new AbortController();
  let releaseAborted;
  const abortedGate = new Promise(resolve => { releaseAborted = resolve; });
  let replacementCalls = 0;
  const oldRequest = load({
    url: "/aborted",
    cache: abortedCache,
    inflight: abortedInflight,
    active: abortedActive,
    inflightLimit: 1,
    fetchJson: async (_url, _message, signal) => {
      await abortedGate;
      if (signal?.aborted) throw Object.assign(new Error("aborted"), { name: "AbortError" });
      return "old";
    },
    signal: oldController.signal,
    epoch: 1,
  });
  oldController.abort();
  const replacement = load({
    url: "/aborted",
    cache: abortedCache,
    inflight: abortedInflight,
    fetchJson: async () => { replacementCalls += 1; return "replacement"; },
    signal: new AbortController().signal,
    active: abortedActive,
    inflightLimit: 2,
    epoch: 1,
  });
  assert.notStrictEqual(replacement, oldRequest, "An aborted request must not capture its replacement by URL");
  assert.strictEqual(await replacement, "replacement");
  assert.strictEqual(replacementCalls, 1);
  // Taking over an abandoned request moves its slot to the replacement, so the
  // counter is balanced as soon as the replacement settles; the dead fetch
  // settling later must not free a second slot.
  assert.strictEqual(abortedActive.value, 0, "the takeover must have moved the slot to the replacement");
  releaseAborted();
  await assert.rejects(oldRequest, error => error?.name === "AbortError");
  assert.strictEqual(abortedActive.value, 0, "Settled cancellation must leave the active counter balanced");

  const invalidationCache = new Map();
  const invalidationInflight = new Map();
  const invalidationActive = { value: 0 };
  let releaseInvalidation;
  const invalidationGate = new Promise(resolve => { releaseInvalidation = resolve; });
  let invalidationSignal;
  const invalidated = load({
    url: "/invalidated",
    cache: invalidationCache,
    inflight: invalidationInflight,
    active: invalidationActive,
    inflightLimit: 1,
    fetchJson: async (_url, _message, signal) => {
      invalidationSignal = signal;
      await invalidationGate;
      if (signal?.aborted) throw Object.assign(new Error("aborted"), { name: "AbortError" });
      return "unexpected";
    },
    epoch: 1,
  });
  await Promise.resolve();
  assert.strictEqual(invalidationActive.value, 1);
  invalidated.__fnAudioAbort();
  assert.strictEqual(invalidationSignal.aborted, true, "Invalidation must cancel the underlying request");
  assert.strictEqual(invalidationActive.value, 1, "Invalidation must not release an active slot before settlement");
  releaseInvalidation();
  await assert.rejects(invalidated, error => error?.name === "AbortError");
  assert.strictEqual(invalidationActive.value, 0, "Settled cancellation must release the active slot");

  const boundedCache = new Map();
  const boundedInflight = new Map([["/busy", Promise.resolve({ items: [] })]]);
  let boundedCalls = 0;
  await assert.rejects(
    load({ url: "/blocked", cache: boundedCache, inflight: boundedInflight, inflightLimit: 1, fetchJson: async () => { boundedCalls += 1; return {}; }, epoch: 1 }),
    /concurrency limit reached/,
  );
  assert.strictEqual(boundedCalls, 0, "A saturated response loader must not start another request");

  const refreshActive = { value: 1 };
  await assert.rejects(
    load({ url: "/refresh-blocked", refresh: true, active: refreshActive, inflightLimit: 1, cache: new Map(), inflight: new Map(), fetchJson: async () => ({}) }),
    /concurrency limit reached/,
  );


  // A blank value from the bridge means "unset", not "no requests allowed".
  // Number("") is 0, and a zero admission budget rejects every page load, so
  // the loader treats blank text the same way as null (see the same rule in
  // visible_metadata_prefetch_policy.js).
  for (const blank of ["", "   ", "\t\n"]) {
    const blankCache = new Map();
    const blankInflight = new Map();
    const blankActive = { value: 0 };
    let blankCalls = 0;
    assert.deepStrictEqual(await load({
      url: "/blank-" + blank.length, cache: blankCache, inflight: blankInflight, active: blankActive,
      inflightLimit: blank, fetchJson: async () => { blankCalls += 1; return { ok: true }; }, epoch: 1,
    }), { ok: true }, "a blank inflight limit must fall back to the default");
    assert.strictEqual(blankCalls, 1);
    assert.strictEqual(blankActive.value, 0, "the slot must be released after settlement");
  }
  await assert.rejects(load({
    url: "/explicit-zero", cache: new Map(), inflight: new Map(), inflightLimit: 0,
    fetchJson: async () => ({}),
  }), /concurrency limit reached/, "an explicit zero still means no budget");
  await assert.rejects(load({
    url: "/explicit-zero-text", cache: new Map(), inflight: new Map(), inflightLimit: "0",
    fetchJson: async () => ({}),
  }), /concurrency limit reached/, "zero written as text is still an explicit zero");
  const fractionalLimitCache = new Map();
  const fractionalLimitInflight = new Map();
  const fractionalLimitActive = { value: 1 };
  let fractionalLimitCalls = 0;
  await assert.rejects(
    load({
      url: "/fractional-limit",
      cache: fractionalLimitCache,
      inflight: fractionalLimitInflight,
      active: fractionalLimitActive,
      inflightLimit: 1.5,
      fetchJson: async () => { fractionalLimitCalls += 1; return {}; },
      epoch: 1,
    }),
    /concurrency limit reached/,
  );
  assert.strictEqual(fractionalLimitCalls, 0, "fractional limits must be floored before admission");

  const staleCache = new Map();
  const staleInflight = new Map();
  let currentEpoch = 1;
  const stale = load({ url: "/stale", cache: staleCache, inflight: staleInflight, fetchJson: async () => "old", epoch: 1, getEpoch: () => currentEpoch });
  currentEpoch = 2;
  assert.strictEqual(await stale, "old");
  assert.strictEqual(staleCache.has("/stale"), false);
  const refreshCache = new Map();
  let refreshEpoch = 1;
  let releaseOldRefresh;
  const oldRefreshGate = new Promise(resolve => { releaseOldRefresh = resolve; });
  const refreshInflight = new Map();
  const oldRefresh = load({ url: "/refresh", refresh: true, cache: refreshCache, inflight: refreshInflight, epoch: 1, getEpoch: () => refreshEpoch, fetchJson: async () => { await oldRefreshGate; return "old refresh"; } });
  const duplicateRefresh = load({ url: "/refresh", refresh: true, cache: refreshCache, inflight: refreshInflight, epoch: 1, getEpoch: () => refreshEpoch, fetchJson: async () => "duplicate refresh" });
  assert.strictEqual(duplicateRefresh, oldRefresh, "Overlapping refreshes for one page must share the active request");
  refreshEpoch = 2;
  assert.strictEqual(await load({ url: "/refresh", refresh: true, cache: refreshCache, inflight: new Map(), epoch: 2, getEpoch: () => refreshEpoch, fetchJson: async () => "new refresh" }), "new refresh");
  assert.strictEqual(refreshCache.get("/refresh"), "new refresh");
  releaseOldRefresh();
  assert.strictEqual(await oldRefresh, "old refresh");
  assert.strictEqual(refreshCache.get("/refresh"), "new refresh");
  // The cap is a hard ceiling, not a starting point: the configured limit is
  // floored, clamped to MAX_INFLIGHT_LIMIT, and every accepted request owns one
  // slot until it settles.
  const clampCache = new Map();
  const clampInflight = new Map();
  const clampActive = { value: 0 };
  let clampRelease;
  const clampGate = new Promise(resolve => { clampRelease = resolve; });
  const clampAccepted = [];
  for (let index = 0; index < 32; index += 1) {
    clampAccepted.push(load({
      url: "/clamp-" + index, cache: clampCache, inflight: clampInflight, active: clampActive,
      inflightLimit: 1000, fetchJson: async () => { await clampGate; return index; },
    }));
  }
  assert.strictEqual(clampActive.value, 32, "one slot per accepted request");
  assert.strictEqual(clampInflight.size, 32);
  await assert.rejects(load({
    url: "/clamp-overflow", cache: clampCache, inflight: clampInflight, active: clampActive,
    inflightLimit: 1000, fetchJson: async () => ({}),
  }), /concurrency limit reached/, "the limit must be clamped to the hard maximum");
  clampRelease();
  await Promise.all(clampAccepted);
  assert.strictEqual(clampInflight.size, 0, "settled requests leave the in-flight map");
  assert.strictEqual(clampActive.value, 0, "settled requests release their slot");
  // A view switch abandons the previous request. Its slot must go to the
  // replacement immediately: an older WebView that ignores `signal` keeps the
  // dead fetch alive until the transport times out, and at the ceiling that
  // makes the next page load reject outright.
  const takeoverCache = new Map();
  const takeoverInflight = new Map();
  const takeoverActive = { value: 0 };
  let releaseTakeover;
  const takeoverGate = new Promise(resolve => { releaseTakeover = resolve; });
  const takeoverController = new AbortController();
  const deadRequest = load({
    url: "/takeover", cache: takeoverCache, inflight: takeoverInflight, active: takeoverActive,
    inflightLimit: 1, signal: takeoverController.signal,
    fetchJson: async () => { await takeoverGate; return "dead"; },
  });
  assert.strictEqual(takeoverActive.value, 1);
  takeoverController.abort();
  assert.strictEqual(
    await load({
      url: "/takeover", cache: takeoverCache, inflight: takeoverInflight, active: takeoverActive,
      inflightLimit: 1, fetchJson: async () => "live",
    }),
    "live",
    "the replacement must be admitted at the ceiling after a takeover",
  );
  assert.strictEqual(takeoverActive.value, 0, "the replacement owns the only slot");
  releaseTakeover();
  assert.strictEqual(await deadRequest, "dead");
  assert.strictEqual(takeoverActive.value, 0, "the abandoned request must not free a slot twice");
  assert.strictEqual(takeoverInflight.size, 0);

  // A deduplicated caller joins the active request: it must not consume a second
  // slot, and it must not free the slot owned by the request it joined.
  const shareCache = new Map();
  const shareInflight = new Map();
  const shareActive = { value: 0 };
  let releaseShare;
  const shareGate = new Promise(resolve => { releaseShare = resolve; });
  const shareFetch = async () => { await shareGate; return "shared"; };
  const shareFirst = load({
    url: "/share", cache: shareCache, inflight: shareInflight, active: shareActive,
    inflightLimit: 1, fetchJson: shareFetch,
  });
  const shareSecond = load({
    url: "/share", cache: shareCache, inflight: shareInflight, active: shareActive,
    inflightLimit: 1, fetchJson: shareFetch,
  });
  assert.strictEqual(shareSecond, shareFirst, "the second caller must join the active request");
  assert.strictEqual(shareActive.value, 1, "one shared request owns exactly one slot");
  releaseShare();
  assert.strictEqual(await shareFirst, "shared");
  assert.strictEqual(await shareSecond, "shared");
  assert.strictEqual(shareActive.value, 0, "the slot is released once, by the request that owns it");

  // Every non-usable limit value has to fall back to the default budget. A NaN
  // budget would make the admission test `activeCount() >= NaN` always false, so
  // a bad bridge value would silently unlimit first-screen concurrency instead of
  // being rejected.
  async function saturate(limitValue, label) {
    const cache = new Map();
    const inflight = new Map();
    const active = { value: 0 };
    let releaseGate;
    const gate = new Promise(resolve => { releaseGate = resolve; });
    const outcomes = [];
    for (let index = 0; index < 33; index += 1) {
      outcomes.push(load({
        url: "/" + label + "-" + index,
        cache,
        inflight,
        active,
        inflightLimit: limitValue,
        fetchJson: async () => { await gate; return index; },
      }).then(() => "accepted", error => error?.message || ""));
    }
    releaseGate();
    const settled = await Promise.all(outcomes);
    return {
      accepted: settled.filter(value => value === "accepted").length,
      limited: settled.filter(value => value === "library response concurrency limit reached").length,
      active,
      inflight,
    };
  }

  for (const [label, limitValue] of [
    ["text", "abc"],
    ["infinite", Infinity],
    ["true", true],
    ["false", false],
  ]) {
    const budget = await saturate(limitValue, "saturate-" + label);
    assert.strictEqual(budget.accepted, 32, label + " must fall back to the default budget");
    assert.strictEqual(budget.limited, 1, label + " must reject exactly one request past the cap");
    assert.strictEqual(budget.active.value, 0, label + " must release every accepted slot");
    assert.strictEqual(budget.inflight.size, 0, label + " must drain the in-flight map");
  }

  // refresh must bypass a warm response cache, a plain read must not.
  const bypassCache = new Map([["/bypass", "cached"]]);
  let bypassCalls = 0;
  assert.strictEqual(
    await load({
      url: "/bypass", refresh: true, cache: bypassCache, inflight: new Map(),
      fetchJson: async () => { bypassCalls += 1; return "fresh"; },
    }),
    "fresh",
    "a refresh must not be served from the response cache",
  );
  assert.strictEqual(bypassCalls, 1);
  assert.strictEqual(bypassCache.get("/bypass"), "fresh");
  assert.strictEqual(
    await load({
      url: "/bypass", cache: bypassCache, inflight: new Map(),
      fetchJson: async () => { bypassCalls += 1; return "never"; },
    }),
    "fresh",
  );
  assert.strictEqual(bypassCalls, 1, "a plain read must still be served from the cache");

  // A corrupt active counter is floored on admission and on release, so one bad
  // write can never wedge the loader into negative slots.
  const corruptActive = { value: -5 };
  const corruptRequest = load({
    url: "/corrupt-active", cache: new Map(), inflight: new Map(), active: corruptActive,
    inflightLimit: 2, fetchJson: async () => "corrupt",
  });
  assert.strictEqual(corruptActive.value, 1, "a negative counter must be floored before a slot is taken");
  corruptActive.value = -3;
  await corruptRequest;
  assert.strictEqual(corruptActive.value, 0, "settling must land on zero, not below it");

  // A manual release frees exactly one slot; settlement must not free it twice or
  // steal the slot still held by a neighbouring request.
  let releaseEarlyA;
  let releaseEarlyB;
  const earlyGateA = new Promise(resolve => { releaseEarlyA = resolve; });
  const earlyGateB = new Promise(resolve => { releaseEarlyB = resolve; });
  const earlyActive = { value: 0 };
  const earlyA = load({
    url: "/early-a", cache: new Map(), inflight: new Map(), active: earlyActive, inflightLimit: 2,
    fetchJson: async () => { await earlyGateA; return "a"; },
  });
  const earlyB = load({
    url: "/early-b", cache: new Map(), inflight: new Map(), active: earlyActive, inflightLimit: 2,
    fetchJson: async () => { await earlyGateB; return "b"; },
  });
  assert.strictEqual(earlyActive.value, 2, "one slot per accepted request");
  earlyA.__fnAudioRelease();
  assert.strictEqual(earlyActive.value, 1, "an explicit release frees one slot");
  releaseEarlyA();
  await earlyA;
  assert.strictEqual(earlyActive.value, 1, "settling a released request must not free its neighbour");
  releaseEarlyB();
  await earlyB;
  assert.strictEqual(earlyActive.value, 0, "both slots end released exactly once");

  // The external abort listener is dropped once the request settles, otherwise a
  // page that reloads on every tab switch piles up listeners on one signal.
  const listenerEvents = [];
  const fakeSignal = {
    aborted: false,
    addEventListener(type, handler) { listenerEvents.push("add:" + type + ":" + typeof handler); },
    removeEventListener(type) { listenerEvents.push("remove:" + type); },
  };
  assert.strictEqual(
    await load({ url: "/listener", cache: new Map(), inflight: new Map(), signal: fakeSignal, fetchJson: async () => "listener" }),
    "listener",
  );
  assert.deepStrictEqual(listenerEvents, ["add:abort:function", "remove:abort"]);

  // Invalid options reject rather than throwing out of the caller's render path.
  await assert.rejects(load({}), /invalid library response loader options/);
  await assert.rejects(load({ url: "/no-fetch", cache: new Map(), inflight: new Map() }), /invalid library response loader options/);
  await assert.rejects(load({ url: "/no-cache", inflight: new Map(), fetchJson: async () => ({}) }), /invalid library response loader options/);
  // A zero admission budget rejects even the first request (`activeCount() >= limit` with 0 >= 0).
  // That is deliberate for an explicit `0`, which is pinned as "no budget" further up. What must
  // not inherit it is an input that reaches zero by accident: `Number([])` is 0 although nobody
  // configured anything, and a negative used to clamp down into that same silent shutdown.
  for (const [label, value] of [["empty array", []], ["empty nested array", [[]]], ["negative", -5],
                                ["negative fraction", -0.5], ["negative string", "-7"],
                                ["blank string", "   "], ["null", null], ["boolean", true]]) {
    let budgetCalls = 0;
    const admitted = await load({
      url: "/budget/" + label,
      cache: new Map(),
      inflight: new Map(),
      inflightLimit: value,
      // One request is already in flight, so a budget of 1 would reject here while the default
      // has no opinion about a single page. That is what separates "unset" from a real 1.
      active: { value: 1 },
      fetchJson: async () => { budgetCalls += 1; return { items: [budgetCalls] }; },
    });
    assert.deepStrictEqual(admitted, { items: [1] }, `${label} must still load one page`);
    assert.strictEqual(budgetCalls, 1, `${label} must reach the transport exactly once`);
  }

  // The fallback must not swallow budgets the caller actually asked for, in either direction:
  // an explicit 0 stays "disabled", a real 1 still binds at one, and 999 still stops at the 32
  // ceiling.
  await assert.rejects(load({
    url: "/explicit-zero-still-disables", cache: new Map(), inflight: new Map(), inflightLimit: 0,
    fetchJson: async () => ({}),
  }), /concurrency limit reached/, "folding the accidental zero must not fold the deliberate one");
  let heldCalls = 0;
  const heldFetch = async () => { heldCalls += 1; return { items: [heldCalls] }; };
  const heldInflight = new Map([["/other", Promise.resolve({ items: [] })]]);
  await assert.rejects(
    () => load({ url: "/tight", cache: new Map(), inflight: heldInflight, inflightLimit: 1,
                 active: { value: 1 }, fetchJson: heldFetch }),
    /concurrency limit reached/,
    "an explicit budget of 1 must still bind at one",
  );
  await assert.rejects(
    () => load({ url: "/ceiling", cache: new Map(), inflight: new Map(), inflightLimit: 999,
                 active: { value: 32 }, fetchJson: heldFetch }),
    /concurrency limit reached/,
    "the ceiling stays 32 no matter what the caller asked for",
  );
  assert.strictEqual(heldCalls, 0, "a rejected load must not reach the transport");

  // R102 --- a superseded request must also lose the right to publish. The
  // takeover case above only proves the admission slot moves. On a transport
  // that ignores `signal` the abandoned fetch still resolves, inside the same
  // generation, with an older body --- and epoch ownership cannot see that,
  // because the replacement inherits the epoch. Handover therefore voids the
  // abandoned request's cache write as well.
  const voidCache = new Map();
  const voidInflight = new Map();
  const voidActive = { value: 0 };
  const voidController = new AbortController();
  let releaseVoided;
  const voidedGate = new Promise(resolve => { releaseVoided = resolve; });
  const abandonedRequest = load({
    url: "/superseded",
    cache: voidCache,
    inflight: voidInflight,
    active: voidActive,
    inflightLimit: 2,
    // Deliberately ignores the abort signal: this is exactly the older WebView
    // the slot handover was written for, and its late body is the stale page.
    fetchJson: async () => { await voidedGate; return "dead response"; },
    signal: voidController.signal,
    epoch: 7,
    getEpoch: () => 7,
  });
  await Promise.resolve();
  voidController.abort();
  const replacementRequest = load({
    url: "/superseded",
    cache: voidCache,
    inflight: voidInflight,
    active: voidActive,
    inflightLimit: 2,
    fetchJson: async () => "fresh response",
    signal: new AbortController().signal,
    epoch: 7,
    getEpoch: () => 7,
  });
  assert.notStrictEqual(replacementRequest, abandonedRequest, "the takeover must own the URL now");
  assert.strictEqual(await replacementRequest, "fresh response");
  assert.strictEqual(voidCache.get("/superseded"), "fresh response", "the replacement owns the cache");
  releaseVoided();
  assert.strictEqual(await abandonedRequest, "dead response",
    "voiding the publish must not change what the abandoned caller still receives");
  assert.strictEqual(voidCache.get("/superseded"), "fresh response",
    "a voided response must never overwrite the fresher entry");
  assert.strictEqual(voidActive.value, 0, "the takeover must leave exactly one balanced slot");
  assert.strictEqual(voidCache.size, 1, "the void is scoped to the superseded URL");
  await load({
    url: "/after-void",
    cache: voidCache,
    inflight: voidInflight,
    inflightLimit: 2,
    fetchJson: async () => "later",
    epoch: 7,
    getEpoch: () => 7,
  });
  assert.strictEqual(voidCache.get("/after-void"), "later", "a later request must still publish");
  assert.strictEqual(voidCache.size, 2);

  // Structural pins for the same rule. The flag has to be declared before the
  // takeover branch that sets it, otherwise the handover hits the temporal dead
  // zone of its own `let`; the hook has to exist before the request is put into
  // the inflight map; and the publish gate must keep testing both guards.
  assert.ok(source.indexOf("if (!cacheWriteVoided && getEpoch() === epoch) cache.set(url, data);") >= 0,
    "the cache write must test the void flag and the epoch");
  assert.ok(source.indexOf("let cacheWriteVoided = false;") < source.indexOf("existing.__fnAudioVoidCacheWrite?.();"),
    "the void flag must be declared before the takeover can set it");
  assert.ok(source.indexOf("request.__fnAudioVoidCacheWrite =") < source.indexOf("inflight.set(url, request);"),
    "the void hook must exist before the request can be handed over");
  assert.strictEqual(([...source.matchAll(/cacheWriteVoided = true/g)]).length, 1,
    "the void setter must exist exactly once");
  console.log("Library response loader regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
