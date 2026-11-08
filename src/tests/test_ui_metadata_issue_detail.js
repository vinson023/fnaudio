const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// R519: 「失败 2 · 未匹配 155」没有说清失败的是什么、未匹配的是什么。状态载荷现在
// 带一份有界明细，这个测试锁住两件事：明细本身要能被渲染出来，摘要行要带上按任务
// 类型的拆分，否则计数又会退回成一句没人能处理的话。
const UI_DIR = path.join(__dirname, "..", "app", "ui");
const app = fs.readFileSync(path.join(UI_DIR, "app.js"), "utf8");
const index = fs.readFileSync(path.join(UI_DIR, "index.html"), "utf8");
const css = fs.readFileSync(path.join(UI_DIR, "app.css"), "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `${name} must be declared as an extractable pure helper`);
  return match[0];
}

assert.match(index, /id="metadataLogIssues"/, "the log dialog needs a detail block, not just counters");
assert.match(index, /id="metadataLogIssuesSummary"/);
assert.match(index, /id="metadataLogIssuesList" role="group"/);
assert.match(index, /id="metadataLogIssuesNote"/);
assert.match(app, /function renderMetadataLogIssues\(/, "the detail block needs its own renderer");
assert.match(functionSource("renderMetadataLog"), /renderMetadataLogIssues\(state\.metadataStatus\)/,
  "opening the log must render the detail, not only the counters");
assert.match(functionSource("renderMetadataLogIssues"), /job\.error/, "a failure row must explain why it failed");
assert.match(functionSource("renderMetadataLogIssues"), /job\.title/, "a row without the track name explains nothing");
assert.doesNotMatch(app, /失败 \$\{counts\.failed\} · 未匹配 \$\{counts\.noMatch\} · 待写入/,
  "the bare counter line must not survive as the summary");

// The counters on the pane are the shortest path to the detail, so they open it.
assert.match(functionSource("renderMetadataTaskState"), /item\.dataset\.metadataStatIssues = /,
  "a non-zero failure/no-match counter must be an entry point");
assert.match(app, /openMetadataIssueLog\(\)/);
assert.match(app, /\$\("metadataLogIssuesList"\)\.addEventListener\("click"/,
  "a named track in the detail list must be openable");
assert.match(app, /function openMetadataIssueTrack\(/);

// The copied log has to carry the same names as the dialog.
assert.match(functionSource("metadataLogText"), /state\.metadataStatus\?\.issue_jobs/);
assert.match(functionSource("metadataLogText"), /失败与未匹配明细/);
assert.match(functionSource("loadMetadataStatus"), /metadataIssueSampleText\(liveStatus\)/,
  "the first status line must name a few of the affected tracks");

const labelsSource = app.match(/const METADATA_JOB_TYPE_LABELS = Object\.freeze\(\{[\s\S]*?\}\);/);
assert.ok(labelsSource, "the job-type labels must stay one frozen table");
const sandbox = {};
vm.runInNewContext([
  labelsSource[0],
  functionSource("metadataTaskCounts"),
  functionSource("metadataJobTypeLabel"),
  functionSource("metadataIssueTypes"),
  functionSource("metadataIssueTypeText"),
  functionSource("metadataIssueCountersText"),
  functionSource("metadataIssueSampleText"),
].join("\n"), sandbox);

const status = {
  jobs: { failed: 2, no_match: 155, pending: 0, retry: 0, running: 0 },
  job_types: { lyrics: { pending: 0 }, tag_write: { pending: 0 } },
  issue_counts: {
    lyrics: { failed: 0, no_match: 153 },
    track_artwork: { failed: 0, no_match: 2 },
    tag_write: { failed: 2, no_match: 0 },
  },
  issue_jobs: [
    { job_type: "tag_write", status: "failed", title: "晴天", artist: "周杰伦", attempts: 3, error: "permission denied" },
    { job_type: "lyrics", status: "no_match", title: "夜的第七章", artist: "周杰伦", attempts: 1, error: "" },
  ],
};

assert.equal(
  sandbox.metadataIssueCountersText(status),
  "失败 2（Tag 写回 2） · 未匹配 155（歌词 153、封面 2）",
  "each counter must name the job types behind it",
);
assert.equal(
  sandbox.metadataIssueSampleText(status),
  "晴天 - 周杰伦（Tag 写回失败：permission denied）、夜的第七章 - 周杰伦（歌词未匹配）",
  "the sample line must name tracks and the reason, not repeat the count",
);
assert.equal(
  sandbox.metadataIssueCountersText({ jobs: { failed: 0, no_match: 0 } }),
  "失败 0 · 未匹配 0",
  "an empty queue keeps the plain counters without empty parentheses",
);
assert.equal(sandbox.metadataJobTypeLabel("track_artwork"), "封面");
assert.equal(sandbox.metadataJobTypeLabel("custom_lane"), "custom_lane",
  "an unknown lane must still be named instead of silently dropped");
assert.equal(sandbox.metadataIssueTypeText({ lyrics: { no_match: 153 } }, "failed"), "");
assert.equal(
  sandbox.metadataIssueTypeText({ lyrics: { no_match: 153 }, track_artwork: { no_match: 2 } }, "no_match"),
  "歌词 153、封面 2",
  "the breakdown is ordered by count so the dominant lane reads first",
);

// The detail rows are a four-column grid on desktop and wrap the reason on phones.
assert.match(css, /\.metadata-log-issue\{[^}]*grid-template-columns/);
assert.match(css, /\.metadata-log-issue\.is-failed \.metadata-log-issue-badge/);
assert.match(css, /@media \(max-width:560px\)\{[\s\S]*\.metadata-log-issue-reason\{grid-column:1\/-1\}/,
  "a 390px phone must not squeeze the reason into a 60px column");

console.log("Metadata issue detail UI regression checks passed.");
