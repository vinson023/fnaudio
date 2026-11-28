// R596: the volume slider has to drive the output that is actually audible.
//
// It used to write `audio.volume` and the native bridge and nothing else.  On a USB
// DAC or a UPnP renderer that meant the slider moved, the rail filled, and no
// output changed -- while the server had the whole path ready:
// `/api/playback/control` accepts a `volume` action, checks the mixer policy and
// answers with a message when the output is fixed-volume (server.py:3693), and
// `playback/mpd_client.py:808` performs the `setvol`.
//
// The capability rule matters as much as the routing: only an explicit
// `volume: false` disables the control.  A *missing* key is "unknown", because the
// UPnP push path sets its volume through the same MPD mixer as the DAC -- treating
// absent as unsupported would switch off a control that works.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the volume routing regression`);
  return match[0];
}

const volumeState = app.match(/^const remoteVolume = \{[^}]*\};$/m);
assert.ok(volumeState, "the in-flight volume state must stay a single top-level literal");

function build(options = {}) {
  const calls = [];
  const input = { disabled: false, title: "", value: "0.5" };
  const button = {
    title: "",
    attrs: {},
    classList: { toggled: [], toggle(name, on) { this.toggled.push(`${name}=${Boolean(on)}`); } },
    setAttribute(name, value) { button.attrs[name] = value; },
  };
  const panel = { hidden: true };
  const bodyClasses = new Set();
  const audio = { volume: 1 };
  const state = {
    playTarget: options.playTarget || "local",
    deviceTargetsRendered: options.targets || [],
  };
  const context = {
    state, audio, calls, input, button,
    $: id => (id === "volume" ? input : id === "volumeBtn" ? button : id === "volumePanel" ? panel : null),
    document: {
      body: {
        classList: {
          toggle(name, on) { if (on) bodyClasses.add(name); else bodyClasses.delete(name); },
          contains(name) { return bodyClasses.has(name); },
        },
      },
    },
    isRemoteTarget: () => Boolean(state.playTarget) && state.playTarget !== "local",
    nativePlaybackAvailable: () => options.native === true,
    nativePlaybackCall: (name, value) => calls.push(`native:${name}=${value}`),
    remoteControl: (action, position) => { calls.push(`remote:${action}=${position}`); return Promise.resolve(true); },
    setTimeout: (fn) => { fn(); return 0; },
    Math, Number, Boolean, String, Array, Object,
  };
  vm.createContext(context);
  vm.runInContext([
    volumeState[0],
    functionSource("activeTargetCapabilities"),
    functionSource("targetVolumeIsFixed"),
    functionSource("volumePercentOf"),
    functionSource("flushRemoteVolume"),
    functionSource("queueRemoteVolume"),
    functionSource("applyVolumeToTarget"),
    functionSource("volumeEntryShouldShow"),
    functionSource("volumeChangesNeedRelease"),
    functionSource("syncVolumeAvailability"),
    "globalThis.h = { activeTargetCapabilities, targetVolumeIsFixed, applyVolumeToTarget, queueRemoteVolume, volumeEntryShouldShow, volumeChangesNeedRelease, syncVolumeAvailability };",
  ].join("\n"), context);
  return { ...context.h, state, audio, calls, input, button, panel, bodyClasses };
}

(async () => {
const TARGETS = [
  { id: "local", kind: "browser", selected: true, capabilities: { seek: true, volume: true } },
  { id: "mpd:dac1", kind: "mpd", capabilities: { seek: true, volume: true } },
  { id: "mpd:fixed", kind: "mpd", capabilities: { seek: true, volume: false } },
  { id: "upnp:r1", kind: "dlna_push", capabilities: { seek: true } },
];

// --- capability lookup -----------------------------------------------------

{
  const env = build({ playTarget: "local", targets: TARGETS });
  assert.deepEqual({ ...env.activeTargetCapabilities() }, { seek: true, volume: true });
}

{
  // An explicit `false` is the only thing that disables the control.
  assert.equal(build({ playTarget: "mpd:fixed", targets: TARGETS }).targetVolumeIsFixed(), true);
  assert.equal(build({ playTarget: "mpd:dac1", targets: TARGETS }).targetVolumeIsFixed(), false);
  // No `volume` key: unknown, not unsupported -- the UPnP path shares the mixer.
  assert.equal(build({ playTarget: "upnp:r1", targets: TARGETS }).targetVolumeIsFixed(), false);
  // No capabilities block at all (an older server): leave the control alone.
  assert.equal(build({ playTarget: "x", targets: [{ id: "x", kind: "mpd" }] }).targetVolumeIsFixed(), false);
  // No rows yet (first paint before the targets payload): also unknown.
  assert.equal(build({ playTarget: "mpd:fixed", targets: [] }).targetVolumeIsFixed(), false);
}

// --- routing ---------------------------------------------------------------

{
  // Local target keeps the old behaviour: element volume plus the native bridge.
  const env = build({ playTarget: "local", native: true });
  env.applyVolumeToTarget(0.4);
  assert.equal(env.audio.volume, 0.4);
  assert.deepEqual(env.calls, ["native:setVolume=0.4"]);
}

{
  // Remote target: one command in the unit the server speaks (0-100), never a
  // local element write -- the browser is not the thing making sound.
  const env = build({ playTarget: "mpd:dac1", native: true });
  env.applyVolumeToTarget(0.37);
  assert.equal(env.audio.volume, 1, "the local element must not be touched for a remote target");
  assert.deepEqual(env.calls, ["remote:volume=37"]);
}

{
  // R635: writes are coalesced while one is in flight, so the second value lands
  // after the first answers - but it must still land, and it must be the value
  // the user stopped on, not the first one.
  const env = build({ playTarget: "mpd:dac1" });
  env.applyVolumeToTarget(1);
  env.applyVolumeToTarget(0);
  assert.deepEqual(env.calls, ["remote:volume=100"], "only one request may be on the wire");
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(env.calls, ["remote:volume=100", "remote:volume=0"]);
}

{
  // Out-of-range and non-numeric input is clamped or dropped, never forwarded.
  const env = build({ playTarget: "mpd:dac1" });
  env.applyVolumeToTarget(4);
  env.applyVolumeToTarget(-2);
  env.applyVolumeToTarget("nonsense");
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(env.calls, ["remote:volume=100", "remote:volume=0"]);
}

// --- R640: 移动端入口的三态（显示 / 显示但禁用 / 隐藏） -----------------------

{
  // 能调就出现：判据是目标能力，不是设置里的软件音量开关。
  const env = build({ playTarget: "mpd:dac1", targets: TARGETS });
  env.syncVolumeAvailability();
  assert.equal(env.bodyClasses.has("volume-entry-visible"), true);
  assert.equal(env.input.disabled, false);
  assert.equal(env.panel.hidden, true, "同步能力不能顺手把浮层打开");
}

{
  // 明确不能调 → 整个入口消失，并且把已经打开的浮层收起来。
  const env = build({ playTarget: "mpd:fixed", targets: TARGETS });
  env.panel.hidden = false;
  env.syncVolumeAvailability();
  assert.equal(env.bodyClasses.has("volume-entry-visible"), false);
  assert.equal(env.panel.hidden, true, "隐藏在打开浮层之后也要把浮层关掉");
}

{
  // 能力缺失（老服务端）按 R596 的约定算“未知”，仍然显示。
  assert.equal(build({ playTarget: "upnp:r1", targets: TARGETS }).volumeEntryShouldShow(), true);
  // 本地目标交给系统音量，不在这里再放一个。
  assert.equal(build({ playTarget: "local", targets: TARGETS }).volumeEntryShouldShow(), false);
  // 有行但没有 capabilities 块：未知，仍然是显示。
  assert.equal(build({ playTarget: "x", targets: [{ id: "x", kind: "mpd" }] }).volumeEntryShouldShow(), false,
    "no capabilities block at all leaves the fact unknown, and an unknown target gets no entry");
}

{
  // 转码增益路径一次改动要重编码整轨，只能松手提交。
  const transcode = build({ playTarget: "upnp:gain", targets: [
    { id: "upnp:gain", kind: "dlna_push", capabilities: { volume: true, volume_mode: "transcode" } },
  ] });
  assert.equal(transcode.volumeChangesNeedRelease(), true);
  const device = build({ playTarget: "upnp:tv", targets: [
    { id: "upnp:tv", kind: "dlna_push", capabilities: { volume: true, volume_mode: "device" } },
  ] });
  assert.equal(device.volumeChangesNeedRelease(), false);
  const mixer = build({ playTarget: "mpd:dac1", targets: TARGETS });
  assert.equal(mixer.volumeChangesNeedRelease(), false);
  // 拖动路径必须真的检查它，否则这条判定形同虚设。
  const oninput = app.match(/\$\("volume"\)\.oninput = e => \{[\s\S]*?\n\};/);
  assert.ok(oninput, "the volume input handler must stay extractable");
  assert.match(oninput[0], /if \(volumeChangesNeedRelease\(\)\) return;/,
    "a transcode-gain target must not be written on every drag step");
}

// --- the disabled state ----------------------------------------------------

{
  const env = build({ playTarget: "mpd:fixed", targets: TARGETS });
  env.syncVolumeAvailability();
  assert.equal(env.input.disabled, true, "a fixed-volume output disables the slider");
  assert.match(env.input.title, /固定音量/, "and says why on hover");
  assert.deepEqual(env.button.classList.toggled, ["is-fixed-volume=true"]);
  assert.match(env.button.attrs["aria-label"], /固定音量/, "the button announces the same thing");
}

{
  const env = build({ playTarget: "mpd:dac1", targets: TARGETS });
  env.syncVolumeAvailability();
  assert.equal(env.input.disabled, false, "a controllable output re-enables the slider");
  assert.equal(env.input.title, "");
  assert.deepEqual(env.button.classList.toggled, ["is-fixed-volume=false"]);
  assert.equal(env.button.attrs["aria-label"], "音量");
}

// --- the wiring ------------------------------------------------------------

{
  // The input handler must not write the local element when a remote target owns
  // the sound; the commit handlers must exist, or a remote drag never lands.
  const input = app.match(/\$\("volume"\)\.oninput = e => \{[\s\S]*?\n\};/);
  assert.ok(input, "the volume input handler must stay extractable");
  assert.match(input[0], /if \(isRemoteTarget\(\)\)[\s\S]*queueRemoteVolume\(/,
    "a remote drag streams the level instead of only moving the rail");
  assert.match(input[0], /audio\.volume = value/, "a local target still writes the element");
  // R635: preview-only was the reported "慢半拍" - three seconds of dragging
  // produced three seconds of silence and one jump on release.
  assert.match(input[0], /updateVolumeRail\(value\)/, "the rail still follows the finger");
  for (const handler of ["onchange", "onpointerup", "ontouchend"]) {
    assert.match(app, new RegExp(`\\$\\("volume"\\)\\.${handler} = e => applyVolumeToTarget\\(e\\.target\\.value\\)`),
      `a remote drag commits on ${handler}`);
  }
  // The capability has to be re-read when the target changes, including when the
  // list itself did not change.
  assert.match(app, /state\.deviceTargetsRendered = targets;\n[\s\S]{0,200}?syncVolumeAvailability\(\);/,
    "the targets payload refreshes the capability before its early return");
  assert.match(app, /updateVolumeRail\(\);\n[\s\S]{0,200}?syncVolumeAvailability\(\);/,
    "boot arms the capability once, before the first payload");
}

{
  assert.match(css, /\.volume-slider:disabled\{/, "a disabled rail has to look disabled");
}

console.log("Volume target routing regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
