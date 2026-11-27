// R635 的判别测试：远端音量必须在拖动过程中就发出去。
//
// 负责人的原话是「调节音量的时候响应会慢半拍，不是那种实时响应」。当时的实现
// 把「预览 / 提交」照搬自进度条：`oninput` 只动轨道，`onchange`/`pointerup`
// 才发一次 POST。拖动三秒就等于三秒没有任何声音变化，松手才跳一下。
//
// 现在的约束有两条，缺一条都会退回原样：
//   1. `oninput` 在远端目标上要真的发命令，而不是只改本地轨道；
//   2. 同时在飞的请求最多一个，后到的值覆盖先到的（拖动不会被旧值堵住）。
// 这里用 vm 把四个函数从 app.js 里抽出来跑，验证的是行为，不是字符串。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join("app", "ui", "app.js"), "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

const volumeState = app.match(/^const remoteVolume = \{[^}]*\};$/m);
assert.ok(volumeState, "the in-flight volume state must stay a single top-level literal");

const source = [
  volumeState[0],
  functionSource("volumePercentOf"),
  functionSource("flushRemoteVolume"),
  functionSource("queueRemoteVolume"),
  functionSource("applyVolumeToTarget"),
].join("\n");

function harness({ remote = true, failFirst = false } = {}) {
  const calls = [];
  const context = {
    Number,
    Math,
    console,
    audio: { volume: 1 },
    isRemoteTarget: () => remote,
    nativePlaybackAvailable: () => false,
    nativePlaybackCall() {},
    setTimeout: (fn) => { fn(); return 0; },  // 完成回调里的“下一帧”直接执行
    remoteControl(action, value, quiet) {
      const call = { action, value, quiet };
      calls.push(call);
      if (failFirst && calls.length === 1) return Promise.reject(new Error("boom"));
      return Promise.resolve(true);
    },
  };
  vm.runInNewContext(`${source}\nthis.api = { applyVolumeToTarget, queueRemoteVolume, flushRemoteVolume, volumePercentOf };`, context);
  return { api: context.api, calls, context };
}

(async () => {
  // 1) 拖动过程中的每一次 oninput 都必须能到达远端；只有最后一个值留在最终状态。
  {
    const h = harness();
    h.api.queueRemoteVolume(30);
    h.api.queueRemoteVolume(45);
    h.api.queueRemoteVolume(60);
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.calls.length >= 2, true, "a drag must produce more than the release command");
    assert.equal(h.calls[h.calls.length - 1].value, 60, "the newest value must win, not the oldest queued one");
    assert.ok(!h.calls.some(call => call.value === 45 && h.calls.indexOf(call) === h.calls.length - 1),
      "a superseded value must not be the last thing written");
    assert.equal(h.calls.every(call => call.action === "volume"), true);
  }

  // 2) 中途的值不能堆积：三次 input 在第一次请求还没回来时到达，最多补发一次。
  {
    const h = harness();
    const gate = [];
    h.context.remoteControl = (action, value, quiet) => {
      h.calls.push({ action, value, quiet });
      return new Promise(resolve => gate.push(() => resolve(true)));
    };
    h.api.queueRemoteVolume(10);
    h.api.queueRemoteVolume(20);
    h.api.queueRemoteVolume(30);
    h.api.queueRemoteVolume(40);
    assert.equal(h.calls.length, 1, "only one request may be in flight");
    assert.equal(h.calls[0].value, 10);
    gate.shift()();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.calls.length, 2, "the queued values collapse into one follow-up");
    assert.equal(h.calls[1].value, 40, "the follow-up must carry the newest value");
  }

  // 3) 松开手是最后一次提交，并且这一次失败要能被看见（quiet=false）。
  {
    const h = harness();
    h.api.applyVolumeToTarget(0);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.calls[0].value, 0, "0% must be sent, not swallowed as falsy");
    assert.equal(h.calls[0].quiet, false, "the final commit must surface a failure");
  }

  // 4) 本地目标不走远端：音量交给 <audio>，一个请求都不发。
  {
    const h = harness({ remote: false });
    h.api.applyVolumeToTarget(0.42);
    assert.equal(h.calls.length, 0, "a local target must not POST a remote volume");
    assert.ok(Math.abs(h.context.audio.volume - 0.42) < 1e-9, String(h.context.audio.volume));
  }

  // 5) 请求失败后不能卡住：状态要复位，下一次输入照常发出。
  {
    const h = harness({ failFirst: true });
    h.api.queueRemoteVolume(70);
    await new Promise(resolve => setImmediate(resolve));
    h.api.queueRemoteVolume(80);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.calls.length, 2, "a failed write must not wedge the queue");
    assert.equal(h.calls[1].value, 80);
  }

  // 6) 结构面：oninput 必须把远端音量交给队列，而不是继续“松手才提交”。
  const oninput = app.match(/\$\("volume"\)\.oninput = e => \{[\s\S]*?\n\};/);
  assert.ok(oninput, 'the #volume input handler must stay extractable');
  assert.match(oninput[0], /isRemoteTarget\(\)[\s\S]*queueRemoteVolume\(/, "dragging must send volume for a remote target");
  assert.doesNotMatch(app, /A remote target is committed on release/,
    "the old commit-on-release comment described behaviour that must not come back");

  console.log("Remote volume streams during the drag, newest value wins, one request in flight.");
})();
