// A DAC load must paint the new track's time readout with the click.
//
// `pushToDevice` used to write the transport row only for CUE segments: a USB DAC
// load refreshed the artist line and nothing else, so `#duration` kept the previous
// track's length and `#elapsed` sat on the previous position until an SSE frame or
// the 5s status poll arrived (measured 2.4s - 5.2s on the test NAS). The load reply
// already carries the authoritative core snapshot - position 0 plus the duration of
// the track that just started - so projecting it is enough to make the row land
// immediately. This test pins that projection and, just as important, that it is not
// narrowed back to one target kind.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^async function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `async function ${name} must stay extractable for the load-paint regression`);
  return match[0];
}

function plainFunctionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the load-paint regression`);
  return match[0];
}

const pushSource = functionSource("pushToDevice");
const loadCurrentSource = functionSource("loadCurrent");

function harness(reply, options = {}) {
  const calls = { snapshots: [], painted: 0, closed: 0, alerts: [], refreshes: 0 };
  const state = {
    playTarget: "dac:usb",
    remoteGeneration: 0,
    remoteEngineEpoch: 1,
    remoteLoadPromise: null,
    remoteLoadController: null,
    remoteLoadedKey: "",
    remoteLoadedAt: 0,
    remoteCueSegment: false,
    remoteStatus: null,
    remoteBaseSeconds: 0,
    remoteSnapshotAt: 0,
    deviceSwitchInFlight: false,
    dacStrategy: null,
    playTargetName: "USB DAC",
  };
  const element = {
    close() { calls.closed += 1; },
    textContent: "",
    dataset: {},
  };
  const context = {
    state,
    console,
    JSON,
    Math,
    Number,
    String,
    Object,
    Promise,
    Date: { now: () => 1_700_000_000_000 },
    AbortController: class { abort() {} },
    setTimeout: () => { calls.refreshes += 1; return 0; },
    alert: message => { calls.alerts.push(String(message)); },
    $: () => element,
    apiFetch: async () => ({ ok: reply.ok !== false, status: reply.ok === false ? 502 : 200 }),
    readResponseJsonBounded: async () => reply.body || reply,
    isDacTarget: () => options.dac !== false,
    playbackCommandId: () => "cmd-1",
    playbackSeconds: (value, fallback = 0) => {
      const number = Number(value);
      return Number.isFinite(number) && number >= 0 ? number : fallback;
    },
    displayText: value => String(value || ""),
    playbackBadge: () => "",
    setTextContentIfChanged: () => { calls.painted += 1; },
    syncPlayerProgress: () => {},
    updateNowMarquee: () => {},
    updateDeviceLabel: () => {},
    updateRemoteUi: () => { calls.painted += 1; },
    nativeRemoteUpdate: () => {},
    remoteSnapshotFromCore: (core, targetId) => (core ? {
      target_id: targetId,
      core,
      transport: { state: core.transport || "STOPPED" },
      position: { rel_seconds: core.position, duration_seconds: core.duration },
    } : null),
    applyRemotePlaybackSnapshot: snapshot => { calls.snapshots.push(snapshot); },
    refreshRemoteStatus: () => { calls.refreshes += 1; },
  };
  vm.createContext(context);
  vm.runInContext(pushSource + "\n;globalThis.__pushToDevice = pushToDevice;", context);
  return { context, calls, state };
}

const core = {
  transport: "PLAYING",
  position: 0,
  duration: 215,
  current: "track-2",
  target_kind: "alsa",
  state_version: 42,
};
const item = { id: "track-2", title: "Second", artist: "Someone", format: "FLAC", duration: 215 };

async function main() {
  // A plain DAC load projects the core snapshot, which is what carries the new
  // duration onto the rail.
  {
    const { context, calls } = harness({ body: { ok: true, core, strategy: "pcm", cue_segment: false } });
    const loaded = await context.__pushToDevice("dac:usb", item);

    assert.equal(loaded, true, "a successful load must report success");
    assert.equal(calls.snapshots.length, 1, "exactly one snapshot is projected per load");
    assert.equal(calls.snapshots[0].target_id, "dac:usb");
    assert.equal(calls.snapshots[0].position.duration_seconds, 215, "the rail must take the new duration immediately");
    assert.equal(calls.snapshots[0].position.rel_seconds, 0, "the readout must restart at 0:00, not keep the old position");
    assert.equal(calls.snapshots[0].transport.state, "PLAYING");
    assert.equal(calls.alerts.length, 0);
  }

  // A CUE track on a DAC is not a cue segment there, so it goes through the same
  // core projection instead of the browser-only optimistic branch.
  {
    const cueItem = { ...item, cue_track: true, cue_start: 12 };
    const { context, calls, state } = harness({ body: { ok: true, core, cue_segment: false } });
    await context.__pushToDevice("dac:usb", cueItem);

    assert.equal(state.remoteCueSegment, false, "a DAC never runs a cue segment");
    assert.equal(calls.snapshots.length, 1, "a DAC cue track still projects the core snapshot");
    assert.equal(calls.snapshots[0].position.duration_seconds, 215);
  }

  // The server declares a cue segment (browser target): the segment length wins and
  // the core duration describes the whole file, so the optimistic branch keeps it.
  {
    const cueItem = { ...item, cue_track: true, cue_start: 30, duration: 90 };
    const { context, calls, state } = harness({ body: { ok: true, core, cue_segment: true } }, { dac: false });
    await context.__pushToDevice("local", cueItem);

    assert.equal(state.remoteCueSegment, true);
    assert.equal(calls.snapshots.length, 0, "a declared segment is painted from the segment, not from core");
    assert.ok(calls.painted > 0, "the segment still repaints the row");
  }

  // A refused load must not paint a playing row it never got.
  {
    const { context, calls } = harness({ ok: false, body: { ok: false, message: "track not found" } });
    const loaded = await context.__pushToDevice("dac:usb", item);

    assert.equal(loaded, false);
    assert.equal(calls.snapshots.length, 0, "a failed load must leave the row alone");
    assert.deepEqual(calls.alerts, ["track not found"]);
  }

  // The row has to move on the click, not on the reply. `loadCurrent` runs
  // synchronously, so the position baseline it writes is what the first paint
  // reads; leaving it on the outgoing track is the "1:14 on a track that just
  // started" shape.
  {
    const baseline = loadCurrentSource.indexOf("state.remoteBaseSeconds = 0;");
    const dispatch = loadCurrentSource.indexOf("pushToDevice(state.playTarget, item)");
    assert.ok(baseline >= 0, "the remote load must reset the position baseline");
    assert.ok(dispatch > baseline, "the baseline reset must happen before the load is sent");
    assert.match(
      loadCurrentSource.slice(baseline, dispatch),
      /state\.remoteSnapshotAt = Date\.now\(\)/,
      "an extrapolation without a fresh snapshot time would count from the outgoing track",
    );
  }

  // The length is part of the same click: `seekDuration` prefers a declared
  // duration, and until the load is confirmed the declaration still belongs to the
  // outgoing track (30s while a cast owned the row). It has to be cleared before
  // the first paint, or the rail keeps the old length for the whole round trip.
  {
    const baseline = loadCurrentSource.indexOf("state.remoteBaseSeconds = 0;");
    const dispatch = loadCurrentSource.indexOf("pushToDevice(state.playTarget, item)");
    const paint = loadCurrentSource.indexOf("updateRemoteUi()", baseline);
    const cleared = loadCurrentSource.indexOf("duration_seconds: 0", baseline);
    assert.ok(cleared >= 0, "the outgoing track's declared length must be dropped at the click");
    assert.ok(cleared < dispatch, "the declaration must be gone before the load is sent");
    assert.ok(
      cleared < paint,
      "dropping the declaration after the paint would leave one frame on the old length",
    );
    assert.match(
      loadCurrentSource.slice(cleared - 200, cleared + 40),
      /state\.remoteStatus/,
      "the declaration lives on the remote snapshot, not on local audio",
    );
  }

  // `seekDuration` is the other half: a device that has not declared a length yet
  // must not read as a zero-length track, or the rail stays empty until a poll.
  {
    const state = { mode: "remote", remoteStatus: null, item: { id: "t", duration: 215 } };
    const context = {
      state,
      Math,
      Number,
      isIncomingRendererSession: () => false,
      nativePlaybackAvailable: () => false,
      isRemoteTarget: () => true,
      currentItem: () => state.item,
      audio: { duration: Number.NaN },
      playbackSeconds: (value, fallback = 0) => {
        const number = Number(value);
        return Number.isFinite(number) && number >= 0 ? number : fallback;
      },
    };
    vm.createContext(context);
    vm.runInContext(plainFunctionSource("seekDuration") + "\n;globalThis.__seekDuration = seekDuration;", context);

    assert.equal(context.__seekDuration(), 215, "the library row states the length until the device does");
    state.remoteStatus = { position: { rel_seconds: 0, duration_seconds: 0 } };
    assert.equal(context.__seekDuration(), 215, "a declared zero is still 'not declared yet'");
    state.remoteStatus = { position: { rel_seconds: 0, duration_seconds: 180 } };
    assert.equal(context.__seekDuration(), 180, "a declared length always wins");
    state.item = null;
    assert.equal(context.__seekDuration(), 180, "without a library row the declaration still stands");
    state.remoteStatus = null;
    assert.equal(context.__seekDuration(), 0, "nothing known anywhere is still zero, not an error");
  }

  // Shape: the projection must stay unconditional once the segment branch declines,
  // so a later target-kind list cannot silently re-open the DAC gap.
  assert.doesNotMatch(
    pushSource,
    /else if \(data\.core && !isDacTarget/,
    "the core projection must not be narrowed to non-DAC targets",
  );
  assert.match(
    pushSource,
    /else if \(data\.core\) \{\s*\n\s*\/\//,
    "the core projection stays the documented fallback for every non-segment load",
  );

  console.log("remote load paint: 4 load cases, click-time baseline, duration fallback ok");
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
