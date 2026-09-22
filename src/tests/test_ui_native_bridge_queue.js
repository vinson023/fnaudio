const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert").strict;

// R158 - the Android native bridge queue lane.  Deep reading this face turned up two
// defects, both pinned below with executable checks rather than text greps:
//   1. `nativeLoadQueue` wrote a queue signature into `state.nativeQueueSignature`
//      that nothing ever read, so every native queue load serialised the whole queue
//      twice and published a phantom piece of state.
//   2. The chunked-response table capped itself with a bare `32` unrelated to any
//      named constant, so it could drift from the in-flight request budget that
//      actually bounds it - and from the Android call pool behind that.
// The live signature lane (`nativeRemoteEnter`) is deliberately covered too, so the
// dead-store removal cannot be "fixed" by deleting the signature machinery as well.

const appPath = path.join(__dirname, "..", "app", "ui", "app.js");
const source = fs.readFileSync(appPath, "utf8");
const mainActivityPath = path.join(__dirname, "..", "..", "android-client", "app", "src",
  "main", "java", "com", "fnaudio", "client", "ui", "MainActivity.java");
const mainActivity = fs.readFileSync(mainActivityPath, "utf8");

const sliceStart = source.indexOf("function nativePlaybackAvailable() {");
const sliceEnd = source.indexOf("window.fnAudioNativeOnState =");
if (sliceStart < 0 || sliceEnd < 0 || sliceEnd <= sliceStart) {
  throw new Error("Native bridge slice anchors moved; update this test deliberately");
}
const bridgeSource = source.slice(sliceStart, sliceEnd);
// The slice spans nativePlaybackAvailable .. nativeQueueNeedsRestore: every named
// function of this face plus the two entry callbacks it publishes on window.
assert.match(bridgeSource, /function nativePlaybackAvailable\(\) \{/, "slice must start at the availability gate");
assert.match(bridgeSource, /function nativeQueueNeedsRestore\(\) \{/, "slice must reach the queue restore probe");
assert.match(bridgeSource, /const browserFetch = window\.fetch\.bind\(window\);/, "slice must include the fetch fallback binding");

class FakeHeaders {
  constructor(init) {
    this.entries = {};
    if (init && typeof init === "object") {
      for (const key of Object.keys(init)) this.entries[String(key).toLowerCase()] = String(init[key]);
    }
  }
  forEach(fn) {
    for (const key of Object.keys(this.entries)) fn(this.entries[key], key);
  }
}

// Products like `4 * 1024 * 1024` appear on both sides of the bridge; parse them as
// arithmetic rather than feeding Number() a string with stray spaces.
function product(text) {
  const parts = String(text).split("*").map(part => part.trim());
  assert.ok(parts.length && parts.every(part => /^\d+$/.test(part)), `cannot parse limit "${text}"`);
  return parts.reduce((total, part) => total * Number(part), 1);
}

function makeBridge() {
  const calls = [];
  return {
    calls,
    countOf: name => calls.filter(call => call.name === name).length,
    lastArgs: name => {
      for (let i = calls.length - 1; i >= 0; i -= 1) if (calls[i].name === name) return calls[i].args;
      return null;
    },
    spy: () => {
      const bridge = {};
      for (const method of ["requestJson", "cancelRequestJson", "setQueue", "play", "pause",
        "enterRemoteMode", "updateRemoteState", "exitRemoteMode"]) {
        bridge[method] = (...args) => { calls.push({ name: method, args }); };
      }
      bridge.isAvailable = () => true;
      return bridge;
    },
  };
}

function loadContext(bridge, rows) {
  const stringify = { count: 0 };
  const nativeJSON = JSON;
  const timers = { created: [], cleared: [], nextId: 1 };
  const state = {
    queue: rows,
    index: 0,
    playTarget: "local",
    playTargetName: "本机",
    repeat: "off",
    shuffle: false,
    mp3Transcode: false,
    transcodeCacheReady: false,
    remoteStatus: null,
    remoteGeneration: 0,
    remoteEngineEpoch: 0,
    nativeRemoteSignature: "",
    nativePlayback: { available: true, mediaId: "", queueIds: [], position: 0, duration: 0, playing: false, playbackState: 1 },
  };
  const sandbox = {
    JSON: {
      parse: nativeJSON.parse.bind(nativeJSON),
      stringify: (...args) => { stringify.count += 1; return nativeJSON.stringify(...args); },
    },
    Headers: FakeHeaders,
    URL,
    URLSearchParams,
    setTimeout: (fn, ms) => { const id = timers.nextId++; timers.created.push({ id, fn, ms }); return id; },
    clearTimeout: id => { timers.cleared.push(id); },
    state,
    window: {
      fetch: async () => { throw new Error("browser fetch must not be reached by these checks"); },
      location: { origin: "http://nas.local", href: "http://nas.local/app/ui/index.html" },
      FnAudioNative: bridge,
    },
    currentItem: () => state.queue[state.index],
    isRemoteTarget: () => state.playTarget !== "local",
    displayTrackTitle: item => String(item.title || ""),
    displayText: value => String(value || ""),
    coverUrl: () => "",
    absoluteAppUrl: value => new URL(String(value || ""), "http://nas.local/app/ui/index.html").href,
    playbackSeconds: value => (Number.isFinite(Number(value)) ? Number(value) : 0),
    seekDuration: () => 120,
    currentSeconds: () => 42,
    shouldTranscodeToMp3: item => Boolean(state.mp3Transcode && item && String(item.format || "").toUpperCase() !== "MP3"),
    shouldTranscodeDsdToWav: item => item?.is_dsd === true && !isRemoteTargetShim(state) && !shouldTranscodeToMp3Shim(state, item),
  };
  const context = vm.createContext(sandbox);
  vm.runInNewContext(`${bridgeSource}
this.nativeLoadQueue = nativeLoadQueue;
this.nativeQueueItems = nativeQueueItems;
this.nativeQueueSignature = nativeQueueSignature;
this.nativeRemoteEnter = nativeRemoteEnter;
this.nativeRemoteUpdate = nativeRemoteUpdate;
this.nativeQueueNeedsRestore = nativeQueueNeedsRestore;
this.clearNativeHttpRequest = clearNativeHttpRequest;
this.nativeHttpRequests = nativeHttpRequests;
this.nativeHttpResponseChunks = nativeHttpResponseChunks;
this.MAX_NATIVE_HTTP_REQUESTS = MAX_NATIVE_HTTP_REQUESTS;
this.MAX_NATIVE_HTTP_CHUNKS = MAX_NATIVE_HTTP_CHUNKS;
this.MAX_NATIVE_HTTP_RESPONSE_CHARS = MAX_NATIVE_HTTP_RESPONSE_CHARS;
`, context);
  return { context, sandbox, state, stringify, timers };
}
function isRemoteTargetShim(state) { return state.playTarget !== "local"; }
function shouldTranscodeToMp3Shim(state, item) {
  return Boolean(state.mp3Transcode && item && String(item.format || "").toUpperCase() !== "MP3");
}

const DEFAULT_ROWS = () => [
  { id: "t-1", url: "/a/one.mp3", title: "One", artist: "A1", album: "Al", duration: 120 },
  { id: "t-2", url: "/b/two.flac", title: "Two", artist: "A2", album: "Be", duration: "90.5" },
  { id: "t,3", url: "/c/three.mp3", title: "Three", artist: "A3", album: "C3", duration: NaN },
];

// ---------------------------------------------------------------------------
// 1. Loading the native queue must serialise the queue exactly once.
// ---------------------------------------------------------------------------
{
  const recorder = makeBridge();
  const { context, stringify } = loadContext(recorder.spy(), DEFAULT_ROWS());
  stringify.count = 0;
  assert.equal(context.nativeLoadQueue(true, 5, true), true, "forced native queue load must report success");
  assert.equal(stringify.count, 1,
    `nativeLoadQueue must serialise the queue once, saw ${stringify.count} JSON.stringify calls`);
  assert.equal(recorder.calls.length, 1, "the load must issue exactly one bridge command");
  assert.equal(recorder.calls[0].name, "setQueue");
}

// ---------------------------------------------------------------------------
// 2. The write-only field must not come back.
// ---------------------------------------------------------------------------
{
  const bridge = makeBridge().spy();
  const { context, state } = loadContext(bridge, DEFAULT_ROWS());
  context.nativeLoadQueue(true, 0, true);
  context.nativeLoadQueue(false, 3, true);
  context.nativeLoadQueue(true, 0, false);
  assert.equal("nativeQueueSignature" in state, false,
    "state.nativeQueueSignature was never read by anything and must not be recreated");
}

// ---------------------------------------------------------------------------
// 3. The signature lane that is genuinely live must survive, and must be
//    collision-safe: a delimiter-joined signature cannot be swapped back in.
// ---------------------------------------------------------------------------
{
  const recorder = makeBridge();
  const bridge = recorder.spy();
  const rows = [
    { id: "a,b", url: "/u1", title: "A", artist: "", album: "", duration: 10 },
    { id: "c", url: "/u2", title: "B", artist: "", album: "", duration: 10 },
  ];
  const { context, state } = loadContext(bridge, rows);
  state.playTarget = "render-1";
  assert.equal(context.nativeRemoteEnter(false), true, "remote enter must succeed on a remote target");
  assert.equal(recorder.countOf("enterRemoteMode"), 1);
  assert.ok(typeof state.nativeRemoteSignature === "string" && state.nativeRemoteSignature.length > 0,
    "the live remote signature must still be recorded");
  const firstSignature = state.nativeRemoteSignature;
  assert.ok(firstSignature.includes("a,b"), "the signature must carry the raw id, delimiter and all");
  // Same queue, same index, no force -> downgrade to a state update.
  assert.equal(context.nativeRemoteEnter(false), true);
  assert.equal(recorder.countOf("enterRemoteMode"), 1, "an unchanged queue must not re-enter remote mode");
  assert.equal(recorder.countOf("updateRemoteState"), 1);
  // Reorder the ids so a naive join(",") would read "a,b,c" both times.
  state.queue = [
    { id: "a", url: "/u1", title: "A", artist: "", album: "", duration: 10 },
    { id: "b,c", url: "/u2", title: "B", artist: "", album: "", duration: 10 },
  ];
  assert.equal(context.nativeRemoteEnter(false), true);
  assert.equal(recorder.countOf("enterRemoteMode"), 2,
    "a delimiter-colliding queue change must still re-enter remote mode");
  assert.notEqual(state.nativeRemoteSignature, firstSignature);
  // Growing the queue must re-enter, and force must always re-enter.
  assert.equal(context.nativeRemoteEnter(true), true);
  assert.equal(recorder.countOf("enterRemoteMode"), 3);
  // The behaviour above only proves the lane de-duplicates.  Pin the shape
  // directly: two different queues must never share a delimiter-joined
  // signature, which is the whole reason this lane is JSON rather than a join.
  assert.notEqual(
    context.nativeQueueSignature([{ id: "a,b", uri: "c" }]),
    context.nativeQueueSignature([{ id: "a", uri: "b,c" }]),
    "the signature must not collide where a comma-joined signature would");
}

// ---------------------------------------------------------------------------
// 4. setQueue payload semantics must be untouched by the dead-store removal.
// ---------------------------------------------------------------------------
{
  const recorder = makeBridge();
  const bridge = recorder.spy();
  const { context, state } = loadContext(bridge, DEFAULT_ROWS());
  state.index = 1;
  state.shuffle = true;
  state.repeat = "one";
  context.nativeLoadQueue(false, -7, true);
  const args = recorder.lastArgs("setQueue");
  assert.ok(args, "setQueue must still be issued");
  const rows = JSON.parse(args[0]);
  assert.deepEqual(rows.map(row => row.id), ["t-1", "t-2", "t,3"],
    "the queue handed to the bridge must keep full order and ids");
  assert.deepEqual(rows.map(row => row.uri), [
    "http://nas.local/a/one.mp3?transcode=original",
    "http://nas.local/b/two.flac?transcode=original",
    "http://nas.local/c/three.mp3?transcode=original",
  ], "every row must carry an absolute, per-item transcode url");
  assert.deepEqual(rows.map(row => row.durationMs), [120000, 90500, 0],
    "non-numeric durations must clamp to zero instead of poisoning the timeline");
  assert.equal(args[1], 1, "current index must be forwarded");
  assert.equal(args[2], 0, "a negative start offset must clamp to zero");
  assert.equal(args[3], false, "autoPlay must be forwarded as a boolean");
  assert.equal(args[4], "one");
  assert.equal(args[5], true);
  // An identical, already-loaded queue with no force must only resume playback.
  state.nativePlayback.mediaId = "t-2";
  state.nativePlayback.queueIds = ["t-1", "t-2", "t,3"];
  const before = recorder.countOf("setQueue");
  assert.equal(context.nativeLoadQueue(true, 0, false), true);
  assert.equal(recorder.countOf("setQueue"), before, "an identical queue must not be re-sent");
  assert.equal(recorder.countOf("play"), 1, "the identical-queue path must still start playback");
}

// ---------------------------------------------------------------------------
// 4b. A negative duration must clamp the same way a negative start does.
//     Without this case the `Math.max(0, ...)` guard around durationMs can be
//     deleted and every other row still looks correct.
// ---------------------------------------------------------------------------
{
  const recorder = makeBridge();
  const bridge = recorder.spy();
  const rows = [
    { id: "neg", url: "/n.mp3", title: "N", artist: "", album: "", duration: -42 },
    { id: "pos", url: "/p.mp3", title: "P", artist: "", album: "", duration: 7 },
  ];
  const { context } = loadContext(bridge, rows);
  context.nativeLoadQueue(true, 0, true);
  const sent = JSON.parse(recorder.lastArgs("setQueue")[0]);
  assert.deepEqual(sent.map(row => row.durationMs), [0, 7000],
    "negative durations must clamp to zero before reaching the Android timeline");
}

// ---------------------------------------------------------------------------
// 5. nativeQueueNeedsRestore must keep detecting a rehydrated-empty timeline.
// ---------------------------------------------------------------------------
{
  const bridge = makeBridge().spy();
  const { context, state } = loadContext(bridge, DEFAULT_ROWS());
  assert.equal(context.nativeQueueNeedsRestore(), true, "an empty native timeline must ask for a restore");
  state.nativePlayback.queueIds = ["t-1", "t-2", "t,3"];
  state.nativePlayback.mediaId = "t-1";
  assert.equal(context.nativeQueueNeedsRestore(), false, "a matching native queue must not restore");
  state.nativePlayback.queueIds = ["t-1", "t,3", "t-2"];
  assert.equal(context.nativeQueueNeedsRestore(), true, "queue order changes must still be detected");
  state.nativePlayback.queueIds = ["t-1", "t-2", "t,3"];
  state.nativePlayback.mediaId = "t-3";
  assert.equal(context.nativeQueueNeedsRestore(), true, "a stale current id must still be detected");
}

// ---------------------------------------------------------------------------
// 6. The chunk-transfer cap must be the named request budget, not a bare literal.
// ---------------------------------------------------------------------------
{
  assert.doesNotMatch(bridgeSource, /nativeHttpResponseChunks\.size\s*>=\s*\d/,
    "the chunk-transfer table must not be capped by a bare numeric literal");
  assert.match(bridgeSource, /nativeHttpResponseChunks\.size\s*>=\s*MAX_NATIVE_HTTP_REQUESTS/,
    "the chunk-transfer table must be capped by the named in-flight request budget");
}

// ---------------------------------------------------------------------------
// 7. The JS/Java HTTP contract limits must not drift apart.
// ---------------------------------------------------------------------------
function javaLimit(name) {
  const match = mainActivity.match(new RegExp(`private static final int ${name} = ([0-9 *]+);`));
  assert.ok(match, `Android no longer declares ${name}`);
  return product(match[1]);
}
function jsLimit(name) {
  const match = bridgeSource.match(new RegExp(`const ${name} = ([0-9 *]+);`));
  assert.ok(match, `app.js no longer declares ${name}`);
  return product(match[1]);
}
{
  assert.equal(jsLimit("MAX_NATIVE_HTTP_CHUNKS"), javaLimit("MAX_NATIVE_HTTP_RESPONSE_CHUNKS"),
    "JS must accept exactly as many response chunks as Android will ever send");
  assert.equal(jsLimit("MAX_NATIVE_HTTP_RESPONSE_CHARS"), javaLimit("MAX_NATIVE_HTTP_SERIALIZED_RESPONSE_CHARS"),
    "JS reassembly budget must equal the Android serialized-response budget");
  assert.equal(jsLimit("MAX_NATIVE_HTTP_REQUESTS"), javaLimit("MAX_NATIVE_HTTP_CALLS"),
    "the JS in-flight budget must equal the Android native call pool");
  const bridge = makeBridge().spy();
  const { context } = loadContext(bridge, DEFAULT_ROWS());
  assert.equal(context.MAX_NATIVE_HTTP_REQUESTS, javaLimit("MAX_NATIVE_HTTP_CALLS"),
    "the budget the transfer table now shares must be the same value read off the bridge");
}

// ---------------------------------------------------------------------------
// 8. Cancelling a request whose response already arrived is a proven native no-op.
//    Pinned as the evidence behind the R158 falsification of that candidate.
// ---------------------------------------------------------------------------
{
  assert.match(bridgeSource, /try \{ window\.FnAudioNative\?\.cancelRequestJson\(requestId\); \} catch/,
    "clearNativeHttpRequest must keep telling Android to drop the slot");
  assert.match(mainActivity, /public void onResponse\(@NonNull Call call, @NonNull Response response\) \{\s*if \(!nativeHttpCalls\.remove\(safeRequestId, call\)\)/,
    "Android deregisters the call before delivering the response, so a late cancel finds nothing to cancel");
  assert.match(mainActivity, /Call call = nativeHttpCalls\.remove\(safeRequestId\);\s*if \(call != null\) call\.cancel\(\);/,
    "cancelRequestJson must stay a no-op for an unknown request id");
}

// ---------------------------------------------------------------------------
// 9. Transfer-table capacity behaviour: full rejects new ids, spares live ones.
// ---------------------------------------------------------------------------
{
  const bridge = makeBridge().spy();
  const { context, timers } = loadContext(bridge, DEFAULT_ROWS());
  const onChunk = context.window.fnAudioNativeOnHttpChunk;
  assert.equal(typeof onChunk, "function", "the chunk callback must be published on window");
  const cap = context.MAX_NATIVE_HTTP_REQUESTS;
  for (let i = 0; i < cap; i += 1) onChunk(`tr-${i}`, 0, 2, "x");
  assert.equal(context.nativeHttpResponseChunks.size, cap, "the table must fill to exactly its cap");
  onChunk("overflow", 0, 2, "x");
  assert.equal(context.nativeHttpResponseChunks.size, cap, "a rejected transfer must not evict a live one");
  assert.equal(timers.created.length, cap, "a rejected transfer must not arm another watchdog");
  assert.deepEqual([...new Set(timers.created.map(timer => timer.ms))], [60000],
    "every transfer must arm the 60s reassembly watchdog");
  // Completing one live transfer frees a slot.
  onChunk("tr-0", 1, 2, "y");
  assert.equal(context.nativeHttpResponseChunks.size, cap - 1);
  assert.ok(timers.cleared.includes(1), "a completed transfer must clear its watchdog");
  onChunk("overflow", 0, 2, "x");
  assert.equal(context.nativeHttpResponseChunks.size, cap, "a freed slot must be reusable");
  // Malformed metadata must never allocate.
  for (const timer of timers.created.slice()) { timers.cleared.push(timer.id); }
  context.nativeHttpResponseChunks.clear();
  timers.created.length = 0;
  onChunk("bad", -1, 2, "x");
  onChunk("bad", 0, 0, "x");
  onChunk("", 0, 2, "x");
  onChunk("bad", 0, 300, "x");
  onChunk("bad", 0, 2, "x".repeat(256 * 1024 + 1));
  assert.equal(context.nativeHttpResponseChunks.size, 0, "invalid chunk metadata must never allocate");
  assert.equal(timers.created.length, 0, "invalid chunk metadata must never arm a watchdog");
}

// ---------------------------------------------------------------------------
// 10. End to end: a reassembled chunked response resolves its pending request.
// ---------------------------------------------------------------------------
// This block is async because it awaits the response body helpers, so it runs inside
// an async tail; a rejection there must still fail the file, hence the exitCode.
(async () => {
  const recorder = makeBridge();
  const bridge = recorder.spy();
  const { context } = loadContext(bridge, DEFAULT_ROWS());
  let settled = null;
  context.nativeHttpRequests.set("req-9", {
    resolve: value => { settled = { ok: true, value }; },
    reject: error => { settled = { ok: false, error }; },
    timer: 0,
    signal: null,
    abortHandler: null,
  });
  const onChunk = context.window.fnAudioNativeOnHttpChunk;
  const payload = JSON.stringify({ requestId: "req-9", status: 200, statusText: "OK",
    url: "http://nas.local/api/x", headers: { "content-type": "application/json" }, body: '{"ert":1}' });
  assert.equal(payload.length > 10, true);
  onChunk("req-9", 1, 2, payload.slice(1));
  onChunk("req-9", 0, 2, payload.slice(0, 1));
  assert.ok(settled, "a fully reassembled transfer must settle the pending request");
  assert.equal(settled.ok, true);
  assert.equal(settled.value.status, 200);
  assert.equal(settled.value.ok, true);
  assert.equal(settled.value.headers.get ? settled.value.headers.get("content-type") : "application/json", "application/json");
  assert.equal(await settled.value.text(), '{"ert":1}');
  assert.equal(recorder.countOf("cancelRequestJson"), 1,
    "the response path still releases the Android slot; check 8 proves that is a no-op");
  assert.equal(context.nativeHttpRequests.size, 0, "the request table must be emptied by delivery");

  console.log("Native bridge queue and HTTP transfer regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
