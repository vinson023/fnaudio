// R582: 离线启动的队列快照。
// 断网时界面是内置的，缺的只有队列——但只有 id 渲染不出任何一行，
// 所以快照必须带最小元数据，且"当前曲找不到"时不能假装可用。

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/offline_queue_policy.js", "utf8");
const sandbox = { globalThis: {}, window: null };
sandbox.window = sandbox;
vm.runInNewContext(source, sandbox);
const policy = sandbox.fnAudioOfflineQueue;

const queue = [
  { id: "a", title: "Alpha", artist: "A", album: "X", url: "/media/a", duration: 200, format: "FLAC" },
  { id: "b", title: "Beta", artist: "B", url: "/media/b", duration: 180 },
];

// 往返：元数据要活着，播放器才有东西可渲染
{
  const raw = policy.encode({ queue, current: "b", repeat: "all", shuffle: true });
  const back = policy.decode(raw);
  assert.equal(back.items.length, 2);
  assert.equal(back.items[1].title, "Beta");
  assert.equal(back.items[0].url, "/media/a");
  assert.equal(back.current, "b");
  assert.equal(back.repeat, "all");
  assert.equal(back.shuffle, true);
  assert.equal(policy.indexOfCurrent(back), 1);
  assert.equal(policy.isUsable(back), true);
}

// 只存 id 的旧格式（v1）不再被当成可用快照
{
  const legacy = JSON.stringify({ ids: ["a", "b"], current: "a" });
  assert.equal(policy.decode(legacy), null, "旧格式没有元数据，恢复出来是空行");
}

// 当前曲不在快照里 → 不可用（否则恢复出一排点了会失败的行）
{
  const raw = policy.encode({ queue, current: "zzz" });
  const back = policy.decode(raw);
  assert.equal(policy.indexOfCurrent(back), -1);
  assert.equal(policy.isUsable(back), false);
}

// 空队列 / 脏输入
{
  assert.equal(policy.decode(""), null);
  assert.equal(policy.decode("{"), null);
  assert.equal(policy.decode(JSON.stringify({ v: 2, items: [] })), null);
  assert.equal(policy.isUsable(null), false);
  const raw = policy.encode({ queue: [null, { title: "没有 id" }], current: "a" });
  assert.equal(policy.decode(raw), null, "没有 id 的条目要丢掉，剩下为空即不可用");
}

// 上限：快照不会无限长
{
  const big = Array.from({ length: policy.MAX_ITEMS + 50 }, (_, i) => ({ id: "t" + i, title: "T" + i }));
  const back = policy.decode(policy.encode({ queue: big, current: "t0" }));
  assert.equal(back.items.length, policy.MAX_ITEMS);
}

// 接线：启动失败要恢复、离线时 next/prev 走本地、横幅要出现
{
  const app = fs.readFileSync("app/ui/app.js", "utf8");
  assert.match(app, /function restoreOfflineQueue\(\)/, "要有离线恢复函数");
  assert.match(app, /restoreOfflineQueue\(\);/, "启动失败分支要调用它");
  assert.match(app, /state\.offline && \(action === "next" \|\| action === "previous"\)/, "离线时不能等服务端回答下一首");
  assert.match(app, /showOfflineBanner\(/, "要告诉用户现在是离线");
  assert.match(app, /globalThis\.fnAudioOfflineQueue/, "要取到离线队列模块");
  assert.match(app, /policy\.encode\(\{/, "快照要带元数据");
  const html = fs.readFileSync("app/ui/index.html", "utf8");
  assert.ok(html.indexOf("offline_queue_policy.js") >= 0, "index.html 要加载它");
  assert.ok(html.indexOf("offline_queue_policy.js") < html.indexOf("app.js?"), "必须早于 app.js");
}

console.log("Offline queue regression checks passed.");
