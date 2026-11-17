// R574: 播放错误分流（P0）。原来只处理 DSD，其它错误什么都不做——元素停住、
// 进度条不动，用户看到的是"卡了"。Audio Station 的做法是"格式错就提示，
// 其它自动下一首"，这里连同"连续失败上限"一起钉住，防止坏文件把整库刷一遍。

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/media_error_policy.js", "utf8");
const sandbox = { globalThis: {}, window: null };
sandbox.window = sandbox;
vm.runInNewContext(source, sandbox);
const policy = sandbox.fnAudioMediaErrorPolicy;

assert.equal(policy.MAX_CONSECUTIVE, 3, "上限是 3 首，改它要同时改文档与测试");

// 格式层面根本放不了的东西：明说，别假装重试。
{
  assert.equal(policy.decide({ isDsd: true, hasNext: true, streak: 0 }), "dsd-unsupported");
  assert.equal(policy.decide({ isDsd: true, hasNext: false, streak: 9 }), "dsd-unsupported",
    "DSD 优先于任何其它判断");
}

// 队尾没有下一首：只能停。
{
  assert.equal(policy.decide({ isDsd: false, hasNext: false, streak: 0 }), "stop");
}

// 还有下一首且没到上限：自动跳。
{
  for (const streak of [0, 1, 2]) {
    assert.equal(policy.decide({ hasNext: true, streak }), "next", "streak=" + streak);
  }
}

// 到上限：停，不再跳。
{
  for (const streak of [3, 4, 99]) {
    assert.equal(policy.decide({ hasNext: true, streak }), "stop", "streak=" + streak);
  }
}

// 脏输入不能把判断带偏。
{
  assert.equal(policy.decide({}), "stop", "缺 hasNext 时按没有下一首处理");
  assert.equal(policy.decide({ hasNext: true, streak: -5 }), "next", "负 streak 当作 0");
  assert.equal(policy.decide({ hasNext: true, streak: "abc" }), "next", "非数字 streak 当作 0");
  assert.equal(policy.decide(null), "stop", "null 也要能处理");
}

// MediaError.code 的语义要能读懂，日志里才看得出是哪类失败。
{
  assert.equal(policy.classify(1), "aborted");
  assert.equal(policy.classify(2), "network");
  assert.equal(policy.classify(3), "decode");
  assert.equal(policy.classify(4), "src-not-supported");
  assert.equal(policy.classify(0), "unknown");
  assert.equal(policy.classify(undefined), "unknown");
}

// 接线检查：app.js 真的调用了它，index.html 真的加载了它。
{
  const app = fs.readFileSync("app/ui/app.js", "utf8");
  assert.match(app, /fnAudioMediaErrorPolicy/, "app.js must consult the policy");
  assert.match(app, /audio\.onerror = \(\) => \{/, "the error handler must stay wired");
  assert.match(app, /action === "next"/, "the handler must act on the 'next' branch");
  assert.match(app, /localErrorStreak/, "the streak must be tracked on state");
  const html = fs.readFileSync("app/ui/index.html", "utf8");
  assert.match(html, /media_error_policy\.js/, "index.html must load the policy before app.js");
  assert.ok(html.indexOf("media_error_policy.js") < html.indexOf("app.js?"),
    "the policy has to be parsed before app.js uses it");
}

// P0-2：坏文件名单。记住一次，下次直接跳过；重新放出来就除名（自愈）。
{
  let list = [];
  list = policy.markUnplayable(list, "x");
  list = policy.markUnplayable(list, "y");
  assert.deepEqual([...list], ["y", "x"], "最近失败的排在最前");
  list = policy.markUnplayable(list, "x");
  assert.equal(list.length, 2, "重复标记不产生重复项");
  assert.equal(list[0], "x", "再次失败会挪到最前");
  assert.equal(policy.isUnplayable(list, "x"), true);
  assert.equal(policy.isUnplayable(list, "z"), false);
  assert.deepEqual([...policy.forgetUnplayable(list, "x")], ["y"], "放出来就除名");
  assert.equal(policy.markUnplayable([], "").length, 0, "空 id 不记");
  const many = Array.from({ length: policy.MAX_UNPLAYABLE + 20 }, (_, i) => "t" + i);
  const capped = many.reduce((acc, id) => policy.markUnplayable(acc, id), []);
  assert.equal(capped.length, policy.MAX_UNPLAYABLE, "名单有上限，不会无限增长");
}

// 自动续播时跳过这些曲目；循环=全部才回绕。
{
  const ids = ["a", "b", "c", "d"];
  const bad = ["b", "c"];
  assert.equal(policy.nextPlayableIndex(ids, bad, 0, false), 0);
  assert.equal(policy.nextPlayableIndex(ids, bad, 1, false), 3, "从 b 开始要跳到 d");
  assert.equal(policy.nextPlayableIndex(ids, ["a", "b", "c", "d"], 0, true), -1, "全坏就返回 -1");
  assert.equal(policy.nextPlayableIndex([], [], 0, true), -1, "空队列返回 -1");
  assert.equal(policy.nextPlayableIndex(ids, [], 9, false), 3, "越界起点要夹回末尾，而不是越界访问");
}

// 接线检查：自动续播与预热都必须真的接上，否则策略只是摆设。
{
  const app = fs.readFileSync("app/ui/app.js", "utf8");
  assert.match(app, /state\.autoAdvancing = true/, "onended 要标记自动续播");
  assert.match(app, /policy\.nextPlayableIndex\(/, "自动续播要用策略挑下一首");
  assert.match(app, /rememberUnplayable\(/, "失败要记名单");
  assert.match(app, /forgetUnplayable\(/, "成功要除名");
  assert.match(app, /preheatUpcomingStream\(/, "下一首要预热连接");
  assert.match(app, /dataset\.preheat = "1"/, "预热元素要能辨认");
}

console.log("Media error policy regression checks passed.");
