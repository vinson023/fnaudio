# fnAudio R163 修改审查对照

生成时间：2026-09-23（Asia/Shanghai）。本轮＝深读＋当轮修复轮。所有行号均为**磁盘实测**：改前行号口径＝HEAD 母本 `058e99c:src/app/ui/app.js`，改后行号口径＝当前工作树。本文件由第三棒（接管复核者）在复跑全部证据后写定，第十一节列出复核增量。

## 一、本轮一句话结论

`src/app/ui/app.js` 里那套「表头横向几何同步」（`syncTrackHeaderScroll` ＋ `bindTrackHeaderScroll`）在两个方向上都写不出任何可观测的几何差——CSS 早已用 `!important` 掌管同一组宽度，而它只写清空值；本轮把整枚机制连同两处调用点一起摘除，并配一枚 10 用例判别套件＋14 格变异全灭作为证据。

## 二、接管取证（修改前）

| 项 | 实测 |
| --- | --- |
| 分支 / HEAD | `main` / `058e99c`（R162 第 5 笔）；`git remote -v` 空、`git stash list` 空 |
| 未完成状态 | `.git/MERGE_HEAD`、`.git/REBASE_HEAD`、`.git/CHERRY_PICK_HEAD`、`.git/BISECT_LOG`、`.git/rebase-merge`、`.git/rebase-apply` 逐个 `Test-Path` 均 False |
| 跟踪树 | 4 处改动＝`TODO.md`、`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md`、`SOURCE_MANIFEST.sha256`（上一棒写入的记录与清单）＋`src/app/ui/app.js`（修复已落盘、未提交） |
| 未跟踪新文件 | `src/tests/test_ui_track_header_scroll_retirement.js`（16,440 B，已写未入库） |
| 其余未跟踪 | 全在禁入区（`artifacts/**`、`music/**`、`references/**`、`tools/android-sdk*`、`tools/platform-tools*`、`tools/skill/`、根目录离线日志），本轮一律未动 |
| `.new/.orig/.rej` | 跟踪树 0；`src`/`tools`/`docs` 0；仅 `_external/runtime/**/surface.new` 2 枚（外部依赖缓存，禁入区不动） |
| 现盘计数 | `TODO.md` 2,183 行（`- [ ]` 4／`- [x]` 1,506）、`CHANGELOG_AI.md` 6,796、`PROJECT_CONTEXT.md` 6,203、清单 721 条（本轮刷新 720 → 721）、`app.js` 8,481 行／414,586 B／行首锚定命名函数 461 |

## 三、缺陷定位与根因

### (a) 面：HEAD 母本 :3667-:3793（127 行／10 枚命名函数）

`renderGroups` :3667、`renderCreatorAllSongsEntry` :3679、`renderAlbumGroups` :3690、`renderCreatorAllTracks` :3702、`renderGenreTracks` :3710、`renderFolders` :3717、`renderPager` :3747、`updateMobilePagerVisibility` :3755、`syncTrackHeaderScroll` :3767、`bindTrackHeaderScroll` :3784。本轮首次点名 9 枚（`renderFolders` :3717 历史已点名，只复读）。

### (b) 死重：两分支写同一组清空值，且清空的对象根本不存在

改前 :3767-:3783 的 `syncTrackHeaderScroll()` 两个分支落笔完全同值：

- 每行 `row.style.width = ""`（:3772 移动分支、:3780 桌面分支）；
- 表头 `head.style.width = ""`、`head.style.transform = ""`（:3774-:3775、:3781-:3782）；
- 桌面分支额外 `viewport.style.setProperty("--fnaudio-library-content-width", "100%")`（:3779）——而 `src/app/ui/app.css:623` 早已在 `@media(min-width:761px)` 里把同一变量声明为 `100%`。

改后磁盘实测（对 `src/app/ui/app.js` 逐串计数）：`style.width =` 4 → **0**、`style.transform =` 2 → **0**、`--fnaudio-library-content-width` 1 → **0**、`new ResizeObserver` 1 → **0**、`addEventListener("resize"` 3 → 2。即：全文件唯一的 `style.width`/`style.transform` 写者就是这枚被摘掉的函数，它只写 `""`，而没有任何代码写非空值；活的列宽机制走的是 `--fnaudio-track-columns` 通道，与它无关。

### (c) 不只是无用，还有常驻成本

`bindTrackHeaderScroll()`（改前 :3784-:3793）在每次 `render()` 里被调用，靠 `viewport.dataset.headerScrollBound` 幂等，一旦绑定就永久注册：一枚 `window` 上的 `resize` 监听 ＋ 一枚观察 `#libraryScroll` 的 `ResizeObserver`，其回调每帧再排一次 `requestAnimationFrame(syncTrackHeaderScroll)`。全树检索 `.disconnect(` 只有 `src/app/ui/cover_load_scheduler.js:42` 一处命中（与本品无关），即 `_headerResizeObserver` 从不解除、`resize` 监听从不移除；剩下的只有每帧一次全行遍历。

## 四、修复逐 hunk（`git diff -U6 -- src/app/ui/app.js`，净 ＋2/−31 ＝ −29 行）

### Hunk 1 · 摘除两枚函数（HEAD :3767-:3793，27 行）

```diff
@@ -3761,39 +3761,12 @@ function updateMobilePagerVisibility() {
      requestFrame: (callback) => requestAnimationFrame(callback),
    });
  }
-function syncTrackHeaderScroll() {
-  const viewport = $("libraryScroll");
-  const list = $("trackList");
-  const head = $("tableHead");
-  if (!viewport || !list || !head || window.matchMedia("(max-width: 760px)").matches) {
-    list?.querySelectorAll(".track,.group-row").forEach(row => { row.style.width = ""; });
-    if (head) {
-      head.style.width = "";
-      head.style.transform = "";
-    }
-    return;
-  }
-  viewport.style.setProperty("--fnaudio-library-content-width", "100%");
-  list.querySelectorAll(".track,.group-row").forEach(row => { row.style.width = ""; });
-  head.style.width = "";
-  head.style.transform = "";
-}
-function bindTrackHeaderScroll() {
-  const viewport = $("libraryScroll");
-  if (!viewport || viewport.dataset.headerScrollBound === "1") return;
-  viewport.dataset.headerScrollBound = "1";
-  window.addEventListener("resize", syncTrackHeaderScroll, { passive: true });
-  if (typeof ResizeObserver === "function") {
-    viewport._headerResizeObserver = new ResizeObserver(() => requestAnimationFrame(syncTrackHeaderScroll));
-    viewport._headerResizeObserver.observe(viewport);
-  }
-}
 function render() {
```

- 现盘 :3766 是 `updateMobilePagerVisibility` 的收尾 `}`，:3767 直接就是 `function render() {`，两枚函数之间不留空壳。

### Hunk 2 · 摘除两处调用点并改写注释（HEAD :3858-:3879 → 现 :3831-:3850）

```diff
   if (pagerChanged) updateMobilePagerVisibility();
-  bindTrackHeaderScroll();
   bindTrackListInteractions();
   // These perform layout reads across visible rows.  Rendering playback state
   // or a favorite must not enqueue another full measurement pass when the list,
-  // its headers and its pager are unchanged; resize observers still handle real
-  // geometry changes independently.
+  // its headers and its pager are unchanged.  The library grid width is a CSS
+  // contract, so no inline per-row geometry is written from this path any more.
   if (listChanged || tableHeadChanged || albumHeadChanged || pagerChanged) {
     requestAnimationFrame(() => {
       measureAutoTrackColumnWidths();
-      syncTrackHeaderScroll();
       updateMobilePagerVisibility();
     });
   }
```

- 旧注释里「resize observers still handle real geometry changes」是在给一枚不能产生几何差的机制发通行证，故一并改写为 CSS 契约口径，不给下轮留下与代码不符的叙述。
- 帧体现存 :3842-:3847，语句只剩 `measureAutoTrackColumnWidths();`（:3844）与 `updateMobilePagerVisibility();`（:3845）。
- 删除后 `git grep` 复算：`syncTrackHeaderScroll`、`bindTrackHeaderScroll` 两枚符号在**当前跟踪树全树 0 命中**（HEAD 有 6 处）。

## 五、判别套件（新文件 `src/tests/test_ui_track_header_scroll_retirement.js`，306 内容行／280 非空／16,440 B／CR 0）

10 个用例（前 5 枚行为/接线，6-7 正控，8-10 面级回归）：

1. `the render() geometry region performs no inline geometry writes`——在 `vm.runInNewContext` 里真跑现盘 :3831-:3847 区段，用假节点记录 width/transform/自定义属性写入次数，要求为 0。
2. `the render() animation frame still measures columns and pager visibility`——两枚幸存者仍被调用。
3. `the render() geometry region no longer walks the visible row set`——渲染道不再有 `querySelectorAll(".track,.group-row")` 遍历。
4. `the render path registers no resize listener and no ResizeObserver`——每视图不再留下永久监听／观察器。
5. `the retired header-geometry helpers are absent from app.js`——四枚标识符（含 `headerScrollBound`、`_headerResizeObserver`）在全文件 0 命中。
6. `app.css still owns the library grid width with !important`——正控：`app.css:621-632` 的 `!important` 契约仍在，正是它使被删机制不可观测。
7. `the column widths still travel through the --fnaudio-track-columns property`——正控：活列宽通道未被牵连。
8. `the render() animation frame body keeps only real layout work`——帧体语句序列必须**恰好等于**两枚幸存者，堵「塞一枚空调用」的假修复。
9. `the folder pager still renders page and total from state`——面级回归：本面 `renderFolders` 的分页算式与文案未动。
10. `mobile pager visibility is only recomputed when the pager markup changed`——面级回归：`pagerChanged` 门控未丢。

判定行：`track header geometry retirement regression checks passed.`

## 六、红证 → 绿证

- 红证：仓库外副本放入 `HEAD:src/app/ui/app.js`（机制未摘）跑本套件 → **rc 1**，`FAIL` 行 5 枚（用例 1、3、4、5、8）。
- 绿证：恢复现盘母本 → **rc 0**，尾行为 §5 判定行。
- 门禁终跑输出内亦实到该判定行（`artifacts/offline-20260923-round257.log` 整行命中 1 次，写入后逐字回读）。

## 七、当轮证伪（不改码、不立项）

- 「每帧同步表头位置」并非缺陷：本轮只证伪**横向**几何同步；纵向表头粘性由 `app.css` 的 `position:sticky` 独立掌管，未被牵连。
- `--fnaudio-library-content-width` 在 JS 里的那一次 `setProperty` 与 CSS 声明同值，属可观测性为 0 的重复写入；不新增「保留但改为条件写入」的中间态，避免再养一枚只写 `""` 的观察者。
- `updateMobilePagerVisibility` 与 `measureAutoTrackColumnWidths` 经用例 2／8 证伪「顺手一起删」的冲动：两者确有可观测效果，保留。

## 八、控制组（先绿）与变异矩阵

- 控制组：`C:\path\to\fnAudio-mut-r163b`（HEAD `058e99c`、无 remote）写入现盘三枚文件后，盘上 86 枚 JS 套件全跑 → **0 失败**（6.5 s）。
- 矩阵：`SURVIVORS none`，**M0 rc 0／M1-M14 全部 rc 1**（mutants 14、killed 14、survivors 0）；逐格 `failed_checks` 依次 M1=5、M2=2、M3=2、M4=2、M5=5、M6=2、M7=1、M8=6、M9=6、M10=1、M11=1、M12=1、M13=1、M14=1。
- 格名：`M0_control_pristine`、`M1_full_mechanism_restored`、`M2_empty_helper_back_in_frame`、`M3_real_inline_transform`、`M4_content_width_property_write`、`M5_observer_and_dataset_only`、`M6_drop_column_measurement`、`M7_drop_frame_pager_visibility`、`M8_drop_gated_pager_handoff`、`M9_ungated_pager_handoff`、`M10_row_scan_only`、`M11_css_loses_important`、`M12_folder_pager_constant`、`M13_css_loses_100_default`、`M14_css_rule_loses_track_selector`（其中 M11/M13/M14 为 CSS-only 三枚）。
- 反证取向：M2/M3/M4/M5 证明「只留外壳／只写真写入／只留观察器」都过不了关；M6-M10 证明幸存者的接线与门控被逐条钉住；M11-M14 证明正控（CSS 契约）本身有判别力。

## 九、门禁与清单

- 门禁＝`tools/test_offline.ps1` 终跑 `artifacts/offline-20260923-round257.log` 退出码 0：Python `Ran 2567 tests`／`OK (skipped=2)`，含 `passed` 的 JS 判定行 84 枚（仅作对照：盘上 JS 套件文件 86 枚），无 Traceback、无 FAILED 行，`git diff --check` 仅吐 `SOURCE_MANIFEST.sha256` 的 CRLF 提示一行。
- 清单＝`tools/update_source_manifest.ps1` 刷新 720 → **721**（新增 1＝本轮套件；改哈希 1：`src/app/ui/app.js`；删除 0）；全量复算 0 missing／0 mismatch；逐文件抽查 `src/app/ui/app.js` 与 `src/tests/test_ui_track_header_scroll_retirement.js` 两枚 sha MATCH。

## 十、本轮计数口径（勿与历史快照合并）

- 代码桶（可离线验证）开放 2 枚＝`TODO.md:115`（旧 L114）与 `TODO.md:166`（旧 L165），均为深读欠账账目，本轮**未关闭**；`- [ ]` 全文件实测 4 枚（另 2 枚为长期观察）。
- 反增长：净关闭 0、新立 0，按第二节的 0-close 口径（负责人裁定 Q2=A、X3=A+C）以「L114 欠读行数下降 29 行 ＋ L165 分子 ＋9 枚」记账；本轮非纯取证轮（实有 1 枚真缺陷摘除、14/14 变异全灭）。
- 深读分子 159 → **168**；分母 381 不动；L114 欠读总量 18,205 → **18,176** ＝ `app.js` 8,481 ＋ 已跟踪 Android `.java` 43 文件 9,695（现盘 `splitlines` 口径复算相符）。
- 双口径 0 点名者（canonical 正则 `(?m)^(?:async )?function ([A-Za-z0-9_$]+)\s*\(`）：HEAD 文档 × HEAD 母本 195（R162 记 196，差 1 ＝口径漂移，登记不改历史）；HEAD 文档 × 现盘母本 193；本轮三份文档写入后 **186**。

## 十一、接管复核（第三棒）与复核增量

第三棒不沿用第二棒自述，逐项在盘复测：

1. 复跑控制组 86 套件（0 失败）、M0-M14 矩阵（14/14 灭）、红证（对 HEAD 母本 rc1／5 枚 FAIL）、绿证（rc0）——全部一手实测。
2. 复算清单 721 条：0 missing／0 mismatch，两枚逐文件 sha MATCH；复算 `app.js` 8,481 行／414,586 B、命名函数 461、§4 删除后五个串计数。
3. 复算 census：`0-bare` **186**，与登记值逐字相符（`0-backtick` 口径 214，一并留档）。
4. 修掉第二棒留下的 4 类文本缺陷并复测：`已跟踣`→`已跟踪`（TODO L2/L115、CHANGELOG L2/L3 共 4 处）、`直到符号读每`→`直到符号读毕`（TODO L115）、`均已读毅并计入分子`→`均已读毕并计入分子`（TODO L166）、`全行遍历。。修复`→单句号（TODO L2、CHANGELOG L3）；并把 R163 新文本里 19 枚裸函数名补上反引号（TODO L2＝10、L166＝9），补完后三份文档裸名命中 0、census 仍 186 不变。
5. 回填 `[[GATE]]` 占位符 2 枚（TODO L2、CHANGELOG L2），回填后全文占位符残留 0；定向守卫 `tests.test_change_record`、`tests.test_device_todos_migrated` 12 项 OK。
6. 设备段（`docs/REAL_DEVICE_GOALS.md` G01-G11、`docs/external-acceptance.md`）与需决策桶（开放 0）未动；纪律：未 push、未 tag、未碰 `.gitignore`/`.gitattributes`、`artifacts/*.log` 不入库、`git add` 逐 pathspec。

## 十二、下一面起点（R164）

按现盘行号，`app.js` 本面之后可续读 `render()` 之后的测量簇与 `measureAutoTrackColumnWidths` 相邻面；`TODO.md:166` 剩 213 枚登记符号未深读、`TODO.md:115` 另含 Android 43 文件／9,695 行整面。
