// R637：手机音量键要能改 DAC 的音量。
//
// 音量键改的是手机自己的 STREAM_MUSIC，而远端输出根本不经过手机；Media3 1.10
// 也没有 setPlaybackToRemote（只有 legacy compat 有），所以只能由 Activity 把键
// 接过来。这条测试守三件事：
//   1. 原生侧只在“远端输出”时接管，其余情况必须把键还给系统；
//   2. 接管之后走的是和滑块完全相同的一条命令（同一个单飞队列）；
//   3. 对话框/输入框在前台时松手，别把音量键从用户正在操作的东西手里抢走。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join("app", "ui", "app.js"), "utf8");
const mainActivity = fs.readFileSync(
  path.join("..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "MainActivity.java"), "utf8");
const bridge = fs.readFileSync(
  path.join("..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "web", "NativePlaybackBridge.java"), "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

const stepConst = app.match(/^const VOLUME_KEY_STEP = \d+;$/m);
assert.ok(stepConst, "the key step must be a named constant");
const keyHandler = app.match(/^globalThis\.fnAudioVolumeKey = [\s\S]*?^};$/m);
assert.ok(keyHandler, "the native bridge needs a stable global entry point");
const panelTimer = app.match(/^let volumePanelHideTimer = \d+;$/m);
assert.ok(panelTimer, "the panel auto-hide timer must stay a single literal");

function harness({ remote = true, native = true, dialog = false, activeTag = "BODY" } = {}) {
  const calls = { queue: [], rail: [], native: [] };
  const rail = { value: "0.5" };
  const panel = { hidden: true };
  const state = {};
  const context = {
    Number, Math, String, console,
    state,
    $: id => (id === "volume" ? rail : id === "volumePanel" ? panel : null),
    updateVolumeRail: value => calls.rail.push(value),
    queueRemoteVolume: value => calls.queue.push(value),
    nativePlaybackCall: (name, value) => { calls.native.push([name, value]); return true; },
    nativePlaybackAvailable: () => native,
    isRemoteTarget: () => remote,
    document: {
      querySelector: selector => (dialog && selector === "dialog[open]" ? {} : null),
      activeElement: { tagName: activeTag, isContentEditable: false },
    },
    setTimeout: (fn) => 0,
    clearTimeout: () => {},
  };
  vm.createContext(context);
  vm.runInContext([
    stepConst[0],
    panelTimer[0],
    functionSource("remoteVolumePercent"),
    functionSource("volumeKeysShouldDriveRemote"),
    functionSource("syncRemoteVolumeKeys"),
    functionSource("showVolumePanelBriefly"),
    keyHandler[0],
    "globalThis.h = { remoteVolumePercent, volumeKeysShouldDriveRemote, syncRemoteVolumeKeys, fnAudioVolumeKey: globalThis.fnAudioVolumeKey };",
  ].join("\n"), context);
  return { h: context.h, calls, rail, state, panel };
}

// --- 每次按键 = 一档，走同一个队列 -----------------------------------------

{
  const env = harness();
  env.h.fnAudioVolumeKey(1);
  assert.deepEqual(env.calls.queue, [55], "one press is one step of 5%");
  assert.deepEqual(env.calls.rail, [0.55], "the rail has to follow immediately");
  env.h.fnAudioVolumeKey(-1);
  assert.deepEqual(env.calls.queue, [55, 50], "each press is relative to the value the last one produced");
}

{
  // 两端夹紧，不能把 100 变成 105 或把 0 变成负数。
  const env = harness();
  env.rail.value = "0.98";
  env.h.fnAudioVolumeKey(1);
  env.rail.value = "0.02";
  env.h.fnAudioVolumeKey(-1);
  assert.deepEqual(env.calls.queue, [100, 0]);
}

// --- 什么时候接管、什么时候还回去 -------------------------------------------

{
  assert.equal(harness().h.volumeKeysShouldDriveRemote(), true);
  assert.equal(harness({ remote: false }).h.volumeKeysShouldDriveRemote(), false,
    "a local target still owns the system volume");
  assert.equal(harness({ native: false }).h.volumeKeysShouldDriveRemote(), false,
    "without the bridge there is nobody to hand the key to");
  assert.equal(harness({ dialog: true }).h.volumeKeysShouldDriveRemote(), false,
    "an open dialog owns every key");
  assert.equal(harness({ activeTag: "INPUT" }).h.volumeKeysShouldDriveRemote(), false,
    "a focused text field owns the keyboard");
}

{
  // 只在答案变化时推给原生：每次状态刷新都推一次会把 Java 侧刷成噪声。
  const env = harness();
  env.h.syncRemoteVolumeKeys();
  env.h.syncRemoteVolumeKeys();
  assert.deepEqual(env.calls.native, [["setRemoteVolumeKeys", true]]);
}

{
  // 远端切回本地时必须显式推 false，否则音量键会一直被困在应用里。
  const env = harness({ remote: true });
  env.h.syncRemoteVolumeKeys();
  const other = harness({ remote: false });
  other.h.syncRemoteVolumeKeys();
  assert.deepEqual(other.calls.native, [["setRemoteVolumeKeys", false]]);
}

// --- 原生侧 ----------------------------------------------------------------

{
  assert.match(mainActivity, /public boolean dispatchKeyEvent\(KeyEvent event\)/,
    "keys that the session cannot redirect have to be taken in the activity");
  assert.match(mainActivity, /KeyEvent\.KEYCODE_VOLUME_UP/);
  assert.match(mainActivity, /KeyEvent\.KEYCODE_VOLUME_DOWN/);
  assert.match(mainActivity, /fnAudioVolumeKey/, "the activity must call into the page");
  assert.match(mainActivity, /private volatile boolean remoteVolumeKeys/,
    "the flag is written by the page thread and read by the input dispatcher");
  assert.match(mainActivity, /return true;[\s\S]{0,80}super\.dispatchKeyEvent/,
    "a taken key must not fall through to the system volume panel");
}

{
  assert.match(bridge, /default void setRemoteVolumeKeys\(boolean enabled\)/,
    "the controller provider contract needs the setter, with a no-op default");
  assert.match(bridge, /@JavascriptInterface\s+public void setRemoteVolumeKeys\(boolean enabled\)/,
    "the page reaches it through the bridge");
}

{
  assert.match(app, /nativePlaybackCall\("setRemoteVolumeKeys", enabled\)/,
    "the page must tell the native side when the answer changes");
}

console.log("Volume keys drive the remote output; local targets keep the system stream.");
