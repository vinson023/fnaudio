// R499 —— 文件夹 / 专辑 / 歌手三行的右键菜单重新提供「播放」。
//
// 0.1.172 把分组右键的「播放」与「插播所选项目」一起摘掉，`runGroupAction()` 里的
// `action === "play"` 分支却一直留着：菜单造不出这个动作，所以那行代码两年没有被
// 任何点击触达过。本轮按负责人要求把「播放」放回菜单（只放回这一个，「插播所选
// 项目」保持缺席），于是有三件事必须钉住：
//
//   1. 菜单真的生产 `play`，且仍是第一项 —— 反过来 `runGroupAction` 处理的每个
//      动作都要有生产者，否则又长出一段没人能点的死码；
//   2. 点击后走的是「把已经读到的歌曲直接交给队列」，不是「把 id 交出去再回头查」——
//      条目缓存只有 12,000 条，超过它的文件夹会静默少掉尾部歌曲；
//   3. 专辑行按专辑详情页的曲序（`track_no` 升序）取歌，而不是按专辑名 ——
//      专辑列表的排序键对同一张专辑的每一行都相等，服务端只能退回标题序，
//      于是「播放这张专辑」会从标题排第一的那首开始。
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

// --- 1. 菜单：播放存在且排第一，「插播所选项目」继续缺席 ---------------------
const menuSource = sourceBetween("function groupActionButtons", "function bindGroupActionButtons");
assert.match(menuSource, /groupActionButton\("播放", "play"\)/, "the group menu must produce the play action");
assert.doesNotMatch(menuSource, /groupActionButton\("插播所选项目"/, "insert stays out of the group menu");
assert.ok(
  menuSource.indexOf('groupActionButton("播放", "play")') < menuSource.indexOf('groupActionButton("加入当前队列", "queue")'),
  "播放 must be the first item: it is the one a right-click on a row is expected to do",
);
for (const action of ["play", "queue", "playlist", "open"]) {
  assert.ok(menuSource.includes(`"${action}"`), `the group menu must keep the ${action} entry`);
}

// --- 2. 生产者与路由器必须咬合 ------------------------------------------------
const routerSource = sourceBetween("async function runGroupAction", "function actionButton");
const handled = new Set([...routerSource.matchAll(/action === "([a-z-]+)"/g)].map(match => match[1]));
const produced = new Set([...menuSource.matchAll(/groupActionButton\([^,]+,\s*"([a-z-]+)"/g)].map(match => match[1]));
assert.ok(produced.size >= 4, "the group menu producers must stay discoverable");
produced.forEach(action => assert.ok(handled.has(action), `data-group-action "${action}" has no branch in runGroupAction`));
// 反方向的唯一例外：`insert` 仍被 `runGroupAction` 处理，却自 0.1.172 起没有生产者。
// 它与 `runTrackAction` 的 favorite-add 同类（活函数、无人调用），删不删归负责人定，
// 本轮只把它显式登记在这里；多出第二个孤儿就是新的死码。
assert.deepEqual(
  [...handled].filter(action => !produced.has(action)),
  ["insert"],
  "an unproduced group action is dead code; insert is the only registered exception",
);

// --- 3. 路由：播放把行对象直接交给队列，不回头查缓存 ------------------------
function loadRouter(resolved) {
  const events = [];
  const context = {
    state: { actionGroupKey: "group:albums:Release" },
    String,
    selectedGroupDescriptors: () => [{ key: "group:albums:Release", type: "group", view: "albums", name: "Release" }],
    closeTrackContextMenu: () => events.push(["close"]),
    resolveSelectedGroupTracks: async () => { events.push(["resolve"]); return resolved; },
    alert: message => events.push(["alert", String(message)]),
    playTracks: tracks => events.push(["playTracks", tracks.map(item => item.id)]),
    // R501: queue / playlist take the rows now.  Recording the raw argument is
    // deliberate — "did it hand over rows or ids" is the whole assertion.
    addTracksToQueue: tracks => events.push(["queue", tracks]),
    insertSelectedTracks: ids => events.push(["insert", ids]),
    openPlaylistDialogForTracks: values => events.push(["playlist", values]),
    openGroupRow: () => events.push(["open"]),
    document: { querySelectorAll: () => [] },
  };
  vm.createContext(context);
  vm.runInContext(`${routerSource}; globalThis.run = runGroupAction;`, context);
  return { run: context.run, events };
}

(async () => {
  const tracks = [{ id: "a" }, { id: "b" }, { id: "c" }];
  const play = loadRouter(tracks);
  await play.run("play");
  assert.deepEqual(play.events.filter(([name]) => name === "playTracks"), [["playTracks", ["a", "b", "c"]]],
    "play must hand the resolved rows to the queue, in resolution order");
  assert.deepEqual(play.events.filter(([name]) => name !== "close" && name !== "resolve" && name !== "playTracks"), [],
    "play must not fall through into queue / insert / playlist routing");
  assert.ok(play.events.findIndex(([name]) => name === "close") < play.events.findIndex(([name]) => name === "resolve"),
    "the menu must close before the (multi-second) group resolution starts");

  const empty = loadRouter([]);
  await empty.run("play");
  assert.deepEqual(empty.events.filter(([name]) => name === "alert"), [["alert", "所选项目下没有可播放的歌曲"]],
    "an empty folder or album must say so instead of returning silently");
  assert.equal(empty.events.filter(([name]) => name === "playTracks").length, 0);

  const emptyQueue = loadRouter([]);
  await emptyQueue.run("queue");
  assert.equal(emptyQueue.events.filter(([name]) => name === "alert").length, 0,
    "only play gained the empty-set message; queueing an empty selection stays silent as before");

  const queue = loadRouter(tracks);
  await queue.run("queue");
  const queueEvents = queue.events.filter(([name]) => name === "queue");
  assert.equal(queueEvents.length, 1, "one queue call");
  assert.ok(queueEvents[0][1].every(item => item && typeof item === "object" && item.id),
    "queueing must hand over the resolved rows: re-deriving them from ids is what capped a large set at the item cache");
  assert.deepEqual(queueEvents[0][1].map(item => item.id), ["a", "b", "c"]);

  const playlist = loadRouter(tracks);
  await playlist.run("playlist");
  const playlistEvents = playlist.events.filter(([name]) => name === "playlist");
  assert.equal(playlistEvents.length, 1, "one playlist call");
  assert.ok(playlistEvents[0][1].every(item => item && typeof item === "object" && item.id),
    "the playlist dialog must receive the rows too, or it re-filters them by id when it saves");

  // --- 4. 取歌口径：文件夹整棵子树、专辑按曲序、歌手按歌手 ---------------
  function loadResolver({ groups, view = "albums", creator = "", creatorName = "" }) {
    const queries = [];
    const context = {
      state: { view, groupName: "", pageSize: 120 },
      String, Set, Number,
      URLSearchParams,
      isCreatorView: () => Boolean(creator),
      currentCreatorName: () => creatorName,
      currentQueryParams: () => new URLSearchParams(`paged=1&view=${view}&sort=album&dir=asc`),
      selectedGroupDescriptors: () => groups,
      fetchAllTracksForCurrentView: async (extra, snapshot) => {
        queries.push({ extra, snapshot: Boolean(snapshot) });
        return [{ id: `${extra.folder || extra.album || extra.group}#0` }, { id: "" }];
      },
      fnAudioBatchRequestPool: (items, concurrency, worker) => {
        const started = items.map(item => Promise.resolve().then(() => worker(item)));
        return { get: index => started[index], cancel: () => {} };
      },
    };
    vm.createContext(context);
    vm.runInContext(`${sourceBetween("async function resolveSelectedGroupTracks", "function applyConfirmedQueue")}
      globalThis.resolveTracks = resolveSelectedGroupTracks;`, context);
    return { run: () => context.resolveTracks(""), queries };
  }

  const plainAlbum = loadResolver({ groups: [{ key: "g", type: "group", view: "albums", name: "Release" }] });
  assert.deepEqual(Array.from(await plainAlbum.run(), item => item.id), ["Release#0"],
    "blank ids must be dropped from the resolved queue");
  assert.deepEqual(JSON.parse(JSON.stringify(plainAlbum.queries[0].extra)),
    { view: "albums", group: "Release", sort: "track_no", dir: "asc" },
    "an album row must be read in album-detail order, not in the album list's own sort");
  assert.equal(plainAlbum.queries[0].snapshot, true, "the query snapshot taken before navigation must still be shared");

  const creatorAlbum = loadResolver({ groups: [{ key: "g", type: "group", view: "albums", name: "Release" }], view: "artists", creator: "1", creatorName: "Artist" });
  await creatorAlbum.run();
  assert.deepEqual(JSON.parse(JSON.stringify(creatorAlbum.queries[0].extra)),
    { view: "artists", group: "Artist", album: "Release", sort: "track_no", dir: "asc" },
    "an album row inside a creator page stays scoped to that creator and keeps album order");

  const artist = loadResolver({ groups: [{ key: "g", type: "group", view: "artists", name: "Artist" }], view: "artists", creator: "1", creatorName: "" });
  await artist.run();
  assert.deepEqual(JSON.parse(JSON.stringify(artist.queries[0].extra)), { view: "artists", group: "Artist" },
    "an artist row keeps the plain view+group contract (the artist list has no track order to force)");

  const folder = loadResolver({ groups: [{ key: "f", type: "folder", root: "/music", path: "disc" }], view: "folders" });
  await folder.run();
  assert.deepEqual(JSON.parse(JSON.stringify(folder.queries[0].extra)),
    { view: "folders", root: "/music", folder: "disc", subtree: 1 },
    "a folder row still covers everything beneath it, in the list's own order");

  // --- 5. 缓存上限不再能截断播放队列 ------------------------------------
  const playSource = sourceBetween("async function playTracks", "async function playSelectedTracks");
  assert.match(playSource, /commitQueue\(items, items\[0\]\.id\)/, "playTracks must commit the rows it was given");
  assert.doesNotMatch(playSource, /itemById|selectedItems/, "playTracks must not re-resolve rows through the bounded item cache");
  assert.match(source, /if \(action === "play"\) playTracks\(tracks\);/,
    "the group play branch must pass rows, not ids: a >12,000-track folder would silently lose its tail");
  assert.match(source, /return playTracks\(selectedItems\(ids\)\);/, "id-based play (track menu / action dialog) keeps its single implementation");

  console.log("Group play-action regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
