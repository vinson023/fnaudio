// R601: the gap between two tracks had two LAN round trips sitting in front of
// `audio.src`, and neither was asking a question this page could not answer.
//
//  1. `audio.onended` awaited `coreControl("next")` -- the server said which track
//     came next, and only then did anything load. But `nextIndex()` is a pure
//     function over `state.queue`; the page already knows.
//  2. `loadCurrent` awaited `warmCurrentTrackCache` -- asking whether the transcode
//     cache was ready, a question `warmUpcomingTrackCache` had already asked one
//     track earlier and then thrown the answer away.
//
// Both are now off the path. The tests below pin the behaviour that makes that
// safe: the local advance refuses to run when this page is not the player, refuses
// at the end of the queue and under 循环=单曲, and the remembered "ready" answer is
// one-shot and id-matched so a stale flag can never claim a cache hit nobody made.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the auto-advance regression`);
  return match[0];
}

// --- the local advance -----------------------------------------------------

function buildAdvance(options) {
  const calls = [];
  const state = { queue: options.queue || [{ id: "a" }, { id: "b" }, { id: "c" }], index: options.index || 0 };
  const context = {
    state,
    isRemoteTarget: () => options.remote === true,
    isIncomingRendererSession: () => options.renderer === true,
    nextIndex: () => options.next,
    syncCurrentQueuePresentation: previous => calls.push(["sync", previous]),
    loadCurrent: () => calls.push(["load"]),
  };
  vm.createContext(context);
  vm.runInContext(
    `${functionSource("advanceLocalQueueForTrackEnd")}\nglobalThis.h = { advance: advanceLocalQueueForTrackEnd };`,
    context,
  );
  return { advance: context.h.advance, state, calls };
}

{
  const env = buildAdvance({ next: 1 });
  assert.equal(env.advance(), true, "本地播放时应当自己接上下一首");
  assert.equal(env.state.index, 1, "下标要先走");
  assert.deepEqual(env.calls, [["sync", 0], ["load"]], "先同步列表呈现，再装载");
}

{
  const env = buildAdvance({ next: 1, remote: true });
  assert.equal(env.advance(), false, "投送/远端目标下不能本地先走，服务端要自己挑并推");
  assert.equal(env.state.index, 0, "下标不许动");
  assert.deepEqual(env.calls, [], "不许装载");
}

{
  const env = buildAdvance({ next: 1, renderer: true });
  assert.equal(env.advance(), false, "有 render session 占着输出时同样交给服务端");
  assert.deepEqual(env.calls, []);
}

{
  const env = buildAdvance({ next: -1 });
  assert.equal(env.advance(), false, "队尾且不循环时不动");
  assert.deepEqual(env.calls, []);
}

{
  // 循环=单曲: nextIndex() 返回当前下标，语义是"重放这一首"。这条重载由服务端的
  // 回话驱动，本地先走会把它变成一次多余的装载，所以明确不接管。
  const env = buildAdvance({ next: 0, index: 0 });
  assert.equal(env.advance(), false, "循环=单曲 不进本地快路径");
  assert.deepEqual(env.calls, []);
}

// --- the remembered warm answer --------------------------------------------

function buildWarmReady() {
  const context = {};
  vm.createContext(context);
  vm.runInContext(
    [
      'let upcomingWarmReadyId = "";',
      functionSource("consumeUpcomingWarmReady"),
      "globalThis.h = {",
      "  consume: consumeUpcomingWarmReady,",
      "  peek: () => upcomingWarmReadyId,",
      "  seed: value => { upcomingWarmReadyId = value; },",
      "};",
    ].join("\n"),
    context,
  );
  return context.h;
}

{
  const h = buildWarmReady();
  h.seed("b");
  assert.equal(h.consume("b"), true, "预热确认过的那一首可以直接认");
  assert.equal(h.peek(), "", "认过就清掉，答案只能用一次");
  assert.equal(h.consume("b"), false, "同一首第二次要回到老实问一次的路");
}

{
  const h = buildWarmReady();
  h.seed("b");
  assert.equal(h.consume("c"), false, "别的曲目不能借这个答案");
  assert.equal(h.peek(), "b", "没认领就不该被清掉");
}

{
  const h = buildWarmReady();
  h.seed("b");
  assert.equal(h.consume(""), false, "空 id 不认");
  assert.equal(h.consume(null), false, "null 不认");
  assert.equal(h.peek(), "b");
}

// --- wiring ----------------------------------------------------------------

{
  // The local advance has to run *before* the server is asked, or the round trip
  // is still in front of `audio.src`.
  const start = app.indexOf("audio.onended = async () => {");
  assert.ok(start >= 0, "找不到 onended");
  const body = app.slice(start, app.indexOf("\n};", start));
  const local = body.indexOf("advanceLocalQueueForTrackEnd()");
  const server = body.indexOf('coreControl("next"');
  assert.ok(local >= 0, "onended 要调用本地快路径");
  assert.ok(server >= 0, "onended 仍要向服务端对齐账本");
  assert.ok(local < server, "本地先接上，服务端那一问不再挡路");
  assert.match(body, /state\.autoAdvancing = true/, "自动续播的标记要在本地装载之前立起来");
  assert.ok(
    body.indexOf("state.autoAdvancing = false") > server,
    "标记要等服务端回话之后再清：它的回复可能触发一次重载",
  );
}

{
  // The server steps *from* the track it is told about: `control_track_alignment`
  // adopts a browser's reported track before dispatching `next`. Reporting the
  // track we just advanced to would make the core adopt it and step again, so the
  // ended track has to be captured before `state.index` moves and sent explicitly.
  const start = app.indexOf("audio.onended = async () => {");
  const body = app.slice(start, app.indexOf("\n};", start));
  const capture = body.indexOf('const endedTrackId = String(currentItem()?.id || "")');
  const advance = body.indexOf("advanceLocalQueueForTrackEnd()");
  assert.ok(capture >= 0, "要在本地步进之前记下刚放完的那一首");
  assert.ok(capture < advance, "endedTrackId 必须先于本地步进，否则记到的是下一首");
  assert.ok(
    body.indexOf("coreControl(\"next\", null, {}, { trackId: endedTrackId })") >= 0,
    "上报给服务端的必须是刚放完的那一首",
  );
  // ... and `coreControl` has to honour it.
  assert.ok(
    app.indexOf('const reportedTrackId = String(options.trackId ?? (item?.id || ""))') >= 0,
    "coreControl 要接受调用方指定的上报曲目",
  );
  assert.ok(app.indexOf("track_id: reportedTrackId") >= 0, "请求体要发这个值，而不是当前的 state.index");
}

{
  // The reuse must sit in front of the await, and only for a confirmed answer.
  const start = app.indexOf("async function loadCurrent()");
  assert.ok(start >= 0, "找不到 loadCurrent");
  const block = app.slice(start, app.indexOf("const useCache", start));
  const reuse = block.indexOf("consumeUpcomingWarmReady(item.id)");
  const ask = block.indexOf("await warmCurrentTrackCache(item)");
  assert.ok(reuse >= 0, "loadCurrent 要先花掉预热留下的答案");
  assert.ok(ask >= 0, "问不到答案时仍要走原来的路");
  assert.ok(reuse < ask, "先认答案，再考虑发请求");
}

{
  // The answer only exists if the warm-up keeps it, and only when it is positive.
  assert.match(app, /upcomingWarmReadyId = trackId/, "预热要把「已就绪」的答案留下来");
  assert.match(app, /data\.ready === true && upcomingWarmTrackId === trackId/, "只留肯定答案，且要对得上那一首");
}

console.log("Auto-advance round trip regression checks passed.");
