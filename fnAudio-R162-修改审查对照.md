# fnAudio R162 修改审查对照

生成时间：2026-09-23（Asia/Shanghai）。本轮＝深读＋当轮修复轮。所有行号均为**磁盘实测**：改前行号口径＝HEAD 母本 `44d9de6`，改后行号口径＝当前工作树。

## 一、本轮一句话结论

`src/app/ui/app.js` 的曲目标题格「单侧结构变化」用一枚 `currentMain?.replaceWith?.(nextMain)` 同时承担删除与新增两个相反方向，两个方向都错且都是粘性的；本轮改为逐节点编辑，并配一枚 9 块判别套件＋7 格变异全灭作为证据。

## 二、接管取证（修改前）

| 项 | 实测 |
| --- | --- |
| 分支 / HEAD | `main` / `44d9de6`（R161 第 5 笔） |
| 未完成状态 | `.git/MERGE_HEAD`、`.git/rebase-merge`、`.git/rebase-apply`、`.git/CHERRY_PICK_HEAD`、`.git/BISECT_LOG` 全部不存在 |
| stash | 空 |
| 跟踪树 | 1 处改动＝`src/app/ui/app.js`（上一棒已写入本轮修复，尚未提交） |
| 未跟踪新文件 | `src/tests/test_ui_track_row_main_cell_patch.js`（已写未跑、未入库） |
| 其余未跟踪 | 全在禁入区（`artifacts/**`、`music/**`、`references/**`、`tools/android-sdk*`、`tools/platform-tools*`、`tools/skill/`、根目录离线日志），本轮一律未动 |
| 现盘计数 | `TODO.md` 2,181 行（`- [ ]` 4／`- [x]` 1,504）、`CHANGELOG_AI.md` 6,792、`PROJECT_CONTEXT.md` 6,201、清单 720 条（本轮刷新 719 → 720）、`app.js` 8,510 行／命名函数 463 枚 unique 463 |

## 三、缺陷定位与根因

### (a) 可达路径：标题列可被用户关掉，于是补丁道两侧之一必为 null

- `renderTrack` 只在当前列为「标题」时产出 `.track-main` 单元格；列设置对话框允许取消／重新勾选标题列（列配置归一化只在全空时回落默认值，从不钉住标题列）。
- 当这一改动经由 `commitTrackListHtml` 的 keyed 道提交时，实机行与新行**恰好差一个标题格**，控制流进入改前 :3593 的 `else if (currentMain || nextMain)`。

### (b) 一枚表达式两个方向皆错，且错误是粘性的

改前 :3594：`currentMain?.replaceWith?.(nextMain);`

1. **取消标题**：`nextMain` 为 null。`ChildNode.replaceWith()` 按规范把非 Node 实参**字符串化**，实机行里留下一个字面 `null` 文本节点。
2. **重新勾选标题**：`currentMain` 为 null，可选链**整体短路**，新标题格被静默丢弃，什么都不发生。
3. 两种结果都不是一次性的：提交随后把 `state.renderedTrackListHtml` 记成 DOM 并不匹配的标记，此后每次提交都经 `trackRowComparableHtml` ＋行签名比较再进同一分支再错一次 ⇒ 行永不自我收敛，只有整表重绘才被动抹平。

### (c) 本轮读毕但未改码的两处（当轮证伪）

见第七节。

## 四、修复逐 hunk（`git diff -U6 -- src/app/ui/app.js`，净 ＋14/−1 ＝ ＋13 行）

### Hunk 1 · `patchTrackRowNode` 单侧分支改逐节点编辑（现 :3593-:3608）

```diff
   } else if (currentMain || nextMain) {
-    currentMain?.replaceWith?.(nextMain);
+    // Exactly one side carries a title cell, so the column set changed. Neither
+    // direction is expressible with replaceWith(): a null argument is stringified
+    // into a literal "null" text node inside the live row, and the optional chain
+    // on the missing side drops the new cell without a trace. Both leave the row
+    // permanently out of step with the markup it is compared against, because the
+    // commit records renderedTrackListHtml for markup the DOM does not match.
+    if (currentMain) {
+      currentMain.remove();
+    } else {
+      const liveChildren = [...current.children];
+      const mainOrdinal = [...next.children].indexOf(nextMain);
+      if (mainOrdinal >= 0 && mainOrdinal < liveChildren.length) current.insertBefore(nextMain, liveChildren[mainOrdinal]);
+      else current.appendChild(nextMain);
+    }
   }
```

- 删除方向＝`currentMain.remove()`（真摘除，不留文本节点）。
- 新增方向＝按**新行里的列序**把标题格插到实机行的同序位子节点之前；序号不可用（-1 或越界）才 `appendChild` 兜底。
- 本 hunk 不新增函数、不动其它分支；:3609 起的既有「非标题单元格逐个比较」通道原样收尾。
- 磁盘实测（改后）：块起 :3593、`currentMain.remove()` 在 :3601、`insertBefore` 在 :3605、整块止于 :3608。

## 五、判别套件（新文件 `src/tests/test_ui_track_row_main_cell_patch.js`，407 行／21,615 B）

切片真跑：`vm.runInNewContext` 载入本面 9 枚函数，用假节点记录写入。

| 块 | 断言要点 | 判别对象 |
| --- | --- | --- |
| 1 | 取消标题⇒行内文本节点数必须为 0 且标题格真被摘除 | 字符串化 null |
| 2 | 重新勾选⇒标题格真被收养进实机行 | 可选链静默丢弃 |
| 3 | 标题格位于中间列位⇒收养后列序与新行逐项一致 | 恒 append 造成的错列 |
| 4 | 已收敛行再提交⇒整行零 DOM 写入 | 整行 innerHTML 覆写 |
| 5 | 同源封面经元数据补丁后节点保持不变 | 封面复用被破坏 |
| 6 | 分组行仍整块替换 | 过度补丁化 |
| 7 | 源码接线钉：模板里标题格必须是条件产物、本分支内不得再出现 `replaceWith`、收养分支必须显式出现删除调用／列序下界判断／按序位插入 | 结构回退（M5 的唯一杀手，见下） |
| 8 | `invalidateLibraryResponseForTrack` 只逐出含该曲目的页 | 第七节证伪一复算 |
| 9 | `trackRowComparableHtml` 归一封面传输态且不改动被检节点 | 第七节证伪二相关面 |

夹具改形（**未放宽任何断言**）：

- 假 DOM 的 `innerHTML` setter 从「一刀切抛错」改为真解析＋写入记录（`innerHTMLWrites` ＋ `parseMarkup` ＋ `assertNoRowRewrite`）。理由＝:3589 与 :3592 对封面格／信息格的 `innerHTML` 写入是既有合法行为，一刀切会误伤块 5 等，使红证以错误理由成立。
- 行签名属性 `data-track-row-signature` 挂到**行根**（对齐 :3201 的生产形状；`trackRowComparableHtml` 只剥离行根），封面 `<img>` 属性顺序按模板排布。
- `insertBefore(child, null)` 按规范实现为追加末尾，否则「删上界」变异会因错误理由被抓。

## 六、红证 → 绿证

- 干净红基线（夹具改形后、生产修复前）：`4 of 9 track row patch checks failed`，FAIL 恰为块 1／2／3／7，退出码 1。原文见 `%TEMP%/r162_red3.txt`。
- 写入生产修复后：9/9 `ok`，末行 `track row patch regression checks passed.`，退出码 0。原文见 `%TEMP%/r162_green.txt`。
- 全程未使用任何 `git checkout --`；基线取自 `git cat-file blob HEAD:<path>`。

## 七、当轮证伪（不改码、不立项，结论已写进套件头部注释 :38-:47）

1. **`invalidateLibraryResponseForTrack` 不推进响应代际不构成缺陷**。取证＝缓存值形状就是顶层 `items`；4 枚调用点（:5098、:5235、:5291、:5773）全部是先写 `state.itemCache` 再失效，且只补此前为空的可继承字段；合并策略同样只补空字段，权威页每条读路径都会重放 ⇒ 被超取的在飞响应写回不可能复活旧值。
2. **`needsVisibleTrackCoverHydration` 在调度器缺席时虚增计数属生产不可达**。取证＝`index.html` 固定加载封面调度器，该函数被询问前调度器必然已构造 ⇒ 仅指标噪声。

## 八、控制组（先绿）与变异矩阵

- 控制组＝JS 侧发现式全跑 `src/tests/test_*.js` 共 85 个文件 0 失败（工作目录必须为 `src`）；Python 两枚根文档守卫 `Ran 12 tests — OK`。
- 变异矩阵＝仓库外 `git clone --no-hardlinks` 副本（`git remote remove origin` 后覆盖本轮两文件），10 格，输出 `%TEMP%/r162_mut.txt`：

| 格 | 变异 | 结果 | 击杀块数 |
| --- | --- | --- | --- |
| C1 | CONTROL（固定代码＋完整套件） | rc0 | — |
| M1 | 退回 `replaceWith(nextMain)` | 全灭 | 4 |
| M2 | 删除方向改空操作 | 全灭 | 2 |
| M3 | 收养恒改为末尾追加 | 全灭 | 3 |
| M4 | 列序下界 off-by-one（`>= 0` → `> 0`） | 全灭 | 2 |
| M5 | 去掉列序上界 | 全灭 | 1（**仅块 7 源码接线断言**） |
| M6 | 单侧变化退回整行 `innerHTML` 覆写 | 全灭 | 5（含块 4 零写入） |
| M7 | `remove()` 只断父指针 | 全灭 | 2 |
| C3 | SPECIFICITY（固定代码＋放宽套件） | rc0 | — |
| C2 | RESTORED（还原后复跑） | rc0 | — |

**诚实口径**：M5 属防御性分支——形状真越界时后续「非标题单元格数不等」会走整行兜底收敛，因此该格只由源码级接线断言击杀，不是行为击杀。本轮如实登记，不冒充行为判别。

## 九、门禁与清单

- 门禁＝`tools/test_offline.ps1` 终跑 `artifacts/offline-20260923-round256.log`，退出码 **0**；`Ran 2567 tests in 129.008s`／`OK (skipped=2)`；本轮新套件成功行在门禁输出内实到；逐字回读无 Traceback、无 FAILED 判定行；`git diff --check` 仅吐 `SOURCE_MANIFEST.sha256` 的 CRLF 提示一行。对照口径＝含 `passed` 的判定行 83 枚 vs 盘上 JS 套件文件 85 枚（措辞行数受套件名与套件数双重漂移影响，按双口径登记）。
- 清单＝`tools/update_source_manifest.ps1` 刷新 719 → **720**（新增 1＝本轮判别套件／改哈希 1＝`src/app/ui/app.js`／删除 0）；全量复算 **0 missing／0 mismatch**；逐文件抽查 `src/app/ui/app.js`、`src/tests/test_ui_track_row_main_cell_patch.js` 两枚 sha MATCH；三份根文档与本文档不入清单（`TODO.md in-manifest False`），写完后总数仍应为 720。

## 十、本轮计数口径（勿与历史快照合并）

- 净关闭既有代码待办 **0** 条、新立 **0** 条；`TODO.md` 开放 `- [ ]` 保持 **4** 条（累计深读门 :114、:165 与两条长期观察门 :2049、:2071，均为本轮插入后的现盘行号），`- [x]` 1,504 → **1,505**。
- 深读分子 154 → **159**（本面 5 枚首次点名），登记分母 381 不动。
- 三份根文档双口径 0 点名者 **201 → 196**，翻转集合逐枚核对＝`invalidateLibraryResponseForTrack`、`trackRowComparableHtml`、`directTrackChild`、`copyTrackRowAttributes`、`patchTrackRowNode`，无多无少、无回退。
- 本轮虽净关闭 0 条，但**不是纯取证轮**＝1 枚真缺陷修复＋7/7 变异击杀＋2 项当轮证伪。

## 十一、下一面起点

`app.js` 现 :3667 起的「分组渲染」面（本轮记录按既有口径不点名），以及本面未展开的 `commitTrackListHtml` 快照写回与 `scheduleMetadataRowRender` 的 180ms 合批窗口。
## 十二、接管复核（第二棒）与四处口径修正

本确记由接管棒在 R162 现场复核后追加，只改文档措辞与测试头部注释里的行号，不改任何生产代码。

- **切片边界**：本面在 HEAD 母本 `44d9de6` 上的区间实为 **:3401-:3653（253 行／9 枚命名函数）**，`renderGroups` 起于 HEAD :3654；原记录写成 `:3401-:3652（252 行）` 与 `:3653 起为下一面`，已在 `TODO.md` L2 与 L165 两处同步改为 253 行／`:3654 起为另面`。取证手法＝`git cat-file blob HEAD:src/app/ui/app.js` 取原始字节后按 `lines[n-1]` 直接取行（HEAD blob 8,498 个 split 片段／414,918 B，现盘 8,511 片段／415,717 B）。
- **判别套件头部注释**：`source lines 3401-3652` 同步更正为 `3401-3653`（纯注释，断言零变化），并为该文件补上仓库主流约定的结尾 LF（83 枚 `test_ui_*.js` 里 77 枚带尾 LF）。
- **门禁日志引用**：`CHANGELOG_AI.md` L2 与本文档 §九 原引 `offline-20260923-round255.log`；因该跑之后又发生上述清单内文件的注释修正，终跑重做为 **`artifacts/offline-20260923-round256.log`**＝退出码 **0**、`Ran 2567 tests in 129.008s`、`OK (skipped=2)`、无 Traceback／无 FAILED 判定行、本轮新套件成功行在输出内实到、含 `passed` 的判定行 **83** 枚 vs 盘上 `src/tests/test_*.js` **85** 枚。
- **§十 开放项行号**：`:113、:164` 属插入前旧位，与同段 `:2049、:2071` 的现盘口径混用；已统一为插入后现盘行号（实测行首 `^- \[ \]` 恰为 :114、:165、:2049、:2071 四行）。
- **两条环境陷阱**（防再犯）：① `git cat-file blob … | Out-File -NoNewline` 会把整个 blob 拼成一行，据此取行号的一切结论无效；② 批处理里 `echo EXIT=%ERRORLEVEL%> file` 的 `%ERRORLEVEL%>` 会被 cmd 当作 **`0>` 句柄重定向**，退出码被吞、文件写成 0 字节，`>` 前必须留空格。
- **修正后复算**：三份根文档双口径 0 点名者仍 **196** 枚；翻转集合仍恰为本面 5 枚、无回退；两枚根文档守卫 `Ran 12 tests — OK`；清单仍 **720** 条、0 缺 0 失配。
