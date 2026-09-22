# fnAudio R160 修改审查对照

分支 `main` · HEAD 基线 `a80663c`（R159 第 5 笔）· 本轮日期 2026-09-23

> 本文件按 Codex 逐 hunk 审查方式呈现 R160 的全部改动：缺陷、根因、修复 diff、判别测试、红证、控制组、变异矩阵、门禁，以及 R151 旧证伪的翻案依据。

## 一、本轮一句话结论

读取 `src/app/ui/app.js` 投送/媒体会话/分组封面/曲目行渲染面（切片 :2177-:3011，51 枚函数），当轮修掉 1 处真缺陷（`prepareLocalGroupArtwork` 对无 `src` 封面图做同步删除），据实推翻 R151 的一条旧证伪，新增 1 枚判别套件并跑满变异矩阵；净关闭代码待办 0 条、新立 0 条。

## 二、缺陷定位与根因

- 缺陷函数：`prepareLocalGroupArtwork`（def :2898），判定块 :2910-:2929。
- 症状：分组／专辑封面在 `render()` 阶段是先建容器、`src` 由共享封面调度器延后注入的 `<img>`。函数原文 `if (image.complete) return verify();` 把 `complete` 当作「加载完成」。
- 根因：按 HTML 规范，无 `src` 的 `<img>` 即 `complete === true` 且 `naturalWidth === 0`（真实无头 Chromium 实据）。于是同步分支立即命中 → `verify()` → 因 `naturalWidth` 不大于 1 走 `failed()` → `image.remove()`，在调度器还没来得及注入源之前一帧删掉封面。
- **翻案（R151）**：`CHANGELOG_AI.md` 记 R151「当轮证伪 4 项」含「`prepareLocalGroupArtwork` 的帧回调校验不构成缺陷（`load`/`error` 监听器仍在位）」。该证伪只覆盖异步路径——无 `src` 时同步分支先 `return`，`load`/`error` 监听器根本没注册。故此形状确为缺陷，R160 据实翻案，但不改写 R151 原记录，仅点名推翻。

## 三、修复逐 hunk（`git diff -- src/app/ui/app.js`）

```diff
diff --git a/src/app/ui/app.js b/src/app/ui/app.js
index 5f84d7a..09c8c10 100644
--- a/src/app/ui/app.js
+++ b/src/app/ui/app.js
@@ -2910,12 +2910,20 @@ function prepareLocalGroupArtwork(node) {
     node.removeAttribute("data-metadata-image");
     if (fallback) applyGroupArtwork(node, fallback);
   };
+  // A group/album cover is emitted without `src` and only receives its URL from
+  // the shared scheduler after this listener setup. Per the HTML spec a src-less
+  // <img> already reports complete === true with naturalWidth === 0, so
+  // `complete` alone cannot mean "finished loading" here. Judging a
+  // not-yet-started cover by `complete` deletes it before the scheduler ever
+  // starts it. Gate on the same "has a source" marker the scheduler uses.
+  const hasArtworkSource = () =>
+    image.hasAttribute?.("src") === true || String(image.dataset?.coverLoadedSrc || "") !== "";
   const verify = () => {
-    if (!image.isConnected || !image.complete) return;
+    if (!image.isConnected || !hasArtworkSource() || !image.complete) return;
     if (image.naturalWidth > 1) loaded();
     else failed();
   };
-  if (image.complete) return verify();
+  if (hasArtworkSource() && image.complete) return verify();
   image.addEventListener("load", loaded, { once: true });
   image.addEventListener("error", failed, { once: true });
   requestAnimationFrame(verify);
```

净增 8 行＝6 行英文注释＋`hasArtworkSource()` 定义＋`verify` 早退与同步分支各 1 处门控。核心不变量：**就绪判定先看「有没有源」再看 `complete`**，与调度器 `cover_load_scheduler.js` 用的 `hasAttribute("src")`/`coverLoadedSrc` 同款标记对齐。

## 四、修复后 `prepareLocalGroupArtwork` 现场（行号 | 内容）

```
 2898| function prepareLocalGroupArtwork(node) {
 2899|   const image = node.querySelector("img");
 2900|   if (!image) return;
 2901|   const loaded = () => {
 2902|     node.classList.add("has-cover");
 2903|     node.removeAttribute("data-metadata-image");
 2904|   };
 2905|   const failed = () => {
 2906|     image.remove();
 2907|     node.classList.remove("has-cover");
 2908|     node.removeAttribute("data-artwork-local");
 2909|     const fallback = node.dataset.metadataImage || "";
 2910|     node.removeAttribute("data-metadata-image");
 2911|     if (fallback) applyGroupArtwork(node, fallback);
 2912|   };
 2913|   // A group/album cover is emitted without `src` and only receives its URL from
 2914|   // the shared scheduler after this listener setup. Per the HTML spec a src-less
 2915|   // <img> already reports complete === true with naturalWidth === 0, so
 2916|   // `complete` alone cannot mean "finished loading" here. Judging a
 2917|   // not-yet-started cover by `complete` deletes it before the scheduler ever
 2918|   // starts it. Gate on the same "has a source" marker the scheduler uses.
 2919|   const hasArtworkSource = () =>
 2920|     image.hasAttribute?.("src") === true || String(image.dataset?.coverLoadedSrc || "") !== "";
 2921|   const verify = () => {
 2922|     if (!image.isConnected || !hasArtworkSource() || !image.complete) return;
 2923|     if (image.naturalWidth > 1) loaded();
 2924|     else failed();
 2925|   };
 2926|   if (hasArtworkSource() && image.complete) return verify();
 2927|   image.addEventListener("load", loaded, { once: true });
 2928|   image.addEventListener("error", failed, { once: true });
 2929|   requestAnimationFrame(verify);
 2930| }
 2931| function loadGroupArtwork() {
```

## 五、判别测试

新建 `src/tests/test_ui_group_artwork_source_gate.js`（切片真跑，8 枚判别块）。逐块语义：

- **V1**（套件 :132）：无 `src` 图片的同步路径**不得**删除封面——本轮缺陷的直接反证块，也是红证判红块。
- **V2**（:257）：`verify` 必须带 `hasArtworkSource()` 门控。
- **V4**（:270）：加载成功阈值为 `naturalWidth > 1`（非 `> 0`）。
- **V5**（:159）：`hasArtworkSource` 必须含 `hasAttribute("src")` 分支。
- **V6**（:192）：`hasArtworkSource` 必须含 `coverLoadedSrc` 分支。
- **V7**（:239）：`load` 监听器接的是 `loaded`（非 `failed`）。
- **V8**（:226）：`error` 监听器接的是 `failed`（非 `loaded`）。
- 对照：无源图必须走异步监听＋`requestAnimationFrame` 而非同步删除。

## 六、红证（判别力证明）

仓库外 `E:\temp\r160red`＝`git show HEAD:src/app/ui/app.js`（未修母本）＋现盘守卫。跑新套件退出码 1，首枚判红在 :132「无 `src`」块。→ 该套件能区分修复前后，非恒绿。

## 七、控制组（先绿纪律）

仓库外 `E:\temp\r160ctl`＝已修 `app.js` ＋ 新套件 ＋ 现盘 718 条清单。结果：新套件 rc0、全部 83 枚 JS 套件发现式 0 失败、Python `Ran 2,567 … OK (skipped=3)` rc0。两套先绿。

## 八、变异矩阵与击杀映射（本轮独立复跑于盘上现文件）

| 变异体 | 手法（单行字符串替换） | 期望 | 实测 | 判红行 |
|---|---|---|---|---|
| M1 | 原样（对照） | 绿 | rc0 绿 | — |
| V1 | 同步分支退回 `if (image.complete)` | 灭 | 判红 | :132 |
| V2 | `verify` 去 `!hasArtworkSource()` | 灭 | 判红 | :257 |
| V4 | `naturalWidth > 1` 改 `> 0` | 灭 | 判红 | :270 |
| V5 | `hasArtworkSource` 去 `hasAttribute("src")` 支 | 灭 | 判红 | :159 |
| V6 | `hasArtworkSource` 去 `coverLoadedSrc` 支 | 灭 | 判红 | :192 |
| V7 | `load` 监听改接 `failed` | 灭 | 判红 | :239 |
| V8 | `error` 监听改接 `loaded` | 灭 | 判红 | :226 |

结论：7/7 全灭、0 存活；每条 `from` 子串在盘上现文件唯一（驱动内 `assert count==1` 通过）。

## 九、门禁

`tools/test_offline.ps1` 终跑 `artifacts/offline-20260923-round252.log`，退出码 0。实测：Python `Ran 2567 tests in 130.367s — OK (skipped=2)`、JS 83 套件 0 失败、本轮新守卫成功行 `group artwork source-gate regression checks passed.` 在门禁输出内实到；`git diff --check` 仅吐 `SOURCE_MANIFEST.sha256` CRLF 提示一行（既有、良性）。

## 十、清单

`SOURCE_MANIFEST.sha256` 刷新 717 → 718：新增 1（本判别套件）／改哈希 1（`app.js`）／删除 0。三份根文档不入取证范围（`tools/update_source_manifest.ps1` 只覆盖 `src` 与 `android-client`）。

## 十一、深读覆盖记账

- 本面 :2177-:3011＝**51 枚**命名函数（R159 前清单登记 52，差 1＝`prepareLocalGroupArtwork` 实为 R151 已反引号点名者、R159 误计为未点名，本轮同步校正口径）。
- 双口径 0 命中者 **23 枚**，本轮全部首次点名：`stopRemoteOnUnload`、`updateMediaSessionMetadata`、`setupMediaSession`、`cancelRemoteStatusRequest`、`maybeAdvanceRemoteQueue`、`playbackCommandId`、`trackMatchesSearch`、`hasMultipleLibraryRoots`、`hasSingleFolderRoot`、`libraryRootLabels`、`folderTracks`、`clientPagedTotal`、`clientPagedTracks`、`currentQueuePage`、`groupFallbackIcon`、`groupIcon`、`activeTrackColumns`、`trackGridTemplate`、`applyTrackGridTemplate`、`trackColumnWidthLimits`、`measureAutoTrackColumnWidths`、`trackQuality`、`trackAddedDate`。
- 深读分子 122 → **145**；登记分母 381 不动；三份根文档双口径 0 点名者 235 → **212**（写入后实测复算，见本文件所附校验）。
- app.js 行首锚定 462／unique 462 不变；`app.js` 8,469 → 8,477（净 +8）；欠读总量 18,164 → **18,172**（=app.js 8,477 + Android 43 文件 9,695，上升 8＝本轮修复净增，如实登记不降反升）。

## 十二、目标完成度快照（还剩多少）

- 三口径并存、不合并：旧目标正文快照 `155=64+82+9`；R99 实测 `115=51+43+8+13`；本棒逐轮现盘——行首可关闭代码项 0（4 枚 `- [ ]` 均为累计型深读门／长期观察项），严格 `- [x]`=1,503。
- 四项终止条件：(3) 决策桶 → 成立；(2) 设备项移出 → 结构性成立（自 R157，冻结于 `docs/REAL_DEVICE_GOALS.md` G01-G11 与 `docs/external-acceptance.md` 45 卡）；(1) 代码待办清空 → **未成立**（纯深读债仍在）；(4) 终轮完整门禁 → 仅在终止轮执行。
- 欠读总量 18,172 行、双口径未点名 212 枚、app.js 每轮约点 23-42 枚＋Android 面，估算**剩余约 22-29 轮**（不含真机）。旧 `maxGoalRounds=72` 不作为终止理由。

