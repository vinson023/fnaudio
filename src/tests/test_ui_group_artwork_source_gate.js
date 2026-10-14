const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert").strict;

// R160 - the "remote session cleanup / host media session / queue+group render /
// column widths" face of app.js (source lines 2177-3022 at intake, 52 named
// functions).
//
// Deep reading this face overturned a prior round's conclusion and fixed one real
// defect:
//
//   `prepareLocalGroupArtwork()` attached the local-vs-online fallback handlers to
//   every `.group-icon img` / `.album-detail-cover img` right after the list HTML
//   was committed (render(): `loadGroupArtwork(); hydrateVisibleTrackCovers();`).
//   Group covers ship as deferred markup - `<img data-cover-src="...">` with no
//   `src` - and only receive their URL later, synchronously, from the shared
//   scheduler.  But the guard opened with `if (image.complete) return verify()`.
//   Per the WHATWG HTML spec (confirmed in headless Chromium) a src-less <img>
//   reports `complete === true` with `naturalWidth === 0`.  So verify() ran on
//   every freshly rendered group cover, read `naturalWidth > 1` as false, and
//   called failed() - which does `image.remove()`.  The local cover was deleted
//   one frame before hydrateVisibleTrackCovers() could ever start it: local-only
//   groups lost their artwork to the generic glyph, and local+online groups had
//   the local cover silently replaced by the network cover.
//
//   CHANGELOG_AI.md line 19 (R151) recorded this as 证伪: "`prepareLocalGroupArtwork`
//   的帧回调校验不构成缺陷（`load`/`error` 监听器仍在位）".  That reasoning only
//   covers the *asynchronous* path.  On the src-less deferred image the synchronous
//   branch fires first and the `load`/`error` listeners are never registered, so
//   "监听器仍在位" is false exactly where it matters.  The fix gates on "does this
//   image have a source yet" - the same `hasAttribute("src")` / `coverLoadedSrc`
//   marker the scheduler itself uses - rather than on the misleading `complete`.
//
// Each numbered case below is a discriminator with a named mutation target; see
// fnAudio-R160 review notes for the mutation matrix (V1..V8).

const uiDir = path.join(__dirname, "..", "app", "ui");
const source = fs.readFileSync(path.join(uiDir, "app.js"), "utf8");
const schedulerSource = fs.readFileSync(path.join(uiDir, "cover_load_scheduler.js"), "utf8");

function countOf(haystack, needle) {
  return haystack.split(needle).length - 1;
}

// --- 1. the face stays anchored where this review read it --------------------
const faceStart = source.indexOf("function stopRemoteOnUnload(");
const canSort = source.indexOf("function canSortTrackColumn(");
assert.ok(canSort > 0, "canSortTrackColumn disappeared; re-read the face before editing this test");
const faceEnd = source.indexOf("\nfunction ", canSort + 10);
assert.ok(faceStart >= 0 && faceEnd > faceStart, "group artwork face anchors moved; re-read the face before editing this test");
const face = source.slice(faceStart, faceEnd);

// --- 2. execute the REAL prepareLocalGroupArtwork against a spec-faithful fake --
//
// The shipped function reads only the DOM contract (hasAttribute/dataset/
// complete/naturalWidth/isConnected/classList/removeAttribute/querySelector/
// remove/addEventListener) and the realm globals requestAnimationFrame and
// applyGroupArtwork.  evaluate() returns the post-call state AND the captured
// rAF callback, so a case can drive the deferred path the way the real scheduler
// does: bind first, assign src later, then let rAF verify run.
function evaluate(makeOpts) {
  const start = source.indexOf("function prepareLocalGroupArtwork(");
  const finish = source.indexOf("\nfunction loadGroupArtwork(", start);
  assert.ok(start >= 0 && finish > start, "prepareLocalGroupArtwork is not terminated where this test expects");
  const body = source.slice(start, finish);

  const attributes = Object.assign({}, makeOpts.attributes || {});
  const hasAttrNames = Object.assign({}, makeOpts.hasAttributes || {});
  const img = {
    complete: !!makeOpts.complete,
    naturalWidth: makeOpts.naturalWidth || 0,
    naturalHeight: makeOpts.naturalWidth || 0,
    isConnected: makeOpts.isConnected !== false,
    dataset: Object.assign({}, makeOpts.dataset || {}),
    listeners: {},
    removed: false,
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(attributes, name) ? attributes[name] : null; },
    hasAttribute(name) { return Object.prototype.hasOwnProperty.call(hasAttrNames, name) || Object.prototype.hasOwnProperty.call(attributes, name); },
    setAttribute(name, value) { attributes[name] = String(value); },
    remove() { this.removed = true; this.isConnected = false; },
    addEventListener(type, cb) { (this.listeners[type] = this.listeners[type] || []).push(cb); },
  };
  const classSet = new Set(makeOpts.classes || []);
  const nodeAttributes = Object.assign({}, makeOpts.nodeAttributes || {});
  const removedNodeAttrs = [];
  const node = {
    classList: {
      add(name) { classSet.add(name); },
      remove(name) { classSet.delete(name); },
      contains(name) { return classSet.has(name); },
    },
    dataset: Object.assign({}, makeOpts.nodeDataset || {}),
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(nodeAttributes, name) ? nodeAttributes[name] : null; },
    removeAttribute(name) { removedNodeAttrs.push(name); delete nodeAttributes[name]; },
    querySelector(sel) { return sel === "img" ? img : null; },
  };
  const applied = { value: null };
  const raf = { count: 0, cb: null };
  const sandbox = {
    requestAnimationFrame: (cb) => { raf.count += 1; raf.cb = cb; },
    applyGroupArtwork: (_n, url) => { applied.value = url; },
    document: { createElement: () => ({ setAttribute() {}, style: {}, dataset: {} }) },
  };
  sandbox.__node = node;
  vm.createContext(sandbox);
  vm.runInContext(body + "\nprepareLocalGroupArtwork(__node);", sandbox);
  return {
    img, classSet, applied: () => applied.value, raf,
    removedNodeAttrs,
    imgRemoved: img.removed,
    hasCover: classSet.has("has-cover"),
    appliedOnline: applied.value,
    rafScheduled: raf.count,
    listeners: Object.keys(img.listeners).sort(),
  };
}


// --- 3. discriminator V1 (fix clause: synchronous guard) ---------------------
// A src-less deferred local-only cover must NOT be judged on the bare complete
// flag. Reverting `if (hasArtworkSource() && image.complete)` to the shipped
// `if (image.complete)` reproduces R151's misjudgement and fails here.
const deferred = evaluate({
  complete: true, naturalWidth: 0,
  attributes: { "data-cover-src": "/cover/1?size=160" },
  hasAttributes: {},                          // note: NO "src"
  nodeDataset: {},
  classes: [],
});
assert.equal(deferred.imgRemoved, false, "V1: a src-less deferred cover must NOT be judged failed (it has not started)");
assert.deepEqual(deferred.listeners, ["error", "load"], "V1: a deferred cover must register the load/error fallback listeners");
assert.equal(deferred.appliedOnline, null, "V1: a deferred local-only cover must not be replaced by any online image");

// --- 4. discriminator: deferred local+online keeps the local cover's turn ------
const deferredBoth = evaluate({
  complete: true, naturalWidth: 0,
  attributes: { "data-cover-src": "/cover/2?size=160" },
  hasAttributes: {},
  nodeDataset: { metadataImage: "https://meta/album.jpg" },
  classes: [],
});
assert.equal(deferredBoth.imgRemoved, false, "the local cover must stay while it is still un-started");
assert.equal(deferredBoth.appliedOnline, null, "the online fallback must not fire before the local load is attempted");
assert.deepEqual(deferredBoth.listeners, ["error", "load"], "fallback must be wired through real load/error events");

// --- 5. discriminator V5 (fix clause: hasArtworkSource src half) -------------
// A *started* (has src), complete, zero-intrinsic-size cover is a real failure and
// must fall back to online synchronously (no listeners left dangling). Dropping
// the hasAttribute("src") test from the gate would skip the sync path and leave
// listeners registered -> fails on listeners == [].
const broken = evaluate({
  complete: true, naturalWidth: 0,
  attributes: { src: "/cover/3?size=160" },
  hasAttributes: { src: true },
  nodeDataset: { metadataImage: "https://meta/album.jpg" },
  classes: ["has-cover"],
});
assert.equal(broken.imgRemoved, true, "V5: a started cover reporting zero intrinsic size is a real failure and is dropped");
assert.equal(broken.hasCover, false, "V5: the failed cover must clear has-cover so the glyph shows");
assert.equal(broken.appliedOnline, "https://meta/album.jpg", "V5: a failed local cover must fall back to the online image");
assert.deepEqual(broken.listeners, [], "V5: the synchronous failure path must not also attach listeners");

// --- 6. discriminator: started + loaded cover is kept synchronously -----------
const loaded = evaluate({
  complete: true, naturalWidth: 160,
  attributes: { src: "/cover/4?size=160" },
  hasAttributes: { src: true },
  nodeDataset: { metadataImage: "https://meta/album.jpg" },
  classes: ["has-cover"],
});
assert.equal(loaded.imgRemoved, false, "a successfully loaded local cover is kept");
assert.equal(loaded.hasCover, true, "a loaded cover keeps has-cover");
assert.equal(loaded.appliedOnline, null, "a loaded cover must not be swapped for the online image");
assert.ok(loaded.removedNodeAttrs.indexOf("data-metadata-image") >= 0, "a loaded cover clears its online-fallback marker");
assert.deepEqual(loaded.listeners, [], "the synchronous success path must not also attach listeners");

// --- 7. discriminator V6 (fix clause: hasArtworkSource coverLoadedSrc half) ---
// The scheduler can leave only `dataset.coverLoadedSrc` after stripping the
// declarative marker; that alone must prove the image started, so a loaded cover
// on this marker runs the success path synchronously. Dropping the coverLoadedSrc
// half would attach listeners instead -> fails on hasCover true / listeners [].
const loadedViaMarker = evaluate({
  complete: true, naturalWidth: 160,
  attributes: {},
  hasAttributes: {},
  dataset: { coverLoadedSrc: "/cover/6?size=160" },
  nodeDataset: {},
  classes: [],                                // start WITHOUT has-cover: loaded() must add it
});
assert.equal(loadedViaMarker.imgRemoved, false, "V6: coverLoadedSrc alone proves the image started; a loaded cover stays");
assert.equal(loadedViaMarker.hasCover, true, "V6: the coverLoadedSrc-loaded path must run loaded() synchronously and set has-cover");
assert.deepEqual(loadedViaMarker.listeners, [], "V6: the coverLoadedSrc path must not fall through to the listener path");

// --- 8. discriminator: in-flight started image defers to load/error ----------
// A started but not-yet-complete image must NOT be judged; it waits on the real
// load/error events. Killing the `|| !image.complete` clause in verify/the guard
// would call failed() on an in-flight image -> fails on imgRemoved false.
const inFlight = evaluate({
  complete: false, naturalWidth: 0,
  attributes: { src: "/cover/5?size=160" },
  hasAttributes: { src: true },
  nodeDataset: {},
  classes: [],
});
assert.equal(inFlight.imgRemoved, false, "an in-flight cover must not be judged before load/error");
assert.deepEqual(inFlight.listeners, ["error", "load"], "an in-flight cover waits on load/error");

// --- 9. discriminator V7/V8 (fix clause: the load/error handlers themselves) --
// After a deferred cover, simulating the scheduler starting the load and the real
// browser firing `error` must run failed() (fall back to online). Removing the
// error handler (V8) or the load handler (V7) fails the corresponding branch.
const deferredThenError = evaluate({
  complete: true, naturalWidth: 0,
  attributes: { "data-cover-src": "/cover/7?size=160" },
  hasAttributes: {},
  nodeDataset: { metadataImage: "https://meta/album.jpg" },
  classes: [],
});
assert.deepEqual(deferredThenError.listeners, ["error", "load"], "V7/V8: the deferred cover must have both handlers bound");
// scheduler later starts the load and the browser reports failure:
deferredThenError.img.complete = true;
deferredThenError.img.naturalWidth = 0;
deferredThenError.__fire = (t) => deferredThenError.img.listeners[t].forEach((cb) => cb({ type: t }));
deferredThenError.__fire("error");
assert.equal(deferredThenError.img.removed, true, "V8: the error handler must drop the failed local cover");
assert.equal(deferredThenError.applied(), "https://meta/album.jpg", "V8: the error handler must apply the online fallback");

const deferredThenLoad = evaluate({
  complete: true, naturalWidth: 0,
  attributes: { "data-cover-src": "/cover/8?size=160" },
  hasAttributes: {},
  nodeDataset: { metadataImage: "https://meta/album.jpg" },
  classes: [],
});
deferredThenLoad.img.complete = true;
deferredThenLoad.img.naturalWidth = 160;
deferredThenLoad.img.listeners.load.forEach((cb) => cb({ type: "load" }));
assert.equal(deferredThenLoad.img.removed, false, "V7: the load handler keeps a successfully loaded local cover");
assert.equal(deferredThenLoad.classSet.has("has-cover"), true, "V7: the load handler must set has-cover");
assert.equal(deferredThenLoad.applied(), null, "V7: a loaded local cover must not be swapped for the online image");

// --- 10. discriminator V2 (fix clause: verify's has-source guard) ------------
// The rAF verify() backstop must itself refuse to judge a still-src-less image
// (the scheduler may not have reached it yet). Removing `!hasArtworkSource()` from
// verify() lets the rAF path delete a deferred cover -> fails here.
const deferredThenRaf = evaluate({
  complete: true, naturalWidth: 0,
  attributes: { "data-cover-src": "/cover/9?size=160" },
  hasAttributes: {},
  nodeDataset: {},
  classes: [],
});
assert.equal(deferredThenRaf.rafScheduled, 1, "V2: a deferred cover schedules the rAF verify() backstop");
assert.ok(typeof deferredThenRaf.raf.cb === "function", "V2: the rAF callback must be captured");
deferredThenRaf.raf.cb();                        // run verify() while still src-less
assert.equal(deferredThenRaf.img.removed, false, "V2: the rAF verify() must NOT judge a src-less deferred cover");

// --- 11. discriminator V4 (fix clause: naturalWidth threshold direction) -----
// loaded() vs failed() split on `naturalWidth > 1`. Flipping it would send a
// loaded cover to failed(); covered by the started+loaded sync case (case 6) whose
// hasCover stays true, and the deferred->load case (case 9).
const loadedTiny = evaluate({
  complete: true, naturalWidth: 1,            // 1px is treated as a broken/placeholder image
  attributes: { src: "/cover/10?size=160" },
  hasAttributes: { src: true },
  nodeDataset: { metadataImage: "https://meta/album.jpg" },
  classes: ["has-cover"],
});
assert.equal(loadedTiny.imgRemoved, true, "V4: naturalWidth 1 (<= 1) is a failure, not a loaded cover");
assert.equal(loadedTiny.appliedOnline, "https://meta/album.jpg", "V4: the sub-threshold cover falls back to online");

// --- 12. source-level: the guard must not fall back to a bare `image.complete` --
const guardStart = source.indexOf("function prepareLocalGroupArtwork(");
const guardEnd = source.indexOf("\nfunction loadGroupArtwork(", guardStart);
const guardBody = source.slice(guardStart, guardEnd);
assert.equal(countOf(guardBody, "if (image.complete) return verify();"), 0,
  "the synchronous guard must not judge a cover on the bare complete flag again");
assert.ok(/hasAttribute\?\.\("src"\)/.test(guardBody) && /coverLoadedSrc/.test(guardBody),
  "the guard must test for an actual source (hasAttribute src / coverLoadedSrc) like the scheduler does");

// --- 13. source-level wiring: render() binds the fallback handlers before the
//         shared scheduler assigns any source, and group covers stay deferred ---
const renderStart = source.indexOf("function render(");
const renderLane = source.slice(renderStart, renderStart + 4000);
assert.match(renderLane, /loadGroupArtwork\(\);\s*\n\s*hydrateVisibleTrackCovers\(\);/,
  "render() must attach the group fallback handlers immediately before the shared scheduler");
const groupIconStart = source.indexOf("function groupIcon(");
const groupIconLane = source.slice(groupIconStart, source.indexOf("function applyGroupArtwork(", groupIconStart));
assert.ok(/<img style="visibility:hidden" data-cover-src="\$\{escapeHtml\(image\)\}" alt="">/.test(groupIconLane),
  "group covers must keep shipping as deferred <img> without a src attribute");

// --- 14. the shared scheduler treats "has a source" as the started marker ------
assert.ok(/hasAttribute\(\s*"src"\s*\)|hasAttribute\?\.\(\s*"src"\s*\)/.test(schedulerSource),
  "cover_load_scheduler.js must keep using hasAttribute(src) as the started marker");

// --- 15. registered orphans: this face may not grow new zero-reference code ---
// Four functions in this face are currently unreferenced. Each is registered here
// rather than deleted because removing them would strand a shipped/Android-bundled
// module (asset/device-round bucket), exactly as R159 registered `effectiveProfile`
// in test_ui_library_sort_shuffle.js. Empty this list when that decision lands; a
// second, unregistered orphan fails here.
const pendingOrphans = ["canSortTrackColumn", "clientPagedTracks", "hasMultipleLibraryRoots", "libraryRootLabels"];
const declared = [];
for (const line of face.split("\n")) {
  const match = /^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/.exec(line);
  if (match) declared.push(match[1]);
}
assert.ok(declared.length >= 40, "the reviewed face must keep its shape; found " + declared.length + " functions");
const orphans = declared.filter(name => countOf(source, name) === 1);
assert.deepEqual(orphans.slice().sort(), pendingOrphans.slice().sort(),
  "every zero-reference function in this face must be registered as a pending orphan");

console.log("group artwork source-gate regression checks passed.");
