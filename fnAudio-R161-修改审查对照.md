# fnAudio R161 修改审查对照

分支 `main` · HEAD 基线 `eaa756f`（R160 第 5 笔）· 本轮日期 2026-09-23

> 本文件按 Codex 逐 hunk 审查方式呈现 R161 的全部改动：接管取证、缺陷与根因、修复 diff、修复后现场、判别套件、红证、控制组、12 格变异矩阵、清单与门禁、口径变动，以及一处「写了又删」的代码裁定。

## 一、本轮一句话结论

读取 `src/app/ui/app.js` 表头渲染／专辑详情／曲目行渲染／元数据行增量渲染面（切片 :3019-:3380，12 枚命名函数），当轮修掉 1 组真缺陷（同一列宽在本文件内的两套带宽口径 ＋ 拖拽 `pointercancel` 出口缺失导致 window 监听器泄漏），新增 1 枚判别套件并跑满 12 格变异矩阵；净关闭代码待办 0 条、新立 0 条，深读分子 145 → 154，三份根文档 0 点名者 212 → 201。

## 二、接管取证（修改前）

| 项 | 实测 |
| --- | --- |
| 仓库／分支 | `C:\path\to\fnAudio` · `main` |
| HEAD | `eaa756f` docs(round-review): R160 逐 hunk 审查对照与变异矩阵 |
| 未完成态 | `.git/MERGE_HEAD`、`.git/rebase-merge`、`.git/rebase-apply`、`.git/CHERRY_PICK_HEAD`、`.git/BISECT_LOG` 逐个 `Test-Path` 均 False；`git stash list` 空；无 remote |
| 跟踪文件 | 0 改（故现盘即 HEAD 母本，红证无需 `git checkout --`） |
| 唯一未跟踪新件 | `src/tests/test_ui_track_column_resize.js`（上一棒已写、未执行） |

## 三、缺陷定位与根因

### (a) 同一列宽存在两套带宽口径

- 声明式路径：`trackColumnWidthLimits`（现 :2959）委托共享模块 `src/app/ui/track_table_presentation.js` 的 `widthLimits` —— 时长 72..96、序号 64..84、标题 260..620、未列名回落 80..260；自动测宽 `measureAutoTrackColumnWidths` 同样按逐列带宽钳。
- 用户写入路径：`saveTrackColumnWidth`（改前 :1032）与 `renderTableHead` 内拖拽处理器（改前 :3091）各自写死扁平 `Math.max(64, Math.min(900, …))`，且改前 :3093 手搓第二份 `px` 网格模板而不复用 `trackGridTemplate`。
- 三条用户可见后果：① 时长列拖过 96px 约 40px 就存下并显示 112px；② 下一次表头签名变化按带宽重算回 96px（列自弹回）；③ 再下一次拖拽起点取盘上并不存在的 112px（首个 `pointermove` 整列跳动）。

### (b) 拖拽监听只有一条出口被摘除

- 改前 :3103-:3104 在 window 上挂 `pointermove` ＋ `pointerup{once}`，而 `pointermove` 只在 `finish`（改前 :3100）内摘。
- 以 `pointercancel`（触控笔／滚动手势接管／指针捕获丢失）结束的拖拽永不触发 `pointerup` ⇒ `pointermove` 永久驻留 window，此后每次鼠标移动都用陈旧 `startWidth`／`startX` 重写全局 `--fnaudio-track-columns`；第二次拖拽起两枚处理器互相覆写。
- 本文件 :7132-:7133 早已有 `pointerup` ＋ `pointercancel` 双出口的既有正确写法 —— 修复不是新发明，而是向既有先例对齐。

## 四、修复逐 hunk（`git diff -U6 -- src/app/ui/app.js`，净 ＋32/−12 ＝ ＋20 行）

### Hunk 1 · 读侧收敛 ＋ 写侧统一钳（:1026 / :1035）

```diff
 function currentTrackColumnWidths() {
   const scope = trackColumnScope();
-  return { ...normalizeTrackColumnWidths(state.autoTrackColumnWidths[scope]), ...normalizeTrackColumnWidths(state.trackColumnWidthPreferences[scope]) };
+  const merged = { ...normalizeTrackColumnWidths(state.autoTrackColumnWidths[scope]), ...normalizeTrackColumnWidths(state.trackColumnWidthPreferences[scope]) };
+  // Stored and auto-measured widths can predate a column's current resize
+  // band.  Converge them on read so the template never shows a width that
+  // saveTrackColumnWidth() could not have written, and so the first drag grabs
+  // the width the user actually sees instead of a phantom out-of-band value.
+  return Object.fromEntries(Object.entries(merged).map(([key, width]) => [key, clampTrackColumnWidth(key, width)]));
 }
 function saveTrackColumnWidth(key, width) {
-  const column = TRACK_COLUMN_DEFINITIONS[key];
-  const value = Math.max(64, Math.min(900, Math.round(Number(width) || column?.width || 120)));
+  const value = clampTrackColumnWidth(key, width);
```

审查要点：读侧收敛是**遗留数据一次性归位**——旧库里已存下的 112px 不需迁移脚本，读取即钳；`const column` 在改用 `clampTrackColumnWidth` 后成为死变量，一并删除。

### Hunk 2 · 模板公式收实时覆写（:2947）

```diff
-function trackGridTemplate() {
-  const widths = currentTrackColumnWidths();
+function trackGridTemplate(widthOverrides = null) {
+  const widths = widthOverrides ? { ...currentTrackColumnWidths(), ...widthOverrides } : currentTrackColumnWidths();
```

审查要点：默认参数为 `null` 时行为与改前逐字一致（零回归面）；覆写只作用于本次构造，不回写 `state`。

### Hunk 3 · 新增共享钳（:2967，紧随 `trackColumnWidthLimits`）

```diff
+function clampTrackColumnWidth(key, value) {
+  const definition = TRACK_COLUMN_DEFINITIONS[key];
+  const numeric = Math.round(Number(value));
+  const preferred = Number.isFinite(numeric) && numeric > 0 ? numeric : definition?.width || 120;
+  const [minimum, maximum] = trackColumnWidthLimits(key);
+  return Math.min(maximum, Math.max(minimum, preferred));
+}
```

审查要点：先判非有限／非正再回落列定义宽度，再双边钳——顺序不可颠倒（`Math.max(min, NaN)` 仍为 `NaN`）；带宽单点取自 `trackColumnWidthLimits`，未列名自动回落 80..260，与共享模块口径一致。

### Hunk 4 · 拖拽：统一钳 ＋ 复用模板 ＋ 双出口对称摘除（:3101-:3124）

```diff
     const resize = move => {
-      const width = Math.max(64, Math.min(900, Math.round(startWidth + move.clientX - startX)));
-      const current = { ...currentTrackColumnWidths(), [key]: width };
-      const template = [...activeTrackColumns().map(column => `${current[column] || TRACK_COLUMN_DEFINITIONS[column].width}px`), "minmax(0,1fr)"].join(" ");
+      const width = clampTrackColumnWidth(key, startWidth + move.clientX - startX);
+      const template = trackGridTemplate({ [key]: width });
       head.style.setProperty("--fnaudio-track-columns", template);
       document.body.style.setProperty("--fnaudio-track-columns", template);
     };
-    const finish = move => {
+    // A drag does not always end with pointerup: pointercancel fires when the
+    // pen/scroll gesture takes over or capture is lost.  The old binding left
+    // pointermove attached in that case, so every later mouse move kept
+    // rewriting the shared grid template from the stale start width.  Each exit
+    // path detaches all three listeners, so neither end event can be handled
+    // twice; a cancelled drag rolls the preview back and persists nothing.
+    const finish = (move, shouldSave) => {
       resize(move);
-      saveTrackColumnWidth(key, startWidth + move.clientX - startX);
+      if (shouldSave) saveTrackColumnWidth(key, startWidth + move.clientX - startX);
       window.removeEventListener("pointermove", resize);
-      window.removeEventListener("pointerup", finish);
+      window.removeEventListener("pointerup", up);
+      window.removeEventListener("pointercancel", cancel);
     };
+    const up = move => finish(move, true);
+    const cancel = () => finish({ clientX: startX }, false);
     window.addEventListener("pointermove", resize);
-    window.addEventListener("pointerup", finish, { once: true });
+    window.addEventListener("pointerup", up, { once: true });
+    window.addEventListener("pointercancel", cancel, { once: true });
```

审查要点：① `cancel` 用 `{ clientX: startX }` 回访 `resize`，即把预览回滚到抓取宽度，不持久化；② `up`／`cancel` 是**固定标识符**，摘除必须用同一引用，故原 `finish` 拆分；③ 两条出口各自摘全三枚监听，任一路径先到即彻底解绑。

## 五、一处「写了又删」的代码裁定

初版在 `finish` 上加了 `let ended = false;` 幂等闩。变异矩阵跑出来后该闩**在 M6a／M6b 下存活**（摘除监听器本身已保证结束事件只生效一次，闩不可观测），故按反死码纪律删除，改以三枚替代变异取证：M6a 不摘 `pointerup`、M6b 不摘 `pointercancel`、M6c 取消也持久化——三格现均判红。结论：幂等由此处的监听器摘除承担，不由额外状态承担。

## 六、判别套件

`src/tests/test_ui_track_column_resize.js`（356 行／16,197 B，`vm.runInNewContext` 真跑切片，12 枚判别块）：拖拽钳到 96px（V1）、持久化值＝可渲染值且改 `sortDir` 后不自弹回（V2）、遗留越界存储 `{duration:372}` 读侧收敛且抓取不跳列（V3）、`pointercancel` 后三枚监听计数归零且悬停不再重写模板且回滚不持久化（V5/V7）、第二枚结束事件不得二次保存或回退、`saveTrackColumnWidth(key, 1e6)` 必等共享模块 `widthLimits` 上界（V9/V10）、模块缺席回落到同一带宽，另含源码级接线断言（拖拽块必含 `pointercancel`／`clampTrackColumnWidth(`／`trackGridTemplate(` 且不得再含扁平带宽）。

## 七、红证 → 绿证

| 步 | 命令 | 结果 |
| --- | --- | --- |
| 红 | `node tests\test_ui_track_column_resize.js`（未修复的现盘＝HEAD 母本） | rc 1，判红于 :251「duration must clamp at 96px」，逐字 `actual [420, 112]` ≠ `expected [420, 96]` |
| 绿 | 同上（修复后） | rc 0，`track column resize regression checks passed.` |

红证未使用任何 `git checkout --`，直接受益于接管时跟踪树 0 改这一事实。

## 八、控制组（必须先绿）

- JS 发现式全跑 `src\tests\test_*.js` **84 个文件 0 失败**。
- Python 两枚解析根文档的守卫：`python -B -m unittest tests.test_change_record tests.test_device_todos_migrated` → `Ran 12 tests` · `OK`。

## 九、变异矩阵（仓库外副本 `E:\temp\r161mutA\repo`，`git clone --no-hardlinks` ＋ `git remote remove origin`）

| 格 | 变异 | 结果 | 杀手断言 |
| --- | --- | --- | --- |
| — | 未变异对照 | rc 0 | 全绿 |
| M1 | 拖拽带宽退回扁平 64..900 | KILLED | V9: the fallback path must clamp the drag the same way |
| M2 | 写库带宽退回扁平 | KILLED | V2: a resize must persist exactly the width the grid is able to render |
| M3 | 删读侧收敛 | KILLED | V3: reading stored widths must converge them to the shared per-column band |
| M4 | 模板退回手搓公式 | KILLED | V10: the resize drag must reuse the committed grid template instead of a second formula |
| M5 | 不绑 `pointercancel` | KILLED | V5: a drag ended by pointercancel must detach its window pointermove handler |
| M6a | 不摘 `pointerup` | KILLED | V5: pointercancel must detach the pointerup handler |
| M6b | 不摘 `pointercancel` | KILLED | V7: a second end event must not rewind or reapply a width after the drag settled |
| M6c | 取消也持久化 | KILLED | a cancelled drag must not persist a width |
| M7 | 不摘 `pointermove` | KILLED | V5: a drag ended by pointercancel must detach its window pointermove handler |
| M8 | 共享钳失去上界 | KILLED | V2: a resize must persist exactly the width the grid is able to render |
| M9 | 非有限值回落被删 | KILLED | an unusable width must fall back to the "title" column definition |
| M10 | 模板构造器忽略实时覆写 | KILLED | V1: dragging must clamp duration at its 96px maximum instead of the flat 900px band |
| — | 还原 | rc 0 | 全绿 |

**12/12 全灭、0 存活**，每格打印指名杀手断言。

## 十、清单与门禁

- `tools/update_source_manifest.ps1`：718 → **719** 条（新增 1＝判别套件／改哈希 1＝`app.js`／删除 0）。逐文件 sha 复算 `src/app/ui/app.js`、`src/tests/test_ui_track_column_resize.js`、`src/app/ui/track_table_presentation.js` 三枚均 **MATCH**。
- `tools/test_offline.ps1` 终跑 `artifacts/offline-20260923-round253.log`：退出码 **0**，Python `Ran 2567 tests in 129.739s` · `OK (skipped=2)`，日志无 Traceback、无 FAILED 行，本轮新套件成功行在门禁输出内实到（证明接入的是发现式而非仅手工跑过）。含 `passed` 的行数 81 → 82（仅作对照；盘上 JS 套件文件数为 84，措辞行数受文件名与套件数双重漂移影响，按 R156 起的双口径登记）。

## 十一、口径变动

| 口径 | 改前 | 改后 |
| --- | --- | --- |
| `app.js` splitlines / 字节 | 8,477 / 413,587 | 8,497 / 414,918（＋20／＋1,331） |
| 行首锚定命名函数 | 462／unique 462 | 463／unique 463 |
| 三份根文档 0 点名者 | HEAD 212 | 现盘 213 → 本轮写入后 **201** |
| 深读分子（登记分母 381 不动） | 145 | **154** |
| `TODO.md` 严格行首 `- [ ]`／`- [x]` | 4／1,503 | 4／**1,504** |

翻转集合实测＝11 枚既有函数（`canSortTrackColumn`、`cancelMetadataRowRender`、`currentTrackColumnWidths`、`invalidateTrackRowsMarkup`、`metadataRowPatchOnly`、`metadataRowRenderBatchMatchesCurrent`、`renderAlbumDetail`、`saveTrackColumnWidth`、`scheduleMetadataRowRender`、`trackRowMarkupSignature`、`trackRowSelectionKey`）＋ 1 枚本轮新增函数 `clampTrackColumnWidth` ＝ 恰好 12 枚，**零意外点名、零回退**。分子只 ＋9（切片面内首次点名者），后 3 枚为切片外被改函数，按分子口径不计入 —— 该区分已在记录内写明。

口径提醒：0 点名普查只覆盖三份根文档，本文件属逐轮审查附件、不入普查。本文件第四节 diff 的上下文行按字面出现了 `normalizeTrackColumnWidths` 与 `trackColumnScope` 两枚当时 0 点名的函数，与 R124／R139／R155／R156／R158 的 diff 上下文同例，不构成点名，也不影响上表 201 这一数字。

## 十二、约束遵循

净关闭 0 条（本面为深读推进轮）、新立 0 条、无 `- [ ]` 增长；未碰 `.gitignore`／`.gitattributes`；未 push、未 tag；未提交 `artifacts/*.log` 与既有未跟踪目录（`_external/`、`music/`、`references/**`、`tools/android-sdk*`、`tools/platform-tools*`、`tools/skill/`、根 `offline-*.log`、`full-test-output.txt`）；设备段与两份冻结清单（`docs/REAL_DEVICE_GOALS.md` G01–G11、`docs/external-acceptance.md` 45 卡）一律未动；`%TEMP%` 辅助脚本与仓库外变异副本于本轮收尾删除。

## 十三、下一面候选

库响应失效／可见封面水合簇（现 :3381 起，紧接本面末枚之后）。本轮三份根文档**未**点名该面任何函数，以保持 −12 严格相符；本文件亦不预先点名，具体起点函数由下一轮首次点名时登记。
