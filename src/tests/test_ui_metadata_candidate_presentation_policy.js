const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/metadata_candidate_presentation_policy.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioMetadataCandidatePresentationPolicy;
assert.equal(typeof policy.selectDisplayCandidate, "function");
assert.equal(typeof policy.selectDisplayArtwork, "function");
assert.equal(typeof policy.confidencePercent, "function");
const sparseBest = { title: "Song", artist: "Artist", confidence: 0.99 };
const complete = { title: "Song", artist: "Artist", album: "Album", image_url: "https://example.test/a.jpg", confidence: 0.72 };
assert.equal(policy.selectDisplayCandidate(sparseBest, [complete]), complete, "display should prefer a complete cover/album candidate over sparse best");
assert.equal(policy.selectDisplayCandidate({}, []), null, "empty projections should remain distinguishable from a candidate");
assert.equal(policy.selectDisplayCandidate(null, [{ title: "Song", confidence: "bad" }]).title, "Song");
const hostile = new Proxy({ title: "Hostile" }, { get() { throw new Error("unexpected coercion"); } });
assert.doesNotThrow(() => policy.selectDisplayCandidate(hostile, [complete]), "hostile provider fields must not break display selection");
assert.equal(policy.selectDisplayCandidate({ title: "Low", confidence: "0.7" }, [{ title: "High", confidence: "0.8" }]).title, "High");
const hostileKeys = new Proxy({ title: "Hostile keys" }, { ownKeys() { throw new Error("unexpected ownKeys"); } });
assert.doesNotThrow(() => policy.selectDisplayCandidate(hostileKeys, [complete]));
assert.equal(policy.selectDisplayCandidate({}, [{ confidence: 0 }]), null, "Candidates without display data must remain absent");
assert.equal(policy.selectDisplayArtwork({ title: "Local", image_url: "" }, [{ title: "Remote", image_url: "https://example.test/remote.jpg" }]), "https://example.test/remote.jpg", "Artwork should be projected independently from the selected metadata candidate");
assert.equal(policy.selectDisplayArtwork({}, [], "https://example.test/fallback.jpg"), "https://example.test/fallback.jpg");
assert.equal(policy.confidencePercent(Infinity), "0%", "non-finite confidence must not leak into the UI");
assert.equal(policy.confidencePercent(2), "100%", "confidence display must be capped at 100%");
assert.equal(policy.confidencePercent("0.375"), "38%");
console.log("Metadata candidate presentation policy checks passed.");

const NL = String.fromCharCode(10);

// ---------------------------------------------------------------------------
// The pending branch of the real showTrackMetadataCandidate(), taken from app.js
// and executed here.  The densest face of the app.js deep read found that the
// poll budget METADATA_CANDIDATE_MAX_POLLS is bounded on purpose, but the
// sentence promising an automatic refresh used to be written *before* that budget
// was consulted: once the last unanswered poll lands, the dialog keeps asserting
// that a display update is still coming while nothing can ever schedule one again,
// and it offers no way out.  That is the residual-state family R99 closed on the
// transport row (:58), on a polling face instead of the投送 one.
// ---------------------------------------------------------------------------
const app = fs.readFileSync("app/ui/app.js", "utf8");
const index = fs.readFileSync("app/ui/index.html", "utf8");

assert.match(index, /id="metadataCandidateDialog"/, "metadata completion must have its own dialog");
assert.match(index, /id="metadataCandidateSearchForm"/, "manual metadata search must have a dedicated form");
assert.match(index, /id="metadataCandidateSearchInput"/, "manual search needs a visible query input");
assert.match(index, /id="metadataCandidateSearchResults"/, "manual search needs a result container");
assert.match(app, /function openMetadataCandidateDialog\(/, "candidate flow must open the dedicated dialog");
assert.match(app, /api\/metadata\/track\/search/, "manual search must use the track-scoped search endpoint");
assert.match(app, /function renderMetadataCandidateSearchResults\(/, "manual results need a dedicated renderer");

function appFunctionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the pending-budget regression`);
  return match[0];
}

const MAX_POLLS_SOURCE = app.match(/^const METADATA_CANDIDATE_MAX_POLLS = [^\n]+/m);
assert.ok(MAX_POLLS_SOURCE, "the poll budget must stay a top-level const");
const MAX_POLLS = Number(/=\s*([0-9]+)/.exec(MAX_POLLS_SOURCE[0])[1]);
assert.equal(MAX_POLLS, 12, "the ruled budget is twelve follow-up polls");

function candidateHarness(respond) {
  // Terminal answers are scripted per case; the default stays the "provider never
  // answers" fixture that the poll-budget sections above rely on.
  const answer = respond || ((url) => ({ ok: true, status: "pending" }));
  const writes = [];
  const timers = [];
  const requests = [];
  const retryButton = { disabled: false, onclick: null };
  const nodes = {
    trackActionTitle: { textContent: "" },
    trackActionDialog: { open: true, showModal() { this.open = true; } },
    trackActionList: {
      _text: "",
      _html: "",
      get textContent() { return this._text; },
      set textContent(value) { this._text = String(value); writes.push(["text", String(value)]); },
      get innerHTML() { return this._html; },
      set innerHTML(value) { this._html = String(value); writes.push(["html", String(value)]); },
      querySelector(selector) { return selector === "[data-retry-track-metadata]" ? retryButton : null; },
    },
  };
  const state = {
    actionTrackId: "t42",
    metadataCandidateController: null,
    metadataCandidatePollTimer: 0,
    metadataCandidatePollAttempts: 0,
    metadataCandidateRequestToken: 0,
  };
  const context = {
    state,
    nodes,
    String, Number, Boolean, Array, Object, JSON, Promise, Error, encodeURIComponent,
    AbortController: class { constructor() { this.signal = { aborted: false }; } abort() { this.signal.aborted = true; } },
    setTimeout: (callback, delay) => { timers.push({ callback, delay }); return timers.length; },
    clearTimeout: id => { const entry = timers[id - 1]; if (entry) { entry.callback = null; entry.cleared = true; } },
    itemById: id => (id === "t42" ? { id: "t42", title: "Sample" } : null),
    unwrapMetadataResponsePayload: payload => payload,
    // The provider never answers: that is the only production way to reach the end of
    // this budget, so the fixture says "pending" for every request it is given.
    fetchMetadataRequest: async url => {
      requests.push(url);
      return { response: { ok: true }, data: { ok: true, ...answer(url) } };
    },
    $: id => nodes[id],
    escapeHtml: value => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"),
    __policy: policy,
  };
  vm.createContext(context);
  vm.runInContext([
    "globalThis.fnAudioMetadataCandidatePresentationPolicy = __policy;",
    MAX_POLLS_SOURCE[0],
    appFunctionSource("renderMetadataCandidateRetry"),
    appFunctionSource("showTrackMetadataCandidate"),
    "globalThis.__target = showTrackMetadataCandidate;",
  ].join(NL), context);
  return {
    context, state, writes, timers, requests, retryButton,
    show: (...args) => context.__target(...args),
    lastWrite: () => writes[writes.length - 1],
    promised: () => writes.some(([, value]) => value.includes("完成后将自动显示")),
    nextTimer: () => timers.slice().reverse().find(entry => entry.callback) || null,
  };
}

async function settle() {
  for (let index = 0; index < 30; index += 1) await Promise.resolve();
}

(async () => {
  // 1. Inside its budget the dialog keeps its word: it promises the automatic refresh
  //    *and* really arms the follow-up, and it must not clutter the list with a manual
  //    action the user does not need yet.
  const polling = candidateHarness();
  await polling.show("t42");
  await settle();
  assert.deepEqual(polling.requests, ["api/metadata/track?track_id=t42"], "the first lookup is unprompted");
  assert.equal(polling.state.metadataCandidatePollAttempts, 1, "the poll that was armed costs one attempt");
  assert.equal(polling.timers.length, 1, "a pending answer inside the budget schedules exactly one follow-up");
  assert.equal(polling.timers[0].delay, 1200, "on the shared 1.2s poll cadence");
  assert.ok(polling.promised(), "the auto-display promise belongs to the state that will auto-display");
  assert.equal(polling.writes.filter(([kind]) => kind === "html").length, 0,
    "no retry markup while the automatic path is still live");
  assert.equal(polling.retryButton.onclick, null, "and no manual handler bound yet");

  // 2. Run the real loop to exhaustion rather than inventing a state.  The budget is
  //    only reachable through continuation calls that carry the dialog request token -
  //    a tokenless call resets it - so this walks the shipped code: first lookup, then
  //    exactly MAX_POLLS follow-ups, and the last one has to change its story.
  const drained = candidateHarness();
  await drained.show("t42");
  await settle();
  const session = drained.state.metadataCandidateRequestToken;
  let fired = 0;
  for (;;) {
    const slot = drained.nextTimer();
    if (!slot) break;
    const armNextPoll = slot.callback;
    slot.callback = null;
    armNextPoll();
    await settle();
    fired += 1;
    if (fired > MAX_POLLS * 3) break;
  }
  assert.equal(fired, MAX_POLLS, `the whole ${MAX_POLLS}-poll budget is really spent`);
  assert.equal(drained.state.metadataCandidatePollAttempts, MAX_POLLS, "attempts are counted, never re-armed");
  assert.equal(drained.requests.length, MAX_POLLS + 1, "one lookup per poll plus the first");
  assert.equal(drained.state.metadataCandidateRequestToken, session, "all of it inside one dialog session");
  assert.ok(drained.writes.slice(0, -1).some(([, value]) => value.includes("完成后将自动显示")),
    "the budget did run through the promising state first - the last write is a change, not an absence");
  assert.ok(!drained.writes.slice(-1).some(([, value]) => value.includes("完成后将自动显示")),
    "the exhausted state must not claim an automatic refresh that can never arrive");
  // Writing the promise first and overwriting it a moment later would still leave
  // one sentence too many on the record: the promise belongs to the branch that
  // keeps it, so its write count has to equal the number of armed follow-ups.
  assert.equal(drained.writes.filter(([, value]) => value.includes("完成后将自动显示")).length, MAX_POLLS,
    "the promise is written once per poll that really arms a follow-up, and never on the last");
  const finalWrite = drained.lastWrite();
  assert.equal(finalWrite[0], "html", "the exhausted state renders the manual retry affordance");
  assert.match(finalWrite[1], /data-retry-track-metadata="t42"/, "pointing at the track being looked up");
  assert.equal(typeof drained.retryButton.onclick, "function", "and the retry button is actually wired");
  assert.equal(drained.nextTimer(), null, "nothing is left armed behind it");

  // 3. The manual exit must be a real exit: it refills the budget and gets the automatic
  //    path back instead of replaying the same exhausted answer.
  const lookedUpBefore = drained.requests.length;
  await drained.retryButton.onclick();
  await settle();
  assert.equal(drained.requests.length, lookedUpBefore + 1, "the click issues one fresh lookup");
  assert.equal(drained.requests[drained.requests.length - 1], "api/metadata/track?track_id=t42&retry=1",
    "as a deliberate retry, so a cached negative answer cannot be replayed");
  assert.equal(drained.state.metadataCandidateRequestToken, session + 1, "under a new request token");
  assert.ok(drained.promised(), "the automatic promise is legitimate again now that a poll is armed");
  assert.notEqual(drained.nextTimer(), null, "and the follow-up really is armed again");

  // 4. Both retry states share one renderer.  Two copies of this markup are what let the
  //    transport-row residual numbers drift apart before R99 closed them.
  assert.doesNotMatch(appFunctionSource("showTrackMetadataCandidate"), /data-retry-track-metadata/,
    "the candidate dialog must not carry the retry markup inline any more");
  assert.equal((app.match(/renderMetadataCandidateRetry\(/g) || []).length, 3,
    "one definition plus exactly the two retry states that call it");
  assert.equal((app.match(/data-retry-track-metadata/g) || []).length, 2,
    "exactly one template plus one selector for the metadata retry action");
  assert.equal((app.match(/重新查询此歌曲/g) || []).length, 1,
    "and one copy of its label, so the two exits cannot diverge");
})().then(() => {
  console.log("Metadata candidate poll budget checks passed.");
}).catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});

// ---------------------------------------------------------------------------
// The other credential this face produces: the password on an external share
// link.  The old code folded a whole byte onto a 57-character alphabet with
// `%`, and 256 is not a multiple of 57: the window 0..227 covers the alphabet
// exactly four times, and the 28 bytes left over land on the first 28
// characters a fifth time.  A share password is an outward-facing credential,
// so the draw is measured against a scripted generator: bytes at or beyond
// 228 have to be refused outright rather than folded back onto the alphabet.
// ---------------------------------------------------------------------------
const SHARE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
const SHARE_ALPHABET_LENGTH = 57;
// Math.floor(256 / 57) * 57: the widest prefix of the byte range that divides
// evenly into the alphabet.  Anything from here up must be discarded.
const UNBIASED_BYTE_LIMIT = 228;

function passwordHarness(script) {
  const draws = [];
  let cursor = 0;
  const context = {
    draws,
    String, Number, Math, Array, Error,
    Uint8Array: class {
      constructor(length) {
        const cells = new Array(length).fill(0);
        return new Proxy(cells, {
          get(target, key) {
            if (key === "byteLength") return target.length;
            return Reflect.get(target, key);
          },
        });
      }
    },
    crypto: {
      getRandomValues(target) {
        draws.push(target.length);
        for (let index = 0; index < target.length; index += 1) {
          target[index] = script[Math.min(cursor, script.length - 1)];
          cursor += 1;
        }
        return target;
      },
    },
  };
  vm.createContext(context);
  vm.runInContext([
    appFunctionSource("generateExternalSharePassword"),
    "globalThis.__target = generateExternalSharePassword;",
  ].join(NL), context);
  return { context, generate: () => context.__target(), draws };
}

// The oracle restates the specification rather than the implementation: walk
// the scripted bytes in order, keep only the ones below the bound, and map
// each survivor onto the alphabet.
function expectedPassword(script) {
  const characters = [];
  for (let index = 0; index < script.length && characters.length < 10; index += 1) {
    if (script[index] < UNBIASED_BYTE_LIMIT) {
      characters.push(SHARE_ALPHABET[script[index] % SHARE_ALPHABET_LENGTH]);
    }
  }
  assert.equal(characters.length, 10, "fixture bug: this script cannot fill ten characters");
  return characters.join("");
}

(async () => {
  // 1. Positive control: a buffer that is entirely inside the unbiased range
  //    costs one draw and maps one-for-one, so fixture and alphabet line up.
  const inRange = [0, 1, 2, 3, 4, 5, 6, 7, 8, 54];
  const clean = passwordHarness(inRange);
  assert.equal(clean.generate(), expectedPassword(inRange),
    "an in-range byte must select its own character");
  assert.equal(clean.draws.length, 1, "and a full buffer of accepted bytes costs exactly one draw");

  // 2. The biased tail must be refused, not folded.  Bytes 228..255 are what
  //    256 % 57 leaves over; here they are spread across the buffer so that
  //    completing the password costs a second read.
  const biased = [228, 0, 255, 1, 227, 2, 250, 3, 229, 4, 5, 6, 7, 8, 9, 240, 10, 11, 12, 13];
  const produced = passwordHarness(biased).generate();
  assert.equal(produced, expectedPassword(biased),
    "every rejected byte has to be replaced by a further draw, in order");
  const costly = passwordHarness(biased);
  costly.generate();
  assert.ok(costly.draws.length > 1, "which costs more than the single naive read");

  // 3. Nothing may leak outside the alphabet, whatever the generator returns
  //    -- including a whole first buffer that sits in the rejected tail.
  for (const script of [
    [56, 56, 56, 56, 56, 56, 56, 56, 56, 56],
    [255, 254, 253, 252, 251, 250, 249, 248, 247, 246, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  ]) {
    const probe = passwordHarness(script);
    const value = probe.generate();
    assert.equal(value.length, 10);
    assert.ok([...value].every(character => SHARE_ALPHABET.includes(character)),
      "the password stays inside its own alphabet: " + value);
  }

  // 3b. The buffer is read ten bytes at a time, so a batch can end with nine
  //     accepted bytes and a rejected one.  Only an outer loop that keeps going
  //     until ten characters are really in hand survives that; one that stops at
  //     "nine or more" hands back a short password.
  const straddle = [0, 1, 2, 3, 4, 5, 6, 7, 8, 255, 254, 9, 10, 11, 12, 13, 14, 15, 16, 17];
  const crossed = passwordHarness(straddle);
  assert.equal(crossed.generate(), expectedPassword(straddle),
    "a first buffer that fills only nine characters has to be followed up");
  assert.equal(crossed.draws.length, 2, "which is measurable as a second read");

  // 4. Wiring: the bound the measurement above relies on is stated in the
  //    source in terms of the byte range, not as a guessed magic number.
  assert.match(appFunctionSource("generateExternalSharePassword"), /256/,
    "the rejection bound has to be derived from the byte range");
})().then(() => {
  console.log("External share password sampling checks passed.");
}).catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});

// ---------------------------------------------------------------------------
// 3. The third defect this face produced: a finished lookup that returns
//    nothing usable used to end in a plain sentence with no way out.  The two
//    server fields that describe such an answer come from different tables -
//    `status` is the cached match projection (server 3372/3667) while
//    `last_error` is whatever the job row still remembers (server 3684, and the
//    worker exception path at 3185 rewrites only the job row) - so a genuine
//    "no match" can arrive together with a leftover provider error.  Texting the
//    error first swallowed the "no match" copy *and* dropped the retry button,
//    which is the same dead-end family as the exhausted poll above.
// ---------------------------------------------------------------------------
function terminalHarness(data) {
  return candidateHarness(() => data);
}

(async () => {
  const cases = [
    {
      name: "no match carrying a residual provider error",
      data: { status: "no_match", last_error: "上一轮检索超时" },
      copy: ["当前数据源没有找到可信匹配", "上一轮检索超时"],
    },
    {
      name: "terminal failure",
      data: { status: "failed", last_error: "数据源暂不可用" },
      copy: ["数据源暂不可用"],
    },
    {
      name: "service switched off",
      data: { status: "unavailable", message: "后台元数据服务没有启动" },
      copy: ["后台元数据服务没有启动"],
    },
    {
      name: "a bare negative answer",
      data: {},
      copy: ["没有找到可信的元数据候选"],
    },
  ];
  for (const testCase of cases) {
    const probe = terminalHarness(testCase.data);
    await probe.show("t42");
    await settle();
    const final = probe.lastWrite();
    assert.equal(final[0], "html", `${testCase.name} must render the manual exit, not a dead end: ${JSON.stringify(final)}`);
    assert.match(final[1], /data-retry-track-metadata="t42"/, `${testCase.name} keeps the retry action`);
    for (const fragment of testCase.copy) {
      assert.ok(final[1].includes(fragment), `${testCase.name} keeps its own wording: ${fragment}`);
    }
    assert.equal(typeof probe.retryButton.onclick, "function", `${testCase.name} binds the retry action`);
    assert.equal(probe.nextTimer(), null, `${testCase.name} leaves nothing armed behind`);
    assert.ok(!probe.promised(), `${testCase.name} must not promise a refresh that is not coming`);
  }

  // Wiring: within the "no usable candidate" block, exactly one plain-text write
  // may survive - the automatic-display promise that is guarded by the poll
  // budget.  Anything else reintroduces a terminal state without an exit.
  const block = app.match(/^ {4}if \(!best\.title\) \{[\s\S]*?\n {4}\}/m);
  assert.ok(block, "the no-candidate block must stay extractable");
  assert.equal((block[0].match(/list\.textContent =/g) || []).length, 1,
    "the only unconditional sentence left inside it is the budgeted auto-display promise");
  assert.equal((block[0].match(/renderMetadataCandidateRetry\(/g) || []).length, 2,
    "the exhausted poll and the terminal answers share one renderer");
})().then(() => {
  console.log("Metadata candidate terminal negative answers checks passed.");
}).catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
