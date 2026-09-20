const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/ui_sync_scheduler.js", "utf8");
const timers = [];
const listeners = new Map();
const calls = [];
const document = {
  visibilityState: "visible",
  addEventListener(name, callback) { listeners.set(name, callback); },
  removeEventListener(name, callback) { if (listeners.get(name) === callback) listeners.delete(name); },
};
const timerHost = {
  setInterval(callback, milliseconds) {
    timers.push({ callback, milliseconds, cleared: false });
    return timers.length - 1;
  },
  clearInterval(id) { timers[id].cleared = true; },
};
const context = vm.createContext({ document, globalThis: {} });
vm.runInContext(source, context);
const scheduler = context.globalThis.fnAudioUiSyncScheduler.create({
  document,
  timerHost,
  isLibraryScanning: () => true,
  isRemoteTarget: () => true,
  isRemoteEventConnected: () => false,
  refreshLibraryStatus: () => calls.push("library"),
  refreshCurrentTranscodeStatus: () => calls.push("transcode"),
  refreshRendererSession: () => calls.push("renderer"),
  refreshServerUserState: () => calls.push("user"),
  startRemoteEventStream: () => calls.push("event-start"),
  stopRemoteEventStream: () => calls.push("event-stop"),
  refreshRemoteStatus: () => calls.push("remote"),
  updateRemoteUi: () => calls.push("remote-ui"),
});

assert.equal(timers.length, 7);
assert.deepEqual(timers.map(timer => timer.milliseconds), [30000, 1000, 1200, 5000, 1500, 500, 10000]);
timers.forEach(timer => timer.callback());
assert.ok(calls.includes("remote"));
assert.ok(calls.includes("remote-ui"));

calls.length = 0;
document.visibilityState = "hidden";
timers.forEach(timer => timer.callback());
assert.deepEqual(calls, []);
listeners.get("visibilitychange")();
assert.deepEqual(calls, ["event-stop"]);

calls.length = 0;
document.visibilityState = "visible";
listeners.get("visibilitychange")();
assert.deepEqual(calls, ["library", "transcode", "renderer", "user", "event-start", "remote", "remote-ui"]);

scheduler.stop();
assert.ok(timers.every(timer => timer.cleared));
assert.equal(listeners.has("visibilitychange"), false);
// An incoming DLNA render paints the same transport row but is not a remote play
// target, so the 500ms tick has to be armed by the renderer session itself.
function arm(options) {
  const ticks = [];
  const fired = [];
  const schedulerContext = vm.createContext({ document, globalThis: {} });
  vm.runInContext(source, schedulerContext);
  const instance = schedulerContext.globalThis.fnAudioUiSyncScheduler.create(Object.assign({
    document,
    timerHost: {
      setInterval(callback, milliseconds) {
        ticks.push({ callback, milliseconds });
        return ticks.length - 1;
      },
      clearInterval() {},
    },
    updateRemoteUi: () => fired.push("remote-ui"),
    isRemoteTarget: () => false,
    isIncomingRendererSession: () => false,
  }, options));
  return {
    fire(milliseconds) {
      ticks.filter(tick => tick.milliseconds === milliseconds).forEach(tick => tick.callback());
    },
    fired,
    stop: () => instance.stop(),
  };
}
const remoteOnly = arm({ isRemoteTarget: () => true });
remoteOnly.fire(500);
assert.deepEqual(remoteOnly.fired, ["remote-ui"], "A remote play target must keep painting the transport row");
const incomingOnly = arm({ isIncomingRendererSession: () => true });
incomingOnly.fire(500);
assert.deepEqual(incomingOnly.fired, ["remote-ui"], "An incoming render session must paint the transport row without being a remote target");
const idle = arm({});
idle.fire(500);
assert.deepEqual(idle.fired, [], "With neither state the transport tick must stay silent");
remoteOnly.stop();
incomingOnly.stop();
idle.stop();
assert.doesNotThrow(() => context.globalThis.fnAudioUiSyncScheduler.create(null, { timerHost }));
assert.doesNotThrow(() => context.globalThis.fnAudioUiSyncScheduler.create({ timerHost: null }));
console.log("UI synchronization scheduler regression checks passed.");
