// R636：进度条的三件事必须一起成立，少一条就退回“定位不准 / 误触歌词”。
//
//   1. 精度：`step` 默认 1，5 分钟的歌一格 3 秒——用 0.01 把分辨率降到 0.03 秒级；
//   2. 命中：指针由行容器统一接管（input 只负责画），轨道上下留出 8px 余量，
//      正好吃掉信息卡底部那条最容易蹭到的边；
//   3. 一次手势只提交一次 seek（onchange/pointerup/touchend 三处都提交过一次）。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join("app", "ui", "app.js"), "utf8");
const index = fs.readFileSync(path.join("app", "ui", "index.html"), "utf8");
const css = fs.readFileSync(path.join("app", "ui", "app.css"), "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

const gestureState = app.match(/^const seekGesture = \{[^}]*\};$/m);
assert.ok(gestureState, "the seek gesture state must stay a single top-level literal");
const thumbConst = app.match(/^const SEEK_THUMB_RADIUS = \d+;$/m);
assert.ok(thumbConst, "the thumb radius must stay a named constant");

function harness({ width = 200, left = 0 } = {}) {
  const calls = { commit: [], preview: [], rail: [] };
  const row = {
    classList: { added: [], add(name) { this.added.push(name); }, remove(name) { this.added = this.added.filter(x => x !== name); } },
    setPointerCapture() {},
    releasePointerCapture() {},
    getBoundingClientRect: () => ({ left: 0, width, top: 0, height: 38 }),
  };
  const rail = { value: "0", getBoundingClientRect: () => ({ left, width, top: 0, height: 38 }) };
  const bubble = { style: {}, textContent: "", hidden: true };
  const state = { seeking: false };
  const context = {
    Number, Math, String, Date, console,
    state,
    $: id => (id === "seek" ? rail : id === "progressRow" ? row : id === "seekBubble" ? bubble : null),
    previewSeek: value => calls.preview.push(value),
    commitSeek: value => { calls.commit.push(value); state.seeking = false; },
    seekDuration: () => 300,
    clock: seconds => `${Math.round(seconds)}s`,
    syncPlayerProgress: () => {},
  };
  vm.createContext(context);
  vm.runInContext([
    thumbConst[0],
    gestureState[0],
    functionSource("seekPercentFromClientX"),
    functionSource("setSeekRailValue"),
    functionSource("seekBubbleShow"),
    functionSource("seekBubbleHide"),
    functionSource("seekGestureStart"),
    functionSource("seekGestureMove"),
    functionSource("seekGestureEnd"),
    functionSource("seekGestureCancel"),
    "globalThis.h = { seekPercentFromClientX, seekGestureStart, seekGestureMove, seekGestureEnd, seekGestureCancel };",
  ].join("\n"), context);
  return { h: context.h, calls, rail, row, state };
}

function pointer(clientX, pointerId = 1) {
  return { clientX, pointerId, button: 0, preventDefault() {} };
}

// --- 坐标映射 ---------------------------------------------------------------

{
  // 两端的落点要真的是 0/100：滑块圆心在 [r, width-r] 之间移动。
  const env = harness({ width: 200, left: 40 });
  assert.ok(env.h.seekPercentFromClientX(40) <= 0.01, String(env.h.seekPercentFromClientX(40)));
  assert.ok(env.h.seekPercentFromClientX(240) >= 99.99);
  assert.ok(Math.abs(env.h.seekPercentFromClientX(140) - 50) < 0.5);
  // 超出范围只夹紧，不返回负数或 >100。
  assert.equal(env.h.seekPercentFromClientX(0), 0);
  assert.equal(env.h.seekPercentFromClientX(9999), 100);
}

// --- 一次手势一个提交 -------------------------------------------------------

{
  const env = harness();
  env.h.seekGestureStart(pointer(50));
  assert.equal(env.state.seeking, true, "a drag must mark the position as unconfirmed");
  assert.equal(env.calls.commit.length, 0, "pointerdown must not commit: the release owns that");
  env.h.seekGestureMove(pointer(100));
  env.h.seekGestureMove(pointer(150));
  env.h.seekGestureEnd(pointer(150));
  assert.equal(env.calls.commit.length, 1, "a whole drag must produce exactly one seek");
  assert.ok(env.calls.commit[0] > 70 && env.calls.commit[0] < 80, env.calls.commit[0]);
  assert.equal(env.state.seeking, false);
}

{
  // 点一下不移动也要跳过去（tap-to-seek），这正是“点不准”最常遇到的动作。
  const env = harness();
  env.h.seekGestureStart(pointer(100));
  env.h.seekGestureEnd(pointer(100));
  assert.equal(env.calls.commit.length, 1);
  assert.ok(Math.abs(Number(env.calls.commit[0]) - 50) < 0.5, env.calls.commit[0]);
}

{
  // pointercancel（来电、手势被系统收走）不能提交，也不能把界面留在“正在拖”的状态。
  const env = harness();
  env.h.seekGestureStart(pointer(30));
  env.h.seekGestureCancel();
  assert.equal(env.calls.commit.length, 0);
  assert.equal(env.state.seeking, false);
}

{
  // 拖动时轨道要跟着手指走，否则看起来还是“没反应”。
  const env = harness();
  env.h.seekGestureStart(pointer(50));
  env.h.seekGestureMove(pointer(180));
  assert.equal(Number(env.rail.value) > 80, true, env.rail.value);
}

// --- 结构面 -----------------------------------------------------------------

{
  const seekInput = index.match(/<input id="seek"[^>]*>/);
  assert.ok(seekInput, "the seek input must stay in the page");
  assert.match(seekInput[0], /step="0\.01"/, "1% steps are 3 seconds on a 5-minute track");
  assert.match(index, /id="progressRow"/, "the row is the pointer target");
  assert.match(index, /id="seekBubble"/, "the drag needs a time readout");
}

{
  assert.match(css, /\.progress input\{pointer-events:none!important\}/,
    "the input is paint-only; the row owns the gesture");
  assert.match(css, /\.progress::before\{[^}]*top:-8px/,
    "the hit band has to reach into the card above, where the misses land");
  assert.match(css, /touch-action:none/, "a vertical scroll must not cancel a seek");
}

{
  // 旧的三处提交（onchange/pointerup/touchend）必须收敛：指针手势自己提交。
  assert.doesNotMatch(app, /\$\("seek"\)\.onpointerup/, "pointerup is handled by the gesture, not a second handler");
  assert.doesNotMatch(app, /\$\("seek"\)\.ontouchend/, "touchend is handled by the gesture, not a second handler");
  assert.match(app, /Date\.now\(\) - seekGesture\.committedAt < 400/,
    "a native change right after a pointer commit must be ignored");
  // 信息卡的点击要能被这次手势的余波挡住。
  const info = app.match(/\$\("nowPlayingSummary"\)\.onclick = event => \{[\s\S]*?\};/);
  assert.ok(info, "the now-playing handler must stay a guarded function");
  assert.match(info[0], /seekGesture\.committedAt/, "a thumb that missed the rail must not open lyrics");
}

console.log("Seek rail: 0.01 steps, one commit per gesture, slop over the card edge.");
