# fnAudio R154 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮：R154 · 2026-09-22 · 深读簇「队列行播放呈现」 · 净关闭既有代码待办 0 条 · 新立 0 条。

本棒（接管后第 33 棒）对下列每一项事实都做了盘上复算，不采信交接快照；凡与快照口径不符处，以本文件为准，并在第九节逐条登记更正。

## 文件净增（`git diff --numstat 0ec68f3..HEAD`；`0ec68f3` = R153 收尾，本轮前三笔为 `f3287b3`／`d72c8ab`／`a7b8041`）

| 文件 | 增 | 删 | 说明 |
| --- | ---: | ---: | --- |
| `src/app/ui/app.js` | 6 | 0 | 当前行标记修复，两个 hunk |
| `src/tests/test_ui_row_play_presentation.js` | 130 | 0 | 判别套件，首入库文件，numstat 由 `git show --numstat` 读取 |
| `SOURCE_MANIFEST.sha256` | 2 | 1 | 上述两枚摘要 |
| `TODO.md` | 3 | 2 | 顶部 R154 记录 1 行；两条深读条各在尾部追加一段（改写既有行，故同时计 2 删） |
| `CHANGELOG_AI.md` | 2 | 0 | R154 两条（取证条＋修复条） |
| `PROJECT_CONTEXT.md` | 1 | 0 | R154 一条 |

第四笔提交即本对照文件自身。

## 一、接管取证（磁盘实测，不采信交接快照）

| 项 | 实测值 | 取证方式 |
| --- | --- | --- |
| 工作目录／分支 | `E:/fnAudio` ／ `main` | `Get-Location`、`git branch --show-current` |
| 接管时 HEAD | `0ec68f3545ccb87ab9e40b9be2db3728ec1a8a40`，无 remote | `git rev-parse HEAD`、`git remote -v` 空 |
| 未完成态 | 无。`MERGE_HEAD`／`REBASE_HEAD`／`CHERRY_PICK_HEAD`／`REVERT_HEAD`／`BISECT_LOG` 五哨兵均不存在，无 `rebase-*`／`sequencer` 目录，`git worktree list` 仅主树，stash 0 条 | `.git` 目录存在性探测 |
| 未提交面 | ` M src/app/ui/app.js`（6/0）、` M SOURCE_MANIFEST.sha256`（2/1）、`?? src/tests/test_ui_row_play_presentation.js`，另根文档三份待写 | `git status --porcelain` **必须带 pathspec**，否则 `artifacts/**`、`tools/**`、`_external/**` 噪声会淹没输出 |
| `app.js` 体量 | 409,301 B ／ 8,411 内容行 ／ CR 0 ／ 无 BOM；`0ec68f3` blob 408,924 B ⇒ 净 +6 行 | 逐字节读盘 |
| 新套件体量 | 5,968 B ／ 130 内容行 ／ CR 0 ／ 16 枚 `assert.*` | 同上 |
| 清单一致性 | `SOURCE_MANIFEST.sha256` 712 条，本棒全表逐文件复算 **OK 712／MISSING 0／MISMATCH 0**；`app.js` 与新套件两枚逐文件 MATCH | `splitlines()` ＋ 大小写无关比对（清单为 CRLF、摘要大小写混用） |
| 清单覆盖面 | 只覆盖 `src` ＋ `android-client` ⇒ **本轮改三份根文档无需再刷清单** | 表内路径前缀统计 |
| 新套件实跑 | `Row play presentation regression checks passed.` RC=0 | `node tests/test_ui_row_play_presentation.js`（cwd = `src`） |
| 终跑门禁 | `artifacts/offline-20260922-round235.log`：436,244 B ／ 2,718 行 ／ `Ran 2559 tests in 121.938s` ／ `OK (skipped=2)` ／ 无 `FAILED`、无 `ERROR` 行 ／ 含 ` passed` 行 76 | 本棒读盘复核；末行为 `git diff --check` 的 CRLF 提示，能走到末段即前序全绿（log 内无 `EXIT=` 标记，故不采信任何回显 rc） |
| 设备段 | `docs/external-acceptance.md` 开放 28 ／ 收口 17 | 行首锚定计数，见第九节第 2 条更正 |

## 二、缺陷与修法（逐 hunk）

### 2.1 取证：`commitQueue` 的 10 处调用里，只有 `playById` 提交后不重建列表

本棒按「调用行之后 20 行内、同一函数内出现 `render();`」判定，实测全库 10 处调用：

| 调用者 | 定义行 | 调用行 | 后续 `render()` |
| --- | ---: | ---: | --- |
| `addSelectedToQueue` | 4105 | 4111 | 4112（+1） |
| `playSelectedTracks` | 4117 | 4125 | 4131（+6） |
| `playFromCurrentTrack` | 4196 | 4214 | 4220（+6） |
| `insertSelectedTracks` | 4222 | 4232 | 4233（+1） |
| `removeTrackFromQueue` | 4238 | 4247 | 4254（+7） |
| `clearQueue` | 4256 | 4259 | 4261（+2） |
| **`playById`** | **4266** | **4276** | **无（20 行内不存在）** |
| `playGroup` | 4288 | 4301 | 4307（+6） |
| `playAll` | 4316 | 4343 | 4353（+10） |
| `deleteTrackFiles` | 7492 | 7521 | 7534（+13，全表最大间隔） |

其余 9 个写者靠随后的 `render()` 重建列表来搬运当前行标记；`playById` 是唯一的例外，于是从曲目行、双击行或外部入口切入下一首时，`is-current` 停留在旧行。

### 2.2 修法（`git diff` 原文，两 hunk）

```diff
@@ -4271,6 +4271,7 @@ async function playById(id) {
   state.transcodeCacheReady = false;
   state.playSourceKind = "";
   const queue = state.queue.some(x => String(x.id) === String(id)) ? [...state.queue] : [...state.queue, item];
+  const previousIndex = state.index;
   try {
     await commitQueue(queue, id);
   } catch (error) {
@@ -4278,6 +4279,11 @@ async function playById(id) {
     return;
   }
   loadCurrent();
+  // ``playById`` is the one queue writer that never rebuilds the list, so it has
+  // to move the current-row marker itself.  The other writers render afterwards,
+  // which is why this stays on this path instead of in ``applyConfirmedQueue``:
+  // a cross-page jump would then render twice.
+  syncCurrentQueuePresentation(previousIndex);
 }
```

要点三条，均为可判别事实：① 捕获必须在 `await commitQueue(...)` **之前**，因为共享写者会改写 `state.index`；② 同步调用挂在 `playById` 而非 `applyConfirmedQueue`，否则 9 个渲染型调用方会连带二次重建（V6／V7 已量化其代价，见第五节）；③ 视图门禁留在 `syncCurrentQueuePresentation` 自身的 `:2783`（`state.view !== "queue" || previousIndex === state.index` 直接返回），非队列视图屏上没有队列行，不得无谓改样式。

## 三、判别测试（`src/tests/test_ui_row_play_presentation.js`，16 枚断言）

`vm.runInNewContext` 真实执行 `presentationSource`／`applyConfirmedSource`／`commitQueueSource`／`playByIdSource` 四段源码，假节点只记录调用轨迹，不模拟 DOM。

| 场景 | 行段 | 断言 | 判别的是什么 |
| --- | --- | ---: | --- |
| 队列视图内播放另一行 | 82–90 | 5 | 标记从旧行移到新行（`["0:off","1:on"]`）、`renderCount` 必须为 0（同页移动不得整表重建）、`loadCurrent` 恰好一次 |
| 重播当前行 | 93–98 | 2 | 位置不变，且**任何**行标记都不许被改写 |
| 非队列视图播放 | 101–107 | 3 | `state.index` 仍要推进，但零行改样式，同步必须留在视图门禁之后 |
| 落点契约（源码级） | 113–127 | 5 | 捕获存在、捕获早于 `commitQueue`、`loadCurrent()` 之后才同步、`applyConfirmedQueue` 内**禁止**出现同步调用 |
| 源码可抽取性守卫 | 9 | 1 | 四个函数体锚定抽取失败即报错，防止改名后测试静默空跑 |

**先红复现（本棒亲跑）**：把 `0ec68f3` 版 `app.js` 灌入仓库外副本跑本套件 ⇒ RC=1，`AssertionError [ERR_ASSERTION]: the current-row marker must move from the old row to the new one`，抛出点 `test_ui_row_play_presentation.js:87:12`；随后还原真树版复跑 ⇒ RC=0 且副本 `app.js` 与真树逐字节相同。

## 四、并入既有条目的缺陷（不另立新项）

| 现象 | 处置 | 落点 |
| --- | --- | --- |
| 「队列在 50k 处被截断」的怀疑 | **当轮证伪**，不立为发现，折入观察 | `TODO.md:157`（`app.js` 浅读面条）R154 段 |
| `cover_cache.py:586`／`:609-610` 扫描截断可致 tier-2 误删 | 仍是独立一轮候选，本轮不动，沿用既有登记 | `TODO.md:106`（R59 量化欠读条） |

证伪证据三条：`50000` 在 `app.js` 全文唯一命中 `:52 const MAX_LOCAL_FAVORITES = 50000;`（属收藏而非队列）；全文无 `MAX_QUEUE`；`queueDisplayEntries`（`:2726-2745`）只做 map／filter／sort，无截断分支。

## 五、仓库外副本变异证明（7 格，本棒按最终代码逐格复跑，每格跑完还原 pristine）

副本：`<TEMP>/fnaudio-r154-mutation`。脚本：`<TEMP>/r154_mutate.py`（V1–V6）、`<TEMP>/r154_tk8_v7canon.py`（V7 权威口径）。

| 格 | 注入 | 结果 | 被杀症状 |
| --- | --- | --- | --- |
| V1 | 删 `previousIndex` 捕获 | KILLED | `ReferenceError: previousIndex is not defined` |
| V2 | 删同步调用 | KILLED | 标记未从旧行移到新行（`:87`） |
| V3 | 捕获移到 `commitQueue` 之后 | KILLED | 同上（此时 `previousIndex` 已等于新行，同步直接 bail） |
| V4 | 改传 `state.index` | KILLED | 同上 |
| V5 | 去掉 queue 视图门禁 | KILLED | `no queue row may be restyled while another view is active`（`:105`） |
| V6 | 同步整体搬进 `applyConfirmedQueue` | KILLED | `playById must re-sync the row presentation after loading the new track`（`:119`） |
| V7 | 两处都放（双写） | KILLED | `:87` 断言，actual `["0:off","1:on","0:off","1:on"]` 对 expected `["0:off","1:on"]` |

**结果 killed=7/7**；V6／V7 即「把同步挂共享写者会按调用方数量成倍放大重建」的直接可观测证据。

**控制组（必须先绿，本棒复跑）**：
- 克隆内 JS：`CLONE_JS files=78 rc0=78 wording_passed=76`。两枚措辞不同者＝`test_ui_control_names.js`（`index.html control names: 79 controls, 0 nameless, 3 labelle...`）与 `test_ui_library_metadata_merge_policy.js`（`... regression ok`）⇒ **JS 绿只认退出码，不认措辞**。
- 克隆内 Python：`Ran 2559 tests in 122.079s` ／ `OK (skipped=3)`。比真树多出的那 1 枚 skip 成因＝`src/tests/test_offline_verification_script.py:236` 的 `skipTest("release evidence index is not present in this checkout")`，纯环境差异，**不立项**；真树的 2 枚＝`test_process_output.py:31`／`:78` 的 POSIX process-group 跳过。

## 六、当轮证伪 2 组（不得记作发现）

1. **「队列在 50k 处截断」**——见第四节三条证据，现盘不复现。
2. **「`render()` 搬不动 `is-current` 标记，所以缺陷根因在渲染层」**——不成立。`renderTrack` 在 `:3129` 生成行 markup 时按 `isCurrent` 直接写入 `is-current` 类；`renderTrackRows`（def `:3133`）在 `:3144` 对 queue 视图把 `cacheKey` 置空（`:3142-3143` 注释明写「不要复用队列行：当前播放指示属于生成 markup 本身」），所以队列视图每次 render 必然重生成、标记必然跟随。这恰好反证了修复应落在「不 render 的那条路径」上，而不是给渲染层加兜底。

## 七、记账与门禁

| 口径 | 值 |
| --- | --- |
| 净关闭既有代码待办 | **0**；新立可离线代码项 **0**（0 ≤ 0，符合 `docs/REVIEW_ROUND_DISCIPLINE.md` 第二节：既不为凑关闭数新立条目，也不把非代码收益谎报成代码关闭） |
| TODO 勾选 | `- [x]` 1,496 → **1,497**（顶部 R154 记录）；`- [ ]` 开放仍 **15** = 代码桶 2 ＋ 长期观察 13；决策段 0 |
| 两条深读条位置 | 因顶部插入 1 行，`R59 量化欠读条` `:105`→**`:106`**、`app.js 浅读面条` `:156`→**`:157`**（本轮文档一律按插入后口径引用） |
| 浅读分子／分母 | 深读分子 **48 → 60**（新点名 12 枚在 `0ec68f3` 基线三份文档中反引号命中全 0，本棒复算；9 枚重读者命中 1／2／1／1／3／1／3／4／2，不重复计入）；登记分母 **381 保持不动**（第五节：禁止改写历史数字） |
| 命名函数实测 | 行首锚定 `^(?:async )?function 名称(` 得 **463** 枚、unique **463**（基线与工作树同值） |
| 欠读面 | 18,100 → **18,106**（`app.js` 8,411 ＋ Android 已跟踪 `.java` 43 文件 9,695），因修复净增 6 行而**不降反升**，如实登记 |
| 三份根文档 | TODO 2,174 → 2,175 行；CHANGELOG 6,776 → 6,778；PROJECT_CONTEXT 6,193 → 6,194；三份均 LF、无 CR、无 BOM、尾换行存在；六段正文与 `<TEMP>/r154_tk7_texts.py` 逐字一致（整段精确命中各 1 次） |
| 格式与唯一性 | 轮号 `R154` 在三份中命中行分别为 TODO [2, 106, 157]、CHANGELOG [2, 3]、PROJECT_CONTEXT [2]；三份最新记录前 70 字各唯一；三份最新日期均为 2026-09-22 |
| 四守卫 | `test_change_record`／`test_source_manifest`／`test_device_todos_migrated`／`test_ledger_evidence_cards` 实跑 **Ran 44 tests / OK** |
| 门禁 | `artifacts/offline-20260922-round235.log`（Python 2559 项 OK、skipped=2；JS ` passed` 76 行） |
| 提交 | 逐 pathspec 四笔；未 `git add -A`、未 push、未碰 `.gitignore`／`.gitattributes`；设备段未动 |

## 八、终止条件进度（成立 **1/4**，禁止自称完成）

| 条件 | 状态 | 现盘依据 |
| --- | --- | --- |
| (1) 可离线代码待办清空 | ✗ | 代码桶剩 2 条：`TODO.md:106` 量化欠读条（判据＝欠读面读完，现欠 18,106 行）、`TODO.md:157` 浅读面符号条（分母 381，分子 60） |
| (2) 设备/外部项移出逐轮任务 | ✗ | `docs/external-acceptance.md` 开放 28 ／ 收口 17 |
| (3) 需产品决策项汇总征询 | ✓ | 决策段开放 0 |
| (4) 终止前跑完整离线门禁 | ✗ | 按裁定 N3=A：终局门禁只在负责人显发终止令时跑，轮内门禁照常（本轮 round235 即轮内） |

三口径并存、不合并：过期目标正文 `155 = 64 + 82 + 9`／R99 实测 `115 = 51 + 43 + 8 + 13`／现盘 `15 = 2 + 13`。已完成轮远超 36，`maxGoalRounds = 72` 不构成终止理由，亦不得改写终止条件。

## 九、提交后复审与更正清单（本棒自查，逐条「原表述 → 现盘实测 → 处置」）

1. **V7 的「消息为空」** → 本棒复跑：V7 症状为 `:87` 断言、actual 四元素。另查明一条**注入脚本自身的陷阱**：若把 `applyConfirmedQueue` 首行锚点写成缺空格的 `...queue, core){`，替换会静默失配，变异退化为「只加调用、不加捕获」，此时杀点是 `:67` 的 fake `alert` 抛 `Error`（`ReferenceError` 被 `playById` 的 try 捕获）而非 `:87`——两种注入都杀得死，但**文档口径只认权威锚点版**（`head` 含 `core) {` 空格）。
2. **设备段计数 28／17** → 用裸子串 `- [ ]`／`- [x]` 计数得 29／18，多出的 1 枚来自 `docs/external-acceptance.md:13` 的图例行（反引号内同时提到两种标记）。正确口径是行首锚定 ⇒ **28／17**，后续各轮不得改用裸子串计数。
3. **「三份文档日期必须全局倒序」** → 不成立为不变量。`TODO.md` 459 枚锚点里有 4 处日期上升（`:235`、`:504`、`:563`、`:2142`），逐条比对 `0ec68f3` 版同样存在（行号各少 1，正是顶部插一行的位移），属历史既有分布；真正的不变量只在**头部连续最新在前段**（本轮为 `:2–:144`，`2026-09-22 → 2026-09-17` 严格不升）。
4. **四守卫「本轮未重跑」** → 本棒已实跑补齐：`Ran 44 tests / OK`；引用前须 `PYTHONPATH` 含 `src/tests`，否则 `test_ledger_evidence_cards` 会因 `from test_device_todos_migrated import ...` 报 `ModuleNotFoundError`（这是运行方式问题，不是代码问题）。
5. **门禁 log 的 `EXIT=` 标记** → 盘上不存在。本棒改以「末行是 `git diff --check` 的 CRLF 警告」判定前序各段全绿（该步骤排在脚本最后），不采信任何 `Start-Process` 回显 rc。
