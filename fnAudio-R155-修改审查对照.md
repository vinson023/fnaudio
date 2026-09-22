# fnAudio R155 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮：R155 · 2026-09-22 · 深读簇「投送切换与播放源 kind 写入面」 · 净关闭既有代码待办 0 条 · 新立 0 条。

本棒（接管后第 37 棒）对下列每一项事实都做了盘上复算，不采信交接快照；凡与快照口径不符处，以本文件为准，并在第九节逐条登记更正。本棒另在提交前订正了本方记录的一处函数归属错误（见第九节第 2 条），订正后重跑守卫与门禁，数字见第七节。

## 文件净增（`git diff --numstat 572caa8`；`572caa8` = R154 对照提交，本轮工作树）

| 文件 | 增 | 删 | 说明 |
| --- | ---: | ---: | --- |
| `src/app/ui/app.js` | 18 | 4 | 两处拆除 ＋ 三处注释纠偏，共三个 hunk |
| `src/tests/test_ui_target_switch_teardown.js` | 238 | 0 | 判别套件，首入库文件（12,413 B），numstat 待第四笔后以 `git show --numstat` 复核 |
| `src/tests/test_ui_android_bridge.js` | 8 | 2 | 收紧一条旧断言 ＋ 6 行英文注释 |
| `SOURCE_MANIFEST.sha256` | 3 | 2 | 两枚摘要改写 ＋ 新增一枚 |
| `TODO.md` | 3 | 2 | 顶部 R155 记录 1 行；两条深读条各在尾部追加一段（改写既有行，故同时计 2 删） |
| `CHANGELOG_AI.md` | 2 | 0 | R155 两条（修复条 ＋ 取证／门禁条，后者含本棒复审补记） |
| `PROJECT_CONTEXT.md` | 1 | 0 | R155 一条 |

六枚已跟踪文件合计 **35 插入／10 删除**；第五笔（本文件）单独提交，不计入该表。

## 一、接管取证（磁盘实测，不采信交接快照）

| 项 | 实测值 | 取证方式 |
| --- | --- | --- |
| 工作目录／分支 | `E:/fnAudio` ／ `main` | `Get-Location`、`git rev-parse --abbrev-ref HEAD` |
| 接管时 HEAD | `572caa835921cc16da291a3e1361572143450016`，无 remote | `git rev-parse HEAD`、`git remote -v` 空 |
| 未完成态 | 无。`MERGE_HEAD`／`CHERRY_PICK_HEAD`／`REVERT_HEAD`／`BISECT_LOG` 四哨兵均为 `False`，无 `rebase-merge`／`rebase-apply` 目录，`git worktree list` 仅主树，`git stash list` 0 条 | `.git` 目录存在性探测 |
| 未提交面 | ` M src/app/ui/app.js`、` M src/tests/test_ui_android_bridge.js`、` M SOURCE_MANIFEST.sha256`、` M TODO.md`、` M CHANGELOG_AI.md`、` M PROJECT_CONTEXT.md`、`?? src/tests/test_ui_target_switch_teardown.js` ＝ 本轮相关 7 项；`artifacts/**`、`_external/`、`music/`、`tools/`、`references/` 等大量 `??` 一律不动 | `git status --porcelain` **必须带 pathspec**，否则噪声淹没输出 |
| `app.js` 体量 | 410,254 B ／ 8,425 内容行 ／ CR 0 ／ 无 BOM ／ 尾换行存在；基线 blob 409,301 B ⇒ 净 +14 行 | 逐字节读盘 |
| 新套件体量 | 12,413 B ／ 238 内容行 ／ CR 0 ／ 26 枚 `assert.*` | 同上 ＋ 正则计数 |
| 桥测体量 | 60,667 B ／ 814 内容行 ／ CR 0 | 逐字节读盘 |
| 清单一致性 | 713 条，本棒全表逐文件复算 **MISSING 0／MISMATCH 0**（须 `splitlines()` ＋ 大小写无关比对，见第九节第 8 条），随机 10 枚 MATCH，三枚改动文件 MATCH（`app.js` `a74ee322…`、桥测 `30f34cd6…`、新套件 `72ef3712…`） | `hashlib.sha256` 逐条比对 |
| 清单覆盖面 | scope 实测 `src` 633 ＋ `android-client` 80 ＝ 713 ⇒ **根文档与本对照文件都不在口径内，写文档无需再刷清单** | 表内路径前缀统计 |
| 命名函数 | 行首锚定 `^(?:async )?function 名称(` 实测 `app.js` **463** 枚、unique **463** | 与 `TODO.md:107`／`:158` 登记值一致 |
| 设备段 | `docs/external-acceptance.md` 765 内容行 ／ 开放 28 ／ 收口 17 ／ `#` 标题 58（`## ` 12） | `splitlines()` ＋ 行首锚定；与快照的「766 行」不符，见第九节第 1 条 |
| 残留补丁文件 | `.new`／`.orig`／`.rej` 全仓仅 2 枚，均在 `_external` 下的 Go module cache（`modernc.org/libc@v1.67.6/surface.new` 及其 `-clean` 副本） | 全仓扫描 |

## 二、缺陷与修法（逐 hunk）

### 2.1 取证：裁定 D-1 在盘上只有一个执行点，只覆盖「外力把声音推回本机」一侧

`stopLocalAudio`（def `:2102-2113`）全文 6 枚调用点，本轮之前只有 `:2070` 一处与「输出易主」有关，且该处的条件 `!previousActive` 只描述**投送到达本机**那一跃：

| 调用点 | 外层函数（def 行） | 触发方向 | 本轮前状态 |
| ---: | --- | --- | --- |
| `:2070` | `refreshRendererSession`（`:2021`） | 外力把投送打到本机（DLNA 会话跃变） | 既有唯一 D-1 执行点，条件 `!previousActive && localIsPlayingNow()` |
| `:2147` | `stopPlayback`（`:2130`） | 用户在本机按停止 | 与 D-1 无关 |
| `:4385` | `loadCurrent`（`:4379`） | 本机载入新曲 | 与 D-1 无关 |
| `:8299` | `toggleLyrics` 内 `audio.onerror`（def `:8186`） | DSD 兼容流失败兜底 | 与 D-1 无关 |
| **`:6427`** | **`loadDevices`（`:6368`）** | **别处控制器把输出移走** | **本轮新增** |
| **`:7917`** | **`selectPlaybackTarget`（`:7864`）** | **用户自己把输出交给设备** | **本轮新增** |

`stopLocalAudio` 的实盘体（`:2103-2112`，本轮未改）＝ `playbackLoadToken += 1` → `streamOffset = 0` → `pendingSeekTime = null` → `transcodeCacheReady = false` → `playSourceKind = ""` → `if (nativePlaybackAvailable()) nativePlaybackCall("stop")` → `audio.pause()` → `audio.removeAttribute("src")` → `audio.load()` → `setPlayButton(false)`，**全程不触 `api/playback/control`**；`nativePlaybackCall("stop")` 是宿主命令，门禁是 `nativePlaybackAvailable()`（def `:490-493`）。

缺陷机理：`selectPlaybackTarget` 在 `:7886` 写 `state.playTarget = nextTarget;` 之后，`$("playBtn")`／`$("stopBtn")`／media-session 全部改判为 `isRemoteTarget()`（def `:1177`）而路由到设备，原 `else` 分支（`:7908-7920`）只做 `stopRemoteEventStream(); startRemoteEventStream(); nativeRemoteEnter(true);`——本机 `<audio>` 于是「聋而不停」，继续解码发声，且再也无法用本机控件停下。落点门禁 `localIsPlayingNow()`（def `:1858-1864`）读的是本机元素／宿主播放器实况（宿主态取 `state.nativePlayback.playing`，否则 `audio.src && !audio.paused && !audio.ended`），刻意不看渲染会话，因此不会被投送记账反噬。

`loadDevices` 一侧的可达性：该调和块受 `:6406` `if (targetRevision > 0 && currentTarget !== state.playTarget) { …; return; }` 早退门约束，仅在 `state.deviceTargetRevision === 0`（本页面会话内从未发生过用户切换）时可进，正对应「别的控制器把输出移走、本机仍在播、用户这时打开设备面板或点重新搜索」。

### 2.2 修法（`git diff` 原文，三 hunk）

```diff
@@ -6420,7 +6420,13 @@ async function loadDevices(forceRefresh = false) {
     if (previousTarget !== currentTarget) {
       stopRemoteEventStream();
-      if (isRemoteTarget()) startRemoteEventStream();
+      if (isRemoteTarget()) {
+        // The server or another controller already moved the audible output away from
+        // this browser, so the same D-1 teardown applies: from here on nothing can
+        // reach the local element through its own controls any more.
+        if (localIsPlayingNow()) stopLocalAudio();
+        startRemoteEventStream();
+      }
     }
```

```diff
@@ -7874,9 +7880,9 @@ async function selectPlaybackTarget(id, name) {
-    // previous output inside `set_target()`. Do not issue a second stop here:
-    // a follow-up control request can race with the new target and move the
-    // server back to the old renderer.
+    // previous output inside `set_target()`. Do not issue a second *request* here:
+    // a follow-up control call can race with the new target and move the server
+    // back to the old renderer. Local element teardown below sends nothing.
     state.playTarget = nextTarget;
```

```diff
@@ -7901,6 +7907,14 @@ async function selectPlaybackTarget(id, name) {
   } else {
     stopRemoteEventStream();
+    // Ruling D-1 stops local playback once the audible output moves elsewhere.  The
+    // transaction above only hands the *server* a new target, so when that target is
+    // a device this browser keeps decoding while every control (play, stop, media
+    // session) has already been routed to the device: the local element is deaf but
+    // still running.  Tear it down here.  This touches the element only and issues
+    // no follow-up control request, so it cannot race the new target the way a second
+    // api/playback/control call would.
+    if (localIsPlayingNow()) stopLocalAudio();
     startRemoteEventStream();
     nativeRemoteEnter(true);
   }
```

落点约束三条（均为可判别事实，逐条对应 V3／V7／V9／V4 变异格）：① 必须在 `state.playTarget = nextTarget;`（`:7886`）**之后**且**只在 device 分支内**——否则切换请求失败时会停掉仍是当前输出的本机音频；② 必须只碰元素、一发请求都不发——`stopLocalAudio` 内唯一外发是宿主命令，不触 `api/playback/control`；③ 必须在 `startRemoteEventStream()`（`:7918`）与 `nativeRemoteEnter(true)`（`:7919`）之前，避免远程事件先落地又被打断。中间 hunk 的注释纠偏只收窄措辞：旧文「不得再发第二次停止」把**请求**与**本地写入**混为一谈，新文写明「本地下方的元素拆除不发包」。
## 三、判别测试（`src/tests/test_ui_target_switch_teardown.js`，26 枚断言／5 组场景）

夹具：`functionSource()`（`:15-19`）以 `^(?:async )?function NAME\b[\s\S]*?^}`（`m` 位）取体，`vm.runInContext`（`:120-127`）**真实执行** `setPlayButton`／`stopLocalAudio`／`localIsPlayingNow`／`selectPlaybackTarget`／`loadDevices` 五段源码；假 `audio`（`:30-39`）把 `pause`／`removeAttribute`／`load`／`play` 记入 `calls`；`apiFetch` 桩记录 `apiFetch:<路径>:<方法>`；`teardownCalls()`（`:131-133`）只筛三枚拆除写入；`flush()`（`:135-137`）跑 30 拍微任务。

| 组 | 行段 | 断言 | 判别的是什么 |
| --- | --- | ---: | --- |
| 源码可抽取性守卫 | `:16-18` | 1 | 五枚函数任一改名／失去行首锚定即报错，防止测试静默空跑 |
| 1 用户切到设备 | `:139-158` | 9 | 正控越过验收块（须见 `apiFetch:api/playback/target:POST`、`startRemoteEventStream`、`nativeRemoteEnter:true`）；拆除序列逐字 `["audio.pause","audio.removeAttribute:src","audio.load"]`；`playSourceKind === ""`；`dataset.playing === "paused"`；`apiFetch:api/playback/control` 计数 **0**（`:152` 为本轮先红复现点） |
| 1b 宿主分支 | `:159-165` | 1 | 宿主播放器下 `native:stop` 恰 1 次（不多发、不漏发） |
| 2 静音态 | `:166-175` | 1 | 本机元素本就没播 ⇒ 切换**零** `audio.*` 写入，门禁 `localIsPlayingNow()` 不得被绕过 |
| 3 切回本机 | `:176-184` | 2 | local 分支不得拆除（否则一次误停会打断恢复） |
| 4 `loadDevices` 三种形状 | `:185-206` | 5 | 远程且本机在播 ⇒ 拆一次；目标未变 ⇒ 不二次拆；移回本机 ⇒ 不拆但 `stopRemoteEventStream` 照走 |
| 5 源码级接线 | `:207-232` | 7 | 拆除必须在 `state.playTarget = nextTarget;` 之后、`} else {` 之内、`nativeRemoteEnter(true);` 之前；local 分支内**禁止**出现 `stopLocalAudio();`；切换路径恰好一枚拆除；`remoteControl("stop"` 永不出现；调和块拆除必须晚于 `if (isRemoteTarget())` 且每路恰一枚 |

**先红复现（PAIR-B，本棒在 `<TEMP>\r155_pair` 亲跑）**：基线 `app.js`（409,301 B）灌入副本配本套件 ⇒ **EXIT 1**，失败点 `test_ui_target_switch_teardown.js:152:10`（`moving the output away must tear the local element down exactly once`）；真树版 ⇒ **EXIT 0**，收尾 `Target switch local teardown checks passed.`。

**配套收紧**：`src/tests/test_ui_android_bridge.js` `:531-540` 旧断言同时禁 `remoteControl("stop"` **或** `stopLocalAudio();`，把「第二次停止**请求**」与「本地元素**拆除**」混为一谈；本轮改为只禁两种请求形态（`remoteControl("stop"`、`api/playback/control"`），报错文案随之由 `…must not issue a second stop` 改为 `…must not issue a second control request`，并补 6 行英文注释说明两者可分。`git log -S` 证该断言与旧注释均来自基线导入提交 `89ded01`，不是任何一轮负责人裁定；**本轮未放宽任何请求约束**（V8 格证明：一旦在拆除后补发 `api/playback/control`，桥测与新套件双 RED）。

## 四、并入既有条目的缺陷（不另立新项）

| 现象 | 处置 | 落点 |
| --- | --- | --- |
| `recoverUnavailablePlaybackTarget`（`:6233-6262`）与 `validateRestoredPlaybackTarget`（`:6304`）是否也欠一次 D-1 拆除 | **当轮证伪**：两者都是**移回本机**，本机元素并未失去控件；boot 恢复在 `:1531` 写 `state.playTarget` 时本机 `<audio>` 尚无 `src` ⇒ `localIsPlayingNow()` 恒假，补码只会多一次空 `pause()/load()` | 折入 `TODO.md:158` R155 追加段 |
| 「`loadDevices` 调和块是死路」 | **当轮证伪**：可达性见 2.1 末段（`:6406` 早退门只在 `state.deviceTargetRevision === 0` 时放行） | 同上 |
| 下一段深读候选 | 不立条目，登记为候选：`applyCoreSnapshot`、`remoteSnapshotFromCore`、`preemptIncomingRendererForLocalPlayback`、`isIncomingRendererSession` | `TODO.md:158` R155 追加段 |

## 五、仓库外副本变异证明（11 格 ＋ 2 配对格）

副本目录：`<TEMP>\r155_clone`（控制组与配对格）、`<TEMP>\r155_red`（先红复现）、`<TEMP>\r155_pair`（本棒补跑配对格）。**棒次归属**：V1–V9、P1、P2 与「每格跑完还原 pristine」由**前一棒（第 36 棒）**执行并登记 `CELLS 11／MISMATCHES 0／RESTORE BYTE-EXACT True`；PAIR-A／PAIR-B 两格由**本棒**补跑，还原后副本 `app.js` 与真树逐字节相同。

| 格 | 注入 | 结果 | 被杀症状 |
| --- | --- | --- | --- |
| V1 | 删 device 分支的拆除 | RED | 新套件 case 1（`:152`） |
| V2 | 删 `loadDevices` 调和块拆除 | RED | 新套件 case 4（`:190`） |
| V3 | 把拆除挪进 local 分支 | RED | case 3 ＋ 接线断言 `:220` |
| V4 | 去掉 `localIsPlayingNow()` 门禁改无条件拆 | RED | case 2（静音态不许写入） |
| V5 | 只清 `playSourceKind` 不拆元素 | RED | case 1 拆除序列为空 |
| V6 | 还原 HEAD 版桥测断言 | **桥测 RED** | 证明收紧后的桥测与新套件互斥，不是单方放宽 |
| V7 | 挪到 `isRemoteTarget()` 门外 | RED | 切回本机也被拆（case 3 ＋ case 4 第三形状） |
| V8 | 拆除后追加一次 `api/playback/control` 请求 | **桥测与新套件双 RED** | 请求约束未被放宽 |
| V9 | 挪到 `state.playTarget = nextTarget;` 之前 | RED | 接线断言 `:218` |
| P1 | 只改注释 | GREEN | 正控：注释改动不触发断言 |
| P2 | 把拆除挪到 `startRemoteEventStream()` 之后 | GREEN | **诚实登记的等价格**：同一同步执行内、两者之间无 `await`，语义不可分辨，故本轮不声称该格有判别力 |
| PAIR-A | 基线 `app.js` ＋ 收紧后的桥测 | GREEN | 新断言从未被基线代码的不变量需要过 ⇒ 收紧非同义反复 |
| PAIR-B | 基线 `app.js` ＋ 新套件 | RED（`:152:10`） | 缺陷真实存在，套件确实判红 |
## 六、当轮证伪 2 组（不得记作发现）

1. **「收紧后的桥测断言只是为本轮新代码开的后门」** —— 双向证伪：V6（把桥测还原为 HEAD 版 ⇒ 桥测 RED）证明新旧代码对该断言确实不对称；PAIR-A（基线 `app.js` ＋ 收紧后的桥测 ⇒ GREEN）证明新断言并不要求基线代码具备任何它没有的性质。两条合起来排除「改断言迁就改动」这种自证。
2. **「`:6427`／`:7917` 是重复保险，既有 `:2070` 迟早会把本机拆掉」** —— 不成立。`:2070` 位于 `refreshRendererSession`（def `:2021`）的 `if (active)` 块内（`:2063`），而 `active`（`:2045-2046`）要求**本浏览器自己的 DLNA 渲染会话**有非空 `uri` 且 transport 不在 `STOPPED`／`NO_MEDIA_PRESENT`；把输出交给设备时本机渲染会话正是停的，`active` 恒假 ⇒ 该执行点永不触发。新套件 case 1 用 `deepEqual` 锁死「拆除写入恰好三枚、恰好一次」，若两路重叠就会翻倍判红。附带一条记账：本棒发现三份根文档 R155 首版把 `:2070` 归到 `updateRemoteUi`（def `:2171`，定义在 `:2070` 之后，结构上不可能包含它），已在提交前订正为 `refreshRendererSession`，见第九节第 2 条。

## 七、记账与门禁

| 口径 | 值 |
| --- | --- |
| 净关闭既有代码待办 | **0**；新立可离线代码项 **0**（0 ≤ 0，依据 `docs/REVIEW_ROUND_DISCIPLINE.md` 第二节：既不为凑关闭数新立条目，也不把非代码收益谎报成代码关闭） |
| TODO 勾选 | `- [x]` 行首锚定 **1,497 → 1,498**（顶部新增 R155 记录 1 枚；基线 `572caa8` 以 `git show HEAD:TODO.md` 复算＝1,497）；另一枚宽松口径「整行含 `- [x]`」为 1,498 → 1,499，两口径恰差 1 枚，唯一差集是 `TODO.md:693` 行首带一个空格的缩进勾选项；第 38 棒把宽松口径的数字标成了行首锚定，本行按第九节第 15 条再订正；`- [ ]` 开放仍 **15** ＝ 代码桶 2（`:107`、`:158`）＋ 长期观察 13；决策段开放 **0** |
| 两条深读条位置 | 顶部插入 1 行导致下移：R59 量化欠读条 `:106`→**`:107`**、`app.js` 浅读面条 `:157`→**`:158`**。本轮根文档正文引用插入前位置，本对照文件一律用插入后位置（沿用 R154 双口径惯例） |
| 浅读分子／分母 | 分子 **60 → 73**（新点名 13 枚在 `572caa8` 基线三份文档中反引号命中全 0；9 枚重读者基线命中分别 6／1／2／4／4／6／1／12／1，不重复计入）；登记分母 **381 保持不动**（历史数字禁改）；本簇真实读入体量 **383 行**（166 ＋ 217，按花括号配对算出的盘上函数范围），登记值 389 已订正，见第九节第 3 条 |
| 欠读面 | 18,106 → **18,120**（`app.js` 8,425 ＋ 已跟踪 Android `.java` 43 文件 9,695，本棒复算逐字相符），因修复净增 14 行而**不降反升**，如实登记；本轮无面出局 |
| 命名函数 | **463** 枚／unique **463**（行首锚定，本棒复算） |
| 三份根文档 | 第 37 棒订正后现盘：TODO 2,176 行／687,753 B；CHANGELOG 6,780 行／1,291,004 B；PROJECT_CONTEXT 6,195 行／817,277 B；三份均 LF、无 CR、无 BOM、尾换行存在。第 38 棒在 CHANGELOG 第三条的 R155 补记尾部追加订正与终验登记两笔（行数不变 6,780，字节 1,291,004 → 1,292,023 → **1292402**）；TODO 与 PROJECT_CONTEXT 未再改动 |
| 格式与唯一性 | 轮号 `R155` 命中行：TODO [2, 107, 158]、CHANGELOG [2, 3]、PROJECT_CONTEXT [2]；三份 L2 前 70 字各唯一；三份最新日期均 2026-09-22；记录校验器 **BAD 0**；`TODO.md` 头部「最新在前」段唯一日期上升处在 **L237**（2026-09-17→2026-09-20），系历史既有分布（基线 `572caa8` 上为 L236，本轮顶部插入 1 行后整体下移），非本轮引入 |
| 聚焦实跑（本棒） | 8 枚 JS 套件 RC 全 0：`test_ui_target_switch_teardown`（`Target switch local teardown checks passed.`）、`test_ui_android_bridge`、`test_ui_control_names`、`test_ui_dead_queue_entry_points`、`test_ui_library_loading`、`test_ui_playback_authority`、`test_ui_renderer_ownership`、`test_ui_transport_state_unknown`；7 枚读根文档／清单的 Python 守卫 **Ran 66 tests／OK** |
| 门禁 | `round236`（前一棒，改源后、写根文档前）436,274 B／2,719 行／`Ran 2559 tests in 123.391s`／`OK (skipped=2)`／` passed` 77 行；`round237`（本棒，三份根文档写入后）同尺寸／`Ran 2559 in 124.104s`／`OK (skipped=2)`／77 passed／**EXIT 0**（`Start-Process -PassThru` 实取）；`round238`（本棒，CHANGELOG 补记后）／`Ran 2559 in 124.257s`／`OK (skipped=2)`／77 passed／**EXIT 0**；订正后终跑见第九节第 10 条；本棒（第 38 棒）就地订正本文件三处记录后复跑 **`round240`** 436,274 B／2,719 行／`Ran 2559 tests in 123.743s`／`OK (skipped=2)`／77 行含 `passed`／无 `FAILED`／无 `Traceback`／**EXIT 0**，全部改文落盘后再以同一条令产出终验跑 **`round241`** 436,274 B／2,719 行／`Ran 2559 tests in 122.576s`／`OK (skipped=2)`／77 行含 `passed`／无 `FAILED`／无 `Traceback`／**EXIT 0**，与 240 仅测试耗时不同 |
| 提交计划 | 逐 pathspec 四笔（源＋新测试＋桥测／清单／三份根文档／本对照文件）；未 `git add -A`、未 push、未碰 `.gitignore`／`.gitattributes`；门禁 log 与 TEMP 产物不入库；设备段未动 |

## 八、终止条件进度（成立 **1/4**，禁止自称完成）

| 条件 | 状态 | 现盘依据 |
| --- | --- | --- |
| (1) 可离线代码待办清空 | ✗ | 代码桶剩 2 条：`TODO.md:107` 量化欠读条（判据＝欠读面全部读完，现欠 18,120 行）、`TODO.md:158` 浅读面符号条（登记分母 381，分子 73） |
| (2) 设备/外部项移出逐轮任务 | ✗ | `docs/external-acceptance.md` 开放 28 ／ 收口 17。R154 提过的「或因迁移已成立」是未经负责人确认的解释，本文件不据此宣布成立 |
| (3) 需产品决策项汇总征询 | ✓ | 决策段开放 0（负责人已逐条裁定） |
| (4) 终止前跑完整离线门禁 | ✗ | 按裁定 N3=A：终局门禁只在负责人**显发终止令**时跑；轮内门禁照常（本轮 round236–239 均为轮内） |

三口径并存、不合并：过期目标正文 `155 = 64 + 82 + 9`／R99 实测 `115 = 51 + 43 + 8 + 13`／现盘 `15 = 2 + 13`。已完成轮远超 36，`maxGoalRounds = 72` 不构成终止理由，亦不得改写终止条件。

负责人 2026-09-22 对 R153 摊开的三项路线裁定给出「按建议执行」，落定为：**N1＝C**（代码桶优先、设备段并行推进，两条线不互斥）、**N2＝C**（真机默认只读取证，每条要动设备权限前单独请示，不盲改）、**N3＝A**（终局门禁只在负责人显发终止令时跑，助手不得自行判定终止）。据此本表 (2)(4) 两行的判据保持不变：条件 (2) 在真机验收证据到手前不得自称成立，条件 (4) 的触发权在负责人手里。

## 九、提交前复审与更正清单（本棒自查，逐条「原表述 → 现盘实测 → 处置」）

1. **设备段行数**：交接快照 766 行 → 现盘 `splitlines()` 实测 **765 内容行**，开放 `- [ ]` **28**、收口 `- [x]` **17**、`#` 标题 58（`## ` 12）。裸子串计数会各多 1（`:13` 图例行同时提到两种标记），正确口径是行首锚定。
2. **`:2070` 的函数归属**：本方根文档首版（TODO L2／CHANGELOG L2）与交接快照都写作「`updateRemoteUi` 内」→ 盘上实测其外层是 `refreshRendererSession`（def `:2021`）；`updateRemoteUi` def 在 `:2171`，位置在 `:2070` 之后，结构上不可能包含它。**提交前已就地订正两处**（needle 各全文唯一），TODO 687,745→687,753 B、CHANGELOG 1,290,996→1,291,004 B，行数不变，行号与结论均未改动。教训与本轮主题同源：函数归属必须由 def 行区间判定，不能由「这个逻辑大概属于那个轮询函数」的记忆推断。
3. **本簇读入体量**：登记 389 行 → 按花括号配对复算 22 枚盘上真实函数范围得 **383**（新点名 13 枚 166 ＋ 复读 9 枚 217）。已在 `TODO.md:158` 就地订正为 383；深读分子 73、登记分母 381 均不受该体量数字影响。
4. **分子口径可复算性**：用同一方法（新点名符号在 `572caa8` 基线三份文档中的反引号命中数）回算 R154 的 12 枚新点名（命中全 0）与 9 枚复读（命中全 ≥1）⇒ 方法自洽，本轮「13 枚全 0／9 枚分别 6／1／2／4／4／6／1／12／1」可被下一棒复算。
5. **配对格棒次**：V1–V9／P1／P2 共 11 格由前一棒执行（`CELLS 11／MISMATCHES 0／RESTORE BYTE-EXACT True`）；PAIR-A／PAIR-B 由本棒补跑。文档不得把前一棒的执行记成本棒复跑，也不得相反。
6. **门禁 `EXIT=` 标记**：log 内不存在该标记。round237／238／239 的 0 由本棒以 `Start-Process cmd.exe -Wait -PassThru` 的 `.ExitCode` 实取；round236 沿用前一棒记录，本棒以 log 内容印证（全文无 `FAILED`／无 `Traceback`，末行为 `git diff --check` 的 CRLF 提示，而该步在脚本最后）。
7. **`.new`／`.orig`／`.rej`**：全仓扫描仅 2 枚，且都在 `_external` 下的 Go module cache（`modernc.org/libc@v1.67.6/surface.new` 及 `gomodcache-clean` 内同名副本），不在版本树内。表述必须限定「仅 `_external` 下」，不得写成「全仓无残留」。
8. **清单比对口径**：表内摘要为大写形态，用 `hexdigest()` 小写直比会得到 **713 全 mismatch** 的假信号；正确口径＝`splitlines()`（清单自身是 CRLF）＋ 大小写无关比对，本棒据此复算得 MISSING 0／MISMATCH 0。
9. **清单覆盖面**：scope 实测 `src` 633 ＋ `android-client` 80 ＝ 713，三份根文档与本对照文件都不在口径内 ⇒ 写文档不需要重刷清单；本轮清单只在源改动后刷新一次（713 条，含新套件一枚）。
10. **订正后终跑**：`artifacts/offline-20260922-round239.log` ＝ 436,274 B／2,719 行／`Ran 2559 tests in 123.541s`／`OK (skipped=2)`／77 行含 `passed`／`Target switch local teardown checks passed.` 在列／**EXIT 0**。该跑时本对照文件已在盘上，故同时证明「根目录新增对照文档不触发任何守卫、也不需要刷清单」。
11. **TEMP 清理**：本轮 `%TEMP%` 下 `r155_*` 共 **70 枚**（3 个目录：`r155_clone`／`r155_pair`／`r155_red`；67 个文件），提交前清空。注意 `$env:TEMP` 返回 8.3 短路径 `C:\Users\ADMINI~1\...`，断言前须解析为 `C:\Users\example\AppData\Local\Temp`。
12. **落盘编码陷阱**（本轮两度踩）：`Set-Content -Encoding UTF8` 会写出 BOM ＋ CRLF，被 `test_source_manifest` 的 unix 行尾用例判红，而 `.gitattributes` 使它在 `git diff` 里隐形（R123 同一陷阱）；本文件与三份根文档的所有改写一律走「读全 bytes → 内存内替换并断言 → 再 `wb` 写回」，替换失败即不落盘，不产生半成品。
13. **提交前终核的三处订正（第 38 棒，本条为追加）**：① 第七节「TODO 勾选」原写 1,497→1,498 —— **该原文是对的**，本棒当时以「整行含 `- [x]`」的宽松口径（基线 1,498／现盘 1,499）改写了它却把口径标成「行首锚定」，属第 38 棒自己引入的新漂移，已由第 39 棒按行首锚定复原为 1,497 → 1,498 并在第九节第 15 条记明（本轮只新增顶部 1 枚勾选项、开放仍 15 这两点不变）；② 同格原写「日期上升处在 L236／R154 时位于 :235」用的是插入前口径，现盘实测 **L237**、基线 **L236**；③ 本节第 11 条原写 TEMP `r155_*` 67 枚（3 目录＋64 文件），提交前实测 **70 枚（3 目录＋67 文件）**，差值来自订正阶段新增的 `r155_bk_*.py`，已按目录／文件分类复核。①②③ 三处均为就地改文，不增删行；本条追加使本文件由 195 行变为 196 行。
14. **第 38 棒终验**：8 枚 JS 套件由本棒独立复跑，RC 全 0（`test_ui_target_switch_teardown`／`test_ui_android_bridge`／`test_ui_control_names`／`test_ui_dead_queue_entry_points`／`test_ui_library_loading`／`test_ui_playback_authority`／`test_ui_renderer_ownership`／`test_ui_transport_state_unknown`）；清单 713 条按 `splitlines()`＋大小写无关复算 **OK 713／MISMATCH 0／MISSING 0**；`app.js` 410,254 B／8,425 行、463 枚命名函数（unique 463）、欠读面 18,120 ＝ 8,425 ＋ 已跟踪 Android `.java` 43 文件 9,695，均与本文件第一／七节登记值逐字相符；`stopLocalAudio` 盘上 6 枚调用点 :2070／:2147／:4385／:6427／:7917／:8299。`round240` 为本棒跑，`round241` 为改文后终验跑，两跑数字见第七节「门禁」行。`round241` 之后的改动只有本条与第七节两处文档-only 登记（不在清单口径内），复跑 7 枚读根文档守卫 `Ran 66 tests`／`OK` 与 8 枚 JS 套件 RC 全 0（`BAD=0`）作为收尾校验。③ **TEMP 清理终核**：删除前实点 `%TEMP%` 下 `r155_*` **77 枚**（3 个目录＋74 个文件，其中含清理脚本自身 1 枚），较本文件第九节第 11 条刚订正过的 70 枚又多 7 枚——`r155_bk_docfix38*.py` 4 枚、`r155_bk_gate240.cmd`／`r155_bk_gate241.cmd` 2 枚、清理脚本 1 枚，全部为本棒订正与终验所新增；逐个 `os.remove`／`shutil.rmtree` 前均断言父目录＝`os.path.realpath($env:TEMP)` 且前缀 `r155_`，删除后复点 **0 枚**。版本树内的 `.new`／`.orig`／`.rej` 仍仅 `_external` 下 2 枚（第 7 条口径不变）。
15. **第 39 棒（本轮终局棒）复核与再订正**：① 勾选项口径之争以本棒复算终结——`git show HEAD:TODO.md` 与现盘同法：行首锚定 `- [x]` **1,497 → 1,498**、未勾 `- [ ]` **15 → 15**；宽松口径（整行含 `- [x]`）**1,498 → 1,499**，两口径差集唯一命中 `TODO.md:693`（行首一个空格）。第 38 棒第 13 条① 的改法据本条撤回，第七节与 `CHANGELOG_AI.md` R155 第三条两处已同步复原，往返全貌留在本条不抹除。② 本棒独立复算并确认现盘：`app.js` 410,254 B／8,425 LF、命名函数 463 枚（unique 463）、`stopLocalAudio` 6 枚调用点 :2070／:2147／:4385／:6427／:7917／:8299（def :2102）；已跟踪 Android `.java` 43 文件 9,695 行 合 欠读面 **18,120**；`SOURCE_MANIFEST.sha256` 713 行按 `splitlines()`＋大小写无关复算 **OK 713／MISMATCH 0／MISSING 0**；`docs/external-acceptance.md` 765 换行／开放 28／收口 17／`#` 58（`## ` 12）；TODO 头部日期上升处现盘 L237（该行 2026-09-20）／基线 L236，与前棒登记一致。③ 负责人批复 **N1＝C／N2＝C／N3＝A** 已登记在第八节下方，据 N2＝C 本轮起真机段默认只读、动权限前单独请示。④ 门禁沿用第 38 棒的 `round240`／`round241`（两跑 EXIT 0）；本棒改文只触及对照文件与 `CHANGELOG_AI.md` 第三条（后者在根文档守卫读取面内），改文后复跑读根文档的 Python 守卫，结果见提交信息。⑤ 提交落盘：本轮按四笔 pathspec 提交，前三笔为 e0523c（pp.js 18/4 ＋ 新套件 238/0 ＋ 桥测 8/2）、37e7703（清单 3/2）、9a428e（三份根文档 3/2 ＋ 2/0 ＋ 1/0），本文件随第四笔入库（故其自身哈希不在此表内）；每笔后 git status --porcelain -- <pathspec> 均为空，未使用 git add -A、未 push、未碰 .gitignore／.gitattributes。
