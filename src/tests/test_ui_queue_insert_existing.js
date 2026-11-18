// R589: 插播一首已经在队列里的歌，必须**移动**它，而不是静默跳过。
//
// 报的现象是"点了插播没反应"。旧实现先把队列里已有的 id 过滤掉，再
// `if (!additions.length) return;` —— 选中的歌只要已经在队列里，函数就在发出
// 任何请求之前退出了：界面不动、没有提示、也没有日志。而「插播所选项目」要的
// 本来就是一个位置（把这首挪到下一首），"已经在队列里"正是它最常见的输入。
//
// 这个文件钉两件事：
//   1. 纯函数 `reorderQueueForInsert()` 的语义（移动、保序、不丢不重、当前曲是锚点）；
//   2. `insertSelectedTracks()` 只在**顺序真的变了**的时候才发请求——否则每次点
//      插播都要整条重发 `setMediaItems`，原生那边会把正在播的流重新加载一遍。

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");

function extracted(pattern, label) {
  const match = source.match(pattern);
  assert.ok(match, `${label} must stay extractable`);
  return match[0];
}

const reorderSource = extracted(/^function reorderQueueForInsert\([\s\S]*?^\}/m, "reorderQueueForInsert");
const insertSource = extracted(/^async function insertSelectedTracks\([\s\S]*?^\}/m, "insertSelectedTracks");

// 回归钉：旧的两步（过滤 existing → 空了就 return）只要回来，这条就红。
assert.ok(
  !/if \(!additions\.length\) return;/.test(insertSource),
  "the silent early return that made 插播 a no-op for queued songs is back",
);

const reorder = (queue, index, items) => {
  const context = { queue, index, items };
  vm.createContext(context);
  vm.runInContext(`${reorderSource}\nthis.result = reorderQueueForInsert(queue, index, items);`, context);
  // Arrays built inside the vm carry that realm's Array.prototype, and strict
  // deepEqual compares prototypes, so copy them out before comparing.
  return JSON.parse(JSON.stringify(context.result));
};

// `Array.from` rather than `.map`: the queue handed back by the sandbox is a
// vm-realm array, and strict deepEqual compares prototypes, so mapping it here
// would keep that realm's Array.prototype and fail for the wrong reason.
const ids = list => Array.from(list, item => String(item.id));
const rows = (...names) => names.map(name => ({ id: name }));

function check(label, actual, expected) {
  assert.deepEqual(ids(actual), expected, label);
}

// --- 纯函数：移动语义 -------------------------------------------------------

// 已在队列**后面**的歌被提到当前曲之后，原来那一份消失（不是复制成两份）。
check(
  "a queued song moves up next instead of being ignored",
  reorder(rows("a", "b", "c", "d"), 0, rows("d")),
  ["a", "d", "b", "c"],
);

// 已经在下一首：顺序不变，函数幂等（重复点不会来回抖）。
check(
  "inserting the row that is already next changes nothing",
  reorder(rows("a", "b", "c"), 0, rows("b")),
  ["a", "b", "c"],
);

// 混合选择：新歌和旧歌都落在当前曲之后，并按**选择顺序**排（不是队列原序）。
check(
  "new and already-queued songs both land after the current one, in pick order",
  reorder(rows("a", "b", "c"), 0, rows("c", "x")),
  ["a", "c", "x", "b"],
);

// 当前曲自己：跳过。把锚点搬走只会和它自己的位置打架。
check(
  "the current row is not movable relative to itself",
  reorder(rows("a", "b", "c"), 1, rows("b")),
  ["a", "b", "c"],
);

// 当前曲 + 另一首：只搬另一首。
check(
  "selecting the current row together with another one still moves the other",
  reorder(rows("a", "b", "c"), 1, rows("b", "c")),
  ["a", "b", "c"],
);

// 从当前曲**前面**搬到后面：锚点下标在删除后会左移，必须重新定位。
check(
  "moving a row from before the anchor still lands immediately after it",
  reorder(rows("a", "b", "c", "d"), 2, rows("a")),
  ["b", "c", "a", "d"],
);

// 不丢不重：长度不变、id 集合不变。
{
  const before = rows("a", "b", "c", "d", "e");
  const after = reorder(before, 2, rows("e", "b"));
  check("multiple picks keep their order", after, ["a", "c", "e", "b", "d"]);
  assert.equal(after.length, before.length, "moving must not change the queue length");
  assert.deepEqual(
    ids(after).slice().sort(),
    ids(before).slice().sort(),
    "moving must not drop or duplicate a row",
  );
}

// 没有当前曲（队列空）：退化成追加，选择顺序保留。
check("with no current row the picks are appended", reorder([], -1, rows("x", "y")), ["x", "y"]);
// 没有当前曲但队列非空（正常路径到不了，`applyConfirmedQueue` 会把 index 落到 0）：
// 同样落到末尾，不丢不重。
check("with no current row a queued row lands at the end", reorder(rows("a", "b", "c"), -1, rows("b")), ["a", "c", "b"]);

// 选择里的重复项只算一次。
check("a repeated pick is placed once", reorder(rows("a", "b", "c"), 0, rows("c", "c")), ["a", "c", "b"]);

// 没有可搬的东西：原样返回同一个数组（调用方靠它判断"没变化"）。
{
  const before = rows("a", "b");
  const after = reorder(before, 0, []);
  check("an empty selection is a no-op", after, ["a", "b"]);
}

// --- insertSelectedTracks：只在顺序真的变了的时候发请求 ---------------------

function build(queue, index, options) {
  const failing = Boolean(options && options.failing);
  const calls = { commit: [], render: 0, alert: [] };
  const context = {
    state: { queue, index },
    selectedItems: picked => picked.map(id => ({ id })),
    commitQueue: async (next, currentId) => {
      calls.commit.push({ ids: ids(next), currentId });
      if (failing) throw new Error("保存失败");
      return {};
    },
    render: () => { calls.render += 1; },
    alert: message => calls.alert.push(String(message)),
  };
  vm.createContext(context);
  vm.runInContext(
    `${reorderSource}\n${insertSource}\nthis.h = { insert: insertSelectedTracks };`,
    context,
  );
  return { h: context.h, calls };
}

(async () => {
  // 已排到下一首：一次请求都不该发。
  {
    const { h, calls } = build(rows("a", "b", "c"), 0);
    await h.insert(["b"]);
    assert.equal(calls.commit.length, 0, "an unchanged queue must not be re-sent");
    assert.equal(calls.render, 0, "an unchanged queue must not repaint");
  }

  // 只选了当前曲：同上。
  {
    const { h, calls } = build(rows("a", "b", "c"), 1);
    await h.insert(["b"]);
    assert.equal(calls.commit.length, 0, "selecting the current row alone must not re-send");
  }

  // 真的挪动了：发一次，当前曲 id 原样带过去（`applyConfirmedQueue` 靠它找回位置）。
  {
    const { h, calls } = build(rows("a", "b", "c", "d"), 0);
    await h.insert(["d"]);
    assert.equal(calls.commit.length, 1, "a real move must be saved exactly once");
    assert.deepEqual(calls.commit[0].ids, ["a", "d", "b", "c"], "the saved order is wrong");
    assert.equal(calls.commit[0].currentId, "a", "the current track must survive the move");
    assert.equal(calls.render, 1, "the queue panel must repaint after a real move");
  }

  // 新歌：仍然追加到当前曲之后（R589 之前的行为不能回退）。
  {
    const { h, calls } = build(rows("a", "b"), 0);
    await h.insert(["x"]);
    assert.deepEqual(calls.commit[0].ids, ["a", "x", "b"], "a brand-new song still lands next");
  }

  // 保存失败：提示，且不重绘（重绘会把失败的样子画成成功）。
  {
    const { h, calls } = build(rows("a", "b", "c"), 0, { failing: true });
    await h.insert(["c"]);
    assert.equal(calls.commit.length, 1, "the failed save was still attempted");
    assert.deepEqual(calls.alert, ["保存失败"], "a failed save must say so");
    assert.equal(calls.render, 0, "a failed save must not repaint as if it worked");
  }

  console.log("Queue insert checks passed (a queued song moves up next instead of vanishing).");
})().catch(error => {
  console.error(error);
  process.exit(1);
});
