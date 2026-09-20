const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const source = fs.readFileSync(require("path").join(__dirname, "..", "app", "ui", "host_playback_session.js"), "utf8");

function load(window) {
  vm.runInNewContext(source, { window, globalThis: window });
  return window.fnAudioCreateHostPlaybackSession(window);
}

const calls = [];
const session = load({ fnOSPlaybackSession: {
  initialize(payload) { calls.push(["initialize", payload]); },
  synchronize(payload) { calls.push(["synchronize", payload]); },
  requestActivation(payload) { calls.push(["requestActivation", payload]); },
} });
assert.strictEqual(session.available, true);
session.initialize({ participantId: "x", generation: 2.9, engineEpoch: 3.8 });
session.synchronize({ trackId: "song", playing: true, position: 4.2 });
session.requestActivation("ctx");
assert.deepStrictEqual(calls.map(item => item[0]), ["initialize", "synchronize", "requestActivation"]);
assert.strictEqual(calls[0][1].generation, 2);
assert.strictEqual(calls[0][1].engineEpoch, 3);
assert.strictEqual(session.requestActivation("ctx-2"), true);

const absent = load({});
assert.strictEqual(absent.available, false);
assert.strictEqual(absent.initialize({}), false);
assert.strictEqual(absent.diagnostics().detected, false);
const generic = load({ flutter_inappwebview: { callHandler() { throw new Error("must not call"); } } });
assert.strictEqual(generic.available, false);
assert.strictEqual(generic.diagnostics().genericWebViewBridgeDetected, true);
assert.deepStrictEqual(Array.from(generic.diagnostics().genericWebViewBridgeMethods), ["callHandler"]);
assert.strictEqual(generic.initialize({}), false);
const hostile = load({ fnOSPlaybackSession: {
  get initialize() { throw new Error("getter"); },
  synchronize() { return Promise.reject(new Error("rejected")); },
} });
assert.strictEqual(hostile.available, true);
assert.strictEqual(hostile.synchronize({}), true);
const poisoned = load({ fnOSPlaybackSession: {
  synchronize(payload) { calls.push(["poisoned", payload]); },
} });
const throwingValue = { valueOf() { throw new Error("valueOf"); } };
const throwingText = { toString() { throw new Error("toString"); } };
const throwingSnapshot = new Proxy({
  generation: throwingValue,
  engineEpoch: true,
  stateVersion: "4.9",
  trackId: throwingText,
  playing: 1,
  position: throwingValue,
  duration: "-3",
  outputTarget: throwingText,
  metadata: new Proxy({ title: "ok", broken: "ignored" }, {
    get(target, key) { if (key === "broken") throw new Error("metadata getter"); return target[key]; },
  }),
}, { get(target, key) { if (key === "stateVersion") throw new Error("snapshot getter"); return target[key]; } });
assert.strictEqual(poisoned.synchronize(throwingSnapshot), true);
const poisonedPayload = calls.find(item => item[0] === "poisoned")[1];
assert.strictEqual(poisonedPayload.generation, 0);
assert.strictEqual(poisonedPayload.engineEpoch, 0);
assert.strictEqual(poisonedPayload.stateVersion, 0);
assert.strictEqual(poisonedPayload.trackId, "");
assert.strictEqual(poisonedPayload.playing, false);
assert.strictEqual(poisonedPayload.position, 0);
assert.strictEqual(poisonedPayload.duration, 0);
assert.strictEqual(poisonedPayload.outputTarget, "");
assert.strictEqual(poisonedPayload.metadata.title, "ok");
assert.strictEqual(Object.prototype.hasOwnProperty.call(poisonedPayload.metadata, "broken"), false);
console.log("host playback session adapter tests passed");
