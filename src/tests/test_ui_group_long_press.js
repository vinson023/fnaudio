// R504 —— 文件夹 / 专辑 / 歌手 / 作曲者 / 类型这几类分组行，手机上要能「长按出菜单」。
//
// R499 已经把「播放」放回分组右键菜单，桌面一直可用；但分组行的 `contextmenu` 在
// 760px 以下直接 return，而分组行又没有歌曲行那样的长按计时器——于是飞牛 App 与
// 安卓 App 里按住专辑 / 歌手 / 类型一行，什么都不发生。本轮补上长按，并把「其他
// 分类列表」这半个问题分成两族：
//
//   A. 分组行列表（文件夹 / 专辑 / 歌手 / 作曲者 / 类型）：行本身就代表一叠歌，
//      入口是右键（桌面）与长按（手机），动作是同一个菜单里的「播放」。
//   B. 平铺歌曲列表（全部音乐 / DSD / 最近添加 / 随机 100 首 / 播放列表 / 收藏 /
//      当前队列）：没有行可以按。R504 曾在列表顶部放「播放全部」，R508 按负责人
//      要求撤掉——现在这些列表只剩计数（播放列表与队列另带自己的删除 / 清空）。
//
// 这个文件钉三件事：
//   1. 长按只在手机宽度 + 手指 + 主键时成立，鼠标与桌面宽度不许抢跑；
//   2. 长按抬起后的那次 click 必须被吃掉 —— 否则专辑行会被「打开专辑」，菜单刚
//      弹出就被导航走，看起来像长按没生效；
//   3. 「播放全部」一个都不许有：R508 撤掉列表顶部那批，R511 把详情页与分类头
//      剩下的三处也撤了，连选择器、类名与回调一起消失。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");

function sourceBetween(start, end) {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from);
  assert.ok(from >= 0 && to > from, `expected ${start} before ${end}; re-read app.js before editing this test`);
  return source.slice(from, to);
}

// --- 1. 分组行的 contextmenu 不许再因为「手机宽度」就不干活 -------------------
const groupRowBinding = sourceBetween("document.querySelectorAll(\"[data-group-row]\").forEach(row => {", "document.querySelectorAll(\"[data-group-back]\")");
assert.ok(groupRowBinding.includes("row.oncontextmenu"), "group rows must keep a contextmenu handler");
assert.doesNotMatch(
  groupRowBinding.slice(groupRowBinding.indexOf("row.oncontextmenu")),
  /if \(window\.matchMedia\("\(max-width: 760px\)"\)\.matches\) return;/,
  "the phone used to be dropped here; a hold on a phone now has to reach the same menu",
);
assert.match(
  groupRowBinding,
  /if \(shouldSuppressGroupClick\(row\.dataset\.groupKey\)\)/,
  "a finished hold also fires a click; the row must swallow it before opening",
);
const openAt = groupRowBinding.indexOf("openGroupRow(row)");
const guardAt = groupRowBinding.indexOf("shouldSuppressGroupClick(row.dataset.groupKey)");
assert.ok(guardAt >= 0 && guardAt < openAt, "the suppression guard has to run before the row opens");

// --- 2. 长按手势：宽度 / 输入源 / 位移三条闸门 -------------------------------
function loadGesture(options = {}) {
  const body = sourceBetween("function cancelGroupLongPress", "function bindTrackListInteractions");
  const events = [];
  const timers = [];
  const context = {
    window: {
      matchMedia: () => ({ matches: options.mobile === true }),
      setTimeout: (fn, ms) => { const handle = { fn, ms, id: timers.length + 1 }; timers.push(handle); return handle.id; },
      clearTimeout: () => {},
    },
    Date: { now: () => (options.now === undefined ? 1000 : options.now) },
    Math,
    GROUP_LONG_PRESS_DURATION_MS: 550,
    GROUP_LONG_PRESS_MOVE_THRESHOLD_PX: 10,
    setGroupSelection: keys => events.push({ type: "select", keys }),
    openGroupContextMenu: (key, x, y) => events.push({ type: "menu", key, x, y }),
    activeGroupLongPress: null,
    suppressedGroupClick: { groupKey: "", until: 0 },
  };
  vm.createContext(context);
  vm.runInContext(`${body}`, context);
  return { context, events, timers };
}

// vm 里造出来的对象与原 realm 的原型不同，deepEqual 会先比原型；这里只比内容。
const plain = value => JSON.parse(JSON.stringify(value));

function row(key = "group:albums:Release") {
  return { isConnected: true, dataset: { groupKey: key } };
}

function pointer(overrides = {}) {
  return { pointerId: 7, pointerType: "touch", button: 0, clientX: 120, clientY: 240, ...overrides };
}

// 桌面宽度：长按必须一个计时器都不排队（右键才是桌面的入口）。
{
  const { context, events, timers } = loadGesture({ mobile: false });
  context.startGroupLongPress(row(), pointer());
  assert.equal(timers.length, 0, "desktop must not start a hold timer");
  assert.deepEqual(plain(events), []);
}

// 鼠标：哪怕是窄窗口（手机投屏、桌面缩放）也不该由按住触发。
{
  const { context, timers } = loadGesture({ mobile: true });
  context.startGroupLongPress(row(), pointer({ pointerType: "mouse" }));
  assert.equal(timers.length, 0, "a mouse must not start a hold");
}

// 手机 + 手指：550ms 后选中该行并就地弹出分组菜单。
{
  const { context, events, timers } = loadGesture({ mobile: true });
  const target = row();
  context.startGroupLongPress(target, pointer({ clientX: 88, clientY: 512 }));
  assert.equal(timers.length, 1, "a phone hold must schedule exactly one timer");
  assert.equal(timers[0].ms, 550, "the hold duration has to match the song rows");
  timers[0].fn();
  assert.deepEqual(plain(events), [
    { type: "select", keys: ["group:albums:Release"] },
    { type: "menu", key: "group:albums:Release", x: 88, y: 512 },
  ]);
  assert.equal(context.shouldSuppressGroupClick("group:albums:Release"), true, "the release click must be swallowed");
  assert.equal(context.shouldSuppressGroupClick("group:albums:Other"), false, "the suppression is per row");
}

// 手指移动超过阈值：这一下是滚动，不是长按。
{
  const { context, events, timers } = loadGesture({ mobile: true });
  context.startGroupLongPress(row(), pointer({ clientX: 100, clientY: 500 }));
  context.moveGroupLongPress(pointer({ pointerId: 7, clientX: 100, clientY: 540 }));
  timers[0].fn();
  assert.deepEqual(plain(events), [], "a scrolled hold must not open a menu");
}

// 行在计时器触发前被重新渲染掉（列表刷新）：不许对一个已经脱离文档的行开菜单。
{
  const { context, events, timers } = loadGesture({ mobile: true });
  const target = row();
  context.startGroupLongPress(target, pointer());
  target.isConnected = false;
  timers[0].fn();
  assert.deepEqual(plain(events), [], "a detached row must not open a menu");
}

// 抬起时确认「已触发」，这样才能把随后的 click 挡在事件链上。
{
  const { context, events, timers } = loadGesture({ mobile: true });
  context.startGroupLongPress(row(), pointer());
  timers[0].fn();
  const prevented = [];
  context.finishGroupLongPress({ pointerId: 7, preventDefault: () => prevented.push("preventDefault"), stopPropagation: () => prevented.push("stop") });
  assert.deepEqual(prevented, ["preventDefault", "stop"], "a triggered hold has to consume the release");
  assert.ok(events.some(event => event.type === "menu"));
}

// 没有触发过长按的抬起（普通点击）不许被吃掉。
{
  const { context, timers } = loadGesture({ mobile: true });
  context.startGroupLongPress(row(), pointer());
  const prevented = [];
  context.finishGroupLongPress({ pointerId: 7, preventDefault: () => prevented.push("preventDefault"), stopPropagation: () => prevented.push("stop") });
  assert.deepEqual(prevented, [], "a plain tap must pass through");
  assert.equal(timers.length, 1);
}

// --- 3. R508：列表顶部不再有「播放全部」 -------------------------------------
// 负责人「取消掉所有列表里面的『播放全部』按钮」。播放列表 / 收藏 / 队列原来就有
// 的计数条保留（删除播放列表 / 清空队列也挂在它上面），不再带按钮；平铺列表整条
// 工具条连同 #listToolbar 一起撤掉。整页播放入口只剩详情页与分类头那三处。
assert.equal(source.includes("FLAT_PLAY_ALL_VIEWS"), false, "the flat play-all view set is gone");
assert.equal(source.includes("playAllBar"), false, "the constructor that injected the button is gone");
assert.equal(source.includes("renderFlatListToolbar"), false, "the flat toolbar renderer is gone");

const countBarDef = sourceBetween("const countBar =", "const playlistToolbar =");
assert.match(countBarDef, /class="playlist-toolbar"/, "the count bar itself stays for playlists / favorites / queue");
assert.equal(/data-play-all/.test(countBarDef), false, "the shared bar must not carry a 播放全部 button");

// 三个调用点：播放列表 / 收藏 / 队列。平铺视图那条分支已经删掉。
const toolbarChain = sourceBetween("const playlistToolbar =", "const listHtml =");
const barCalls = toolbarChain.split("\n").filter(line => line.includes("countBar("));
assert.equal(barCalls.length, 3, `playlist / favorites / queue must all route through countBar, found ${barCalls.length}`);
barCalls.forEach(line => assert.equal(/data-play-all/.test(line), false, "no call site may put 播放全部 back"));
assert.match(toolbarChain, /data-delete-playlist/, "the playlist count bar keeps 删除播放列表");
assert.match(toolbarChain, /data-clear-queue/, "the queue count bar keeps 清空队列");

// 边界：R508 当时把专辑详情、类型详情面包屑与分类详情头三处留了下来；负责人看到
// 之后在 R511 说「还是有些地方有『播放全部』按钮」，于是这三处也一并撤掉——现在
// 四类位置一个都不剩，包括共用的 data-play-all 选择器与它的类名。
const albumDetail = sourceBetween("function renderAlbumDetail", "function trackRowSelectionKey");
assert.equal(albumDetail.includes("data-play-all"), false, "the album detail breadcrumb lost its button in R511");
const genreTracks = sourceBetween("function renderGenreTracks", "function renderFolders");
assert.equal(genreTracks.includes("data-play-all"), false, "the genre detail breadcrumb lost its button in R511");
assert.equal(toolbarChain.includes("data-play-all"), false, "the category detail header lost its button in R511");
assert.equal(source.includes("data-play-all"), false, "no 播放全部 button survives anywhere in app.js");
assert.equal(source.includes("breadcrumb-play-all"), false, "nor the class that styled it");

// --- 4. 平铺列表不再有独立工具条节点 -----------------------------------------
// R504 把它挂在 #trackList 外面是为了保住键控复用（混进列表会让
// `nextKeySet.size === next.length` 不成立，退化成整表替换）。节点现在整个撤了，
// 这条继续钉住「不许把任何工具条塞回列表」。
const listMarkup = sourceBetween("const listHtml =", "if (!window.matchMedia");
assert.equal(listMarkup.includes("flatToolbar"), false, "no toolbar may be spliced into #trackList or keyed row reuse dies");
// 注意别用 includes("listToolbar")：`playlistToolbar` 里含有这个子串。
assert.equal(/\blistToolbar\b/.test(listMarkup), false, "the flat container is gone from the list markup");
const page = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "index.html"), "utf8");
assert.equal(page.includes("listToolbar"), false, "index.html no longer carries the flat toolbar container");
assert.equal(page.includes("list-toolbar"), false, "nor its class");

console.log("group long press + list toolbars: ok");
