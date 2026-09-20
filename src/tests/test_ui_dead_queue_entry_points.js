// L71 的判别测试：三个死函数连同 queue-play 别名必须已经消失，且右键菜单的
// 队列入口仍然真实可达。删错方向（把活代码一起删掉）与留死代码都会红。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const UI_DIR = "app/ui";
const app = fs.readFileSync(path.join(UI_DIR, "app.js"), "utf8");

function uiSources() {
  return fs.readdirSync(UI_DIR)
    .filter(name => /\.(js|html)$/.test(name))
    .map(name => [name, fs.readFileSync(path.join(UI_DIR, name), "utf8")]);
}

// 1) 死码确实消失：不是「调用点为 0」，而是全 UI 树里连名字都不再出现。
["addQueue", "addQueueAndPlay", "playFolder"].forEach(name => {
  uiSources().forEach(([file, text]) => {
    assert.doesNotMatch(text, new RegExp("\\b" + name + "\\b"), `${name} must stay deleted (${file})`);
  });
});
assert.doesNotMatch(app, /"queue-play"/, "The queue-play alias must go with its dead entry point");
// 2) 活路径仍然可达：runTrackAction 真跑，而不是只对着源码做正则。
function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

const calls = [];
const record = name => (...args) => { calls.push([name, args]); };
const state = { actionTrackId: "t7" };
const context = {
  state,
  String, Number, Math, Boolean, Array, JSON,
  selectedTrackIds: () => ["t7"],
  closeTrackActionDialog: record("closeActionDialog"),
  closeTrackContextMenu: record("closeContextMenu"),
  playSelectedTracks: record("playSelectedTracks"),
  playFromCurrentTrack: record("playFromCurrentTrack"),
  addSelectedToQueue: record("addSelectedToQueue"),
  toggleSelectedFavorites: record("toggleSelectedFavorites"),
  addSelectedFavorites: record("addSelectedFavorites"),
  openPlaylistDialogForTracks: record("openPlaylistDialog"),
  insertSelectedTracks: record("insertSelectedTracks"),
  showTrackInformation: record("showTrackInformation"),
  showTrackMetadataCandidate: record("showTrackMetadataCandidate"),
  openContainingFolder: record("openContainingFolder"),
  shareTrack: record("shareTrack"),
  openDeleteTrackDialog: record("openDeleteTrackDialog"),
  removeTrackFromQueue: record("removeTrackFromQueue"),
  removeFavorite: record("removeFavorite"),
  removeTrackFromCurrentPlaylist: record("removeTrackFromCurrentPlaylist"),
};
vm.createContext(context);
vm.runInContext([functionSource("runTrackAction"), "globalThis.run = runTrackAction;"].join("\n"), context);

context.run("queue");
assert.deepEqual(
  calls.filter(([name]) => name === "addSelectedToQueue").map(([, args]) => args),
  [[["t7"]]],
  "The context-menu queue entry must still enqueue the selection exactly once"
);
assert.ok(calls.some(([name]) => name === "closeContextMenu"), "Routing must still close the menu");
calls.length = 0;
context.run("queue-play");
assert.deepEqual(calls.filter(([name]) => !/^close/.test(name)), [], "queue-play must no longer route anywhere");
calls.length = 0;
context.run("play");
assert.ok(calls.some(([name]) => name === "playSelectedTracks"), "play must still be routed");

// 3) 菜单按钮与路由器必须一对一咬合：新增按钮却忘了处理分支、或处理分支
//    却没有生产者（本次清掉的 queue-play 就是后者），都算缺陷。
const routerSource = functionSource("runTrackAction");
const handled = new Set([...routerSource.matchAll(/action === "([a-z-]+)"/g)].map(m => m[1]));
const produced = new Set([...app.matchAll(/actionButton\([^,]+,\s*"([a-z-]+)"/g)].map(m => m[1]));
assert.ok(produced.size >= 10, "The action-menu producers must still be discoverable");
produced.forEach(action => {
  assert.ok(handled.has(action), `data-track-action "${action}" has no branch in runTrackAction`);
});
// 反方向同样要咬住：被处理却没人生产的分支就是死码（本轮清掉的 queue-play
// 正是这一类）。唯一登记在册的例外是 favorite-add —— 它连着的
// addSelectedFavorites 仍是活函数，负责人未授权删除，只在 TODO.md 记录现状。
assert.deepEqual(
  [...handled].filter(action => !produced.has(action)),
  ["favorite-add"],
  "A handled action with no producer is dead code; favorite-add is the only registered exception"
);

// 4) 删除不得把仍然活着的判定一起带走。
const isPlayingNowCalls = (app.match(/\bisPlayingNow\(/g) || []).length;
assert.ok(isPlayingNowCalls >= 3, `isPlayingNow must keep its live callers (found ${isPlayingNowCalls})`);
assert.ok(/\blocalIsPlayingNow\(/.test(app), "The local-only playback probe must survive");
assert.match(routerSource, /addSelectedToQueue\(selected\)/, "Queue routing must keep using the live helper");

console.log("Dead queue entry point regression checks passed.");