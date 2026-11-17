// R577: 曲间空档的度量（P1-2 预热 / P2-1 衔接都靠这个数说话）。
// 之前没人量过，只能猜；现在样本在客户端收，随时可读。

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/playback_gap_stats.js", "utf8");
const sandbox = { globalThis: {}, window: null };
sandbox.window = sandbox;
vm.runInNewContext(source, sandbox);
const stats = sandbox.fnAudioGapStats;

// 只收合法样本
{
  let list = [];
  list = stats.push(list, 120);
  list = stats.push(list, "88");
  list = stats.push(list, -5);       // 负数丢掉
  list = stats.push(list, NaN);      // 非数字丢掉
  list = stats.push(list, null);
  assert.deepEqual([...list], [120, 88], "只留有限非负数并取整");
}

// 有上限，不会无限增长
{
  let list = [];
  for (let i = 0; i < stats.MAX_SAMPLES + 7; i += 1) list = stats.push(list, i * 10);
  assert.equal(list.length, stats.MAX_SAMPLES);
  assert.equal(list[list.length - 1], (stats.MAX_SAMPLES + 6) * 10, "保留最近的一批");
}

// 中位数 / p95
{
  const summary = stats.summarize([300, 100, 200, 50, 400]);
  assert.equal(summary.count, 5);
  assert.equal(summary.median, 200);
  assert.equal(summary.max, 400);
  assert.ok(summary.p95 >= 300 && summary.p95 <= 400, "p95 落在尾部");
  assert.deepEqual({ ...stats.summarize([]) }, { count: 0, median: null, p95: null, max: null });
  assert.equal(stats.summarize(["x", -1]).count, 0, "脏样本不算数");
}

// 接线：放完记时刻、出声算差、暴露报告
{
  const app = fs.readFileSync("app/ui/app.js", "utf8");
  assert.match(app, /state\.gapStartedAt = .*performance\.now/, "onended 要记时刻");
  assert.match(app, /stats\.push\(state\.gapSamples/, "onplaying 要收样本");
  assert.match(app, /window\.fnAudioGapReport = /, "要能读报告");
  const html = fs.readFileSync("app/ui/index.html", "utf8");
  assert.ok(html.indexOf("playback_gap_stats.js") >= 0, "index.html 要加载它");
  assert.ok(html.indexOf("playback_gap_stats.js") < html.indexOf("app.js?"), "必须早于 app.js");
}

console.log("Playback gap stats regression checks passed.");
