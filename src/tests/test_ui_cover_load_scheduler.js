const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/cover_load_scheduler.js", "utf8");
const observed = [];
const events = [];
let latestObserver = null;
const observers = [];
class Observer {
  constructor(callback, options) { this.callback = callback; this.options = options; this.disconnected = false; latestObserver = this; observers.push(this); }
  observe(image) { observed.push(image); }
  unobserve() {}
  disconnect() { this.disconnected = true; }
}
function image(source) {
  const listeners = {};
  return {
    isConnected: true,
    hidden: false,
    style: {},
    dataset: { coverSrc: source },
    attributes: new Set(),
    addEventListener(name, callback) { listeners[name] = callback; },
    removeEventListener(name, callback) {
      if (listeners[name] === callback) delete listeners[name];
      this.removedListeners = (this.removedListeners || 0) + 1;
    },
    hasAttribute(name) { return this.attributes.has(name); },
    removeAttribute(name) {
      if (name === "data-cover-src") delete this.dataset.coverSrc;
      if (name === "data-cover-loaded-src") delete this.dataset.coverLoadedSrc;
      if (name === "data-cover-retry-count") delete this.dataset.coverRetryCount;
      if (name === "hidden") this.hiddenAttributeRemoved = true;
      this.attributes.delete(name);
    },
    set src(value) { this.loaded = value; this.attributes.add("src"); },
    finish() { listeners.load?.({ type: "load" }); },
    fail() { listeners.error?.({ type: "error" }); },
  };
}
function eagerImage(source) {
  const node = image(source);
  node.attributes.add("src");
  node.loaded = source;
  return node;
}
const context = vm.createContext({ globalThis: {}, window: { IntersectionObserver: Observer } });
vm.runInContext(source, context);
const first = image("one");
const second = image("two");
const third = image("three");
const scrollRoot = {};
const scheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => ({ querySelectorAll: () => [first, second, third] }),
  getScrollRoot: () => scrollRoot,
  maxConcurrent: 2,
  onEvent: event => events.push(event),
});
const malformedScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({ maxConcurrent: Symbol("bad") });
assert.equal(malformedScheduler.snapshot().inFlight, 0);
assert.equal(scheduler.hydrate().dropped, 0);
assert.equal(observed.length, 0, "eager first-page covers do not wait for observer registration");
assert.equal(scheduler.snapshot().inFlight, 2, "the first visible covers start without waiting for an observer callback");
assert.equal(latestObserver.options.root, scrollRoot);
latestObserver.callback([first, second, third].map(target => ({
  target,
  isIntersecting: true,
  rootBounds: null,
  boundingClientRect: { top: 0, bottom: 1 },
}))); 
assert.equal(scheduler.snapshot().inFlight, 2);
assert.equal(Boolean(first.loaded) || Boolean(second.loaded) || Boolean(third.loaded), true);
first.finish();
assert.equal(scheduler.snapshot().inFlight, 2);
assert.equal(first.dataset.coverLoadedSrc, "one", "loaded covers retain their declarative source for keyed row comparisons");
assert.equal(events.filter(event => event === "request").length, 3);
assert.equal(events.filter(event => event === "load").length, 1);

// A transient cover error gets one bounded retry while retaining the music
// glyph fallback. The retry must not make the scheduler's in-flight count
// negative or require a complete list rebuild.
const retryImage = image("retry-one");
const revealImage = image("reveal-one");
revealImage.hidden = true;
const revealScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => ({ querySelectorAll: () => [revealImage] }),
  maxConcurrent: 1,
});
revealScheduler.hydrate();
revealImage.finish();
assert.equal(revealImage.hidden, false, "a successful cover load must reveal an image that started hidden");
assert.equal(revealImage.hiddenAttributeRemoved, true, "a successful cover load must explicitly remove the hidden attribute for WebView compatibility");
assert.equal(revealImage.style.visibility, "visible", "a successful cover load must reveal the image without relying on hidden-attribute behavior");
const retryRoot = { querySelectorAll: () => [retryImage] };
const retryContext = vm.createContext({ globalThis: {}, window: {} });
vm.runInContext(source, retryContext);
const retryEvents = [];
const retryScheduler = retryContext.globalThis.fnAudioCoverLoadScheduler.create({
  window: retryContext.window,
  getImageRoot: () => retryRoot,
  maxConcurrent: 1,
  onEvent: event => retryEvents.push(event),
});
retryScheduler.hydrate();
assert.equal(retryImage.loaded, "retry-one");
assert.equal(retryImage.dataset.coverSchedulerOwned, "1", "scheduler-owned images must suppress the row inline retry");
retryImage.fail();
assert.equal(retryImage.loaded, "retry-one", "cover errors should receive one bounded retry");
assert.equal(retryScheduler.snapshot().inFlight, 1);
retryImage.finish();
assert.equal(retryScheduler.snapshot().inFlight, 0);
assert.deepEqual(retryEvents, ["request", "error", "retry", "request", "load"]);

// A stale/missing artwork URL can still reach the scheduler after metadata has
// been cached.  Once its bounded retry is exhausted, the image must disappear
// so the row's music glyph is visible instead of the browser's broken-image
// indicator.
const terminalImage = image("terminal-missing");
terminalImage.dataset.coverRetryCount = "1";
const terminalScheduler = retryContext.globalThis.fnAudioCoverLoadScheduler.create({
  window: retryContext.window,
  getImageRoot: () => ({ querySelectorAll: () => [terminalImage] }),
  maxConcurrent: 1,
});
terminalScheduler.hydrate();
terminalImage.fail();
assert.equal(terminalImage.hidden, true, "a terminal cover error must hide the broken image");

// A second list commit against the same root must reconcile incrementally:
// existing requests stay alive and only a newly inserted cover is queued.
const incrementalFirst = image("incremental-one");
const incrementalSecond = image("incremental-two");
const incrementalThird = image("incremental-three");
const appended = image("appended");
let currentImages = [incrementalFirst, incrementalSecond, incrementalThird];
const incrementalRoot = { querySelectorAll: () => currentImages };
const incrementalScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => incrementalRoot,
  maxConcurrent: 2,
});
incrementalScheduler.hydrate();
const incrementalGeneration = incrementalScheduler.snapshot().generation;
const beforeInFlight = incrementalScheduler.snapshot().inFlight;
currentImages = [incrementalFirst, incrementalSecond, incrementalThird, appended];
incrementalScheduler.hydrate();
assert.equal(incrementalScheduler.snapshot().generation, incrementalGeneration, "same-root hydration must keep its generation");
assert.equal(incrementalScheduler.snapshot().inFlight, beforeInFlight, "same-root hydration must preserve active cover requests");
assert.equal(appended.dataset.coverQueued, String(incrementalGeneration), "same-root hydration queues newly inserted covers");

// A paginated list commits into the same root, so only a bounded burst of the
// newly inserted rows may enter the queue. Without that bound, browsing a
// large library downloaded thousands of covers the user never scrolled to.
const burstImages = Array.from({ length: 60 }, (_, index) => image("burst-" + index));
let burstCurrent = burstImages.slice(0, 4);
const burstRoot = { querySelectorAll: () => burstCurrent };
const burstScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => burstRoot,
  maxConcurrent: 1,
  initialPriorityCount: 2,
});
const firstBurst = burstScheduler.hydrate();
assert.equal(firstBurst.queued, 1, "the first commit queues only its bounded eager burst");
burstCurrent = burstImages;
const secondBurst = burstScheduler.hydrate();
assert.equal(secondBurst.generation, firstBurst.generation, "an appended page keeps the cover generation");
assert.equal(secondBurst.queued, firstBurst.queued + 2, "an appended page queues only its eager burst");
assert.equal(burstImages[40].dataset.coverQueued, undefined, "offscreen artwork must not enter the cover queue");
assert.equal(burstImages[40].dataset.coverObserved, String(secondBurst.generation), "offscreen artwork must stay observer-owned");
burstCurrent = burstImages;
const thirdBurst = burstScheduler.hydrate();
assert.equal(thirdBurst.queued, secondBurst.queued, "observer-owned artwork must not be re-classified as fresh work");
burstScheduler.stop();

// Detached in-flight nodes must not permanently consume scheduler capacity.
const detached = image("detached");
const replacement = image("replacement");
let detachImages = [detached];
const detachRoot = { querySelectorAll: () => detachImages };
const detachScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => detachRoot,
  maxConcurrent: 1,
});
detachScheduler.hydrate();
detached.isConnected = false;
detachImages = [replacement];
detachScheduler.hydrate();
assert.equal(detachScheduler.snapshot().inFlight, 1, "detached cover slot is released for the replacement");
assert.equal(replacement.loaded, "replacement");
assert.equal(detached.removedListeners, 2, "detached cover listeners are cleaned up when the slot is released");
detached.finish();
assert.equal(detachScheduler.snapshot().inFlight, 1, "late detached image events must not decrement a replacement slot");

const eagerFirst = eagerImage("eager-one");
const eagerSecond = eagerImage("eager-two");
const lazyThird = image("lazy-three");
const eagerScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => ({ querySelectorAll: () => [eagerFirst, eagerSecond, lazyThird] }),
  maxConcurrent: 1,
  initialPriorityCount: 0,
});
eagerScheduler.hydrate();
assert.equal(eagerFirst.dataset.coverLoadedSrc, "eager-one", "browser-started eager artwork retains a stable comparison source");
assert.equal(eagerFirst.dataset.coverSrc, undefined, "browser-started eager artwork is removed from the lazy scheduler queue");
assert.equal(eagerScheduler.snapshot().inFlight, 0, "eager browser loads do not masquerade as scheduler work");
assert.equal(observed.at(-1), lazyThird, "only still-lazy artwork is observed after eager normalization");

const orderedContext = vm.createContext({ globalThis: {}, window: { IntersectionObserver: Observer } });
vm.runInContext(source, orderedContext);
const orderedImages = [image("ordered-one"), image("ordered-two"), image("ordered-three"), image("ordered-four")];
const orderedScheduler = orderedContext.globalThis.fnAudioCoverLoadScheduler.create({
  window: orderedContext.window,
  getImageRoot: () => ({ querySelectorAll: () => orderedImages }),
  maxConcurrent: 1,
  initialPriorityCount: 4,
});
orderedScheduler.hydrate();
assert.equal(orderedImages[0].loaded, "ordered-one");
orderedImages[0].finish();
assert.equal(orderedImages[1].loaded, "ordered-two", "eager covers must retain visual FIFO order after the first slot frees");
orderedImages[1].finish();
assert.equal(orderedImages[2].loaded, "ordered-three");
scheduler.hydrate();
assert.equal(latestObserver.disconnected, false, "new observer remains active after re-hydration");
assert.equal(observers[0].disconnected, true, "previous observer is disconnected after re-hydration");
const secondGeneration = scheduler.snapshot().generation;
second.finish();
assert.equal(scheduler.snapshot().generation, secondGeneration, "stale image callbacks cannot mutate the replacement run");

const fallbackFirst = image("fallback-one");
const fallbackSecond = image("fallback-two");
const fallbackThird = image("fallback-three");
const fallbackImages = { 0: fallbackFirst, 1: fallbackSecond, 2: fallbackThird, length: 3 };
const fallbackContext = vm.createContext({ globalThis: {}, window: {} });
vm.runInContext(source, fallbackContext);
const fallbackScheduler = fallbackContext.globalThis.fnAudioCoverLoadScheduler.create({
  window: fallbackContext.window,
  getImageRoot: () => ({ querySelectorAll: () => fallbackImages }),
  maxConcurrent: 2,
});
assert.equal(fallbackScheduler.hydrate().dropped, 0);
assert.equal(fallbackScheduler.snapshot().inFlight, 2, "legacy fallback only starts the configured concurrency");
assert.equal(fallbackThird.loaded, undefined, "legacy fallback defers covers beyond its active window");
fallbackFirst.finish();
assert.equal(fallbackThird.loaded, "fallback-three", "legacy fallback advances when a slot is released");
const fallbackFourth = image("fallback-four");
let fallbackCurrent = [fallbackFirst, fallbackSecond, fallbackThird];
const fallbackRoot = { querySelectorAll: () => fallbackCurrent };
const incrementalFallback = fallbackContext.globalThis.fnAudioCoverLoadScheduler.create({
  window: fallbackContext.window,
  getImageRoot: () => fallbackRoot,
  maxConcurrent: 1,
});
incrementalFallback.hydrate();
fallbackCurrent = [fallbackFirst, fallbackSecond, fallbackThird, fallbackFourth];
incrementalFallback.hydrate();
fallbackSecond.finish();
fallbackThird.finish();
assert.equal(fallbackFourth.loaded, "fallback-four", "legacy incremental hydration must append newly discovered covers");
incrementalFallback.stop();
fallbackScheduler.stop();
fallbackSecond.finish();
assert.equal(fallbackScheduler.snapshot().inFlight, 0, "stopped scheduler exposes no stale in-flight work");

const stoppedImage = image("stopped");
const stoppedScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => ({ querySelectorAll: () => [stoppedImage] }),
  maxConcurrent: 1,
});
stoppedScheduler.hydrate();
stoppedScheduler.stop();
assert.equal(stoppedImage.removedListeners, 2, "stopping a scheduler must detach active image listeners");
assert.equal(stoppedScheduler.snapshot().inFlight, 0, "stopping must release active image slots immediately");
assert.equal(typeof context.globalThis.fnAudioCoverLoadScheduler.create, "function");
const boundedScheduler = context.globalThis.fnAudioCoverLoadScheduler.create({
  window: context.window,
  getImageRoot: () => ({ querySelectorAll: () => [] }),
  maxConcurrent: Infinity,
});
assert.equal(boundedScheduler.hydrate().inFlight, 0);
assert.match(source, /Math\.min\(32/);
assert.doesNotThrow(() => context.globalThis.fnAudioCoverLoadScheduler.create(null));
assert.match(source, /while \(run\.inFlight < maxConcurrent && run\.queue\.length\)/);
assert.match(source, /job\.generation !== run\.generation \|\| !job\.image\?\.isConnected/);
assert.match(source, /rootMargin: "280px 0px"/);
assert.match(source, /initialPriorityCount/);
assert.match(source, /run\.queue\.findIndex\(job => job\.priority\)/, "Priority work should preserve FIFO order instead of unshifting visible rows");
assert.match(source, /priority: Boolean\(priority\)/, "Queued cover jobs must carry an explicit priority class");
assert.match(source, /run\.fallbackImages = images/);
assert.match(source, /const maxQueued = 4096/);
assert.doesNotMatch(source, /findLastIndex/, "Cover scheduling must remain compatible with older Android WebViews");
assert.match(source, /image.dataset.coverLoadedSrc = source;/, "scheduler must retain the original cover source after browser URL resolution");
assert.match(source, /dropped: activeRun\.dropped/);
assert.match(source, /if \(enqueue\(entry\.target, visible\)\) run\.observer\?\.unobserve/);

const pressureContext = vm.createContext({ globalThis: {}, window: { IntersectionObserver: Observer } });
vm.runInContext(source, pressureContext);
const pressureImages = Array.from({ length: 4100 }, (_, index) => image(`pressure-${index}`));
const pressureScheduler = pressureContext.globalThis.fnAudioCoverLoadScheduler.create({
  window: pressureContext.window,
  getImageRoot: () => ({ querySelectorAll: () => pressureImages }),
  maxConcurrent: 1,
});
pressureScheduler.hydrate();
const pressureObserver = observers.at(-1);
pressureObserver.callback(pressureImages.map(target => ({
  target,
  isIntersecting: true,
  rootBounds: { top: 0, bottom: 1 },
  boundingClientRect: { top: 100, bottom: 101 },
})));
assert.equal(pressureScheduler.snapshot().queued, 4096);
assert.equal(pressureScheduler.snapshot().dropped, 3);

// A full queue evicts the newest normal job to make room for visible artwork.
// The displaced row must stay recoverable, otherwise one saturated list leaves
// permanent fallback glyphs behind.
const pressureGeneration = pressureScheduler.snapshot().generation;
const markedBefore = pressureImages.filter(node => node.dataset.coverQueued === String(pressureGeneration)).length;
assert.equal(
  markedBefore,
  pressureScheduler.snapshot().queued + pressureScheduler.snapshot().inFlight,
  "each queued or in-flight cover owns exactly one queue marker",
);
pressureObserver.callback([{
  target: pressureImages[4099],
  isIntersecting: true,
  rootBounds: { top: 0, bottom: 1000 },
  boundingClientRect: { top: 1, bottom: 2 },
}]);
const pressured = pressureScheduler.snapshot();
assert.equal(pressured.queued, 4096);
assert.equal(pressured.dropped, 4, "an evicted cover must be reported as dropped");
assert.equal(
  pressureImages.filter(node => node.dataset.coverQueued === String(pressured.generation)).length,
  pressured.queued + pressured.inFlight,
  "evicting a queued cover must release its marker so a later pass can retry it",
);
console.log("Cover load scheduler regression checks passed.");
